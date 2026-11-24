"""
Predictions for the sellers: two interpretable, training-free views built on the sales history.

* Season radar: which products usually sell at least double in an upcoming week (the same weeks come back every
  year), and by when to order given the supplier's lead time. A forecast is plain arithmetic on the weekly sales:
  the average of the same week across years, smoothed over 3 weeks, divided by a usual week.
* Stock to rescue: lots that the expected sales will not clear before their ERP end date (`expiresAt`: reception date + the product's shelf life, first-expired-first-out),
  with the clients who buy that product and a discount that never goes below cost. Offers are drafts: a seller
  marks one as proposed, which only writes a line in the client's history.

* Carnet de Noël (holiday reservations): the « Fêtes <year> : réservation de volumes » notes clients wrote, which nobody
  entered as orders. The arithmetic estimates each line from the client's OWN late-December purchases of past years and
  the historical share of such notes that became orders; an LLM (AI service, POST /insights/reservations/extract) only
  READS the notes and stores signals here (`prediction_signals`): a change of mind (« finalement, mettez le double ! » → ×2),
  a cancellation, a condition, a client asking for a deal. The LLM never computes a quantity or a price.
* AI signals also feed the pricing side: in the stock to rescue, clients who asked for a deal in writing come first.

Both take the business date from `today()` (never the wall clock). The radar can also be asked "as of" an earlier
day, using only the data before it, to be judged on what really happened (`radar_backtest`).
"""

from __future__ import annotations

import datetime as dt
import math
import re
import statistics
from collections import defaultdict

from app import crud
from app.core.activity import Ctx, today
from app.core.db import Doc, per_data_version, transactional
from app.core.errors import bad_request
from app.core.utils import fr_day, round2, round3
from app.services import pricing
from app.services.client_events import create_client_event
from app.services.clients import is_sale
from app.services.purchasing import purchase_price
from app.services.stock import line_qty, stock_levels

MIN_UNITS = 300  # a product needs this much history to have a seasonal profile
MIN_WEEKS = 60  # and more than a year of it
USUAL_WEEKS = 52  # a "usual week" = the mean of the last 52 complete weeks
PEAK_WINDOW = 4  # weeks after the ramp in which the strongest week is looked for
HIT_RATIO = 1.5  # backtest: an announced peak counts as right when real demand (3 weeks smoothed) reached this x a usual week in its window
REAL_PEAK_RATIO = 2.0  # backtest: a "real peak" is a week at this x a usual week
BUYER_DAYS = 90
SALES_WEEKS = 8  # the current sales rate of a product = the mean of its last 8 complete weeks
EXPIRY_UNIT_MIN = 1  # an at-risk lot counts from this many units


# ───────── Weekly demand ─────────


def _monday(iso: str | dt.date) -> dt.date:
    d = iso if isinstance(iso, dt.date) else dt.date.fromisoformat(iso[:10])
    return d - dt.timedelta(days=d.weekday())


@per_data_version
def _weekly_demand() -> dict[str, dict[dt.date, float]]:
    """Units sold per product and week (Monday), by delivery date, from every sale order. Shared: never mutate."""
    out: dict[str, dict[dt.date, float]] = defaultdict(lambda: defaultdict(float))
    for o in crud.orders.all():
        if not is_sale(o):
            continue
        week = _monday(o["deliveryDate"])
        for line in o["lines"]:
            out[line["productId"]][week] += line_qty(line)
    return out


def _series(weeks: dict[dt.date, float], current: dt.date) -> dict[dt.date, float] | None:
    """The complete weeks before `current`, zeros included, or None when the history is too short for a seasonal profile."""
    hist = {w: q for w, q in weeks.items() if w < current}
    if not hist or sum(hist.values()) < MIN_UNITS:
        return None
    first = min(hist)
    if (current - first).days // 7 < MIN_WEEKS:
        return None
    series, w = {}, first
    while w < current:
        series[w] = hist.get(w, 0.0)
        w += dt.timedelta(days=7)
    return series


def _week_number(d: dt.date) -> int:
    return min(d.isocalendar()[1], 52)


