"""
V1 order reliability — INTEGRATION tests against the REAL ERP (not mocked), with a SCRIPTED model.

The LLM is replaced by a script (the model "decides" to call exactly these tools); everything else is real: the agent
loop, the tools, the guards, the ERP API. Each test then asserts the resulting ERP STATE, not what the agent says.
These tests prove the safeguards in code. They do NOT prove that a real LLM chooses the right tool: for that, replay
the scenarios with the real provider (scripts outside the test suite, see DECISIONS.md).

Run against the running stack:   docker compose cp apps/ai/tests ai:/app/apps/ai/ && docker compose exec ai python -m pytest tests/test_order_v1_erp.py
Isolation: no reset. Each test cancels the orders it created (fixture `track`); skipped when the ERP is unreachable.
Needs the Comptoir des Chartrons data pack: cli_0002 (Régent), cli_0007 (Zinc, blocked), cli_0024 (Pey-Berland, near its limit).
"""

import itertools

import httpx
import pytest

from app.agent import loop as agent_loop
from app.clients import LLMClient, LLMRequest, LLMText, LLMToolCall
from app.config import settings
from app.schemas import ChatMessage, ToolCall, ToolResultEvent
from app.agent.loop import run_agent
from app.tools import all_tools

REGENT, ZINC, PEY = "cli_0002", "cli_0007", "cli_0024"
KEG, WATER, CHAMPAGNE = "prd_0046", "prd_0053", "prd_0027"  # blonde Garonne fût 30 L · eau plate 1 L (casier) · champagne brut


def erp_up() -> bool:
    try:
        return httpx.get(f"{settings.erp_api_url}/api/meta", timeout=2).is_success
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not erp_up(), reason="ERP not reachable")


# ───────── ERP access for assertions (sync, independent from the agent's own client) ─────────


def api(method: str, path: str, actor: str = "user", **kw):
    r = httpx.request(method, f"{settings.erp_api_url}/api{path}", headers={"x-actor": actor}, timeout=15, **kw)
    return r


def orders_of(client_id: str) -> dict[str, dict]:
    rows = api("GET", f"/orders?clientId={client_id}&limit=200").json()
    return {o["id"]: o for o in rows}


def detail(order_id: str) -> dict:
    return api("GET", f"/orders/{order_id}").json()


def events_for(order_id: str, client_id: str) -> list[dict]:
    return [e for e in api("GET", f"/clients/{client_id}/events?limit=100").json() if e.get("orderId") == order_id]


@pytest.fixture
def track():
    """Remember the orders that exist before the test; cancel every order the test created, whatever its status."""
    before = {c: set(orders_of(c)) for c in (REGENT, ZINC, PEY)}
    yield before
    for client_id, known in before.items():
        for oid, o in orders_of(client_id).items():
            if oid not in known and o["status"] in ("draft", "confirmed", "prepared"):
                api("POST", f"/orders/{oid}/cancel")


def new_orders(track, client_id: str) -> list[dict]:
    return [detail(oid) for oid in orders_of(client_id) if oid not in track[client_id]]


# ───────── scripted model + a phone call ─────────


class ScriptedLLM(LLMClient):
    provider, model = "scripted", "scripted"

    def __init__(self, steps):
        self.steps = list(steps)

    async def stream(self, request: LLMRequest):
        for ev in self.steps.pop(0) if self.steps else [LLMText("Fin.")]:
            yield ev


_ids = itertools.count(1)


def tool(name: str, **arguments) -> LLMToolCall:
    return LLMToolCall(ToolCall(id=f"call_{next(_ids)}", name=name, arguments=arguments))


def say(text: str) -> list:
    return [LLMText(text)]


class Call:
    """One phone call: keeps the history across turns, like the voice session does."""

    def __init__(self, mode: str = "voice"):
        self.messages: list[ChatMessage] = []
        self.mode = mode

    async def turn(self, user_text: str, *steps) -> list[ToolResultEvent]:
        """The customer speaks; the scripted model plays `steps` (one list of events per model call)."""
        self.messages.append(ChatMessage(role="user", content=user_text))
        results = []
        async for ev in run_agent(self.messages, llm=ScriptedLLM(steps), tools=all_tools(), mode=self.mode):
            if isinstance(ev, ToolResultEvent):
                results.append(ev)
        return results


@pytest.fixture(autouse=True)
def no_prompt_lookup(monkeypatch):
    async def prompt(mode, actor_name=None):
        return "SYS"

    async def parts(mode, actor_name=None, brief=None):
        return "SYS", ""

    monkeypatch.setattr(agent_loop, "build_system_prompt", prompt)
    monkeypatch.setattr(agent_loop, "build_system_parts", parts)


