"""
Real phone calls (PHONE_MODE=twilio), offline: Twilio's media-stream events are replayed by a fake WebSocket, the STT is
scripted, the TTS is the mock (μ-law silence), the ERP and Twilio's REST API are fakes. Nothing leaves the machine.

What must hold on stage: only the demo number is ever dialled; the opening is ready before pickup and plays at once; the
ERP call is marked answered; each caller sentence is one agent turn; "allô ?" over the agent is ignored but a real
interruption clears Twilio's audio; after the outcome is recorded and the goodbye heard, the agent hangs up; no-answer /
busy show up as missed / declined; Twilio callbacks need a valid signature. Plus: the Soniox hands-free parser, the
record_call_outcome tool, the prompt split for the cache, and the no-invented-promises rule.
"""

import asyncio
import base64
import dataclasses
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent import prompts
from app.clients.anthropic import AnthropicLLM
from app.clients.base import LLMRequest, STTClient, STTUpdate
from app.clients.elevenlabs import ElevenLabsTTS
from app.clients.mock_speech import MockTTS
from app.clients.soniox import SonioxSTT
from app.clients.twilio import signature, stream_twiml, valid_signature
from app.config import settings
from app.routers import phone as phone_router
from app.schemas import DoneEvent, TextEvent, ToolCall, ToolCallEvent, ToolResultEvent
from app.schemas.chat import ChatMessage
from app.services import phone, voice_session
from app.services.phone_live import live
from app.tools import ErpClient, ToolContext
from app.tools.calls import record_call_outcome

DEMO = "+33600000000"
PHONE = dataclasses.replace(
    settings.phone, mode="twilio", account_sid="ACtest", auth_token="secret", from_number="+15550001111", to_number=DEMO,
    public_url="https://demo.example.test", validate_signature=True, barge_in_words=2, machine_detection=False,
)  # fmt: skip

# ── fakes ──


class ScriptedSTT(STTClient):
    """listen(): the test pushes STTUpdates into `heard`; the caller's audio is consumed and counted."""

    name, listens = "scripted", True

    def __init__(self):
        self.heard: asyncio.Queue[STTUpdate | None] = asyncio.Queue()
        self.audio_bytes = 0
        self.kwargs: dict = {}

    async def transcribe(self, audio, mime, hint=None):
        return ""

    async def listen(self, audio, hint=None, **kwargs):
        self.kwargs = kwargs

        async def drain():
            async for chunk in audio:
                self.audio_bytes += len(chunk)

        reader = asyncio.create_task(drain())
        try:
            while (u := await self.heard.get()) is not None:
                yield u
        finally:
            reader.cancel()


class FakeErp:
    log: list[tuple[str, str, dict | None]] = []
    call_status = "ringing"

    def __init__(self, actor, actor_name=None, **_):
        pass

    async def get(self, path, query=None):
        FakeErp.log.append(("GET", path, None))
        if path.startswith("/api/proactive/calls/"):
            return {"id": "call1", "status": FakeErp.call_status, "channel": "phone", "opportunityId": "opp1", "clientName": "Château Test",
                    "orderId": "ord_1", "title": "Livraison à décaler"}  # fmt: skip
        if path.startswith("/api/proactive/opportunities/"):
            return {"brief": "BRIEF"}
        raise AssertionError(path)

    async def post(self, path, body=None):
        FakeErp.log.append(("POST", path, body))
        return {}


class FakeTwilio:
    def __init__(self):
        self.created: list[dict] = []
        self.hung_up: list[str] = []

    async def create_call(self, **kwargs):
        self.created.append(kwargs)
        return "CA123"

    async def hang_up(self, sid):
        self.hung_up.append(sid)


