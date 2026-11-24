"""Predictions: the season radar (coming demand peaks) and stock to rescue (lots that will not sell before their ERP end date)."""

from app.schemas.base import Input, Schema

# ───────── Season radar ─────────


class SeasonPeak(Schema):
    """A product whose demand usually at least doubles in an upcoming week, with what it means for buying."""

    product_id: str
    product_name: str
    unit: str
    supplier_id: str | None = None
    supplier_name: str | None = None
    lead_time_days: int | None = None
    ramp_week_start: str  # Monday of the first upcoming week at or above the threshold
    peak_week_start: str  # Monday of the strongest week in the window that follows
    peak_index: float  # demand of that week / a usual week (x2.0 = double)
    usual_week_qty: float  # a usual week, from the last 52 complete weeks
    expected_peak_week_qty: float  # usual_week_qty x index of the ramp week
    days_until_ramp: int
    order_by: str  # ramp week start minus the supplier lead time
    days_to_order_by: int  # negative = already late
    late: bool
    available: float
    incoming: float  # confirmed purchase orders only (sent / partially received), never drafts
    suggested_qty: float
    estimated_cost: float | None = None
    years_of_history: int
    reason: str


class SupplierBasket(Schema):
    """What the suggestions add up to per supplier, against the supplier's minimum order."""

    supplier_id: str
    supplier_name: str
    lead_time_days: int | None = None
    min_order_amount: float | None = None
    product_count: int
    total_cost: float
    meets_minimum: bool
    order_by: str


class SeasonRadar(Schema):
    as_of: str
    horizon_weeks: int
    threshold: float
    peaks: list[SeasonPeak]
    suppliers: list[SupplierBasket]


class RadarBacktestItem(Schema):
    product_id: str
    product_name: str
    ramp_week_start: str
    predicted_index: float
    window_ratio: float  # best real demand (3 weeks smoothed) in the announced window / a usual week
    exact_week_ratio: float  # real demand of the announced ramp week alone / a usual week
    hit: bool  # window_ratio reached 1.5
    exact_week_hit: bool


class RadarBacktest(Schema):
    """The radar as it would have looked on `as_of` (only data before that day), judged on what really happened
    (only weeks that are over). `precision` = share of announced peaks whose window reached 1.5x a usual week;
    `recall` = share of real peaks (3-week demand at 2x or more) that had been announced."""

    as_of: str
    horizon_weeks: int
    announced: int  # announced peaks whose ramp week is over, so they can be judged
    hits: int
    exact_week_hits: int  # the stricter count: only the announced ramp week counts
    precision: float | None = None
    real_peaks: int
    found: int
    recall: float | None = None
    items: list[RadarBacktestItem]


# ───────── Stock to rescue ─────────


class RescueClient(Schema):
    client_id: str
    client_name: str
    orders_last_90d: int
    suggested_qty: float
    unit_price: float
    offer_price: float
    already_proposed: bool


class RescueItem(Schema):
    product_id: str
    product_name: str
    unit: str
    at_risk_units: float  # units the sales rate will not clear before the lots expire
    at_risk_value: float  # at cost
    earliest_expiry: str  # the soonest ERP end date (`expiresAt`) among the lots at risk: an ERP date, not a guarantee of spoilage
    days_to_expiry: int
    weekly_sales: float
    list_price: float
    cost: float
    suggested_discount_pct: int  # never below cost; 0 when the margin is too thin
    covered_units: float  # what the suggested offers add up to (can be far below at_risk_units)
    clients: list[RescueClient]
    reason: str


class StockRescue(Schema):
    as_of: str
    horizon_days: int
    items: list[RescueItem]


class OfferInput(Input):
    """A seller marks an offer as proposed to a client: it is written in the client's history, nothing else changes."""

    client_id: str
    product_id: str
    qty: float
    discount_pct: float
    offer_price: float
