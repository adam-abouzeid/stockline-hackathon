"""
Real phone calls for « Appels du jour » (PHONE_MODE=twilio): the ERP decides to call, a real phone rings, the agent talks.

HARD RULE: the only number ever dialled is DEMO_PHONE_TO, whatever client the agent is calling (the seed contacts are fictional).

    backend dispatch_once()  ──POST /phone/calls {callId, opportunityId}──►  place_call()
        checks the call really rings in the ERP, then:
          1. starts the agent's OPENING right away, while the phone rings: brief → LLM → TTS (μ-law), the audio waits in a queue
          2. Twilio REST: call DEMO_PHONE_TO with <Connect><Stream url=wss://PUBLIC_URL/phone/stream>
    pickup  ──Twilio opens WS /phone/stream──►  PhoneCall.serve_media()
          → the queued opening plays at once (first words ≈ network latency), the ERP call is marked answered
          → caller audio (μ-law 8 kHz) streams continuously to the STT (Soniox listen(): end-of-sentence detection)
          → each sentence = one agent turn (the SAME turn as the browser: VoiceConnection.run_turn, tools, recap, explicit yes)
          → each spoken sentence: TTS ulaw_8000 → Twilio media frames (no transcoding), then a "mark" to know when it was heard
    barge-in: the caller says ≥ PHONE_BARGE_IN_WORDS words over the agent → Twilio "clear" (drops queued audio) + the turn is
              cancelled. Shorter sounds over the agent ("allô ?", "oui", "hm") are backchannel: ignored.
    end: the agent recorded the outcome (record_call_outcome) and its goodbye was heard → it hangs up. Or the caller hangs up,
         or Twilio reports no-answer / busy / failed (→ « Manqué » / « Refusé » in the journal, POST /api/proactive/calls/{id}/status).

Everything is published to the « Appel en cours » panel (services/phone_live.py).
"""

import asyncio
import base64
import json
import re
import secrets
import time
from contextlib import aclosing, suppress
from urllib.parse import quote

from fastapi import WebSocket, WebSocketDisconnect

from app.clients import get_stt_client, get_tts_client
from app.clients.twilio import TwilioClient, stream_twiml
from app.config import settings
from app.schemas import AgentAudioEndMessage, AgentDoneMessage, AgentToolMessage
from app.schemas.base import WireModel
from app.tools import ErpClient
from app.tools.erp import ErpError

from .phone_live import live
from .vocabulary import stt_hint
from .voice_session import Conversation, VoiceConnection

TTS_FORMAT = "ulaw_8000"
CHUNK = 3200  # bytes of μ-law per media message (400 ms)
OPENING_GUARD_S = 2.0  # just after pickup, nobody can interrupt the opening ("Allô ? Oui ?" overlaps it)
GOODBYE_GRACE_S = 1.2  # after the goodbye was heard, wait this long (the caller may still speak) before hanging up
SILENCE_HANGUP_S = 45  # nobody says anything for this long: hang up
AMD_WAIT_S = 6  # with answering-machine detection: how long to wait for Twilio's verdict before treating it as a human
MACHINE = ("machine_start", "machine_end_beep", "machine_end_silence", "machine_end_other", "fax")


def words(text: str) -> int:
    """Spoken words, punctuation left out ("Allô ?" = 1, "d'accord" = 1)."""
    return len(WORD.findall(text))


WORD = re.compile(r"[\w'’-]*\w[\w'’-]*")


class PhoneError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def problems() -> list[str]:
    """What prevents a real call, from the configuration alone (French, shown as is in the web app)."""
    p = settings.phone
    out = []
    if p.mode != "twilio":
        out.append("PHONE_MODE n'est pas « twilio » (les appels sonnent dans le simulateur du navigateur)")
    if not p.account_sid or not p.auth_token:
        out.append("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN manquants")
    if not p.from_number:
        out.append("TWILIO_FROM manquant (le numéro Twilio qui appelle)")
    if not p.to_number:
        out.append("DEMO_PHONE_TO manquant : aucun appel ne part sans le numéro de démo (jamais celui d'un client)")
    elif not p.to_number.startswith("+"):
        out.append("DEMO_PHONE_TO doit être au format international (+33…)")
    if not p.public_url.startswith("https://"):
        out.append("PUBLIC_URL manquant ou pas en https:// (le tunnel ngrok / cloudflared vers le port 4100)")
    try:
        if not get_stt_client().listens:
            out.append(f"STT_PROVIDER={get_stt_client().name} n'écoute pas en continu : choisissez soniox pour le téléphone")
        if TTS_FORMAT not in get_tts_client().formats:
            out.append(f"TTS_PROVIDER={get_tts_client().name} ne produit pas l'audio téléphone : choisissez elevenlabs")
    except Exception as e:  # noqa: BLE001  (a provider misconfigured: say it)
        out.append(f"fournisseur voix : {e}")
    return out


