"""Deterministic tests (no ERP, no LLM): what counts as the customer's approval, and when confirm_order may run."""

import pytest

from app.schemas import ChatMessage, ToolCall
from app.tools.approval import confirmation_gate, is_explicit_approval
from app.tools.order_state import derive_state


@pytest.mark.parametrize(
    "text",
    ["Oui", "oui.", "OK", "Ok, vas-y", "OK, vas-y.", "Oui, confirme", "C'est bon", "d'accord", "Parfait", "ouais ouais", "Oui, pas de souci", "Yes", "Nickel, envoie", "Allez, go", "Oui c'est ça",
     # V2: plain yeses with polite filler stay accepted
     "Oui, c'est tout", "Oui merci, au revoir", "Ben oui", "Bah ouais", "Oui je confirme", "Oui, c'est noté", "Tout à fait", "Oui oui, parfait"],
)
def test_clear_approvals(text):
    assert is_explicit_approval(text).approved, text


@pytest.mark.parametrize(
    "text",
    [
        "",  # nothing heard
        "   ",
        "Euh...",
        "Hum, oui, je sais pas",  # hesitation
        "Oui mais attends",  # reservation
        "Oui, enfin peut-être",
        "Non",
        "Non, pas comme ça",
        "Ok mais mets-en six",  # change hidden behind an ok
        "Oui, et ajoute une caisse d'eau",
        "Oui et deux fûts de plus",
        "D'accord, finalement quatre",
        "Oui, c'est livré quand ?",  # question
        "Ok, et si tu n'as pas la blonde ?",
        "C'est bon pour combien ?",
        "Oui, mets 12 bouteilles",  # digit
        "Je réfléchis",
        "Laisse tomber",
        "Vas-y, annule",
        "Bof, ok",
        "Ça dépend, je vérifie avec le chef et je te rappelle dans une heure ou deux ok",  # too long
        "Merci",  # polite, not an approval
        "Bonjour",
        # V2: hedged or conditional "yes" that the old blocklist let through (found by the bench: "oui si tu veux" confirmed)
        "Oui si tu veux",
        "Oui je pense",
        "Oui je crois que c'est bon",
        "Oui normalement",
        "Oui, c'est bon pour moi a priori",
        "Hmm ok",
        "Oui... enfin je crois",
        "Oui pour lundi",  # a date slipped into the yes
        "Oui, livrez demain",
        "Ouais pourquoi pas",
        "Oui, comme vous voulez",
        "On verra",
        "Si vous voulez",
    ],
)
def test_ambiguous_or_conditional_consent_is_not_approval(text):
    assert not is_explicit_approval(text).approved, text


def msgs(*items) -> list[ChatMessage]:
    out = []
    for kind, content in items:
        match kind:
            case "user" | "assistant":
                out.append(ChatMessage(role=kind, content=content))
            case "tool":  # a modifying tool round: assistant call + result
                out.append(ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id=f"t{len(out)}", name=content, arguments={})]))
                out.append(ChatMessage(role="tool", tool_call_id=f"t{len(out) - 1}", name=content, content='{"id":"ord_1","status":"draft"}'))
    return out


def test_gate_happy_path():
    h = msgs(("user", "deux fûts"), ("tool", "create_draft_order"), ("assistant", "Deux fûts, 184 euros. Je confirme ?"), ("user", "Oui vas-y"))
    assert confirmation_gate(h).approved


def test_gate_accepts_an_order_prepared_by_reorder_last_order():
    # regression found by the bench: reorder_last_order was unknown to the gate → "la commande n'a pas été préparée" forever
    h = msgs(("user", "comme d'habitude"), ("tool", "reorder_last_order"), ("assistant", "Je reprends votre dernière commande, 888 euros. On confirme ?"), ("user", "Oui, c'est bon, vas-y"))
    assert confirmation_gate(h).approved


def test_reorder_last_order_makes_its_order_the_active_one():
    h = msgs(("user", "comme d'habitude"), ("tool", "reorder_last_order"))
    assert derive_state(h).order_id == "ord_1"  # so a 2nd create_draft_order is refused: no duplicate order


def test_gate_refuses_without_recap_turn():
    # created and "approved" in the same turn: the customer never heard the recap
    h = msgs(("user", "deux fûts, vas-y"), ("tool", "create_draft_order"))
    assert not confirmation_gate(h).approved


def test_gate_refuses_ambiguous_reply_after_recap():
    h = msgs(("user", "deux fûts"), ("tool", "create_draft_order"), ("assistant", "Je confirme ?"), ("user", "euh, oui mais attends"))
    assert not confirmation_gate(h).approved


def test_gate_refuses_stale_recap_after_a_modification():
    h = msgs(
        ("user", "deux fûts"), ("tool", "create_draft_order"), ("assistant", "Je confirme ?"),
        ("user", "oui"), ("tool", "update_order_line"),  # the agent changed something AFTER the approved recap
    )  # fmt: skip
    assert not confirmation_gate(h).approved


def test_gate_refuses_when_modified_in_the_current_turn():
    h = msgs(("user", "deux fûts"), ("tool", "create_draft_order"), ("assistant", "Je confirme ?"), ("user", "oui"))
    assert confirmation_gate(h).approved
    assert not confirmation_gate(h, modified_this_turn=True).approved


def test_gate_requires_a_new_recap_after_a_correction():
    h = msgs(
        ("user", "deux fûts"), ("tool", "create_draft_order"), ("assistant", "Je confirme ?"),
        ("user", "non finalement quatre"), ("tool", "update_order_line"), ("assistant", "Quatre fûts, 368 euros. Je confirme ?"), ("user", "oui"),
    )  # fmt: skip
    assert confirmation_gate(h).approved
    no_new_recap = msgs(
        ("user", "deux fûts"), ("tool", "create_draft_order"), ("assistant", "Je confirme ?"),
        ("user", "non finalement quatre"), ("tool", "update_order_line"), ("user", "oui"),
    )  # fmt: skip
    assert not confirmation_gate(no_new_recap).approved


def test_derive_state_follows_the_order_through_the_conversation():
    def tool_msg(name, content):
        return ChatMessage(role="tool", tool_call_id="x", name=name, content=content)

    h = [tool_msg("create_draft_order", '{"id":"ord_7","status":"draft"}')]
    assert derive_state(h).order_id == "ord_7"
    h.append(tool_msg("confirm_order", '{"confirmed":true,"id":"ord_7","status":"confirmed"}'))
    assert derive_state(h).status == "confirmed"
    h.append(tool_msg("cancel_order", '{"cancelled":true,"id":"ord_7","status":"cancelled"}'))
    assert not derive_state(h).active
    h.append(tool_msg("add_order_line", '{"error":"boom"}'))  # an error never changes the state
    assert not derive_state(h).active
