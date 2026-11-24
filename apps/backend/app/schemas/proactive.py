"""Proactive calls: occasions where the agent should phone a client first, each with a call brief."""

from typing import Literal

from app.schemas.base import Input, Schema

OpportunityType = Literal["order_issue"]  # the only reason to phone: a client's open order cannot be delivered as planned
IssueKind = Literal["stock", "delivery"]
CallStatus = Literal["ringing", "answered", "declined", "missed", "cancelled"]


class ProactiveOpportunity(Schema):
    id: str  # "<type>~<clientId>~<key>": stable, so a call can be launched from it
    type: OpportunityType
    priority: int  # higher = call first
    client_id: str
    client_name: str
    contact_name: str | None = None
    title: str  # one line for the list
    reason: str  # why the agent calls, in a sentence
    facts: list[str]  # the verified facts the agent may quote
    objective: str  # what the agent does on the call
    kinds: list[IssueKind]  # stock = a product is short, delivery = no route serves the zone that day
    deadline: str  # e.g. "Livraison aujourd'hui : à prévenir avant le départ du camion"
    product_ids: list[str] = []
    order_id: str | None = None
    order_value: float = 0  # the order's total excl. VAT: same urgency, the bigger order is called first


class ProactiveBrief(ProactiveOpportunity):
    """The opportunity plus the full instructions given to the agent for the call (its system-prompt section)."""

    brief: str


class ProactiveCall(Schema):
    """A call the agent decided to place by itself. It rings on the client's side until someone picks up, declines, or it is missed."""

    id: str
    opportunity_id: str
    client_id: str
    client_name: str
    contact_name: str | None = None
    type: OpportunityType
    title: str
    reason: str
    deadline: str
    priority: int
    status: CallStatus
    channel: Literal["simulator", "phone"] = "simulator"  # phone = a real call to the demo number through Twilio (PHONE_MODE=twilio)
    order_id: str | None = None
    created_at: str
    ended_at: str | None = None  # when it stopped ringing (picked up, declined, missed or cancelled)
    hung_up_at: str | None = None  # phone: when an answered call hung up
    note: str | None = None  # why it did not ring / was cancelled
    outcome: str | None = None  # what was decided on the call (record_call_outcome)


class DispatchResult(Schema):
    status: Literal["ringing", "nothing"]  # nothing: a call is already ringing, the pause runs, or no opportunity is left to call
    call: ProactiveCall | None = None


class AutodialState(Schema):
    enabled: bool
    interval_seconds: int  # how often the agent looks for someone to call
    ring_seconds: int  # a call that nobody picks up within this time is missed
    cooldown_seconds: int  # pause after a call before the next one
    min_priority: int  # it never calls below this urgency
    ringing: int
    phone_mode: Literal["simulator", "twilio"] = "simulator"  # where calls ring: the web simulator or the real demo phone


class CallStatusInput(Input):
    """Reported by the phone bridge. completed = an answered call hung up."""

    status: Literal["declined", "missed", "cancelled", "completed"]
    note: str | None = None


class OutcomeInput(Input):
    decision: str  # what was decided, in one short sentence (« livraison décalée au jeudi 24, jus ramené à 67 »)
    summary: str | None = None
    call_id: str | None = None  # optional: the call (the phone bridge knows it; the browser simulator only knows the opportunity)


class OutcomeResult(Schema):
    call: ProactiveCall | None = None
    event_id: str
    client_id: str
    decision: str


class AutodialInput(Input):
    enabled: bool