class TwilioWS:
    """Twilio's side of the media stream: scripted events in, everything we send recorded."""

    def __init__(self):
        self.incoming: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[dict] = []
        self.closed = False

    def push(self, event: dict) -> None:
        self.incoming.put_nowait(json.dumps(event))

    async def accept(self):
        pass

    async def receive_text(self) -> str:
        return await self.incoming.get()

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self, code: int = 1000) -> None:
        self.closed = True

    def of(self, event: str) -> list[dict]:
        return [m for m in self.sent if m["event"] == event]


def agent_saying(*replies, tools_by_turn: dict[int, str] | None = None):
    """A fake run_agent: turn n says replies[n] (the last one repeats); tools_by_turn[n] = a tool it runs first."""
    seen: list[list[ChatMessage]] = []

    async def run(messages, **kwargs):
        n = len(seen)
        seen.append(list(messages))
        if tools_by_turn and n in tools_by_turn:
            call = ToolCall(id=f"t{n}", name=tools_by_turn[n], arguments={"decision": "livraison jeudi"})
            yield ToolCallEvent(call=call)
            yield ToolResultEvent(call_id=call.id, name=call.name, ok=True, result={"ok": True}, ms=3)
        text = replies[min(n, len(replies) - 1)]
        yield TextEvent(delta=text)
        yield DoneEvent(message=ChatMessage(role="assistant", content=text), ms=1)

    return run, seen


@pytest.fixture
def env(monkeypatch):
    stt, tw = ScriptedSTT(), FakeTwilio()
    FakeErp.log, FakeErp.call_status = [], "ringing"
    monkeypatch.setattr(phone, "settings", dataclasses.replace(settings, phone=PHONE))
    monkeypatch.setattr(phone_router, "settings", dataclasses.replace(settings, phone=PHONE))
    monkeypatch.setattr(phone, "get_stt_client", lambda: stt)
    monkeypatch.setattr(phone, "get_tts_client", lambda: MockTTS())
    monkeypatch.setattr(voice_session, "get_tts_client", lambda: MockTTS())
    monkeypatch.setattr(voice_session, "get_llm_client", lambda: type("L", (), {"provider": "mock", "model": "m"})())
    monkeypatch.setattr(phone, "twilio", lambda: tw)
    monkeypatch.setattr(phone, "ErpClient", FakeErp)
    monkeypatch.setattr(voice_session, "ErpClient", FakeErp)

    async def no_hint(name, hint):
        return None

    monkeypatch.setattr(phone, "stt_hint", no_hint)
    monkeypatch.setattr(phone, "OPENING_GUARD_S", 0.0)
    monkeypatch.setattr(phone, "GOODBYE_GRACE_S", 0.05)
    phone.calls.clear()
    yield stt, tw
    for c in list(phone.calls.values()):
        c.ended = True
        for t in c.tasks:
            t.cancel()
        if c.turn:
            c.turn.cancel()
    phone.calls.clear()


async def until(cond, timeout=2.0):
    for _ in range(int(timeout / 0.01)):
        if cond():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not reached")


async def pick_up(call: phone.PhoneCall) -> tuple[TwilioWS, asyncio.Task]:
    ws = TwilioWS()
    ws.push({"event": "connected", "protocol": "Call", "version": "1.0.0"})
    ws.push({"event": "start", "streamSid": "MZ1", "start": {"streamSid": "MZ1", "callSid": "CA123", "tracks": ["inbound"],
             "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
             "customParameters": {"callId": call.call_id, "token": call.token}}})  # fmt: skip
    task = asyncio.create_task(phone.accept_stream(ws))  # type: ignore[arg-type]
    await until(lambda: call.media_ws is not None)
    return ws, task


def media(payload: bytes = b"\xff" * 160) -> dict:
    return {"event": "media", "streamSid": "MZ1", "media": {"track": "inbound", "chunk": "1", "timestamp": "20", "payload": base64.b64encode(payload).decode()}}


# ── dialling ──


