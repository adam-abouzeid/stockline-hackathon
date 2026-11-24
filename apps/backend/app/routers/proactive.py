"""/api/proactive: the occasions where the voice agent should phone a client first, and the brief for each call."""

from fastapi import APIRouter, Query

from app.dependencies import CtxDep

from app.schemas.proactive import (
    AutodialInput,
    AutodialState,
    CallStatusInput,
    DispatchResult,
    OutcomeInput,
    OutcomeResult,
    ProactiveBrief,
    ProactiveCall,
    ProactiveOpportunity,
)
from app.services import proactive

router = APIRouter(prefix="/api/proactive", tags=["proactive"])


@router.get("/opportunities", response_model=list[ProactiveOpportunity])
async def list_opportunities():
    """Most urgent first. Kinds: shortage_order (a client's open order contains a product in shortage), shortage_heads_up,
    overdue (a regular client late against its own rhythm; seasonal businesses that are closed are left out) and seasonal."""
    return proactive.opportunities()


@router.get("/opportunities/{opportunity_id}", response_model=ProactiveBrief)
async def get_opportunity(opportunity_id: str):
    """One opportunity with the full call brief the agent is given: the client, why it calls, the only facts it may quote,
    the objective, how to proceed and what it must not promise."""
    return proactive.opportunity_brief(opportunity_id)


# ───────── the agent places the calls itself ─────────


@router.get("/autodial", response_model=AutodialState)
async def autodial_state():
    """Whether the agent looks for someone to call by itself, and the rules it follows."""
    return proactive.autodial_state()


@router.post("/autodial", response_model=AutodialState)
async def set_autodial(body: AutodialInput):
    """Pause or resume the agent's own initiative."""
    return proactive.set_autodial(body.enabled)


@router.post("/dispatch", response_model=DispatchResult)
async def dispatch(force: bool = Query(True, description="Skip the pause between two calls (a manual cycle)")):
    """Run one decision cycle now (the loop does it on its own). It never rings two calls at once, never calls a client twice in a day
    and never goes below the minimum urgency."""
    call = proactive.dispatch_once(force=force)
    return {"status": "ringing" if call else "nothing", "call": call}


@router.get("/calls", response_model=list[ProactiveCall])
async def list_calls(status: str | None = Query(None, description="ringing | answered | declined | missed | cancelled")):
    """The journal of the calls the agent placed, newest first."""
    return proactive.calls(status or None)


@router.post("/calls/{call_id}/answer", response_model=ProactiveCall)
async def answer_call(call_id: str):
    """The client picks up: the agent then opens the conversation (opportunityId -> the Voix page, outbound mode)."""
    return proactive.answer_call(call_id, "answered")


@router.post("/calls/{call_id}/decline", response_model=ProactiveCall)
async def decline_call(call_id: str):
    return proactive.answer_call(call_id, "declined")


@router.get("/calls/{call_id}", response_model=ProactiveCall)
async def get_call(call_id: str):
    return proactive.get_call(call_id)


@router.post("/calls/{call_id}/status", response_model=ProactiveCall)
async def set_call_status(call_id: str, body: CallStatusInput):
    """The phone bridge reports what the phone network said: no answer (missed), busy / declined, failed, or hung up (completed)."""
    return proactive.set_call_status(call_id, body.status, body.note)


@router.post("/opportunities/{opportunity_id}/outcome", response_model=OutcomeResult)
async def record_outcome(opportunity_id: str, body: OutcomeInput, ctx: CtxDep):
    """The agent records what was decided on the call (tool record_call_outcome): stored on the call and written as one
    « Appel proactif : … » line in the client's history. Works even when the order no longer has a problem (it was just fixed)."""
    return proactive.record_outcome(ctx, opportunity_id, body.decision, body.summary, body.call_id)


@router.delete("/calls", status_code=204)
async def clear_calls():
    """Empty the journal (demo / tests)."""
    proactive.clear_calls()
