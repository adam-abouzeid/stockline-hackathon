"""
V3 proactive calls: the agent records what was decided at the end of a call IT placed (Appels du jour).

One dedicated tool instead of a title convention: the journal of calls shows the decision whatever the wording, the client's
history gets one « Appel proactif : … » line (which also stops a second call to that client today), and on a real phone call
the bridge knows the call can end once the goodbye is spoken (services/phone.py).
"""

from pydantic import Field

from .erp import enc
from .registry import ToolContext, tool


@tool
async def record_call_outcome(
    ctx: ToolContext,
    decision: str = Field(description="Ce qui a été décidé, en une phrase courte, ex. « livraison décalée au jeudi 24, jus ramené à 67 »"),
    summary: str | None = Field(None, description="Optionnel : 1 à 2 phrases de détail (ce que le client a dit)"),
) -> dict:
    """
    UNIQUEMENT pendant un appel sortant (Appels du jour) : enregistre la décision prise avec le client, à la fin de l'appel,
    AVANT de dire au revoir — qu'il ait accepté, refusé ou n'ait pas eu le temps (ex. « client pas disponible, rien changé »).
    Un seul appel suffit ; le rappeler corrige la décision. Records the outcome of an outbound call.
    """
    call = ctx.call or {}
    if not call.get("opportunityId"):
        raise ValueError("Aucun appel sortant en cours : pour noter quelque chose dans le dossier du client, utilise log_client_event.")
    body = {"decision": decision, "summary": summary, "callId": call.get("callId")}
    res = await ctx.erp.post(f"/api/proactive/opportunities/{enc(call['opportunityId'])}/outcome", {k: v for k, v in body.items() if v})
    return {"ok": True, "decision": res.get("decision", decision), "noteDansLeDossier": True}