async def test_only_the_demo_number_is_dialled_and_the_opening_is_ready_before_pickup(env, monkeypatch):
    stt, tw = env
    run, seen = agent_saying("Bonjour, ici le Comptoir des Chartrons. Vous avez une minute ?")
    monkeypatch.setattr(voice_session, "run_agent", run)

    res = await phone.place_call("call1", "opp1")
    assert res["callSid"] == "CA123" and DEMO not in res["to"]  # the number is masked in answers
    created = tw.created[0]
    assert created["to"] == DEMO  # never a client's number, whatever the client
    assert "wss://demo.example.test/phone/stream" in created["twiml"] and phone.calls["call1"].token in created["twiml"]
    assert created["status_callback"] == "https://demo.example.test/phone/twilio/status?callId=call1"

    call = phone.calls["call1"]
    await call.turn  # the opening was written and spoken while the phone rings
    assert seen[0][0].content == voice_session.OUTBOUND_OPENING
    assert call.conversation.brief == "BRIEF" and call.conversation.outbound_call() == {"opportunityId": "opp1", "callId": "call1"}
    queued = [kind for kind, _ in list(call.out._queue)]  # type: ignore[attr-defined]
    assert "media" in queued and queued[-1] == "mark"  # audio waiting for pickup, then the end-of-speech mark


async def test_refuses_without_demo_number_or_when_the_erp_call_does_not_ring(env, monkeypatch):
    stt, tw = env
    monkeypatch.setattr(phone, "settings", dataclasses.replace(settings, phone=dataclasses.replace(PHONE, to_number="")))
    with pytest.raises(phone.PhoneError, match="DEMO_PHONE_TO"):
        await phone.place_call("call1", "opp1")
    monkeypatch.setattr(phone, "settings", dataclasses.replace(settings, phone=PHONE))
    FakeErp.call_status = "cancelled"
    with pytest.raises(phone.PhoneError) as e:
        await phone.place_call("call1", "opp1")
    assert e.value.status == 409 and tw.created == []


# ── the call ──


async def test_pickup_plays_the_opening_at_once_and_marks_the_call_answered(env, monkeypatch):
    stt, tw = env
    run, _ = agent_saying("Bonjour, ici le Comptoir. Vous avez une minute ?")
    monkeypatch.setattr(voice_session, "run_agent", run)
    await phone.place_call("call1", "opp1")
    call = phone.calls["call1"]
    await call.turn

    ws, task = await pick_up(call)
    await until(lambda: ws.of("mark"))
    sent_audio = b"".join(base64.b64decode(m["media"]["payload"]) for m in ws.of("media"))
    assert sent_audio and set(sent_audio) == {0xFF}  # the μ-law opening, as produced by the TTS (no transcoding)
    assert all(m["streamSid"] == "MZ1" for m in ws.sent)
    assert call.first_audio_at is not None and call.first_audio_at - call.answered_at < 0.5
    await until(lambda: any(p == "/api/proactive/calls/call1/answer" for _, p, _ in FakeErp.log))

    ws.push(media())  # the caller's audio reaches the STT, hands-free (μ-law 8 kHz)
    await until(lambda: stt.audio_bytes >= 160)
    assert stt.kwargs["audio_format"] == "mulaw" and stt.kwargs["sample_rate"] == 8000

    ws.push({"event": "stop", "streamSid": "MZ1"})
    await task
    assert ("POST", "/api/proactive/calls/call1/status", {"status": "completed", "note": "Fin de l'appel"}) in FakeErp.log