def _profile(series: dict[dt.date, float], smooth: bool = True):
    """(usual week of the last 52 weeks, index function by ISO week number, years of history).
    `smooth` averages each week with its two neighbours: right to spot a season, but it spreads a one-week spike (the Beaujolais
    day) onto the weeks around it, so the stock forecast turns it off."""
    by_week: dict[int, list[float]] = defaultdict(list)
    for w, q in series.items():
        by_week[_week_number(w)].append(q)
    avg = {k: sum(v) / len(v) for k, v in by_week.items()}
    overall = sum(series.values()) / len(series)
    recent = list(series.values())[-USUAL_WEEKS:]
    usual = sum(recent) / len(recent)

    def index(week: dt.date) -> float:
        k = _week_number(week)
        vals = [avg[((k - 1 + d) % 52) + 1] for d in ((-1, 0, 1) if smooth else (0,)) if ((k - 1 + d) % 52) + 1 in avg]
        return (sum(vals) / len(vals)) / overall if overall > 0 and vals else 0.0

    years = max(1, round(len(series) / 52))  # years of history = weeks of history / 52 (not calendar-year labels)
    return usual, index, years


# ───────── Season radar ─────────


def _peaks(as_of: str, horizon_weeks: int, threshold: float) -> list[Doc]:
    """Products whose demand reaches `threshold` x a usual week in a coming week, using only weeks before `as_of`."""
    current = _monday(as_of)
    out = []
    for pid, weeks in _weekly_demand().items():
        series = _series(weeks, current)
        if series is None:
            continue
        usual, index, years = _profile(series)
        if usual <= 0:
            continue
        upcoming = [current + dt.timedelta(weeks=k) for k in range(1, horizon_weeks + 1)]
        if index(current) >= threshold:
            continue  # already in the peak: too late to announce it
        ramp = next((w for w in upcoming if index(w) >= threshold), None)
        if ramp is None:
            continue
        window = [w for w in upcoming if ramp <= w <= ramp + dt.timedelta(weeks=PEAK_WINDOW)]
        peak = max(window, key=index)
        out.append({"productId": pid, "ramp": ramp, "peak": peak, "peakIndex": index(peak), "rampIndex": index(ramp),
                    "usual": usual, "years": years})
    return out


def season_radar(as_of: str | None = None, horizon_weeks: int = 10, threshold: float = 2.0) -> Doc:
    t = as_of or today()
    levels = stock_levels()
    peaks = []
    for p in _peaks(t, horizon_weeks, threshold):
        product = crud.products.get(p["productId"])
        if not product or not product["active"]:
            continue
        supplier = crud.suppliers.get(product.get("mainSupplierId") or "")
        lead = supplier.get("leadTimeDays") if supplier else None
        ramp: dt.date = p["ramp"]
        days_until = (ramp - dt.date.fromisoformat(t)).days
        order_by = ramp - dt.timedelta(days=lead or 0)
        days_to_order_by = (order_by - dt.date.fromisoformat(t)).days
        level = levels.get(product["id"], {"available": 0, "incoming": 0})
        weeks_until = days_until / 7
        projected = level["available"] + level["incoming"] - p["usual"] * weeks_until  # normal sales until the ramp
        expected = p["usual"] * p["rampIndex"]
        suggested = max(0, math.ceil(expected - max(0, projected)))
        cost = round2(suggested * purchase_price(supplier["id"], product["id"])) if supplier and suggested else None
        reason = (
            f"La demande de ce produit double habituellement à partir de la semaine du {fr_day(ramp.isoformat()).removeprefix('le ')} "
            f"(×{p['rampIndex']:.1f}, {p['years']} ans d'historique)."
        )
        if supplier:
            reason += f" {supplier['name']} livre en {lead} j : commander avant {fr_day(order_by.isoformat())}"
            reason += " (déjà en retard : commande urgente)." if days_to_order_by < 0 else "."
        peaks.append({
            "productId": product["id"], "productName": product["name"], "unit": product["unit"],
            "supplierId": supplier["id"] if supplier else None, "supplierName": supplier["name"] if supplier else None,
            "leadTimeDays": lead, "rampWeekStart": ramp.isoformat(), "peakWeekStart": p["peak"].isoformat(),
            "peakIndex": round(p["peakIndex"], 1), "usualWeekQty": round3(p["usual"]),
            "expectedPeakWeekQty": round3(expected), "daysUntilRamp": days_until, "orderBy": order_by.isoformat(),
            "daysToOrderBy": days_to_order_by, "late": days_to_order_by < 0, "available": level["available"],
            "incoming": level["incoming"], "suggestedQty": suggested, "estimatedCost": cost,
            "yearsOfHistory": p["years"], "reason": reason,
        })  # fmt: skip
    peaks.sort(key=lambda x: (x["daysToOrderBy"], -x["peakIndex"]))
    return {"asOf": t, "horizonWeeks": horizon_weeks, "threshold": threshold, "peaks": peaks, "suppliers": _baskets(peaks)}


