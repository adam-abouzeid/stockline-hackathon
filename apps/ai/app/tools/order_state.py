"""
The active order of a conversation.

One call = at most one order being built. The state is NOT stored anywhere: it is rebuilt from the conversation
history at the start of each agent turn (`derive_state`), because the history already carries every order tool result
(the same list is kept by the voice session, the web chat and the CLI). The tools then update it during the turn so
that two tool calls of the same step see each other.

    derive_state(messages) → OrderState(order_id, status)
      create_draft_order / add_order_line / update_* / remove_* / get_order / confirm_order → that order is active
      cancel_order → no active order
"""

import json
from dataclasses import dataclass

# Tools whose result is an order summary (see tools/orders.py summarize_order): `{id, number, status, lines, …}`.
ORDER_TOOLS = {
    "create_draft_order",
    "reorder_last_order",  # V2: creates the draft from the last order
    "add_order_line",
    "update_order_line",
    "remove_order_line",
    "update_order",
    "confirm_order",
    "cancel_order",
    "get_order",
}
# Tools that change what the customer would be agreeing to (lines, quantities, date): a recap becomes stale after them.
MODIFYING_TOOLS = {"create_draft_order", "reorder_last_order", "add_order_line", "update_order_line", "remove_order_line", "update_order"}


@dataclass
class OrderState:
    order_id: str | None = None
    status: str | None = None  # draft | confirmed (cancelled / finished → no active order)
    modified_this_turn: bool = False  # a modifying tool ran during the current turn: the last recap is stale

    @property
    def active(self) -> bool:
        return self.order_id is not None

    def track(self, order: dict | None) -> None:
        """Record the order summary returned by a tool (None → nothing active)."""
        if not order or not order.get("id"):
            return
        if order.get("status") in ("draft", "confirmed"):
            self.order_id, self.status = order["id"], order["status"]
        else:  # cancelled, prepared, delivered…: not ours to edit any more
            self.order_id = self.status = None


def state_of(ctx) -> OrderState:
    """The OrderState of a ToolContext (created on the fly for a bare context, e.g. in a unit test)."""
    if ctx.state is None:
        ctx.state = derive_state(ctx.messages)
    return ctx.state


def resolve_order_id(ctx, order_id: str | None) -> str:
    """Which order does this tool call act on? The active order of the conversation, by default.
    Naming ANOTHER order while one is active is refused: it is how a wrong order gets modified."""
    state = state_of(ctx)
    if order_id and state.active and order_id != state.order_id:
        raise ValueError(
            f"La commande active de cet appel est {state.order_id} et non {order_id} : ne modifie que la commande active "
            "(ou annule-la d'abord)."
        )
    resolved = order_id or state.order_id
    if not resolved:
        raise ValueError("Aucune commande en cours dans cet appel : crée d'abord un brouillon avec create_draft_order.")
    return resolved


def derive_state(messages: list | None) -> OrderState:
    state = OrderState()
    for m in messages or []:
        if m.role != "tool" or m.name not in ORDER_TOOLS:
            continue
        try:
            result = json.loads(m.content)
        except (TypeError, ValueError):
            continue
        if isinstance(result, dict) and "error" not in result and result.get("id"):
            state.track(result)
    return state
