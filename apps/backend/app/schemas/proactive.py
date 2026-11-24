"""Proactive calls: occasions where the agent should phone a client first, each with a call brief."""

from typing import Literal

from app.schemas.base import Input, Schema

OpportunityType = Literal["order_issue"]  # the only reason to phone: a client's open order cannot be delivered as planned
IssueKind = Literal["stock", "delivery"]


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
    status: Literal["ringing", "answered", "declined", "missed"]
    created_at: str
    ended_at: str | None = None
    outcome: str | None = None  # what was decided on the call (the line the agent wrote in the client's history)


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


class AutodialInput(Input):
    enabled: bool
