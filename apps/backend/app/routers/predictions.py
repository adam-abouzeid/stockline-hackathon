"""/api/predictions: the season radar (coming demand peaks) and stock to rescue (lots that will not sell in time)."""

from fastapi import APIRouter, Query

from app.dependencies import CtxDep, iso_date_query
from app.schemas.domain import ClientEvent
from app.schemas.views import OrderDetail
from app.schemas.predictions import (
    HolidayReservations,
    OfferInput,
    RadarBacktest,
    RescueAcceptInput,
    SeasonRadar,
    Signal,
    SignalsInput,
    SignalsSaved,
    StockRescue,
)
from app.services import predictions

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/season-radar", response_model=SeasonRadar)
async def season_radar(
    horizon_weeks: int = Query(10, alias="horizonWeeks", ge=2, le=26, description="How many coming weeks to look at"),
    threshold: float = Query(2.0, ge=1.2, le=6, description="Demand / a usual week that counts as a peak"),
    as_of: str | None = Query(None, alias="asOf", description="Business date to simulate (backtests); default: today"),
):
    """Products whose demand usually reaches `threshold` x a usual week in a coming week, with the supplier's
    lead time, the date to order by, a suggested quantity and what each supplier's suggestions add up to.
    Draft purchase orders never count as incoming stock. Most urgent first."""
    return predictions.season_radar(iso_date_query(as_of), horizon_weeks, threshold)


@router.get("/season-radar/backtest", response_model=RadarBacktest)
async def season_radar_backtest(
    as_of: str = Query(..., alias="asOf", description="A past business date: the radar only sees data before it"),
    horizon_weeks: int = Query(10, alias="horizonWeeks", ge=2, le=26),
    threshold: float = Query(2.0, ge=1.2, le=6),
):
    """How the radar of `asOf` compares with what really happened: precision (announced peaks that happened)
    and recall (real peaks that were announced)."""
    return predictions.radar_backtest(iso_date_query(as_of), horizon_weeks, threshold)


@router.get("/stock-rescue", response_model=StockRescue)
async def stock_rescue(horizon_days: int = Query(120, alias="horizonDays", ge=7, le=180)):
    """Lots that the expected sales will not clear before their ERP end date (first-expired-first-out), the clients who buy
    that product and a discount that never goes below cost. Soonest ERP end date first."""
    return predictions.stock_rescue(horizon_days)


@router.post("/stock-rescue/offers", response_model=ClientEvent, status_code=201)
async def propose_offer(body: OfferInput, ctx: CtxDep):
    """A seller marks an offer as proposed. Only writes a line in the client's history: no price, order or stock changes.
    Refused below cost."""
    return predictions.propose_offer(ctx, body.data())


@router.post("/stock-rescue/accept", response_model=OrderDetail, status_code=201)
async def accept_rescue_offer(body: RescueAcceptInput, ctx: CtxDep):
    """The client accepted a rescue offer on a call (agent tool add_rescue_offer): the lot is added to its DRAFT order at the
    rescue price, computed here (never sent by the caller) and refused below cost. The order still needs the client's explicit yes."""
    return predictions.accept_rescue_offer(ctx, body.data())


@router.get("/holiday-reservations", response_model=HolidayReservations)
async def holiday_reservations(client_id: str | None = Query(None, alias="clientId")):
    """Carnet de Noël: the « Fêtes <year> : réservation de volumes » notes of this season, each product estimated from the client's
    own late-December purchases of past years, the AI signals read in the notes (×2, cancelled, asked for a deal), the historical
    conversion of such notes into orders, and the products whose reservations exceed stock + incoming."""
    return predictions.holiday_reservations(client_id)


@router.get("/holiday-reservations/backtest")
async def holiday_reservations_backtest(season: int = Query(..., description="A past season, e.g. 2025"), signals: bool = Query(True, description="Use the AI signals read in the notes")):
    """The Carnet de Noël estimate of a past season (only history before it), compared with what those clients really bought
    15–31 December: wape (weighted % error on units), share of lines within ±30 %, expected value vs real value."""
    return predictions.reservations_backtest(season, signals)


@router.get("/holiday-reservations/notes")
async def holiday_reservation_notes(season: int | None = Query(None)):
    """The raw reservation notes of a season (default: this one), for the AI service to read: [{eventId, clientId, clientName, text, productIds, productNames}]."""
    return predictions.reservation_notes(season)


@router.get("/signals", response_model=list[Signal])
async def list_signals():
    """What an LLM read in the client notes (one per note)."""
    return predictions.list_signals()


@router.put("/signals", response_model=SignalsSaved)
async def save_signals(body: SignalsInput):
    """Store what an LLM read in client notes (AI service, POST /insights/reservations/extract). Validated: the note exists,
    multiplier 0–5. These signals never carry a quantity or a price: the ERP does the sums."""
    return predictions.save_signals(body.data())