def twilio() -> TwilioClient:
    p = settings.phone
    return TwilioClient(p.account_sid, p.auth_token, p.from_number)


def masked(number: str) -> str:
    """+33612345678 → +33 6•• ••• •78 (the web app shows which phone rings without printing it)."""
    return f"{number[:4]}••••••{number[-2:]}" if len(number) > 6 else ("••" if number else "")


calls: dict[str, "PhoneCall"] = {}  # call id (the ERP journal's) → its phone session


def active_call() -> "PhoneCall | None":
    return next((c for c in calls.values() if not c.ended), None)


class PhoneCall(VoiceConnection):
    """One phone call: the voice session of the browser, with Twilio's media stream as transport."""

    tts_format = TTS_FORMAT

    def __init__(self, call_id: str, opportunity_id: str, info: dict | None = None):
        super().__init__(None)
        self.call_id, self.opportunity_id, self.info = call_id, opportunity_id, info or {}
        self.token = secrets.token_urlsafe(18)  # comes back in the stream's parameters: only Twilio's stream for THIS call is accepted
        self.conversation = Conversation(id=f"phone-{call_id}", opportunity_id=opportunity_id, call_id=call_id)
        self.out: asyncio.Queue[tuple[str, bytes | str]] = asyncio.Queue()  # ("media", μ-law) | ("mark", name), played in order
        self.audio_in: asyncio.Queue[bytes | None] = asyncio.Queue()  # caller audio → STT, None = end of call
        self.media_ws: WebSocket | None = None
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.pending_marks: set[str] = set()  # sent to Twilio, not yet played to the caller = the agent is still talking
        self._marks = 0
        self.tasks: list[asyncio.Task] = []
        self.goodbye: asyncio.Task | None = None
        self.wrap_up = False  # the outcome was recorded: once the goodbye is heard, hang up
        self.ended = False
        self.answered_at: float | None = None
        self.dialled_at = time.perf_counter()
        self.first_audio_at: float | None = None
        self.last_activity = time.monotonic()
        self.answered_by: str | None = None  # answering-machine detection verdict
        self.amd = asyncio.Event()
        self.answer_reported = False
        self.opening_audio = False  # the opening produced audio (else it is retried at pickup)

    # ── what the shared turn logic sends: to the audience panel, and audio / marks to the caller ──

    async def send(self, msg: WireModel) -> None:
        if isinstance(msg, AgentToolMessage) and msg.name == "record_call_outcome" and msg.ok:
            self.wrap_up = True
        elif isinstance(msg, AgentAudioEndMessage):
            self._marks += 1
            name = f"m{self._marks}"
            self.pending_marks.add(name)
            self.out.put_nowait(("mark", name))
        elif isinstance(msg, AgentDoneMessage):
            self.last_activity = time.monotonic()
            if self.wrap_up and not self.ended:
                self.goodbye = asyncio.create_task(self._hang_up_after_goodbye())
        live.publish(self.call_id, json.loads(msg.to_json()))

    async def send_bytes(self, data: bytes) -> None:
        self.opening_audio = True
        self.out.put_nowait(("media", data))

    # ── lifecycle ──

    def prepare(self) -> None:
        """While the phone rings: the agent writes and speaks its opening (queued until pickup), the STT vocabulary is loaded."""
        self.tasks.append(asyncio.create_task(stt_hint(get_stt_client().name, None)))
        self.start_turn(outbound=self.opportunity_id)

    def agent_busy(self) -> bool:
        return bool(self.pending_marks) or bool(self.turn and not self.turn.done())

    async def interrupt(self) -> None:
        """Barge-in: stop the turn (VoiceConnection) AND drop the audio Twilio has not played yet."""
        await super().interrupt()
        await self.clear_audio()

    async def clear_audio(self) -> None:
        while not self.out.empty():
            self.out.get_nowait()
        if self.pending_marks and self.media_ws:
            await self._ws_send({"event": "clear", "streamSid": self.stream_sid})
        self.pending_marks.clear()

    async def serve_media(self, ws: WebSocket, start: dict) -> None:
        """Twilio's media stream for this call, from its "start" event until the call ends."""
        self.media_ws, self.stream_sid = ws, start.get("streamSid")
        self.call_sid = self.call_sid or (start.get("start") or {}).get("callSid")
        self.answered_at = time.perf_counter()
        self.last_activity = time.monotonic()
        live.publish(self.call_id, {"type": "call", "status": "answered", "dialToAnswerMs": int((self.answered_at - self.dialled_at) * 1000)})
        if self.turn and self.turn.done() and not self.opening_audio:  # the opening failed while ringing (ERP / LLM hiccup): try again
            self.start_turn(outbound=self.opportunity_id)
        self.tasks += [
            asyncio.create_task(self._send_loop()),
            asyncio.create_task(self._listen()),
            asyncio.create_task(self._watchdog()),
            asyncio.create_task(self._report_answer()),
        ]
        try:
            while True:
                msg = json.loads(await ws.receive_text())
                match msg.get("event"):
                    case "media":
                        media = msg.get("media") or {}
                        if media.get("track", "inbound") == "inbound":
                            self.audio_in.put_nowait(base64.b64decode(media.get("payload") or ""))
                    case "mark":
                        self.pending_marks.discard((msg.get("mark") or {}).get("name"))
                        if not self.pending_marks:
                            self.last_activity = time.monotonic()
                    case "stop":
                        break
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            self.media_ws = None
            await self.end("completed", "Fin de l'appel")

    async def end(self, status: str, note: str | None = None) -> None:
        """Idempotent. status: completed (an answered call hung up) | missed | declined | cancelled."""
        if self.ended:
            return
        self.ended = True
        self.audio_in.put_nowait(None)
        if self.goodbye and self.goodbye is not asyncio.current_task():
            self.goodbye.cancel()
        with suppress(Exception):
            await VoiceConnection.interrupt(self)
        for t in self.tasks:
            if t is not asyncio.current_task():
                t.cancel()
        if self.media_ws:
            with suppress(Exception):
                await self.media_ws.close()
        answered = self.answered_at is not None
        report = "completed" if answered and status == "completed" else ("missed" if status == "completed" else status)
        if report == "completed" and not self.answer_reported:  # hung up before the ERP heard of the pickup
            with suppress(Exception):
                await ErpClient("voice_agent").post(f"/api/proactive/calls/{quote(self.call_id, safe='')}/answer")
        with suppress(Exception):
            await ErpClient("voice_agent").post(f"/api/proactive/calls/{quote(self.call_id, safe='')}/status", {"status": report, "note": note})
        live.publish(self.call_id, {"type": "call", "status": "ended", "result": report, "note": note,
                                    "durationS": round(time.perf_counter() - self.answered_at) if answered else 0})  # fmt: skip
        print(f"[phone] call {self.call_id} ended: {report} ({note or ''})", flush=True)

    async def hang_up(self, note: str, status: str | None = None) -> None:
        live.publish(self.call_id, {"type": "hangup", "note": note})
        if self.call_sid and settings.phone.account_sid:
            with suppress(Exception):
                await twilio().hang_up(self.call_sid)
        await self.end(status or ("completed" if self.answered_at else "cancelled"), note)

    # ── background tasks ──

    async def _ws_send(self, payload: dict) -> None:
        if self.media_ws:
            with suppress(WebSocketDisconnect, RuntimeError):
                await self.media_ws.send_text(json.dumps(payload))

    async def _send_loop(self) -> None:
        """Queued agent audio → Twilio, as fast as it comes (Twilio buffers and plays it in real time)."""
        while True:
            kind, value = await self.out.get()
            if kind == "mark":
                await self._ws_send({"event": "mark", "streamSid": self.stream_sid, "mark": {"name": value}})
                continue
            for i in range(0, len(value), CHUNK):
                payload = base64.b64encode(value[i : i + CHUNK]).decode()
                await self._ws_send({"event": "media", "streamSid": self.stream_sid, "media": {"payload": payload}})
            if self.first_audio_at is None and self.answered_at is not None:
                self.first_audio_at = time.perf_counter()
                ms = int((self.first_audio_at - self.answered_at) * 1000)
                live.publish(self.call_id, {"type": "latency", "pickupToFirstAudioMs": ms})
                print(f"[phone] call {self.call_id}: first words {ms} ms after pickup", flush=True)

    async def _caller_audio(self):
        """The caller's audio for the STT, ~100 ms per message (Twilio sends 20 ms frames)."""
        while (chunk := await self.audio_in.get()) is not None:
            while not self.audio_in.empty() and len(chunk) < 800:
                more = self.audio_in.get_nowait()
                if more is None:
                    yield chunk
                    return
                chunk += more
            yield chunk

    async def _listen(self) -> None:
        stt = get_stt_client()
        hint = await stt_hint(stt.name, None)
        for attempt in range(3):  # the STT stream broke (network…): reopen it, the call goes on
            try:
                listening = stt.listen(self._caller_audio(), hint, audio_format="mulaw", sample_rate=8000,
                                       endpoint_delay_ms=settings.phone.endpoint_delay_ms)  # fmt: skip
                async with aclosing(listening) as updates:  # type: ignore[type-var]
                    async for update in updates:
                        await (self.on_sentence(update.text) if update.final else self.on_partial(update.text))
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                live.publish(self.call_id, {"type": "error", "message": f"STT : {e}"})
                print(f"[phone] call {self.call_id}: STT stream failed ({e}), attempt {attempt + 1}", flush=True)
                if self.ended:
                    return
                await asyncio.sleep(0.3)

    def _barge_in_words(self) -> int:
        return settings.phone.barge_in_words

    def _guarded(self) -> bool:
        return self.answered_at is not None and time.perf_counter() - self.answered_at < OPENING_GUARD_S

    async def on_partial(self, text: str) -> None:
        self.last_activity = time.monotonic()
        live.publish(self.call_id, {"type": "transcript", "track": "caller", "text": text, "final": False})
        if self.goodbye and not self.goodbye.done():
            self.goodbye.cancel()  # the caller is still talking: don't hang up on them
        if self.agent_busy() and words(text) >= self._barge_in_words() and not self._guarded():
            live.publish(self.call_id, {"type": "barge_in", "text": text})
            await self.interrupt()

    async def on_sentence(self, text: str) -> None:
        """One sentence of the caller, complete (they paused)."""
        self.last_activity = time.monotonic()
        if self.agent_busy() and words(text) < self._barge_in_words():
            # "allô ?", "oui", "hm" while the agent is talking: backchannel, not a turn
            live.publish(self.call_id, {"type": "transcript", "track": "caller", "text": text, "final": True, "ignored": True})
            return
        self.wrap_up = False
        if self.goodbye and not self.goodbye.done():
            self.goodbye.cancel()
        await self.interrupt()
        self.start_turn(text=text)

    async def _hang_up_after_goodbye(self) -> None:
        deadline = time.monotonic() + 30
        while self.pending_marks and time.monotonic() < deadline:  # the goodbye is still playing
            await asyncio.sleep(0.1)
        await asyncio.sleep(GOODBYE_GRACE_S)
        if self.wrap_up and not self.agent_busy():
            await self.hang_up("L'agent a raccroché après avoir noté la décision")

    async def _watchdog(self) -> None:
        while not self.ended:
            await asyncio.sleep(1)
            if self.answered_at and time.perf_counter() - self.answered_at > settings.phone.max_call_seconds:
                await self.hang_up(f"Durée maximale atteinte ({settings.phone.max_call_seconds} s)")
            elif not self.agent_busy() and time.monotonic() - self.last_activity > SILENCE_HANGUP_S:
                await self.hang_up("Plus personne ne parle")

    async def _report_answer(self) -> None:
        """Mark the ERP call answered. With answering-machine detection, wait for Twilio's verdict first: a voicemail is « Manqué »."""
        if settings.phone.machine_detection:
            with suppress(TimeoutError):
                await asyncio.wait_for(self.amd.wait(), AMD_WAIT_S)
            if self.answered_by in MACHINE:
                live.publish(self.call_id, {"type": "call", "status": "voicemail"})
                self.answered_at = None  # never really answered
                await self.hang_up("Messagerie vocale", status="missed")
                return
        try:
            await ErpClient("voice_agent").post(f"/api/proactive/calls/{quote(self.call_id, safe='')}/answer")
            self.answer_reported = True
        except ErpError as e:
            if e.code == "not_ringing":  # cancelled (pause) or expired in the ERP meanwhile: the agent must not go on
                await self.hang_up("L'appel avait été annulé dans l'ERP")
            else:
                live.publish(self.call_id, {"type": "error", "message": f"ERP : {e}"})