async def test_each_caller_sentence_is_one_turn_and_backchannel_is_ignored(env, monkeypatch):
    stt, tw = env
    run, seen = agent_saying("Bonjour, c'est le Comptoir.", "Très bien, je décale au jeudi 24.")
    monkeypatch.setattr(voice_session, "run_agent", run)
    await phone.place_call("call1", "opp1")
    call = phone.calls["call1"]
    await call.turn
    ws, task = await pick_up(call)
    await until(lambda: ws.of("mark"))

    # "Allô ?" while the opening still plays (Twilio has not echoed the mark): not a turn
    assert call.agent_busy()
    stt.heard.put_nowait(STTUpdate("Allô ?", final=True))
    await asyncio.sleep(0.05)
    assert len(seen) == 1 and ws.of("clear") == []

    ws.push({"event": "mark", "streamSid": "MZ1", "mark": {"name": ws.of("mark")[0]["mark"]["name"]}})  # opening heard
    await until(lambda: not call.agent_busy())
    stt.heard.put_nowait(STTUpdate("Jeudi c'est très bien", final=True))
    await until(lambda: len(seen) == 2)
    assert seen[1][-1].content == "Jeudi c'est très bien"
    assert seen[1][0].content == voice_session.OUTBOUND_OPENING  # same conversation: the brief and the opening stay

    ws.push({"event": "stop"})
    await task


async def test_talking_over_the_agent_clears_twilio_audio_and_cancels_the_turn(env, monkeypatch):
    stt, tw = env
    run, seen = agent_saying("Bonjour, c'est le Comptoir. J'ai deux choses à vous dire sur votre commande de décembre.")
    monkeypatch.setattr(voice_session, "run_agent", run)
    await phone.place_call("call1", "opp1")
    call = phone.calls["call1"]
    await call.turn
    ws, task = await pick_up(call)
    await until(lambda: ws.of("mark"))

    stt.heard.put_nowait(STTUpdate("Attendez une"))  # partial, 2 words over the agent: barge-in
    await until(lambda: ws.of("clear"))
    assert not call.pending_marks and call.out.empty()
    stt.heard.put_nowait(STTUpdate("Attendez une seconde", final=True))
    await until(lambda: len(seen) == 2)
    assert seen[1][-1].content == "Attendez une seconde"

    ws.push({"event": "stop"})
    await task


async def test_after_the_outcome_and_the_goodbye_the_agent_hangs_up(env, monkeypatch):
    stt, tw = env
    run, seen = agent_saying("Bonjour, c'est le Comptoir.", "C'est noté dans votre dossier, bonne journée.", tools_by_turn={1: "record_call_outcome"})
    monkeypatch.setattr(voice_session, "run_agent", run)
    await phone.place_call("call1", "opp1")
    call = phone.calls["call1"]
    await call.turn
    ws, task = await pick_up(call)
    await until(lambda: ws.of("mark"))
    ws.push({"event": "mark", "mark": {"name": ws.of("mark")[0]["mark"]["name"]}})
    await until(lambda: not call.agent_busy())

    stt.heard.put_nowait(STTUpdate("Oui jeudi c'est bon", final=True))
    await until(lambda: len(ws.of("mark")) == 2)
    assert call.wrap_up
    await asyncio.sleep(0.15)
    assert not tw.hung_up  # the goodbye has not been heard yet: never hang up over it
    ws.push({"event": "mark", "mark": {"name": ws.of("mark")[1]["mark"]["name"]}})
    await until(lambda: tw.hung_up == ["CA123"])
    assert call.ended and ws.closed
    ws.push({"event": "stop"})
    await task


async def test_no_answer_and_busy_show_as_missed_and_declined(env, monkeypatch):
    stt, tw = env
    run, _ = agent_saying("Bonjour.")
    monkeypatch.setattr(voice_session, "run_agent", run)
    await phone.place_call("call1", "opp1")
    await phone.on_twilio_status("call1", {"CallStatus": "no-answer"})
    assert ("POST", "/api/proactive/calls/call1/status", {"status": "missed", "note": "Pas de réponse"}) in FakeErp.log
    assert phone.calls["call1"].ended

    phone.calls.clear()
    FakeErp.log = []
    await phone.place_call("call1", "opp1")
    await phone.on_twilio_status("call1", {"CallStatus": "busy"})
    assert ("POST", "/api/proactive/calls/call1/status", {"status": "declined", "note": "Occupé ou refusé"}) in FakeErp.log


