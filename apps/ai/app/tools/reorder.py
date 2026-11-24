"""
V2: « comme la dernière fois » in one gesture.

`reorder_last_order` copies the lines of the client's latest real order into the draft of this call. It goes through the
same draft as `create_draft_order` (one active order per call), so the recap + explicit approval gate still applies:
the customer hears the copied order and must say a plain yes. Prices and stock are resolved by the ERP, not copied.
"""

from pydantic import Field

from .erp import enc
from .history import without_none
from .order_state import state_of
from .orders import OrderLine, summarize_order
from .registry import ToolContext, tool

REAL_STATUSES = {"confirmed", "prepared", "delivered", "invoiced"}  # not a draft, not a cancelled order


@tool
async def reorder_last_order(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    delivery_date: str | None = Field(None, description="YYYY-MM-DD, optionnel (sinon prochain jour de livraison du client)"),
) -> dict:
    """
    Pour « comme d'habitude », « comme la dernière fois », « la même chose » : crée le brouillon de cet appel avec les MÊMES
    lignes que la dernière vraie commande du client (prix et stock recalculés par l'ERP). Ensuite : lis le récapitulatif,
    demande s'il veut ajuster quelque chose, et n'attends son accord explicite qu'après. Refusé si une commande est déjà en cours.
    Copies the client's last real order into this call's draft.
    """
    state = state_of(ctx)
    if state.active:
        raise ValueError(
            f"Une commande est déjà en cours dans cet appel ({state.order_id}, {state.status}) : modifie-la, n'en recrée pas une."
        )
    client = await ctx.erp.get(f"/api/clients/{enc(client_id)}")
    source = None
    for o in client.get("recentOrders") or []:  # newest first
        if o.get("status") in REAL_STATUSES:
            detail = await ctx.erp.get(f"/api/orders/{enc(o['id'])}")
            if detail.get("lines"):
                source = detail
                break
    if source is None:
        raise ValueError("Aucune commande précédente à reprendre pour ce client : demande-lui ce qu'il veut commander.")

    state.modified_this_turn = True
    lines = [OrderLine(product_id=l["productId"], qty=l["qty"], note=l.get("note")) for l in source["lines"]]
    body = without_none(
        {
            "clientId": client_id,
            "deliveryDate": delivery_date,
            "lines": [line.to_erp() for line in lines],
            "source": "voice_agent" if ctx.actor == "voice_agent" else "web",
        }
    )
    summary = summarize_order(await ctx.erp.post("/api/orders", body))
    state.track(summary)
    return {
        **summary,
        "copiedFrom": {"number": source["number"], "deliveryDate": source.get("deliveryDate")},
        "instruction": "Annonce que tu reprends la commande du client (dis laquelle, brièvement), lis le récapitulatif, "
        "puis demande s'il veut ajuster quelque chose. Ne confirme pas avant son accord explicite.",
    }
