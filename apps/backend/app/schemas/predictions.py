"""Predictions: the season radar (coming demand peaks) and stock to rescue (lots that will not sell before their ERP end date)."""

from typing import Literal

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
    asked_for_deal: str | None = None  # AI signal: this client asked for a deal in writing (why) → offered first


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


# ───────── AI signals and the Carnet de Noël (holiday reservations) ─────────

Intent = Literal["firm", "tentative", "cancelled", "unclear"]


class SignalIn(Input):
    """What an LLM read in ONE client note. It never gives a quantity or a price: only how to read the note."""

    event_id: str
    intent: Intent  # firm = « réservez », tentative = « peut-être / si… », cancelled = « finalement non », unclear = nothing to read
    multiplier: float = 1  # « mettez le double » → 2 (0–5)
    dropped_product_ids: list[str] = []  # products of the note the client took back
    asked_for_deal: bool = False  # « vous me faites un geste ? », « plus cher que le voisin »
    condition: str | None = None  # « si le beau temps se maintient »
    summary: str | None = None  # one short sentence, French


class SignalsInput(Input):
    signals: list[SignalIn]
    model: str | None = None  # which model read them


class Signal(Schema):
    event_id: str
    client_id: str
    intent: Intent
    multiplier: float
    dropped_product_ids: list[str]
    asked_for_deal: bool
    condition: str | None = None
    summary: str
    model: str
    at: str


class SignalsSaved(Schema):
    saved: int
    signals: list[Signal]


class ReservationNote(Schema):
    event_id: str
    client_id: str
    client_name: str
    at: str
    text: str
    quote: str | None = None  # what the client said, as written
    intent: Intent
    multiplier: float
    asked_for_deal: bool
    condition: str | None = None
    ai_summary: str | None = None
    analyzed: bool  # an LLM has read this note


class PastYear(Schema):
    year: int
    qty: float


class ReservationLine(Schema):
    event_id: str
    client_id: str
    client_name: str
    product_id: str
    product_name: str
    unit: str
    past_years: list[PastYear]  # the client's own deliveries of this product, 15–31 December
    baseline_qty: int | None = None  # mean of those years; None = no history (ask the client)
    multiplier: float
    qty: float | None = None  # baseline × multiplier (0 if cancelled)
    unit_price: float  # the client's price (negotiated, group and volume rules)
    value: float | None = None
    intent: Intent
    expected_value: float  # value, 0 if cancelled (measured: reserved lines are bought at ~1.0x their estimate)
    ordered: bool  # an order already covers it


class ReservationProduct(Schema):
    product_id: str
    product_name: str
    unit: str
    reserved_units: float
    available: float
    incoming: float
    shortfall: float  # reserved − (available + incoming), never negative
    supplier_name: str | None = None
    order_by: str | None = None  # to have it by 23 December, given the supplier's lead time
    late: bool


class Conversion(Schema):
    rate: float | None = None
    converted: int
    total: int
    seasons: list[int]


class ReservationTotals(Schema):
    notes: int
    lines: int
    lines_without_history: int
    reserved_value: float
    expected_value: float
    ordered_lines: int
    analyzed_notes: int
    short_products: int


class HolidayReservations(Schema):
    as_of: str
    season: int
    notes: list[ReservationNote]
    lines: list[ReservationLine]
    products: list[ReservationProduct]
    conversion: Conversion
    totals: ReservationTotals


class RescueAcceptInput(Input):
    """The client accepted a rescue offer on a call: add it to its draft order at the rescue price (computed by the ERP)."""

    client_id: str
    product_id: str
    order_id: str
    qty: float | None = None  # default: the suggested quantity