async def test_a_stream_with_a_wrong_token_is_refused(env, monkeypatch):
    run, _ = agent_saying("Bonjour.")
    monkeypatch.setattr(voice_session, "run_agent", run)
    await phone.place_call("call1", "opp1")
    ws = TwilioWS()
    ws.push({"event": "start", "streamSid": "MZ1", "start": {"customParameters": {"callId": "call1", "token": "forged"}}})
    await phone.accept_stream(ws)  # type: ignore[arg-type]
    assert ws.closed and phone.calls["call1"].media_ws is None


# ── Twilio callbacks: signature ──


def test_twilio_callbacks_need_a_valid_signature(env, monkeypatch):
    seen: list[tuple[str, dict]] = []

    async def on_status(call_id, params):
        seen.append((call_id, params))

    monkeypatch.setattr(phone, "on_twilio_status", on_status)
    app = FastAPI()
    app.include_router(phone_router.router)
    client = TestClient(app)
    form = {"CallSid": "CA123", "CallStatus": "no-answer"}
    url = "https://demo.example.test/phone/twilio/status?callId=call1"
    assert client.post("/phone/twilio/status?callId=call1", data=form).status_code == 403
    assert client.post("/phone/twilio/status?callId=call1", data=form, headers={"x-twilio-signature": "bad"}).status_code == 403
    ok = client.post("/phone/twilio/status?callId=call1", data=form, headers={"x-twilio-signature": signature("secret", url, form)})
    assert ok.status_code == 200 and seen == [("call1", form)]


def test_words_ignore_punctuation():
    assert [phone.words(t) for t in ("Allô ?", "Oui, d'accord.", "Attendez une seconde", "…", "Jeudi 24")] == [1, 2, 3, 0, 2]


def test_signature_and_twiml_helpers():
    sig = signature("tok", "https://x.test/a?b=1", {"B": "2", "A": "1"})
    assert valid_signature("tok", "https://x.test/a?b=1", {"A": "1", "B": "2"}, sig)
    assert not valid_signature("tok", "https://x.test/a?b=1", {"A": "1", "B": "3"}, sig)
    xml = stream_twiml("wss://x.test/phone/stream", {"callId": "c&1", "token": "t\"2"})
    assert xml.startswith("<Response><Connect><Stream url=") and "c&amp;1" in xml and "<Parameter" in xml


# ── providers ──


async def test_soniox_hands_free_cuts_one_sentence_per_end_token():
    messages = [
        {"tokens": [{"text": "Oui", "is_final": True}, {"text": " jeu", "is_final": False}]},
        {"tokens": [{"text": " jeudi", "is_final": True}, {"text": "<end>", "is_final": True}, {"text": " Et", "is_final": True}]},
        {"tokens": [{"text": " le", "is_final": True}, {"text": " jus", "is_final": False}]},
        {"tokens": [{"text": " jus", "is_final": True}, {"text": "<end>", "is_final": True}], "finished": True},
    ]
    sent: list = []

    class WS:
        async def send(self, m):
            sent.append(m)

        def __aiter__(self):
            async def it():
                for m in messages:
                    yield json.dumps(m)

            return it()

        async def close(self):
            pass

    @asynccontextmanager
    async def connect(url, headers, who):
        yield WS()

    async def audio():
        yield b"\xff" * 160

    updates = [u async for u in SonioxSTT("k", connect=connect).listen(audio(), "Château Benoît", endpoint_delay_ms=700)]
    finals = [u.text for u in updates if u.final]
    assert finals == ["Oui jeudi", "Et le jus"]
    assert updates[0].text == "Oui jeu" and not updates[0].final
    start = json.loads(sent[0])
    assert (start["audio_format"], start["sample_rate"], start["num_channels"], start["max_endpoint_delay_ms"]) == ("mulaw", 8000, 1, 700)
    assert start["enable_endpoint_detection"] is True and start["context"] == {"terms": ["Château Benoît"]}