# ───────── entry points (routers/phone.py) ─────────


async def place_call(call_id: str, opportunity_id: str) -> dict:
    if issues := problems():
        raise PhoneError(400, "Appel téléphonique impossible : " + " ; ".join(issues))
    if (current := active_call()) and current.call_id != call_id:
        raise PhoneError(409, "Un appel téléphonique est déjà en cours")
    if call_id in calls:
        return {"callId": call_id, "callSid": calls[call_id].call_sid, "to": masked(settings.phone.to_number)}
    # Only a call the ERP really placed, still ringing, on the phone channel (this route is reachable through the tunnel).
    try:
        info = await ErpClient("voice_agent").get(f"/api/proactive/calls/{quote(call_id, safe='')}")
    except ErpError as e:
        raise PhoneError(404, f"Appel inconnu de l'ERP : {e}") from None
    if info.get("status") != "ringing" or info.get("channel") != "phone" or info.get("opportunityId") != opportunity_id:
        raise PhoneError(409, "Cet appel ne sonne pas (ou pas sur le téléphone) dans l'ERP")

    call = calls[call_id] = PhoneCall(call_id, opportunity_id, info)
    for old in [k for k, c in calls.items() if c.ended][:-10]:
        calls.pop(old, None)
    live.publish(call_id, {"type": "call", "status": "dialling", "clientName": info.get("clientName"), "contactName": info.get("contactName"),
                           "title": info.get("title"), "orderId": info.get("orderId"), "opportunityId": opportunity_id,
                           "to": masked(settings.phone.to_number)})  # fmt: skip
    call.prepare()  # the opening is written and spoken while the phone rings
    p = settings.phone
    twiml = stream_twiml(p.public_url.replace("https://", "wss://", 1) + "/phone/stream", {"callId": call_id, "token": call.token})
    try:
        call.call_sid = await twilio().create_call(
            to=p.to_number,  # ALWAYS the demo number, never a client's
            twiml=twiml,
            status_callback=f"{p.public_url}/phone/twilio/status?callId={quote(call_id, safe='')}",
            timeout=p.ring_timeout,
            machine_detection="Enable" if p.machine_detection else None,
            amd_callback=f"{p.public_url}/phone/twilio/amd?callId={quote(call_id, safe='')}",
        )
    except Exception as e:
        call.ended = True  # the backend marks the call missed with this reason (our error answer)
        with suppress(Exception):
            await VoiceConnection.interrupt(call)
        live.publish(call_id, {"type": "call", "status": "ended", "result": "missed", "note": f"Twilio : {e}"})
        raise PhoneError(502, f"Twilio a refusé l'appel : {e}") from None
    live.publish(call_id, {"type": "call", "status": "ringing"})
    print(f"[phone] calling the demo phone for {info.get('clientName')} (call {call_id}, sid {call.call_sid})", flush=True)
    return {"callId": call_id, "callSid": call.call_sid, "to": masked(p.to_number)}