def lines_of(order: dict) -> list[tuple[str, float]]:
    return [(l["productId"], l["qty"]) for l in order["lines"]]


def keg_order(qty: float = 2) -> list:
    return [tool("create_draft_order", clientId=REGENT, lines=[{"productId": KEG, "qty": qty}])]


# ───────── corrections, removals, cancellation, repeated instructions ─────────


async def test_two_corrections_leave_one_order_with_one_correct_line(track):
    call = Call()
    await call.turn("Deux fûts de blonde.", keg_order(2), say("Deux fûts, je confirme ?"))
    await call.turn("Non, quatre.", [tool("update_order_line", productId=KEG, qty=4)], say("Quatre fûts, je confirme ?"))
    await call.turn("Finalement trois.", [tool("update_order_line", productId=KEG, qty=3)], say("Trois fûts, je confirme ?"))
    (order,) = new_orders(track, REGENT)  # exactly one order for the whole call
    assert order["status"] == "draft"
    assert lines_of(order) == [(KEG, 3.0)]  # one line, final quantity
    assert order["totalHt"] == pytest.approx(3 * 92.0)  # negotiated price, computed by the ERP


async def test_remove_a_line(track):
    call = Call()
    lines = [{"productId": KEG, "qty": 4}, {"productId": WATER, "qty": 6}]
    await call.turn("Quatre fûts et six caisses d'eau.", [tool("create_draft_order", clientId=REGENT, lines=lines)], say("OK, je confirme ?"))
    await call.turn("Retire les caisses d'eau.", [tool("remove_order_line", productId=WATER)], say("C'est retiré."))
    (order,) = new_orders(track, REGENT)
    assert lines_of(order) == [(KEG, 4.0)]


async def test_adding_a_product_already_in_the_order_is_refused_no_duplicate_line(track):
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Je confirme ?"))
    (result,) = await call.turn("Mets-en deux de plus.", [tool("add_order_line", productId=KEG, qty=2)], say("Désolé."))
    assert not result.ok and "update_order_line" in str(result.result)
    (order,) = new_orders(track, REGENT)
    assert lines_of(order) == [(KEG, 2.0)]


async def test_repeated_create_in_one_call_does_not_make_a_second_order(track):
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Je confirme ?"))
    (result,) = await call.turn("Deux fûts de blonde, je t'ai dit.", keg_order(2), say("Je confirme ?"))
    assert not result.ok and "déjà en cours" in str(result.result)
    assert len(new_orders(track, REGENT)) == 1


async def test_cancel_a_draft_then_start_again(track):
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Je confirme ?"))
    await call.turn("Annule tout.", [tool("cancel_order")], say("C'est annulé."))
    first = new_orders(track, REGENT)
    assert [o["status"] for o in first] == ["cancelled"]
    await call.turn("Finalement trois fûts.", keg_order(3), say("Trois fûts, je confirme ?"))  # allowed again: nothing active
    statuses = sorted(o["status"] for o in new_orders(track, REGENT))
    assert statuses == ["cancelled", "draft"]


async def test_delivery_date_change_and_a_date_in_the_past(track):
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Je confirme ?"))
    await call.turn("Plutôt vendredi.", [tool("update_order", deliveryDate="2026-11-27")], say("Vendredi, je confirme ?"))
    (order,) = new_orders(track, REGENT)
    assert order["deliveryDate"] == "2026-11-27"
    (result,) = await call.turn("Livre-moi hier.", [tool("update_order", deliveryDate="2026-11-01")], say("Impossible."))
    assert not result.ok
    assert detail(order["id"])["deliveryDate"] == "2026-11-27"  # unchanged


async def test_a_tool_cannot_touch_an_order_other_than_the_active_one(track):
    other = detail(next(iter(orders_of(REGENT))))["id"]  # an existing order of the same client (not ours)
    before = lines_of(detail(other))
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Je confirme ?"))
    (result,) = await call.turn("Change l'autre commande.", [tool("update_order_line", orderId=other, productId=KEG, qty=99)], say("Non."))
    assert not result.ok
    assert lines_of(detail(other)) == before


# ───────── recap + explicit approval before confirming ─────────


async def test_no_confirmation_in_the_turn_where_the_order_is_created(track):
    call = Call()
    # the model tries to create AND confirm in one go: the customer never heard a recap
    await call.turn("Deux fûts, confirme direct.", keg_order(2), [tool("confirm_order")], say("C'est fait."))
    (order,) = new_orders(track, REGENT)
    assert order["status"] == "draft"


