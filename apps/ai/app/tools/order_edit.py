"""Order editing tools (V1): change a quantity, remove a line, move the delivery date, cancel — on the ACTIVE order of
the conversation (tools/order_state.py). They only wrap existing ERP routes; business rules stay in the ERP."""

import re
from datetime import date

from pydantic import Field

from .erp import enc
from .order_state import resolve_order_id, state_of
from .orders import summarize_order
from .registry import ToolContext, tool

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
CANCEL_INTENT = re.compile(r"annul|supprim|laisse\w* tomber|oubli|plus besoin|retire\w* (tout|la commande)|efface", re.I)


async def pick_line(ctx: ToolContext, order_id: str, line_id: str | None, product_id: str | None) -> tuple[dict, dict]:
    """Find the line to act on, by lineId or by productId (exactly one match). Returns (order, line)."""
    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}")
    if not line_id and not product_id:
        raise ValueError("Précise la ligne : lineId (renvoyé par get_order) ou productId.")
    matches = [l for l in order["lines"] if (l["id"] == line_id if line_id else l["productId"] == product_id)]
    if not matches:
        what = f"la ligne {line_id}" if line_id else f"le produit {product_id}"
        raise ValueError(f"{what} n'est pas dans la commande {order['number']} (lignes : {[(l['id'], l['productName']) for l in order['lines']]}).")
    if len(matches) > 1:
        raise ValueError(f"Plusieurs lignes pour ce produit : {[(l['id'], l['qty']) for l in matches]} — précise lineId.")
    return order, matches[0]


@tool
async def update_order_line(
    ctx: ToolContext,
    qty: float | None = Field(None, description="NOUVELLE quantité totale de la ligne (pas un ajout), > 0"),
    product_id: str | None = Field(None, description="ex. prd_0046 : la ligne de ce produit dans la commande en cours"),
    line_id: str | None = Field(None, description="ex. lin_ab12cd34, à la place de productId"),
    note: str | None = Field(None, description="remplace la note de la ligne, ex. « bien frais »"),
    order_id: str | None = Field(None, description="inutile : la commande en cours est utilisée"),
) -> dict:
    """
    Corrige une ligne de la commande en cours : « finalement quatre fûts » = qty 4 (nouvelle quantité totale, pas un ajout).
    Utilise-le pour toute correction de quantité ou de note ; n'ajoute jamais une 2e ligne du même produit.
    Change the quantity (or note) of an existing line of the active order.
    """
    if qty is None and note is None:
        raise ValueError("Rien à modifier : donne qty et/ou note.")
    state = state_of(ctx)
    state.modified_this_turn = True  # set at the START: a confirm in the same step must see it
    oid = resolve_order_id(ctx, order_id)
    _, line = await pick_line(ctx, oid, line_id, product_id)
    patch = {k: v for k, v in {"qty": qty, "note": note}.items() if v is not None}
    summary = summarize_order(await ctx.erp.patch(f"/api/orders/{enc(oid)}/lines/{enc(line['id'])}", patch))
    state.track(summary)
    return summary


@tool
async def remove_order_line(
    ctx: ToolContext,
    product_id: str | None = Field(None, description="ex. prd_0053 : le produit à retirer de la commande en cours"),
    line_id: str | None = Field(None, description="ex. lin_ab12cd34, à la place de productId"),
    order_id: str | None = Field(None, description="inutile : la commande en cours est utilisée"),
) -> dict:
    """
    Retire une ligne de la commande en cours (« enlève les caisses d'eau »). Si c'est la dernière ligne d'une commande déjà
    confirmée, annule la commande à la place. Remove one line from the active order.
    """
    state = state_of(ctx)
    state.modified_this_turn = True  # set at the START: a confirm in the same step must see it
    oid = resolve_order_id(ctx, order_id)
    _, line = await pick_line(ctx, oid, line_id, product_id)
    summary = summarize_order(await ctx.erp.delete(f"/api/orders/{enc(oid)}/lines/{enc(line['id'])}"))
    state.track(summary)
    return summary


@tool
async def update_order(
    ctx: ToolContext,
    delivery_date: str | None = Field(None, description="YYYY-MM-DD, jamais dans le passé"),
    note: str | None = Field(None, description="note de commande, ex. « livrer avant 10 h »"),
    order_id: str | None = Field(None, description="inutile : la commande en cours est utilisée"),
) -> dict:
    """
    Change la date de livraison et/ou la note de la commande en cours (brouillon ou confirmée).
    Ne promets pas une date : lis les alertes renvoyées (aucune tournée…) et le champ deliveryDayWarning.
    Change the delivery date / note of the active order.
    """
    if delivery_date is None and note is None:
        raise ValueError("Rien à modifier : donne delivery_date et/ou note.")
    state = state_of(ctx)
    state.modified_this_turn = True  # set at the START: a confirm in the same step must see it
    oid = resolve_order_id(ctx, order_id)
    body: dict = {}
    if delivery_date is not None:
        try:
            wanted = date.fromisoformat(delivery_date)
        except ValueError:
            raise ValueError("delivery_date doit être au format YYYY-MM-DD.") from None
        today = date.fromisoformat((await ctx.erp.get("/api/meta"))["today"][:10])
        if wanted < today:
            raise ValueError(f"Date dans le passé (aujourd'hui : {today.isoformat()}) : impossible.")
        body["deliveryDate"] = delivery_date
    if note is not None:
        body["note"] = note
    detail = await ctx.erp.patch(f"/api/orders/{enc(oid)}", body)
    summary = summarize_order(detail)
    if delivery_date is not None:
        weekday = date.fromisoformat(delivery_date).weekday()
        days = (detail.get("client") or {}).get("deliveryDays") or []
        if days and WEEKDAYS[weekday] not in days:
            usual = ", ".join(WEEKDAYS_FR[WEEKDAYS.index(d)] for d in days if d in WEEKDAYS)
            summary["deliveryDayWarning"] = (
                f"Ce client est habituellement livré le {usual}, pas le {WEEKDAYS_FR[weekday]} : ne promets pas cette date."
            )
    state.track(summary)
    return summary


@tool
async def cancel_order(
    ctx: ToolContext,
    order_id: str | None = Field(None, description="inutile : la commande en cours est utilisée"),
) -> dict:
    """
    Annule la commande en cours (« annule tout », « laisse tomber »). Un brouillon est annulé tout de suite ; une commande
    déjà confirmée (stock réservé, tournée) seulement si le client vient de demander l'annulation en toutes lettres.
    Cancel the active order.
    """
    state = state_of(ctx)
    oid = resolve_order_id(ctx, order_id)
    current = await ctx.erp.get(f"/api/orders/{enc(oid)}")
    if current["status"] == "confirmed" and ctx.mode == "voice":
        last_user = next((m.content for m in reversed(ctx.messages or []) if m.role == "user"), "")
        if not CANCEL_INTENT.search(last_user or ""):
            return {
                "cancelled": False,
                "reason": "cancellation_not_explicit",
                "instruction": "La commande est confirmée : demande au client s'il veut bien annuler la commande, puis attends sa réponse.",
            }
    summary = summarize_order(await ctx.erp.post(f"/api/orders/{enc(oid)}/cancel"))
    state.track(summary)
    return {"cancelled": True, **summary}
