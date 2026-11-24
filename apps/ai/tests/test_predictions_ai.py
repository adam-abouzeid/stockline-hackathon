"""V2 predictions with AI, offline: the LLM reading of the holiday reservation notes (structured tool output, validation,
fallback to rules), and the agent tools that use the predictions (the rescue price is never sent by the model)."""

import json

import httpx

from app.clients.base import LLMToolCall, LLMText
from app.schemas import ToolCall
from app.services import insights
from app.tools import ErpClient, ToolContext
from app.tools.order_state import MODIFYING_TOOLS, ORDER_TOOLS, OrderState
from app.tools.predictions import add_rescue_offer, get_rescue_offers


def note(eid: str, quote: str, products=("prd_1", "prd_2")) -> dict:
    return {"eventId": eid, "clientId": "cli_1", "clientName": "Bar Test", "productIds": list(products), "productNames": ["A", "B"],
            "text": f"Léa veut réserver pour les fêtes : A et B en volume pour les 23-24 et 30-31/12. Léa : « {quote} »"}  # fmt: skip


def test_rules_read_a_change_of_mind_a_question_and_a_price_complaint():
    r = insights.rule_signal
    assert (r(note("1", "Finalement non, mettez le double !"))["multiplier"], r(note("1", "Finalement non, mettez le double !"))["intent"]) == (2.0, "firm")
    question = r(note("2", "Et si j'en prends le double ?"))
    assert question["multiplier"] == 1.0 and question["intent"] == "tentative"  # a question is not a decision
    assert r(note("3", "À ce prix-là, je prends ailleurs."))["askedForDeal"] is True
    assert r(note("4", "Vous me faites un geste ?"))["askedForDeal"] is True
    noise = r(note("5", "Bref, je disais quoi ?"))
    assert (noise["intent"], noise["multiplier"], noise["askedForDeal"]) == ("firm", 1.0, False)  # off-topic: changes nothing
    assert r(note("6", "C'est noté où, ça ?"))["intent"] == "firm"  # any question is not hesitation


async def test_llm_signals_are_validated_and_missing_ones_fall_back_to_rules(monkeypatch):
    class FakeLLM:
        provider, model = "anthropic", "claude-test"

        def __init__(self):
            self.requests = []

        async def stream(self, req):
            self.requests.append(req)
            yield LLMText("Je lis les notes.")
            yield LLMToolCall(ToolCall(id="t1", name="save_signals", arguments={"signals": [
                {"eventId": "1", "intent": "firm", "multiplier": 12, "askedForDeal": False, "summary": "x", "droppedProductIds": ["prd_1", "prd_999"]},
                {"eventId": "2", "intent": "maybe", "multiplier": 1, "askedForDeal": False, "summary": "bad intent"},
            ]}))  # fmt: skip

    llm = FakeLLM()
    monkeypatch.setattr(insights, "get_llm_client", lambda: llm)
    signals, model = await insights.llm_signals([note("1", "Mettez-en plein"), note("2", "Et si j'en prends le double ?"), note("3", "À ce prix-là, je prends ailleurs.")])
    by = {s["eventId"]: s for s in signals}
    assert by["1"]["multiplier"] == 5.0  # clamped
    assert by["1"]["droppedProductIds"] == ["prd_1"]  # only products of the note
    assert by["2"]["intent"] == "tentative"  # invalid answer → rules
    assert by["3"]["askedForDeal"] is True  # missed by the LLM → rules
    assert model.startswith("anthropic:claude-test") and "règles pour 2" in model
    assert llm.requests[0].tools[0].name == "save_signals" and "JAMAIS de quantité" in llm.requests[0].system


async def test_without_a_real_llm_the_rules_are_used(monkeypatch):
    monkeypatch.setattr(insights, "get_llm_client", lambda: type("M", (), {"provider": "mock", "model": "m"})())
    signals, model = await insights.llm_signals([note("1", "Finalement non, mettez le double !")])
    assert model == "règles (sans LLM)" and signals[0]["multiplier"] == 2.0


def erp_with(routes: dict) -> tuple[ErpClient, list]:
    seen: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        return httpx.Response(200 if request.method == "GET" else 201, json=routes[(request.method, request.url.path)])

    return ErpClient("voice_agent", http=httpx.AsyncClient(transport=httpx.MockTransport(handler))), seen


async def test_rescue_offers_only_for_this_client_and_the_model_never_sends_a_price():
    rescue = {"items": [
        {"productId": "prd_9", "productName": "Glaçons", "unit": "bag", "suggestedDiscountPct": 20, "daysToExpiry": 3,
         "clients": [{"clientId": "cli_1", "unitPrice": 6.8, "offerPrice": 5.44, "suggestedQty": 4, "alreadyProposed": False}]},
        {"productId": "prd_8", "productName": "Glace pilée", "unit": "bag", "suggestedDiscountPct": 15, "daysToExpiry": 15,
         "clients": [{"clientId": "cli_2", "unitPrice": 5, "offerPrice": 4.2, "suggestedQty": 2, "alreadyProposed": False}]},
    ]}  # fmt: skip
    order = {"id": "ord_1", "number": "CMD-1", "status": "draft", "clientId": "cli_1", "lines": []}
    erp, seen = erp_with({
        ("GET", "/api/predictions/stock-rescue"): rescue,
        ("GET", "/api/orders/ord_1"): order,
        ("POST", "/api/predictions/stock-rescue/accept"): {**order, "lines": [{"id": "l1", "productId": "prd_9", "qty": 4, "unitPrice": 5.44}]},
    })  # fmt: skip
    offers = await get_rescue_offers.run({"clientId": "cli_1"}, ToolContext(erp=erp, actor="voice_agent"))
    assert [o["productId"] for o in offers] == ["prd_9"] and offers[0]["prixOffreHT"] == 5.44

    ctx = ToolContext(erp=erp, actor="voice_agent", mode="voice", state=OrderState(order_id="ord_1", status="draft"))
    res = await add_rescue_offer.run({"productId": "prd_9", "price": 0.01}, ctx)  # a price from the model is not even an argument
    post = next(b for m, p, b in seen if p == "/api/predictions/stock-rescue/accept")
    assert post == {"clientId": "cli_1", "productId": "prd_9", "orderId": "ord_1"} and "price" not in json.dumps(post).lower()
    assert res["id"] == "ord_1" and ctx.state.modified_this_turn  # the recap is stale: a new « oui » is needed
    assert "add_rescue_offer" in MODIFYING_TOOLS and "add_rescue_offer" in ORDER_TOOLS