@pytest.mark.parametrize("reply", ["Euh, je sais pas.", "Oui mais attends.", "Ok, et mets-en deux de plus.", "C'est livré quand ?", "Non.", "Merci."])
async def test_ambiguous_consent_never_confirms(track, reply):
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Deux fûts, 184 euros, je confirme ?"))
    (result,) = await call.turn(reply, [tool("confirm_order")], say("Je ne confirme pas."))
    assert result.result["confirmed"] is False
    (order,) = new_orders(track, REGENT)
    assert order["status"] == "draft"


async def test_clear_approval_after_the_recap_confirms_exactly_once(track):
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Deux fûts, 184 euros, livraison demain. Je confirme ?"))
    (result,) = await call.turn("Oui, vas-y.", [tool("confirm_order")], say("C'est confirmé."))
    assert result.result["confirmed"] is True
    (order,) = new_orders(track, REGENT)
    assert order["status"] == "confirmed" and lines_of(order) == [(KEG, 2.0)]
    # the customer repeats "oui": a second confirm must not create or change anything
    (again,) = await call.turn("Oui oui.", [tool("confirm_order")], say("Déjà confirmé."))
    assert not again.ok
    assert len(new_orders(track, REGENT)) == 1


async def test_a_modification_after_the_approved_recap_requires_a_new_recap(track):
    call = Call()
    await call.turn("Deux fûts.", keg_order(2), say("Deux fûts, je confirme ?"))
    # the customer says "oui", but the model changes the quantity in the same step as the confirm: the recap is stale
    (_, result) = await call.turn("Oui.", [tool("update_order_line", productId=KEG, qty=6), tool("confirm_order")], say("Six fûts, je confirme ?"))
    assert result.result["confirmed"] is False
    (order,) = new_orders(track, REGENT)
    assert order["status"] == "draft" and lines_of(order) == [(KEG, 6.0)]
    # the model then recapped the six: THIS "oui" confirms
    (final,) = await call.turn("Oui.", [tool("confirm_order")], say("Confirmé."))
    assert final.result["confirmed"] is True
    assert detail(order["id"])["status"] == "confirmed"


async def test_command_mode_keeps_working_for_salespeople(track):
    """A salesperson's one-sentence voice command is itself the instruction: no recap needed (the ERP guards still apply)."""
    call = Call(mode="command")
    (_, result) = await call.turn("Crée et confirme une commande de deux fûts pour le Régent.", keg_order(2), [tool("confirm_order")], say("Fait."))
    assert result.result["confirmed"] is True
    (order,) = new_orders(track, REGENT)
    assert order["status"] == "confirmed"


# ───────── blocked customers and credit limits: a human decides ─────────


async def test_blocked_client_order_stays_a_draft_and_accounting_is_told(track):
    call = Call()
    await call.turn("Deux fûts pour le match.", [tool("create_draft_order", clientId=ZINC, lines=[{"productId": KEG, "qty": 2}])], say("Deux fûts, je confirme ?"))
    (result,) = await call.turn("Oui, vas-y.", [tool("confirm_order")], say("Martine va vous rappeler."))
    assert result.result["confirmed"] is False and result.result["humanApprovalRequired"] is True
    assert result.result["reason"] == "client_blocked"
    (order,) = new_orders(track, ZINC)
    assert order["status"] == "draft"
    assert events_for(order["id"], ZINC), "the request should be traced in the client's history for Martine"


async def test_over_credit_limit_needs_human_validation(track):
    call = Call()
    big = [tool("create_draft_order", clientId=PEY, lines=[{"productId": CHAMPAGNE, "qty": 400}])]
    await call.turn("Quatre cents bouteilles de champagne.", big, say("Quatre cents bouteilles, je confirme ?"))
    (result,) = await call.turn("Oui, confirme.", [tool("confirm_order")], say("Martine doit valider."))
    assert result.result["confirmed"] is False and result.result["reason"] == "credit_approval_required"
    (order,) = new_orders(track, PEY)
    assert order["status"] == "draft"
    assert events_for(order["id"], PEY)


async def test_erp_refuses_the_ai_even_when_the_tool_layer_is_bypassed(track):
    """The guard is in the ERP, not in the tool: a direct API call as the voice agent is refused too."""
    created = api("POST", "/orders", actor="voice_agent", json={"clientId": ZINC, "lines": [{"productId": KEG, "qty": 1}]}).json()
    refused = api("POST", f"/orders/{created['id']}/confirm", actor="voice_agent")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "client_blocked"
    refused_chat = api("POST", f"/orders/{created['id']}/confirm", actor="ai_chat")
    assert refused_chat.status_code == 409
    assert detail(created["id"])["status"] == "draft"
    # a human (the web UI, actor `user`) keeps the right to decide
    assert api("POST", f"/orders/{created['id']}/confirm", actor="user").json()["status"] == "confirmed"
