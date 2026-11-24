"""Checks of the V2 AI additions against the running ERP (plain asserts, like check_predictions.py): the Carnet de Noël (written
holiday reservations), its backtest, the AI signals store, and a rescue offer accepted on a call (price set by the ERP only).
It writes signals, a draft order and a history line: run it on a throwaway ERP (`make reset` afterwards).

    API=http://localhost:4000 python apps/backend/tests/check_reservations.py

Exit code 1 if a check fails.
"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("API", "http://localhost:4000").rstrip("/") + "/api"
failures: list[str] = []


def call(path: str, method: str = "GET", body=None, actor: str = "user"):
    req = urllib.request.Request(
        API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json", "x-actor": actor, "x-actor-name": "check_reservations"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else None)


def check(name: str, ok: bool, detail: str = ""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        failures.append(name)


# ── Carnet de Noël ──
s, r = call("/predictions/holiday-reservations")
check("the Carnet de Noël answers", s == 200, str(s))
t = r["totals"]
check("it finds this season's written reservations (30 notes, 60 product lines, 14 without history)", (t["notes"], t["lines"], t["linesWithoutHistory"]) == (30, 60, 14), str(t))
check("every estimated line comes from the client's own past late-December purchases", all((ln.get("baselineQty") is None) == (not ln["pastYears"]) for ln in r["lines"]))
check("a line with history has a quantity, a client price and a value", all(ln.get("qty") is not None and ln["unitPrice"] > 0 and ln.get("value") is not None for ln in r["lines"] if ln.get("baselineQty") is not None))
check("the reserved value adds up", abs(t["reservedValue"] - sum(ln.get("value") or 0 for ln in r["lines"] if ln["intent"] != "cancelled")) < 0.05)
check("each note keeps what the client said", all(n["text"] for n in r["notes"]) and sum(1 for n in r["notes"] if n.get("quote")) >= 25)
check("stock check per reserved product", all(p["shortfall"] >= 0 and p["reservedUnits"] > 0 for p in r["products"]))
s, one = call(f"/predictions/holiday-reservations?clientId={r['notes'][0]['clientId']}")
check("filter by client", s == 200 and {n["clientId"] for n in one["notes"]} == {r["notes"][0]["clientId"]})

# ── backtest: judged on what clients really bought ──
s, bt = call("/predictions/holiday-reservations/backtest?season=2025&signals=false")
check("the 2025 season can be judged", s == 200 and bt["lines"] > 30, str(s))
check("the expected value is within 15 % of what clients really bought in 2025", bt.get("valueError") is not None and abs(bt.get("valueError")) <= 0.15, str(bt.get("valueError")))
s, bt24 = call("/predictions/holiday-reservations/backtest?season=2024&signals=false")
check("...and in 2024", s == 200 and abs(bt24.get("valueError")) <= 0.15, str(bt24.get("valueError")))
s, _x = call("/predictions/holiday-reservations/backtest?season=2026")
check("a season that is not over cannot be judged (400)", s == 400, str(s))

# ── AI signals: validated, stored, used ──
target = next(ln for ln in r["lines"] if ln.get("baselineQty"))
s, bad = call("/predictions/signals", "PUT", {"signals": [{"eventId": "nope", "intent": "firm"}]})
check("a signal for an unknown note is refused", s == 400, str(s))
s, bad = call("/predictions/signals", "PUT", {"signals": [{"eventId": target["eventId"], "intent": "firm", "multiplier": 9}]})
check("a multiplier above 5 is refused", s == 400, str(s))
s, ok = call("/predictions/signals", "PUT", {"model": "check", "signals": [{"eventId": target["eventId"], "intent": "firm", "multiplier": 2, "askedForDeal": True, "summary": "veut le double"}]})
check("a valid signal is stored", s == 200 and ok["saved"] == 1)
s, r2 = call("/predictions/holiday-reservations")
line2 = next(ln for ln in r2["lines"] if ln["eventId"] == target["eventId"] and ln["productId"] == target["productId"])
check("×2 doubles the estimate (the ERP does the sum, not the LLM)", line2.get("qty") == -(-target.get("baselineQty") * 2 // 1), f"{line2['qty']} vs {target['baselineQty']}")
call("/predictions/signals", "PUT", {"model": "check", "signals": [{"eventId": target["eventId"], "intent": "cancelled", "summary": "annule"}]})
s, r3 = call("/predictions/holiday-reservations")
line3 = next(ln for ln in r3["lines"] if ln["eventId"] == target["eventId"] and ln["productId"] == target["productId"])
check("a cancelled note counts for nothing", line3.get("qty") == 0 and line3["expectedValue"] == 0)

# ── a rescue offer accepted on a call: the price comes from the ERP ──
s, rescue = call("/predictions/stock-rescue")
item = next((i for i in rescue["items"] if i["clients"] and i["suggestedDiscountPct"] > 0), None)
if item is None:
    print("SKIP no rescue lot with a discount in this data")
else:
    buyer = item["clients"][0]
    s, meta = call("/meta")
    s, draft = call("/orders", "POST", {"clientId": buyer["clientId"], "deliveryDate": meta["today"], "lines": []}, actor="voice_agent")
    if s != 201:  # an order needs a line in some packs: start with another product
        other = next(p for p in call("/products?limit=50")[1] if p["id"] != item["productId"] and p["active"])
        s, draft = call("/orders", "POST", {"clientId": buyer["clientId"], "lines": [{"productId": other["id"], "qty": 1}]}, actor="voice_agent")
    check("a draft order for the buyer", s == 201, str(draft)[:200])
    s, res = call("/predictions/stock-rescue/accept", "POST", {"clientId": buyer["clientId"], "productId": item["productId"], "orderId": draft["id"]}, actor="voice_agent")
    line = next((ln for ln in (res or {}).get("lines", []) if ln["productId"] == item["productId"]), None)
    check("the accepted lot is added at the rescue price computed by the ERP", s == 201 and line and line["unitPrice"] == buyer["offerPrice"], str(res)[:200])
    check("...never below cost", line and line["unitPrice"] >= item["cost"])
    s, again = call("/predictions/stock-rescue/accept", "POST", {"clientId": buyer["clientId"], "productId": item["productId"], "orderId": draft["id"]}, actor="voice_agent")
    check("not twice in the same order", s == 400, str(s))
    stranger = next(c["id"] for c in call("/clients?limit=200")[1] if c["id"] not in {b["clientId"] for b in item["clients"]})
    s, nope = call("/predictions/stock-rescue/accept", "POST", {"clientId": stranger, "productId": item["productId"], "orderId": draft["id"]}, actor="voice_agent")
    check("only for a client who buys that product", s == 400, str(s))
    s, evs = call(f"/clients/{buyer['clientId']}/events?type=price_negotiation&limit=5")
    check("the accepted offer is written in the client's history", any("Acceptée au téléphone" in (e.get("description") or "") for e in evs))
    call(f"/orders/{draft['id']}/cancel", "POST", {}, actor="user")

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