def _baskets(peaks: list[Doc]) -> list[Doc]:
    by: dict[str, list[Doc]] = defaultdict(list)
    for p in peaks:
        if p["supplierId"] and p["suggestedQty"]:
            by[p["supplierId"]].append(p)
    out = []
    for sid, items in by.items():
        s = crud.suppliers.require(sid)
        total = round2(sum(i["estimatedCost"] or 0 for i in items))
        minimum = s.get("minOrderAmount")
        out.append({
            "supplierId": sid, "supplierName": s["name"], "leadTimeDays": s.get("leadTimeDays"), "minOrderAmount": minimum,
            "productCount": len(items), "totalCost": total, "meetsMinimum": minimum is None or total >= minimum,
            "orderBy": min(i["orderBy"] for i in items),
        })  # fmt: skip
    return sorted(out, key=lambda b: b["orderBy"])


def radar_backtest(as_of: str, horizon_weeks: int = 10, threshold: float = 2.0) -> Doc:
    """The radar on `as_of` (it only sees data before that day), compared with what the sales really did afterwards.

    Only weeks that are fully observed today are judged (never the future). Demand is compared 3 weeks at a time, like the
    radar's own profile, so a single noisy week is not a "peak":
    * an announced peak is right when, within its announced window (the week before the ramp to PEAK_WINDOW weeks after),
      real demand reached HIT_RATIO x a usual week at least once (`hits`); `exactWeekHits` is the stricter version that
      only looks at the announced ramp week;
    * a real peak is a product whose real demand reached REAL_PEAK_RATIO x a usual week within the horizon, and `found`
      counts how many of those had been announced."""
    current = _monday(as_of)
    observed_until = _monday(today())  # weeks before this one are complete
    one = dt.timedelta(weeks=1)
    weekly = _weekly_demand()

    def smoothed(weeks: dict[dt.date, float], w: dt.date) -> float | None:
        return None if w + one >= observed_until else (weeks.get(w - one, 0.0) + weeks.get(w, 0.0) + weeks.get(w + one, 0.0)) / 3

    items, announced_ids = [], set()
    for p in _peaks(as_of, horizon_weeks, threshold):
        if p["ramp"] >= observed_until:
            continue  # this week is not over yet: nothing to judge
        weeks = weekly[p["productId"]]
        series = _series(weeks, current)
        usual = _profile(series)[0] if series else 0
        if usual <= 0:
            continue
        window = [p["ramp"] + dt.timedelta(weeks=k) for k in range(-1, PEAK_WINDOW + 1)]
        ratios = [r for r in (smoothed(weeks, w) for w in window) if r is not None]
        best = max(ratios) / usual if ratios else 0.0
        exact = weeks.get(p["ramp"], 0.0) / usual
        announced_ids.add(p["productId"])
        items.append({"productId": p["productId"], "productName": crud.products.require(p["productId"])["name"],
                      "rampWeekStart": p["ramp"].isoformat(), "predictedIndex": round(p["rampIndex"], 1),
                      "windowRatio": round(best, 1), "exactWeekRatio": round(exact, 1), "hit": best >= HIT_RATIO,
                      "exactWeekHit": exact >= HIT_RATIO})  # fmt: skip
    real = set()
    for pid, weeks in weekly.items():
        series = _series(weeks, current)
        usual = _profile(series)[0] if series else 0
        if usual <= 0:
            continue
        for k in range(1, horizon_weeks + 1):
            r = smoothed(weeks, current + dt.timedelta(weeks=k))
            if r is not None and r / usual >= REAL_PEAK_RATIO:
                real.add(pid)
                break
    hits = sum(1 for i in items if i["hit"])
    found = len(real & announced_ids)
    return {
        "asOf": as_of, "horizonWeeks": horizon_weeks, "announced": len(items), "hits": hits,
        "exactWeekHits": sum(1 for i in items if i["exactWeekHit"]),
        "precision": round(hits / len(items), 2) if items else None, "realPeaks": len(real), "found": found,
        "recall": round(found / len(real), 2) if real else None, "items": sorted(items, key=lambda i: i["rampWeekStart"]),
    }  # fmt: skip


# ───────── Stock to rescue ─────────


def _weekly_rate(product_id: str, as_of: str) -> float:
    """Units sold per week: the mean of the last SALES_WEEKS complete weeks (fallback when there is no seasonal profile)."""
    current = _monday(as_of)
    weeks = _weekly_demand().get(product_id, {})
    return sum(weeks.get(current - dt.timedelta(weeks=k), 0.0) for k in range(1, SALES_WEEKS + 1)) / SALES_WEEKS


