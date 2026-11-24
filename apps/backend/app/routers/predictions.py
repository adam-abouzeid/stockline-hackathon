"""/api/predictions: the season radar (coming demand peaks) and stock to rescue (lots that will not sell in time)."""

from fastapi import APIRouter, Query

from app.dependencies import CtxDep, iso_date_query
from app.schemas.domain import ClientEvent
from app.schemas.predictions import OfferInput, RadarBacktest, SeasonRadar, StockRescue
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
