"""
V2 predictions, for the agent: what a client reserved in writing for the holidays (with its own past volumes), and the stock
to rescue it could be offered. The agent never sets a price: add_rescue_offer goes through an ERP route that computes the
rescue price itself, refuses it below cost, and only for a client who buys that product. The order still needs the recap
and the client's explicit « oui » (approval gate, tools/approval.py).
"""

from pydantic import Field

from .erp import enc
from .order_state import resolve_order_id, state_of
from .orders import summarize_order
from .registry import ToolContext, tool


@tool
async def get_holiday_reservation(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Carnet de Noël d'un client : ce qu'il a réservé par écrit pour les fêtes (note du commercial) et, pour chaque produit, ce
    qu'il a pris fin décembre les années passées (« l'an dernier vous aviez pris 24 pomerols »). Quantités = estimation à
    partir de SON historique, à faire confirmer par le client. Holiday reservations of a client, with its past late-December volumes.
    """
    data = await ctx.erp.get("/api/predictions/holiday-reservations", {"clientId": client_id})
    notes = [{"date": n["at"], "ceQuilADit": n.get("quote"), "lecture": n.get("aiSummary"), "intention": n["intent"]} for n in data["notes"]]
    lines = [
        {
            "productId": ln["productId"], "produit": ln["productName"], "unite": ln["unit"],
            "anneesPassees": {str(p["year"]): p["qty"] for p in ln["pastYears"]}, "estimation": ln["qty"],
            "prixUnitaireHT": ln["unitPrice"], "dejaCommande": ln["ordered"],
        }
        for ln in data["lines"]
    ]  # fmt: skip
    if not notes:
        return {"reservation": None, "message": "Aucune réservation écrite pour les fêtes cette année."}
    return {"saison": data["season"], "notes": notes, "lignes": lines, "livraisons": "23-24 et 30-31 décembre (selon la note)"}


@tool
async def get_rescue_offers(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> list[dict]:
    """
    Offres de déstockage possibles pour CE client : lots qui ne se vendront pas avant leur date limite, d'un produit qu'il achète
    déjà, avec un prix remisé calculé par l'ERP (jamais sous le coût). À proposer UNE fois au plus, seulement une fois le
    sujet de l'appel réglé et si le client semble ouvert ; jamais d'insistance. Rescue offers for this client.
    """
    data = await ctx.erp.get("/api/predictions/stock-rescue")
    out = []
    for item in data["items"]:
        offer = next((c for c in item["clients"] if c["clientId"] == client_id), None)
        if offer:
            out.append({
                "productId": item["productId"], "produit": item["productName"], "unite": item["unit"],
                "prixHabituelHT": offer["unitPrice"], "prixOffreHT": offer["offerPrice"], "remisePct": item["suggestedDiscountPct"],
                "quantiteSuggeree": offer["suggestedQty"], "joursAvantDateLimite": item["daysToExpiry"], "dejaProposee": offer["alreadyProposed"],
            })  # fmt: skip
    return out


@tool
async def add_rescue_offer(
    ctx: ToolContext,
    product_id: str = Field(description="Le produit de l'offre (get_rescue_offers)"),
    qty: float | None = Field(None, description="Quantité acceptée par le client (défaut : la quantité suggérée)"),
    order_id: str | None = None,
) -> dict:
    """
    Le client ACCEPTE une offre de déstockage : ajoute le lot à sa commande en cours (brouillon) au prix d'offre calculé par
    l'ERP. Ensuite, récapitule et attends son « oui » avant confirm_order. Ne l'appelle jamais sans son accord explicite.
    Adds an accepted rescue offer to the draft order (price set by the ERP).
    """
    state = state_of(ctx)
    state.modified_this_turn = True  # a new line: the last recap is stale
    oid = resolve_order_id(ctx, order_id)
    order = await ctx.erp.get(f"/api/orders/{enc(oid)}")
    body = {"clientId": order["clientId"], "productId": product_id, "orderId": oid, **({"qty": qty} if qty else {})}
    summary = summarize_order(await ctx.erp.post("/api/predictions/stock-rescue/accept", body))
    state.track(summary)
    return summary