def _cumulative_sales(product_id: str, as_of: str, days: int) -> list[float]:
    """cum[d] = units expected to sell in the next d days. Season-aware when the product has a seasonal profile
    (a usual week x the index of each coming week, like the radar), else the recent weekly rate held constant."""
    t = dt.date.fromisoformat(as_of)
    series = _series(_weekly_demand().get(product_id, {}), _monday(as_of))
    if series is None:
        rate = _weekly_rate(product_id, as_of) / 7
        daily = lambda _d: rate  # noqa: E731
    else:
        usual, index, _ = _profile(series, smooth=False)  # a sharp spike must not leak onto the next weeks
        daily = lambda d: usual * index(_monday(t + dt.timedelta(days=d))) / 7  # noqa: E731
    cum = [0.0]
    for d in range(1, days + 1):
        cum.append(cum[-1] + daily(d))
    return cum


@per_data_version
def _buyers() -> dict[str, dict[str, list[tuple[dt.date, float]]]]:
    """product -> client -> [(delivery date, qty)] for every sale order. Shared: never mutate."""
    out: dict[str, dict[str, list[tuple[dt.date, float]]]] = defaultdict(lambda: defaultdict(list))
    for o in crud.orders.all():
        if not is_sale(o):
            continue
        d = dt.date.fromisoformat(o["deliveryDate"][:10])
        for line in o["lines"]:
            out[line["productId"]][o["clientId"]].append((d, line_qty(line)))
    return out


def _unsold_units(lots: list[Doc], reserved: float, cum: list[float], t: dt.date) -> list[tuple[Doc, float, int]]:
    """FEFO: committed orders take the oldest lots first, then the expected sales (`cum`). Returns (lot, unsold units at expiry, days left)."""
    to_commit, consumed, out = reserved, 0.0, []
    for lot in lots:  # already sorted by expiry
        qty = lot["qtyRemaining"]
        used = min(qty, to_commit)
        qty -= used
        to_commit -= used
        days = (dt.date.fromisoformat(lot["expiresAt"][:10]) - t).days
        if days < 1:
            continue  # expires today or already expired: nothing can still be delivered, it is not a rescue any more
        capacity = cum[min(days, len(cum) - 1)]
        sold_here = min(qty, max(0.0, capacity - consumed))
        consumed += sold_here
        if qty - sold_here >= EXPIRY_UNIT_MIN:
            out.append((lot, qty - sold_here, days))
    return out


