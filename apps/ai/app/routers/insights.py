"""POST /insights/reservations/extract: the LLM reads the holiday reservation notes (services/insights.py) and the ERP stores
the signals. Then GET /api/predictions/holiday-reservations shows the Carnet de Noël with them, and
GET /api/predictions/holiday-reservations/backtest?season=2025&signals=true|false measures whether they help."""

from fastapi import APIRouter, Query

from app.services.insights import extract_reservations

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("/reservations/extract")
async def extract(season: int | None = Query(None, description="Default: this season; a past season (e.g. 2025) to backtest with signals")):
    """Read every reservation note of the season with the LLM (rules without one) and store one signal per note in the ERP."""
    return await extract_reservations(season)
