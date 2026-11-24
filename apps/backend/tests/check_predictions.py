"""Checks of /api/predictions against the running ERP (like parity.py: plain asserts, no test framework needed).

    API=http://localhost:4000 python apps/backend/tests/check_predictions.py

It writes ONE client-history line (an "offer proposed" note) and resets nothing: run it on a throwaway ERP
(`make reset` afterwards). Exit code 1 if a check fails.
"""

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("API", "http://localhost:4000").rstrip("/") + "/api"
failures: list[str] = []


def call(method: str, path: str, body=None):
    req = urllib.request.Request(
        API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json", "x-actor": "user", "x-actor-name": "check_predictions"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def check(name: str, ok: bool, detail: str = ""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(name)


_, meta = call("GET", "/meta")
today = meta["today"]
d = lambda s: dt.date.fromisoformat(s)

# ── Season radar ──
s, radar = call("GET", "/predictions/season-radar")
check("radar answers", s == 200 and radar["asOf"] == today, str(s))
peaks = radar["peaks"]
check("radar finds peaks", len(peaks) > 0)
check("most urgent first", [p["daysToOrderBy"] for p in peaks] == sorted(p["daysToOrderBy"] for p in peaks))
check("order-by = ramp week - supplier lead time", all((d(p["rampWeekStart"]) - d(p["orderBy"])).days == (p.get("leadTimeDays") or 0) for p in peaks))
check("late flag matches the date", all(p["late"] == (d(p["orderBy"]) < d(today)) for p in peaks))
check("every peak is a coming week, never the past", all(d(p["rampWeekStart"]) > d(today) - dt.timedelta(days=7) for p in peaks))
check("suggested quantities are never negative", all(p["suggestedQty"] >= 0 for p in peaks))
check("a cost is given when something is suggested", all((p.get("estimatedCost") or 0) > 0 for p in peaks if p["suggestedQty"] > 0 and p.get("supplierId")))

# Draft purchase orders never count as incoming stock: the radar reads the same figure as the stock list.
s, st = call("GET", "/stock?limit=500")
incoming = {row["productId"]: row["incoming"] for row in (st if isinstance(st, list) else st["items"])}
check("radar 'incoming' = confirmed purchase orders only (same as the stock list)", all(abs(p["incoming"] - incoming.get(p["productId"], 0)) < 1e-6 for p in peaks))
s, pos = call("GET", "/purchase-orders?limit=500")
drafts = [p for p in (pos if isinstance(pos, list) else pos["items"]) if p["status"] == "draft"]
check("the data has draft purchase orders to prove it", len(drafts) > 0)

# Supplier baskets add up and respect the supplier's minimum.
for b in radar["suppliers"]:
    items = [p for p in peaks if p.get("supplierId") == b["supplierId"] and p["suggestedQty"]]
    check(f"basket {b['supplierName'][:24]} adds up", abs(b["totalCost"] - sum(p.get("estimatedCost") or 0 for p in items)) < 0.05)
    check(f"basket {b['supplierName'][:24]} minimum flag", b["meetsMinimum"] == (b.get("minOrderAmount") is None or b["totalCost"] >= b["minOrderAmount"]))

# ── Backtest: never judge the future ──
s, bt = call("GET", f"/predictions/season-radar/backtest?asOf={today}")
check("backtest as of today judges nothing (the weeks are not over)", s == 200 and bt["announced"] == 0, json.dumps(bt)[:120])
past = (d(today) - dt.timedelta(days=364)).isoformat()
s, bt = call("GET", f"/predictions/season-radar/backtest?asOf={past}")
check("backtest of a year ago answers", s == 200 and bt["announced"] > 0, str(s))
check("exact-week hits never exceed window hits' possible", bt["exactWeekHits"] <= bt["announced"] and bt["hits"] <= bt["announced"])
s, bad = call("GET", "/predictions/season-radar/backtest?asOf=not-a-date")
check("a malformed date is refused", s in (400, 422), str(s))

# ── Stock to rescue ──
s, rescue = call("GET", "/predictions/stock-rescue")
check("rescue answers", s == 200 and rescue["asOf"] == today)
items = rescue["items"]
check("nothing that expires today or earlier (it can no longer be delivered)", all(i["daysToExpiry"] >= 1 for i in items))
check("discounts are steps of 5 %, at most 30 %", all(i["suggestedDiscountPct"] % 5 == 0 and 0 <= i["suggestedDiscountPct"] <= 30 for i in items))
check("an offer price is never below cost", all(c["offerPrice"] >= i["cost"] - 1e-9 for i in items for c in i["clients"]))
check("covered units = sum of the suggested quantities", all(abs(i["coveredUnits"] - sum(c["suggestedQty"] for c in i["clients"])) < 1e-6 for i in items))
s, blocked = call("GET", "/clients?status=blocked&limit=100")
blocked_ids = {c["id"] for c in blocked}
check("blocked clients are never offered anything", all(c["clientId"] not in blocked_ids for i in items for c in i["clients"]))

# ── Proposing an offer ──
target = next(((i, c) for i in items for c in i["clients"] if i["suggestedDiscountPct"] > 0 and not c["alreadyProposed"]), None)
check("there is an offer to propose", target is not None)
if target:
    i, c = target
    body = dict(clientId=c["clientId"], productId=i["productId"], qty=c["suggestedQty"], discountPct=i["suggestedDiscountPct"], offerPrice=c["offerPrice"])
    _, orders_before = call("GET", "/orders?limit=1&envelope=1")
    _, prod_before = call("GET", f"/products/{i['productId']}")
    s, ev = call("POST", "/predictions/stock-rescue/offers", body)
    check("an offer can be proposed", s == 201 and ev["type"] == "price_negotiation" and ev["clientId"] == c["clientId"], str(s))
    _, orders_after = call("GET", "/orders?limit=1&envelope=1")
    _, prod_after = call("GET", f"/products/{i['productId']}")
    check("proposing changes no order and no price", orders_before.get("total") == orders_after.get("total") and prod_before["price"] == prod_after["price"])
    _, again = call("GET", "/predictions/stock-rescue")
    row = next(x for x in again["items"] if x["productId"] == i["productId"])
    check("it then shows as already proposed", next(x for x in row["clients"] if x["clientId"] == c["clientId"])["alreadyProposed"])
    s, e = call("POST", "/predictions/stock-rescue/offers", dict(body, offerPrice=round(i["cost"] - 0.01, 2)))
    check("a price below cost is refused", s == 400 and e["error"]["code"] == "below_cost", f"{s} {e}")
    s, e = call("POST", "/predictions/stock-rescue/offers", dict(body, discountPct=45))
    check("a discount above 30 % is refused", s == 400 and e["error"]["code"] == "invalid_offer", f"{s} {e}")
    s, e = call("POST", "/predictions/stock-rescue/offers", dict(body, clientId="cli_9999"))
    check("an unknown client is refused", s == 404, str(s))

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
