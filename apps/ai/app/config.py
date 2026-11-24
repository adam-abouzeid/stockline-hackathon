"""
Configuration, read once from the environment at import time.

The repo-root `.env` (see `.env.example`) is loaded if present; real environment variables win.
Every setting has a default, so with no `.env` at all the service runs on the mock providers.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# apps/ai/app/config.py → the repo root is three folders up.
REPO_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(REPO_ROOT / ".env", override=False)  # never overrides variables already set


def env(name: str, default: str = "") -> str:
    """An environment variable, trimmed; empty counts as unset."""
    return os.environ.get(name, "").strip() or default


@dataclass(frozen=True)
class LLMSettings:
    provider: str  # openai | openai-compatible | anthropic | gemini | mock
    model: str  # empty → the provider's default model
    api_key: str
    base_url: str  # empty → the provider's public endpoint
    effort: str  # anthropic only: low | medium | high


@dataclass(frozen=True)
class STTSettings:
    provider: str  # openai | deepgram | soniox | gradium | mock
    api_key: str
    model: str  # empty → the provider's default model (see clients/factory.py)
    language: str  # ISO code of what the caller speaks
    mock_text: str  # what the mock STT "hears"


@dataclass(frozen=True)
class TTSSettings:
    provider: str  # openai | elevenlabs | gradium | mock
    api_key: str
    model: str  # empty → the provider's default model
    voice: str  # empty → the provider's default (French) voice
    language: str  # elevenlabs language_code; Gradium / OpenAI follow the voice and the text


@dataclass(frozen=True)
class JevSettings:
    api_key: str  # empty → no Jev client (get_jev_client() returns None)
    base_url: str
    model: str


@dataclass(frozen=True)
class PhoneSettings:
    """Real phone calls (V3 Appels du jour) through Twilio. Every call goes to ONE demo number, never to a client's number."""

    mode: str  # simulator (default: the web app plays the client's phone) | twilio (a real phone rings)
    account_sid: str
    auth_token: str
    from_number: str  # TWILIO_FROM: the Twilio number that calls (E.164, e.g. +15551234567)
    to_number: str  # DEMO_PHONE_TO: the ONLY number ever dialled (E.164, e.g. +33612345678)
    public_url: str  # PUBLIC_URL: https://<tunnel> that reaches this service (ngrok / cloudflared to port 4100)
    validate_signature: bool  # check X-Twilio-Signature on Twilio's HTTP callbacks
    ring_timeout: int  # seconds the phone rings before Twilio gives up (no-answer → « Manqué »)
    endpoint_delay_ms: int  # Soniox max_endpoint_delay_ms: how long a pause ends the caller's sentence (500–3000)
    barge_in_words: int  # words the caller must say over the agent to interrupt it (1 = any word)
    max_call_seconds: int  # safety net: hang up after this long
    machine_detection: bool  # Twilio async answering-machine detection: hang up on a voicemail (marked « Manqué »)


@dataclass(frozen=True)
class Settings:
    port: int
    erp_api_url: str
    data_dir: Path  # data pack (separate repo); relative paths are resolved from the repo root
    max_steps: int  # max model ↔ tools round-trips per turn
    llm: LLMSettings
    stt: STTSettings
    tts: TTSSettings
    jev: JevSettings  # optional decision model, used next to the LLM (clients/jev.py)
    phone: PhoneSettings


settings = Settings(
    port=int(env("AI_PORT", "4100")),
    erp_api_url=env("ERP_API_URL", "http://localhost:4000").rstrip("/"),
    data_dir=(REPO_ROOT / env("DATA_DIR", "../hackathon-data")).resolve(),
    max_steps=int(env("AGENT_MAX_STEPS", "8")),
    llm=LLMSettings(
        provider=env("LLM_PROVIDER", "mock").lower(),
        model=env("LLM_MODEL"),
        api_key=env("LLM_API_KEY"),
        base_url=env("LLM_BASE_URL"),
        effort=env("LLM_EFFORT", "low"),
    ),
    stt=STTSettings(
        provider=env("STT_PROVIDER", "mock").lower(),
        api_key=env("STT_API_KEY"),
        model=env("STT_MODEL"),
        language=env("STT_LANGUAGE", "fr"),
        mock_text=env("MOCK_STT_TEXT", "Bonjour, il vous reste du bar ?"),
    ),
    tts=TTSSettings(
        provider=env("TTS_PROVIDER", "mock").lower(),
        api_key=env("TTS_API_KEY"),
        model=env("TTS_MODEL"),
        voice=env("TTS_VOICE"),
        language=env("TTS_LANGUAGE", "fr"),
    ),
    jev=JevSettings(
        api_key=env("JEV_API_KEY"),
        base_url=env("JEV_BASE_URL", "https://api.typesafe.ai").rstrip("/"),
        model=env("JEV_MODEL", "jev-latest"),
    ),
    phone=PhoneSettings(
        mode=env("PHONE_MODE", "simulator").lower(),
        account_sid=env("TWILIO_ACCOUNT_SID"),
        auth_token=env("TWILIO_AUTH_TOKEN"),
        from_number=env("TWILIO_FROM").replace(" ", ""),
        to_number=env("DEMO_PHONE_TO").replace(" ", ""),
        public_url=env("PUBLIC_URL").rstrip("/"),
        validate_signature=env("TWILIO_VALIDATE_SIGNATURE", "1") != "0",
        ring_timeout=int(env("PHONE_RING_TIMEOUT", "30")),
        endpoint_delay_ms=min(3000, max(500, int(env("PHONE_ENDPOINT_DELAY_MS", "800")))),
        barge_in_words=max(1, int(env("PHONE_BARGE_IN_WORDS", "2"))),
        max_call_seconds=int(env("PHONE_MAX_CALL_SECONDS", "420")),
        machine_detection=env("PHONE_MACHINE_DETECTION", "0") == "1",
    ),
)