def _discount_pct(price: float, cost: float, days_left: int) -> int:
    """A discount that always keeps part of the margin: never below cost, steps of 5 %, at most 30 %."""
    margin = (price - cost) / price if price > 0 else 0
    if margin <= 0:
        return 0
    share = 0.9 if days_left <= 7 else 0.75
    return int(min(0.30, margin * share) * 100 // 5 * 5)


def _already_proposed(client_id: str, product_id: str) -> bool:
    return any(
        e["type"] == "price_negotiation" and e["title"].startswith("Offre de déstockage") and product_id in (e.get("productIds") or [])
        for e in crud.client_events.filter(lambda e: e["clientId"] == client_id)
    )


def stock_rescue(horizon_days: int = 120) -> Doc:
    t_iso = today()
    t = dt.date.fromisoformat(t_iso)
    levels = stock_levels()
    items = []
    for product in crud.products.all():
        level = levels.get(product["id"])
        if not product["active"] or not level or not level["lots"]:
            continue
        last_expiry = max((dt.date.fromisoformat(lot["expiresAt"][:10]) - t).days for lot in level["lots"])
        cum = _cumulative_sales(product["id"], t_iso, max(28, min(last_expiry, horizon_days)))
        weekly = cum[28] / 4  # expected units per week over the next 4 weeks
        risk = [(lot, u, d) for lot, u, d in _unsold_units(level["lots"], level["reserved"], cum, t) if d <= horizon_days]
        units = sum(u for _, u, _ in risk)
        if units < EXPIRY_UNIT_MIN:
            continue
        earliest = min(risk, key=lambda r: r[2])
        price, cost = product["price"], product["cost"]
        pct = _discount_pct(price, cost, earliest[2])
        clients = _rescue_clients(product, units, pct, t)
        covered = sum(c["suggestedQty"] for c in clients)
        reason = (
            f"{round(units)} {product['unit']} ne seront pas vendues avant la date limite ERP des lots (la plus proche : {fr_day(earliest[0]['expiresAt'])}), "
            f"car on n'en attend qu'environ {round(weekly, 1)} par semaine (saison comprise)."
        )
        reason += (
            f" Remise possible : {pct} % (jamais sous le coût)." if pct else " La marge est trop faible pour une remise : à proposer au prix normal ou à donner."
        )
        if covered < units:
            reason += f" Les offres ci-dessous ne couvrent que {round(covered)} unités sur {round(units)} : il faut d'autres débouchés pour le reste."
        items.append({
            "productId": product["id"], "productName": product["name"], "unit": product["unit"],
            "atRiskUnits": round3(units), "atRiskValue": round2(units * cost), "earliestExpiry": earliest[0]["expiresAt"][:10],
            "daysToExpiry": earliest[2], "weeklySales": round(weekly, 1), "listPrice": price, "cost": cost,
            "suggestedDiscountPct": pct, "coveredUnits": covered, "clients": clients, "reason": reason,
        })  # fmt: skip
    items.sort(key=lambda i: (i["daysToExpiry"], -i["atRiskValue"]))
    return {"asOf": t_iso, "horizonDays": horizon_days, "items": items}


def _rescue_clients(product: Doc, units: float, pct: int, t: dt.date) -> list[Doc]:
    """Active clients who bought this product in the last 90 days, most regular first, until the at-risk units are covered."""
    since = t - dt.timedelta(days=BUYER_DAYS)
    ranked = []
    for client_id, buys in _buyers().get(product["id"], {}).items():
        recent = [(d, q) for d, q in buys if since < d <= t]
        client = crud.clients.get(client_id)
        if not recent or not client or client["status"] != "active":
            continue
        ranked.append((len(recent), sum(q for _, q in recent), client, statistics.median(q for _, q in recent)))
    deal = deal_seekers()
    ranked.sort(key=lambda r: (r[2]["id"] not in deal, -r[0], -r[1]))  # asked for a deal in writing (AI signal) first
    out, covered = [], 0.0
    for count, _, client, typical in ranked[:6]:
        own = crud.client_prices.get(f"{client['id']}|{product['id']}")
        unit_price = own["price"] if own else product["price"]
        offer = max(product["cost"], round2(unit_price * (1 - pct / 100)))
        qty = max(1, round(typical))
        out.append({"clientId": client["id"], "clientName": client["name"], "ordersLast90d": count, "suggestedQty": qty,
                    "unitPrice": unit_price, "offerPrice": offer, "alreadyProposed": _already_proposed(client["id"], product["id"]),
                    "askedForDeal": deal.get(client["id"])})  # fmt: skip
        covered += qty
        if covered >= units:
            break
    return out


def propose_offer(ctx: Ctx, input: Doc) -> Doc:
    """A seller marks an offer as proposed: a line in the client's history (type price_negotiation). No price, order or stock changes."""
    product = crud.products.require(input["productId"])
    client = crud.clients.require(input["clientId"])
    if input["qty"] <= 0 or not (0 <= input["discountPct"] <= 30):
        raise bad_request("invalid_offer", "Quantité ou remise invalide (remise de 0 à 30 %)")
    if input["offerPrice"] < product["cost"]:
        raise bad_request("below_cost", f"Le prix proposé est sous le coût ({product['cost']} €) : offre refusée")
    qty = round(input["qty"], 3)
    return create_client_event(
        ctx,
        client["id"],
        {
            "type": "price_negotiation",
            "title": f"Offre de déstockage : {product['name']}",
            "description": f"Remise de {round(input['discountPct'])} % proposée : {qty:g} × {input['offerPrice']:.2f} € HT au lieu de {product['price']:.2f} €, pour écouler un lot dont la date limite ERP approche. Proposée par un vendeur, à confirmer par le client.",
            "productIds": [product["id"]],
            "amount": round2(qty * input["offerPrice"]),
        },
    )


# ───────── AI signals (read by an LLM in the client notes, stored here; the numbers stay arithmetic) ─────────

INTENTS = ("firm", "tentative", "cancelled", "unclear")
# Measured on the 2024 and 2025 seasons (holiday-reservations/backtest): the reserved lines were bought at ~1.0x their estimate
# (actual / estimated value 1.10 and 0.97), so neither a hesitation nor the notes-to-orders rate discounts the expected value
# (doing so made it 17 % to 53 % too low). Only an explicit cancellation does.
INTENT_WEIGHT = {"firm": 1.0, "unclear": 1.0, "tentative": 1.0, "cancelled": 0.0}


def save_signals(input: Doc) -> Doc:
    """Store what the LLM read in client notes (one signal per note). Checked: the note exists, the multiplier is 0–5,
    product ids are ones the note is about. Replaces an earlier signal of the same note."""
    saved = []
    for sig in input.get("signals") or []:
        ev = crud.client_events.get(sig.get("eventId", ""))
        if not ev:
            raise bad_request("unknown_event", f"Note client introuvable : {sig.get('eventId')}")
        if sig.get("intent") not in INTENTS:
            raise bad_request("invalid_intent", f"Intention inconnue : {sig.get('intent')} ({', '.join(INTENTS)})")
        mult = float(sig.get("multiplier") if sig.get("multiplier") is not None else 1)
        if not 0 <= mult <= 5:
            raise bad_request("invalid_multiplier", "Le multiplicateur doit être entre 0 et 5")
        dropped = [pid for pid in sig.get("droppedProductIds") or [] if pid in (ev.get("productIds") or [])]
        doc = {
            "eventId": ev["id"], "clientId": ev["clientId"], "intent": sig["intent"], "multiplier": round(mult, 2),
            "droppedProductIds": dropped, "askedForDeal": bool(sig.get("askedForDeal")), "condition": (sig.get("condition") or "")[:200] or None,
            "summary": (sig.get("summary") or "")[:300], "model": (input.get("model") or "")[:80], "at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        }  # fmt: skip
        crud.prediction_signals.put(doc)
        saved.append(doc)
    return {"saved": len(saved), "signals": saved}


def list_signals() -> list[Doc]:
    return crud.prediction_signals.all()


def deal_seekers() -> dict[str, str]:
    """client id → why (the note's summary), for clients whose notes asked for a deal / found us too expensive."""
    return {s["clientId"]: s.get("summary") or "a demandé un geste" for s in crud.prediction_signals.all() if s.get("askedForDeal")}


# ───────── Carnet de Noël: written holiday reservations ─────────

HOLIDAY_FROM = "12-15"  # a « late-December purchase » is delivered from 15 to 31 December
CONVERTED_FROM = "12-20"  # a reservation became an order when an order for the client is delivered 20–31 December


def _season_notes(year: int) -> list[Doc]:
    prefix = f"Fêtes {year}"
    return sorted((e for e in crud.client_events.all() if e["title"].startswith(prefix) and "réservation" in e["title"]), key=lambda e: e["at"])


@per_data_version
def _late_december() -> dict[tuple[str, str], dict[int, float]]:
    """(client, product) → {year: units delivered 15–31 December} over every sale order."""
    out: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for o in crud.orders.all():
        d = o["deliveryDate"][:10]
        if not is_sale(o) or d[5:] < HOLIDAY_FROM:
            continue
        for line in o["lines"]:
            out[(o["clientId"], line["productId"])][int(d[:4])] += line_qty(line)
    return out


def _orders_after(client_id: str, year: int) -> list[Doc]:
    lo, hi = f"{year}-{CONVERTED_FROM}", f"{year}-12-31"
    return [o for o in crud.orders.all() if o["clientId"] == client_id and o["status"] != "cancelled" and lo <= o["deliveryDate"][:10] <= hi]


def _conversion(year: int) -> Doc:
    """Share of the reservation notes of the 2 previous seasons whose client then had an order delivered 20–31 December."""
    total = converted = 0
    for y in (year - 2, year - 1):
        for e in _season_notes(y):
            total += 1
            converted += bool(_orders_after(e["clientId"], y))
    return {"rate": round(converted / total, 2) if total else None, "converted": converted, "total": total, "seasons": [year - 2, year - 1]}


def _quote(text: str) -> str | None:
    m = re.search(r"«\s*(.+?)\s*»", text or "")
    return m[1] if m else None


def holiday_reservations(client_id: str | None = None, season: int | None = None, use_signals: bool = True) -> Doc:
    """`season` (default: this year) lets the same estimate run on a past season, seeing only the years before it (backtest)."""
    t_iso = today()
    year = season or int(t_iso[:4])
    late = _late_december()
    signals = {s["eventId"]: s for s in crud.prediction_signals.all()} if use_signals else {}
    conv = _conversion(year)
    levels = stock_levels()
    lines, notes = [], []
    for e in _season_notes(year):
        if client_id and e["clientId"] != client_id:
            continue
        client = crud.clients.get(e["clientId"])
        if not client:
            continue
        sig = signals.get(e["id"])
        intent = sig["intent"] if sig else "unclear"
        mult = sig["multiplier"] if sig else 1.0
        ordered = _orders_after(client["id"], year) if year == int(t_iso[:4]) else []  # past season: what happened is the backtest's answer
        notes.append({"eventId": e["id"], "clientId": client["id"], "clientName": client["name"], "at": e["at"][:10],
                      "text": e.get("description", ""), "quote": _quote(e.get("description", "")), "intent": intent, "multiplier": mult,
                      "askedForDeal": bool(sig and sig.get("askedForDeal")), "condition": sig.get("condition") if sig else None,
                      "aiSummary": sig.get("summary") if sig else None, "analyzed": bool(sig)})  # fmt: skip
        for pid in e.get("productIds") or []:
            product = crud.products.get(pid)
            if not product:
                continue
            past = {y: q for y, q in late.get((client["id"], pid), {}).items() if year - 3 <= y < year and q > 0}
            baseline = round(sum(past.values()) / len(past)) if past else None
            dropped = bool(sig and pid in sig.get("droppedProductIds", []))
            qty = None if baseline is None else (0 if dropped or intent == "cancelled" else math.ceil(baseline * mult))
            unit_price = pricing.price_for(client["id"], pid, qty or 1)
            value = round2(qty * unit_price) if qty else (0.0 if qty == 0 else None)
            already = any(any(l["productId"] == pid for l in o["lines"]) for o in ordered)
            weight = 0.0 if dropped else INTENT_WEIGHT[intent]
            lines.append({
                "eventId": e["id"], "clientId": client["id"], "clientName": client["name"], "productId": pid, "productName": product["name"],
                "unit": product["unit"], "pastYears": [{"year": y, "qty": round3(q)} for y, q in sorted(past.items())], "baselineQty": baseline,
                "multiplier": mult, "qty": qty, "unitPrice": unit_price, "value": value, "intent": "cancelled" if dropped else intent,
                "expectedValue": round2(value * weight) if value else 0.0, "ordered": already,
            })  # fmt: skip
    # stock check: the reserved units (best estimate) against what we have and what is coming, per product
    by_product: dict[str, float] = defaultdict(float)
    for ln in lines:
        if ln["qty"] and not ln["ordered"]:
            by_product[ln["productId"]] += ln["qty"]
    products = []
    for pid, units in by_product.items():
        product = crud.products.require(pid)
        level = levels.get(pid, {"available": 0, "incoming": 0})
        supplier = crud.suppliers.get(product.get("mainSupplierId") or "")
        lead = supplier.get("leadTimeDays") if supplier else None
        order_by = (dt.date(year, 12, 23) - dt.timedelta(days=lead or 0)).isoformat()
        short = max(0.0, units - max(0, level["available"]) - level["incoming"])
        products.append({"productId": pid, "productName": product["name"], "unit": product["unit"], "reservedUnits": round3(units),
                         "available": level["available"], "incoming": level["incoming"], "shortfall": round3(short),
                         "supplierName": supplier["name"] if supplier else None, "orderBy": order_by if short else None,
                         "late": bool(short) and order_by < t_iso})  # fmt: skip
    products.sort(key=lambda p: (-p["shortfall"], p["productName"]))
    known = [ln for ln in lines if ln["value"] is not None]
    return {
        "asOf": t_iso, "season": year, "notes": notes, "lines": lines, "products": products, "conversion": conv,
        "totals": {
            "notes": len(notes), "lines": len(lines), "linesWithoutHistory": sum(1 for ln in lines if ln["baselineQty"] is None),
            "reservedValue": round2(sum(ln["value"] for ln in known if ln["intent"] != "cancelled")),
            "expectedValue": round2(sum(ln["expectedValue"] for ln in lines)),
            "orderedLines": sum(1 for ln in lines if ln["ordered"]), "analyzedNotes": sum(1 for n in notes if n["analyzed"]),
            "shortProducts": sum(1 for p in products if p["shortfall"] > 0),
        },
    }  # fmt: skip


def reservation_notes(season: int | None = None) -> list[Doc]:
    year = season or int(today()[:4])
    out = []
    for e in _season_notes(year):
        client = crud.clients.get(e["clientId"])
        pids = [pid for pid in e.get("productIds") or [] if crud.products.get(pid)]
        out.append({"eventId": e["id"], "clientId": e["clientId"], "clientName": client["name"] if client else e["clientId"], "at": e["at"][:10],
                    "text": e.get("description", ""), "productIds": pids, "productNames": [crud.products.require(p)["name"] for p in pids]})  # fmt: skip
    return out


def reservations_backtest(season: int, use_signals: bool = True) -> Doc:
    """The Carnet de Noël estimate of a PAST season (history before it only), judged on what those clients really bought
    15–31 December of that season. `use_signals` = with the LLM's reading of the notes (×2, cancelled…), else plain arithmetic."""
    if season >= int(today()[:4]):
        raise bad_request("season_not_over", "Seule une saison terminée peut être évaluée")
    data = holiday_reservations(season=season, use_signals=use_signals)
    late = _late_december()
    rows = []
    for ln in data["lines"]:
        if ln["qty"] is None:
            continue  # no history: no estimate to judge
        actual = late.get((ln["clientId"], ln["productId"]), {}).get(season, 0.0)
        rows.append({"clientName": ln["clientName"], "productName": ln["productName"], "predicted": ln["qty"], "actual": round3(actual),
                     "unitPrice": ln["unitPrice"], "intent": ln["intent"], "multiplier": ln["multiplier"]})  # fmt: skip
    actual_units = sum(r["actual"] for r in rows)
    abs_err = sum(abs(r["predicted"] - r["actual"]) for r in rows)
    actual_value = sum(r["actual"] * r["unitPrice"] for r in rows)
    predicted_value = sum(r["predicted"] * r["unitPrice"] for r in rows)
    expected_value = sum(r["predicted"] * r["unitPrice"] * INTENT_WEIGHT.get(r["intent"], 1.0) for r in rows)
    return {
        "season": season, "useSignals": use_signals, "lines": len(rows), "notesToOrders": data["conversion"]["rate"],
        "linesBought": sum(1 for r in rows if r["actual"] > 0),
        "wape": round(abs_err / actual_units, 3) if actual_units else None,  # weighted absolute % error on units
        "within30Pct": round(sum(1 for r in rows if r["actual"] and abs(r["predicted"] - r["actual"]) <= 0.3 * r["actual"]) / len(rows), 3) if rows else None,
        "predictedValue": round2(predicted_value), "expectedValue": round2(expected_value), "actualValue": round2(actual_value),
        "valueError": round((expected_value - actual_value) / actual_value, 3) if actual_value else None,
        "items": rows,
    }  # fmt: skip


# ───────── A rescue offer accepted on a call (agent tool add_rescue_offer) ─────────


@transactional
def accept_rescue_offer(ctx: Ctx, input: Doc) -> Doc:
    """Add a rescue lot to the client's DRAFT order at the rescue price. The price is computed HERE from the current stock to
    rescue (never sent by the caller), refused below cost, and only for a client listed as a buyer of that lot. The line goes
    through the order's usual recap + explicit yes before any confirmation. Writes the offer in the client's history."""
    from app.services import orders  # (circular at import time)

    client_id, product_id, order_id = input["clientId"], input["productId"], input["orderId"]
    item = next((i for i in stock_rescue()["items"] if i["productId"] == product_id), None)
    if not item:
        raise bad_request("no_rescue", "Ce produit n'est pas (ou plus) dans le stock à écouler")
    offer = next((c for c in item["clients"] if c["clientId"] == client_id), None)
    if not offer:
        raise bad_request("not_a_buyer", "Cette offre n'est pas prévue pour ce client (il n'achète pas ce produit)")
    product = crud.products.require(product_id)
    if offer["offerPrice"] < product["cost"]:
        raise bad_request("below_cost", "Prix d'offre sous le coût : refusé")
    order = crud.orders.require(order_id)
    if order["clientId"] != client_id or order["status"] != "draft":
        raise bad_request("order_not_editable", "L'offre ne s'ajoute qu'à une commande en brouillon de ce client")
    if any(line["productId"] == product_id for line in order["lines"]):
        raise bad_request("already_in_order", "Ce produit est déjà dans la commande")
    qty = float(input.get("qty") or offer["suggestedQty"])
    if qty <= 0 or qty > item["atRiskUnits"] + 1e-9:
        raise bad_request("invalid_qty", f"Quantité entre 0 et {item['atRiskUnits']:g} (le lot à écouler)")
    detail = orders.add_line(ctx, order_id, {"productId": product_id, "qty": qty, "unitPrice": offer["offerPrice"],
                                             "note": f"Offre de déstockage -{item['suggestedDiscountPct']} %"})  # fmt: skip
    create_client_event(ctx, client_id, {
        "type": "price_negotiation", "title": f"Offre de déstockage : {product['name']}",
        "description": f"Acceptée au téléphone : {qty:g} × {offer['offerPrice']:.2f} € HT au lieu de {offer['unitPrice']:.2f} € "
                       f"(-{item['suggestedDiscountPct']} %), ajoutée au brouillon {order['number']} à confirmer.",
        "productIds": [product_id], "amount": round2(qty * offer["offerPrice"]), "orderId": order_id,
    })  # fmt: skip
    return detail
