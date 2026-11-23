"""Write tools: build an order step by step (draft → lines → confirm). Business rules live in the ERP API."""

from pydantic import Field

from .approval import confirmation_gate
from .erp import ErpError, enc, pick
from .history import without_none
from .order_state import resolve_order_id, state_of
from .registry import ToolArgs, ToolContext, tool


class OrderLine(ToolArgs):
    product_id: str
    qty: float = Field(description="Quantité dans l'unité du produit (kg, pièce, caisse…)")
    note: str | None = Field(None, description="ex. « livrer avant 7 h », « bien mûr »")
    substitute_for: str | None = Field(None, description="productId remplacé, si c'est une substitution")

    def to_erp(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


def summarize_order(o: dict) -> dict:
    """What the model gets back after any order operation: short, with line ids for later edits."""
    return {
        **pick(o, "id", "number", "status"),
        "client": (o.get("client") or {}).get("name"),
        **pick(o, "deliveryDate", "totalHt"),
        "lines": [
            {
                "lineId": line["id"],
                **pick(line, "productId", "productName", "qty", "unit", "unitPrice", "available"),
                **({"note": line["note"]} if line.get("note") else {}),
            }
            for line in o["lines"]
        ],
        "warnings": o.get("warnings") or [],
    }


@tool
async def create_draft_order(
    ctx: ToolContext,
    client_id: str,
    delivery_date: str | None = Field(None, description="YYYY-MM-DD, optionnel"),
    lines: list[OrderLine] | None = None,
    note: str | None = None,
    additional_order: bool = Field(False, description="true SEULEMENT si le client demande explicitement une 2e commande distincte après avoir confirmé la 1re"),
) -> dict:
    """
    Crée une pré-commande (brouillon) pour un client, avec ou sans lignes. Prix résolus par l'ERP (prix client > catalogue).
    UNE SEULE commande par appel : si une commande est déjà en cours, modifie-la (update_order_line, add_order_line…), n'en crée pas une autre.
    Create a draft order. Delivery date defaults to the client's next delivery day.
    """
    state = state_of(ctx)
    if state.active and (state.status == "draft" or not additional_order):
        raise ValueError(
            f"Une commande est déjà en cours dans cet appel ({state.order_id}, {state.status}) : modifie-la avec update_order_line / "
            "add_order_line / remove_order_line / update_order, ou annule-la avec cancel_order. Ne crée pas de doublon."
        )
    state.modified_this_turn = True
    body = {
        "clientId": client_id,
        "deliveryDate": delivery_date,
        "lines": [line.to_erp() for line in lines] if lines is not None else None,
        "note": note,
        "source": "voice_agent" if ctx.actor == "voice_agent" else "web",
    }
    summary = summarize_order(await ctx.erp.post("/api/orders", without_none(body)))
    state.track(summary)
    return summary


@tool
async def add_order_line(
    ctx: ToolContext,
    order_id: str | None = None,
    product_id: str = Field(description="ex. prd_0042"),
    qty: float = Field(description="Quantité dans l'unité du produit (kg, pièce, caisse…)"),
    note: str | None = Field(None, description="ex. « livrer avant 7 h », « bien mûr »"),
    substitute_for: str | None = Field(None, description="productId remplacé, si c'est une substitution"),
) -> dict:
    """
    Ajoute une NOUVELLE ligne (un produit pas encore dans la commande) à la commande en cours.
    Si le produit y est déjà, change sa quantité avec update_order_line. Add a line for a product not yet in the order.
    """
    state = state_of(ctx)
    state.modified_this_turn = True  # set at the START: a confirm in the same step must see it
    oid = resolve_order_id(ctx, order_id)
    current = await ctx.erp.get(f"/api/orders/{enc(oid)}")
    existing = next((l for l in current["lines"] if l["productId"] == product_id), None)
    if existing:
        raise ValueError(
            f"Ce produit est déjà dans la commande (ligne {existing['id']}, quantité {existing['qty']}) : "
            "utilise update_order_line pour changer la quantité, pas une 2e ligne."
        )
    line = OrderLine(product_id=product_id, qty=qty, note=note, substitute_for=substitute_for)
    summary = summarize_order(await ctx.erp.post(f"/api/orders/{enc(oid)}/lines", line.to_erp()))
    state.track(summary)
    return summary


@tool
async def confirm_order(ctx: ToolContext, order_id: str | None = None) -> dict:
    """
    Confirme la commande en cours : réserve le stock et l'affecte à une tournée. Renvoie des alertes (encours, stock…).
    Refusé tant que le récapitulatif n'a pas été lu au client ET qu'il n'a pas répondu par un accord explicite (oui, ok, vas-y…).
    Refusé aussi pour un client bloqué ou un dépassement de crédit : ces cas relèvent de la comptabilité (Martine), jamais de toi.
    Only after the caller explicitly agreed to the recap.
    """
    state = state_of(ctx)
    oid = resolve_order_id(ctx, order_id)
    if ctx.mode == "voice":  # a salesperson's chat / voice command is itself the instruction; a customer call needs the recap
        verdict = confirmation_gate(ctx.messages, state.modified_this_turn)
        if not verdict.approved:
            return {
                "confirmed": False,
                "reason": "customer_approval_missing",
                "detail": verdict.reason,
                "instruction": "Ne confirme pas. Lis au client le récapitulatif (produits, quantités, prix HT, total, date de livraison) "
                "puis attends son « oui » explicite dans sa réponse suivante.",
            }
    try:
        summary = summarize_order(await ctx.erp.post(f"/api/orders/{enc(oid)}/confirm"))
    except ErpError as e:
        if e.code in ("client_blocked", "credit_approval_required"):
            return await human_approval_needed(ctx, oid, e)
        raise
    state.track(summary)
    return {"confirmed": True, **summary}


async def human_approval_needed(ctx: ToolContext, order_id: str, error: ErpError) -> dict:
    """The ERP refused to let the AI confirm (blocked client / credit limit): leave the order a draft and leave a trace for
    the accounting team (Martine) in the client's history. The AI never overrides this."""
    blocked = error.code == "client_blocked"
    logged = False
    try:
        order = await ctx.erp.get(f"/api/orders/{enc(order_id)}")
        await ctx.erp.post(
            f"/api/clients/{enc(order['clientId'])}/events",
            {
                "type": "special_request",
                "title": "Commande à valider par la comptabilité" + (" (compte bloqué)" if blocked else " (plafond de crédit)"),
                "description": f"Commande {order['number']} prise par l'agent vocal, laissée en brouillon : {error}. À traiter par Martine.",
                "orderId": order_id,
                "severity": "medium",
            },
        )
        logged = True
    except ErpError:
        pass
    return {
        "confirmed": False,
        "reason": error.code,
        "orderStatus": "draft",
        "humanApprovalRequired": True,
        "traceLoggedForAccounting": logged,
        "instruction": "Dis simplement que la comptabilité (Martine) doit valider cette commande et qu'on rappelle le client. "
        "Ne promets AUCUNE livraison, n'évoque pas le détail des impayés, ne propose pas de contourner.",
    }


@tool
async def get_order(ctx: ToolContext, order_id: str | None = None) -> dict:
    """Détail de la commande en cours (ou d'une commande donnée) : lignes, statut, total, alertes. Order detail."""
    summary = summarize_order(await ctx.erp.get(f"/api/orders/{enc(resolve_order_id(ctx, order_id))}"))
    state_of(ctx).track(summary)
    return summary
