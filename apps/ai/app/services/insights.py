"""
Reading client notes with the LLM, for the predictions (V2): the « Fêtes <year> : réservation de volumes » notes.

The arithmetic (backend, services/predictions.py) estimates each reserved line from the client's own past purchases. What
it cannot read is what the client WROTE: a change of mind (« Finalement non, mettez le double ! »), a cancellation, a
condition, a question that is not a commitment (« Et si j'en prends le double ? »), or a client who finds us too expensive
(« À ce prix-là, je prends ailleurs »). The LLM reads the notes and returns ONE signal per note through a tool call
(structured output); the ERP validates and stores them (PUT /api/predictions/signals). The LLM never gives a quantity or a
price. Without a real LLM (LLM_PROVIDER=mock, or an error), simple French rules do the same job, less finely.

Whether the signals make the forecast better is MEASURED, not assumed: GET /api/predictions/holiday-reservations/backtest
?season=2025&signals=true|false compares the estimate with what clients really bought.
"""

import asyncio
import json
import re

from app.clients import LLMRequest, LLMText, LLMToolCall, get_llm_client
from app.schemas import ChatMessage, ToolInfo
from app.tools import ErpClient

BATCH = 12  # notes per LLM call (calls run in parallel)

SYSTEM = """Tu lis des notes de clients d'un grossiste en vins et boissons, écrites par les commerciaux : des réservations de volumes pour les fêtes.
Pour CHAQUE note, tu dis comment la lire. Tu ne donnes JAMAIS de quantité ni de prix : l'ERP les calcule à partir de l'historique du client.

- intent : "firm" (il réserve, sans réserve), "tentative" (il hésite, pose une question, met une condition, demande du temps), "cancelled" (il annule tout), "unclear" (rien à en tirer).
- multiplier : 1 par défaut. 2 SEULEMENT si le client demande clairement le double (« mettez le double ! »). Une QUESTION (« et si j'en prends le double ? ») n'est pas une décision : multiplier 1, intent "tentative". 0.5 pour « moitié moins ».
- droppedProductIds : les produits de la note que le client retire explicitement (sinon []).
- askedForDeal : true s'il réclame un geste, une remise, trouve les prix trop chers ou menace d'aller ailleurs pour le prix.
- condition : la condition qu'il pose, en quelques mots, sinon null.
- summary : une phrase courte en français pour un commercial (ex. « Réserve ses volumes habituels, trouve les prix élevés »).
Les phrases hors sujet (« Bref, je disais quoi ? », « Et ta famille, ça va ? », « Passez goûter le nouveau plat ! ») ne changent rien : intent "firm" si la réservation est faite, multiplier 1.
Appelle l'outil save_signals UNE seule fois avec un signal par note (le même eventId)."""

TOOL = ToolInfo(
    name="save_signals",
    description="Enregistre la lecture de chaque note (un signal par note).",
    parameters={
        "type": "object",
        "properties": {
            "signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "eventId": {"type": "string"},
                        "intent": {"type": "string", "enum": ["firm", "tentative", "cancelled", "unclear"]},
                        "multiplier": {"type": "number"},
                        "droppedProductIds": {"type": "array", "items": {"type": "string"}},
                        "askedForDeal": {"type": "boolean"},
                        "condition": {"type": "string", "description": "la condition posée, ou chaîne vide"},
                        "summary": {"type": "string"},
                    },
                    "required": ["eventId", "intent", "multiplier", "askedForDeal", "summary"],
                },
            }
        },
        "required": ["signals"],
    },
)

# ── rules: the fallback without an LLM (and the reference the LLM is compared with) ──

DEAL = re.compile(r"geste|remise|ristourne|plus cher|trop cher|à ce prix|ailleurs|bordereau de prix|moins cher", re.I)
TENTATIVE = re.compile(r"peut-être|on verra|laisse[- ]moi|jusqu'à la fin|et si j'en prends|je vous redis|à confirmer|si (le|la|ça|on)\b", re.I)
DOUBLE_FIRM = re.compile(r"mettez le double|doublez|le double\s*!", re.I)
CANCEL = re.compile(r"annul|on oublie|plus besoin", re.I)


def quote_of(text: str) -> str:
    m = re.search(r"«\s*(.+?)\s*»", text or "")
    return m[1] if m else ""


