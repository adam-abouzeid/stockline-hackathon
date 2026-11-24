"""V3 outbound calls: the agent phones first. Deterministic (no ERP, no LLM): the wire contract, the call brief in the system
prompt, and a voice turn where the agent speaks before any caller speech and keeps its brief for the whole conversation."""

import json

from app.agent import prompts
from app.clients.mock_speech import MockSTT, MockTTS
from app.schemas import DoneEvent, OutboundMessage, TextEvent
from app.schemas.chat import ChatMessage
from app.services import voice_session
from app.services.voice_session import OUTBOUND_OPENING, client_message


def test_outbound_is_part_of_the_voice_contract():
    msg = client_message.validate_python({"type": "outbound", "opportunityId": "overdue~cli_0001~-"})
    assert isinstance(msg, OutboundMessage) and msg.opportunity_id == "overdue~cli_0001~-"


async def test_the_brief_reaches_the_system_prompt_only_for_an_outbound_call(monkeypatch):
    async def meta():
        return {"company": "Test", "today": "2026-11-24"}

    monkeypatch.setattr(prompts, "get_meta", meta)
    monkeypatch.setattr(prompts, "read_context_files", lambda: "")
    with_brief = await prompts.build_system_prompt("voice", "Agent", "APPEL SORTANT : client X, fait Y")
    assert "APPEL SORTANT : client X, fait Y" in with_brief
    assert "Appel sortant" in with_brief and "25 mots" in with_brief  # the outbound rules come with it
    without = await prompts.build_system_prompt("voice", "Agent")
    assert "Appel sortant" not in without and "APPEL SORTANT" not in without


class FakeWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def send_bytes(self, data: bytes) -> None:
        pass


async def test_agent_speaks_first_and_keeps_its_brief(monkeypatch):
    class FakeLLM:
        provider, model = "mock", "mock"

    class FakeErp:
        def __init__(self, actor, actor_name=None, **_):
            pass

        async def get(self, path, query=None):
            assert path == "/api/proactive/opportunities/opp-1"
            return {"brief": "BRIEF DU CLIENT"}

    calls: list[tuple[list[ChatMessage], dict]] = []

    async def fake_agent(messages, **kwargs):
        calls.append((list(messages), kwargs))
        yield TextEvent(delta="Bonjour, c'est le Comptoir. ")
        yield DoneEvent(message=ChatMessage(role="assistant", content="Bonjour, c'est le Comptoir."), ms=1)

    monkeypatch.setattr(voice_session, "get_stt_client", lambda: MockSTT("x"))
    monkeypatch.setattr(voice_session, "get_tts_client", lambda: MockTTS())
    monkeypatch.setattr(voice_session, "get_llm_client", lambda: FakeLLM())
    monkeypatch.setattr(voice_session, "run_agent", fake_agent)
    monkeypatch.setattr(voice_session, "ErpClient", FakeErp)

    conn = voice_session.VoiceConnection(FakeWS())  # type: ignore[arg-type]
    await conn.handle_text(json.dumps({"type": "outbound", "opportunityId": "opp-1"}))
    await conn.turn

    # the agent opened the call: its first words, but NO transcript of a caller (nobody has spoken)
    kinds = [m["type"] for m in conn.ws.sent]
    assert "agent_text" in kinds and "transcript" not in kinds
    first_messages, first_kwargs = calls[0]
    assert [m.content for m in first_messages] == [OUTBOUND_OPENING] and first_kwargs["brief"] == "BRIEF DU CLIENT"

    # the caller answers: same brief, and the opening is still the start of the history
    await conn.handle_text(json.dumps({"type": "text", "text": "Oui, j'ai une minute"}))
    await conn.turn
    second_messages, second_kwargs = calls[1]
    assert second_kwargs["brief"] == "BRIEF DU CLIENT"
    assert second_messages[0].content == OUTBOUND_OPENING and second_messages[-1].content == "Oui, j'ai une minute"

    # a reset ends the outbound call: the next conversation has no brief
    await conn.handle_text(json.dumps({"type": "reset"}))
    await conn.handle_text(json.dumps({"type": "text", "text": "Bonjour"}))
    await conn.turn
    assert calls[2][1]["brief"] is None
