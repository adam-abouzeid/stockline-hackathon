"""ElevenLabs TTS, streaming endpoint: POST /v1/text-to-speech/{voice}/stream → mp3 chunks (audio/mpeg).
For the phone: audio_format="ulaw_8000" → raw μ-law 8 kHz (audio/x-mulaw), what Twilio media streams carry: no transcoding."""

import httpx

from .base import TTSClient, TTSResult
from .http import body_chunks, http_client, post_stream


class ElevenLabsTTS(TTSClient):
    name = "elevenlabs"
    formats = ("ulaw_8000",)

    def __init__(
        self,
        api_key: str,
        model: str = "eleven_flash_v2_5",  # ~100 ms, French OK, cheapest; eleven_v4_turbo = same latency, more expressive
        voice: str = "JBFqnCBsd6RMkjVDRZzb",  # a premade multilingual voice; pick a French one in your ElevenLabs library
        language: str = "fr",
        http: httpx.AsyncClient | None = None,
    ):
        self.api_key, self.model, self.voice, self.language, self.http = api_key, model, voice, language, http

    def build_body(self, text: str) -> dict:
        body = {"text": text, "model_id": self.model}
        if "multilingual_v2" not in self.model:  # language_code is refused by eleven_multilingual_v2
            body["language_code"] = self.language
        return body

    async def synthesize(self, text: str, voice: str | None = None, audio_format: str | None = None) -> TTSResult:
        output = "ulaw_8000" if audio_format == "ulaw_8000" else "mp3_44100_128"
        res = await post_stream(
            self.http or http_client(),
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice or self.voice}/stream?output_format={output}",
            who="elevenlabs tts",
            headers={"xi-api-key": self.api_key},
            json=self.build_body(text),
        )
        return TTSResult("audio/x-mulaw" if output == "ulaw_8000" else "audio/mpeg", body_chunks(res))