def rule_signal(note: dict) -> dict:
    text, q = note.get("text", ""), quote_of(note.get("text", ""))
    intent, mult = "firm", 1.0
    if CANCEL.search(q) and not DOUBLE_FIRM.search(q):
        intent, mult = "cancelled", 0.0
    elif DOUBLE_FIRM.search(q):
        mult = 2.0
    elif TENTATIVE.search(q):
        intent = "tentative"
    deal = bool(DEAL.search(q))
    summary = {"cancelled": "Annule sa réservation", "tentative": "Réservation à confirmer : il hésite"}.get(intent, "Réserve ses volumes habituels")
    if mult == 2:
        summary = "A changé d'avis : il veut le double"
    if deal:
        summary += ", sensible au prix"
    return {"eventId": note["eventId"], "intent": intent, "multiplier": mult, "droppedProductIds": [], "askedForDeal": deal,
            "condition": None, "summary": summary}  # fmt: skip


async def llm_signals(notes: list[dict]) -> tuple[list[dict], str]:
    """One signal per note from the LLM (batches in parallel). Notes it missed or garbled fall back to the rules."""
    llm = get_llm_client()
    if llm.provider == "mock":
        return [rule_signal(n) for n in notes], "règles (sans LLM)"

    async def batch(items: list[dict]) -> list[dict]:
        payload = "\n".join(json.dumps({"eventId": n["eventId"], "client": n["clientName"], "produits": dict(zip(n["productIds"], n["productNames"])),
                                        "note": n["text"]}, ensure_ascii=False) for n in items)  # fmt: skip
        req = LLMRequest(system=SYSTEM, messages=[ChatMessage(role="user", content=f"Notes (une par ligne) :\n{payload}")], tools=[TOOL], max_tokens=4000)
        text, out = "", []
        async for ev in llm.stream(req):
            if isinstance(ev, LLMToolCall) and ev.call.name == "save_signals":
                out += ev.call.arguments.get("signals") or []
            elif isinstance(ev, LLMText):
                text += ev.delta
        if not out and "{" in text:  # a model that answered in JSON text instead of calling the tool
            try:
                out = json.loads(text[text.index("{") : text.rindex("}") + 1]).get("signals") or []
            except ValueError:
                out = []
        return out

    results = await asyncio.gather(*(batch(notes[i : i + BATCH]) for i in range(0, len(notes), BATCH)), return_exceptions=True)
    by_id: dict[str, dict] = {}
    for r in results:
        if isinstance(r, Exception):
            print(f"[insights] LLM batch failed: {r}", flush=True)
            continue
        for s in r:
            if isinstance(s, dict) and s.get("eventId"):
                by_id[s["eventId"]] = s
    out, fallback = [], 0
    for n in notes:
        s = by_id.get(n["eventId"])
        if not s or s.get("intent") not in ("firm", "tentative", "cancelled", "unclear"):
            s, fallback = rule_signal(n), fallback + 1
        try:
            mult = float(s.get("multiplier", 1))
        except (TypeError, ValueError):
            mult = 1.0
        out.append({
            "eventId": n["eventId"], "intent": s["intent"], "multiplier": min(5.0, max(0.0, mult)),
            "droppedProductIds": [p for p in s.get("droppedProductIds") or [] if p in n["productIds"]],
            "askedForDeal": bool(s.get("askedForDeal")), "condition": s.get("condition") or None, "summary": str(s.get("summary") or "")[:300],
        })  # fmt: skip
    model = f"{llm.provider}:{llm.model}" + (f" (+ règles pour {fallback} note(s))" if fallback else "")
    return out, model


async def extract_reservations(season: int | None = None) -> dict:
    erp = ErpClient("ai_chat", "Analyse IA des notes")
    notes = await erp.get("/api/predictions/holiday-reservations/notes", {"season": season})
    if not notes:
        return {"season": season, "notes": 0, "saved": 0, "model": None, "byIntent": {}, "askedForDeal": 0}
    signals, model = await llm_signals(notes)
    await erp.put("/api/predictions/signals", {"signals": signals, "model": model})
    by_intent: dict[str, int] = {}
    for s in signals:
        by_intent[s["intent"]] = by_intent.get(s["intent"], 0) + 1
    return {
        "season": season, "notes": len(notes), "saved": len(signals), "model": model, "byIntent": by_intent,
        "doubled": sum(1 for s in signals if s["multiplier"] > 1), "askedForDeal": sum(1 for s in signals if s["askedForDeal"]),
    }  # fmt: skip
