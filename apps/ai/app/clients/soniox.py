"""
Soniox STT over the real-time WebSocket (wss://stt-rt.soniox.com/transcribe-websocket).

Live push-to-talk: the voice session streams the browser's frames here AS THEY ARE RECORDED, so most of the words
are already transcribed when the key is released. At the end of the audio we ask Soniox to FINALIZE: it turns the
last provisional words into final ones right away and marks the spot with a <fin> token — a few hundred ms,
instead of transcribing the whole recording after the release (~4 s).
The browser's WebM/Opus is accepted as is ("audio_format": "auto" detects webm, ogg, wav, mp3…; not mp4).

    → start request {model, audio_format, language_hints, enable_endpoint_detection, context: {terms}}
    → binary audio frames …                       (as they arrive)
    → {"type": "finalize"}                        (end of audio: "make everything final now")
    ← {"tokens": [{"text": " Bon", "is_final": false}, …]}         provisional words: resent whole, may change
    ← {"tokens": [{"text": " Bonjour", "is_final": true}, …]}      final words: sent ONCE, never change
    ← {"tokens": [… {"text": "<fin>", "is_final": true}]}         everything before it is final: done
    ← on error: {"error_code": 401, "error_type": "...", "error_message": "..."} then close

Control tokens: <fin> answers a finalize; <end> marks the end of a sentence when the speaker pauses (endpoint
detection — the hook for hands-free mode, see GUIDE-VOIX.md 4.2). Neither is spoken text.

Hands-free (the phone, listen()): raw μ-law 8 kHz from Twilio ("audio_format": "mulaw", "sample_rate": 8000,
"num_channels": 1), one socket for the whole call, and each <end> closes one sentence of the caller.
"max_endpoint_delay_ms" (500–3000, default 2000) caps how long Soniox waits after speech before it says <end>.
"""

import json
from collections.abc import AsyncIterator, Callable

from .base import STTClient, STTUpdate
from .http import provider_error
from .ws import chunked, once, open_ws, sending

URL = "wss://stt-rt.soniox.com/transcribe-websocket"
FINALIZE = json.dumps({"type": "finalize"})
MAX_TERMS_CHARS = 6000  # context terms budget, first terms first (Soniox limits the whole context's size)


class SonioxSTT(STTClient):
    name = "soniox"
    streams = True
    listens = True

    def __init__(self, api_key: str, model: str = "stt-rt-v6", language: str = "fr", connect: Callable = open_ws):
        self.api_key, self.model, self.language, self.connect = api_key, model, language, connect

    def start_request(self, hint: str | None, raw: dict | None = None) -> dict:
        req: dict = {
            "model": self.model,
            "audio_format": "auto",
            "language_hints": [self.language],
            "enable_endpoint_detection": True,  # final words at each pause, not only at the end
            **(raw or {}),  # phone: raw μ-law → {"audio_format": "mulaw", "sample_rate": 8000, "num_channels": 1, …}
        }
        terms, size = [], 0
        for t in (t.strip() for t in (hint or "").split(",")):
            if t and size + len(t) <= MAX_TERMS_CHARS:
                terms.append(t)
                size += len(t)
        if terms:
            req["context"] = {"terms": terms}  # names the model would otherwise mishear ("Lemoine", "loup")
        return req

    async def transcribe(self, audio: bytes, mime: str, hint: str | None = None) -> str:
        text = ""
        async for update in self.transcribe_stream(once(*chunked(audio)), mime, hint):
            text = update.text
        return text

    async def transcribe_stream(self, audio: AsyncIterator[bytes], mime: str, hint: str | None = None) -> AsyncIterator[STTUpdate]:
        async with self.connect(URL, {"Authorization": f"Bearer {self.api_key}"}, "soniox stt") as ws:
            await ws.send(json.dumps(self.start_request(hint)))
            async with sending(ws, audio, end=FINALIZE):
                final = ""  # final tokens, accumulated (each arrives once)
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("error_code"):
                        raise provider_error(
                            "soniox stt", msg["error_code"], f"{msg.get('error_type', '')}: {msg.get('error_message', '')}"
                        )
                    provisional, finalized = "", False  # provisional tokens: the whole current guess, every message
                    for tok in msg.get("tokens") or []:
                        text = tok.get("text") or ""
                        if text == "<fin>":
                            finalized = True
                        elif text.startswith("<"):  # <end>: a pause (endpoint), not a word
                            continue
                        elif tok.get("is_final"):
                            final += text
                        else:
                            provisional += text
                    if finalized or msg.get("finished"):
                        yield STTUpdate(final.strip(), final=True, stable=final.strip())
                        return  # leaving the blocks closes the socket
                    yield STTUpdate((final + provisional).strip(), stable=final.strip())
        raise provider_error("soniox stt", "closed", "connection closed before the final words")

    async def listen(
        self, audio: AsyncIterator[bytes], hint: str | None = None, *, audio_format: str = "mulaw", sample_rate: int = 8000,
        endpoint_delay_ms: int = 800,
    ) -> AsyncIterator[STTUpdate]:
        raw = {"audio_format": audio_format, "sample_rate": sample_rate, "num_channels": 1, "max_endpoint_delay_ms": endpoint_delay_ms}
        async with self.connect(URL, {"Authorization": f"Bearer {self.api_key}"}, "soniox stt") as ws:
            await ws.send(json.dumps(self.start_request(hint, raw)))
            async with sending(ws, audio, end=""):  # an empty text frame ends the stream (when the call ends)
                sentence = ""  # final words of the sentence in progress (each final token arrives once)
                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    if msg.get("error_code"):
                        raise provider_error("soniox stt", msg["error_code"], f"{msg.get('error_type', '')}: {msg.get('error_message', '')}")
                    provisional, done = "", []  # tokens in order: an <end> closes the sentence before it
                    for tok in msg.get("tokens") or []:
                        text = tok.get("text") or ""
                        if text == "<end>":
                            if sentence.strip():
                                done.append(sentence.strip())
                            sentence = ""
                        elif text.startswith("<"):
                            continue
                        elif tok.get("is_final"):
                            sentence += text
                        else:
                            provisional += text
                    for heard in done:
                        yield STTUpdate(heard, final=True, stable=heard)
                    if (sentence + provisional).strip():
                        yield STTUpdate((sentence + provisional).strip(), stable=sentence.strip())
                    if msg.get("finished"):
                        if sentence.strip():
                            yield STTUpdate(sentence.strip(), final=True, stable=sentence.strip())
                        return