async def test_elevenlabs_speaks_mulaw_8k_for_the_phone():
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, content=b"\x7f\x7f")

    tts = ElevenLabsTTS("k", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    phone_audio = await tts.synthesize("Bonjour", audio_format="ulaw_8000")
    browser_audio = await tts.synthesize("Bonjour")
    assert phone_audio.mime == "audio/x-mulaw" and "output_format=ulaw_8000" in urls[0]
    assert browser_audio.mime == "audio/mpeg" and "output_format=mp3_44100_128" in urls[1]
    assert b"".join([c async for c in phone_audio.chunks]) == b"\x7f\x7f"


# ── record_call_outcome ──


async def test_record_call_outcome_posts_to_the_call_and_refuses_outside_a_call():
    posted: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"decision": "livraison jeudi"})

    erp = ErpClient("voice_agent", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError, match="Aucun appel sortant"):
        await record_call_outcome.run({"decision": "x"}, ToolContext(erp=erp, actor="voice_agent"))
    ctx = ToolContext(erp=erp, actor="voice_agent", call={"opportunityId": "order_issue~cli_1~ord_1", "callId": "c1"})
    res = await record_call_outcome.run({"decision": "livraison jeudi"}, ctx)
    assert res["ok"] and posted == [("/api/proactive/opportunities/order_issue~cli_1~ord_1/outcome", {"decision": "livraison jeudi", "callId": "c1"})]


# ── prompt: cached static part, and no invented promises ──


async def test_static_prompt_comes_first_and_the_brief_gets_its_own_cache_breakpoint(monkeypatch):
    async def meta():
        return {"company": "Test", "today": "2026-11-24"}

    monkeypatch.setattr(prompts, "get_meta", meta)
    monkeypatch.setattr(prompts, "read_context_files", lambda: "CONTEXTE " * 50)
    static_a, dyn_a = await prompts.build_system_parts("voice", None, "BRIEF A")
    static_b, dyn_b = await prompts.build_system_parts("voice", "Hélène", "BRIEF B")
    assert static_a == static_b  # every call shares the cached company context
    assert "BRIEF A" in dyn_a and "BRIEF" not in static_a and "Hélène" in dyn_b
    full = await prompts.build_system_prompt("voice", None, "BRIEF A")
    assert full.index("CONTEXTE") < full.index("BRIEF A")

    body = AnthropicLLM("m", "k").build_body(LLMRequest(system=full, messages=[ChatMessage(role="user", content="x")],
                                                         system_blocks=[static_a, dyn_a]))  # fmt: skip
    assert [b["text"] for b in body["system"]] == [static_a, dyn_a] and all("cache_control" in b for b in body["system"])
    breakpoints = json.dumps(body).count('"cache_control"')
    assert breakpoints <= 4
    plain = AnthropicLLM("m", "k").build_body(LLMRequest(system="SYS", messages=[ChatMessage(role="user", content="x")]))
    assert plain["system"] == [{"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}]  # unchanged without blocks


@pytest.mark.parametrize("mode", ["chat", "voice", "command"])
async def test_no_invented_promises_in_every_mode(monkeypatch, mode):
    async def meta():
        return {"company": "Test", "today": "2026-11-24"}

    monkeypatch.setattr(prompts, "get_meta", meta)
    monkeypatch.setattr(prompts, "read_context_files", lambda: "")
    text = await prompts.build_system_prompt(mode)
    assert "Ne promets JAMAIS" in text and "avant 10 heures" in text and "e-mail" in text and "rappel" in text


def test_live_bus_keeps_the_latest_call_for_late_viewers():
    live.publish("callA", {"type": "call", "status": "ringing"})
    live.publish("callB", {"type": "call", "status": "ringing"})
    live.publish("callB", {"type": "transcript", "text": "Allô"})
    assert [e["type"] for e in live.latest()] == ["call", "transcript"] and all(e["callId"] == "callB" for e in live.latest())