async def hang_up(call_id: str) -> dict:
    call = calls.get(call_id)
    if call and not call.ended:
        await call.hang_up("Annulé depuis l'ERP")
    return {"callId": call_id, "ended": True}


# Twilio CallStatus → (ERP status, note). in-progress is handled by the media stream itself.
STATUS_MAP = {
    "no-answer": ("missed", "Pas de réponse"),
    "busy": ("declined", "Occupé ou refusé"),
    "failed": ("missed", "L'appel n'a pas pu aboutir"),
    "canceled": ("cancelled", "Annulé"),
}


async def on_twilio_status(call_id: str, params: dict[str, str]) -> None:
    status = params.get("CallStatus", "")
    call = calls.get(call_id)
    live.publish(call_id, {"type": "twilio", "status": status})
    if status in STATUS_MAP:
        erp_status, note = STATUS_MAP[status]
        if status == "failed" and params.get("ErrorCode"):
            note += f" (erreur Twilio {params['ErrorCode']})"
        if call:
            await call.end(erp_status, note)
        else:
            with suppress(Exception):
                await ErpClient("voice_agent").post(f"/api/proactive/calls/{quote(call_id, safe='')}/status", {"status": erp_status, "note": note})
    elif status == "completed" and call:
        await call.end("completed", "Raccroché")


async def on_amd(call_id: str, params: dict[str, str]) -> None:
    call = calls.get(call_id)
    live.publish(call_id, {"type": "amd", "answeredBy": params.get("AnsweredBy")})
    if call:
        call.answered_by = params.get("AnsweredBy")
        call.amd.set()


async def accept_stream(ws: WebSocket) -> None:
    """WS /phone/stream: Twilio's media stream. The first events are "connected" then "start" (with our parameters)."""
    await ws.accept()
    try:
        for _ in range(5):
            msg = json.loads(await ws.receive_text())
            if msg.get("event") == "start":
                break
        else:
            await ws.close(code=1008)
            return
    except (WebSocketDisconnect, ValueError):
        return
    params = (msg.get("start") or {}).get("customParameters") or {}
    call = calls.get(params.get("callId", ""))
    if not call or call.ended or not secrets.compare_digest(params.get("token", ""), call.token):
        print(f"[phone] refused a media stream for unknown call {params.get('callId')!r}", flush=True)
        await ws.close(code=1008)
        return
    await call.serve_media(ws, msg)
