"""Checks of /api/proactive against the running ERP (like check_predictions.py: plain asserts, no framework).
It writes ONE client-history line ("Appel proactif : ...") and pauses/resumes the agent's autodial: run it on a throwaway ERP.

    API=http://localhost:4000 python apps/backend/tests/check_proactive.py

Principle under test: the agent phones a client ONLY to solve a problem on an order it already has (a product that cannot be
delivered, a delivery day without a route). Never to sell, never to chase a usual order. Exit code 1 if a check fails.
"""

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("API", "http://localhost:4000").rstrip("/") + "/api"
failures: list[str] = []


def call(path: str, method: str = "GET", body=None):
    req = urllib.request.Request(
        API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json", "x-actor": "user", "x-actor-name": "check_proactive"},
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


_, meta = call("/meta")
today = dt.date.fromisoformat(meta["today"])
s, opps = call("/proactive/opportunities")
check("missions answer", s == 200 and isinstance(opps, list) and len(opps) > 0, str(s))
check("most urgent first", [o["priority"] for o in opps] == sorted((o["priority"] for o in opps), reverse=True))
check("ids are unique", len({o["id"] for o in opps}) == len(opps))
check("every mission has a problem, a reason, facts, what the agent does and a deadline", all(o["title"] and o["reason"] and o["facts"] and o["objective"] and o["deadline"] and o["kinds"] for o in opps))

# ── The principle: only problems on orders in progress ──
check("the only kind of call is a problem on an order (never a sale, never a reminder)", all(o["type"] == "order_issue" and set(o["kinds"]) <= {"stock", "delivery"} for o in opps))
check("every mission is tied to one order", all(o.get("orderId") for o in opps))
status_ok, in_horizon = True, True
for o in opps:
    s, order = call("/orders/" + o["orderId"])
    status_ok &= s == 200 and order["status"] in ("draft", "confirmed", "prepared") and order["clientId"] == o["clientId"]
    in_horizon &= 0 <= (dt.date.fromisoformat(order["deliveryDate"][:10]) - today).days <= 30
check("each order is still open and belongs to the client called", status_ok)
check("each delivery is today or within 30 days", in_horizon)
s, clients = call("/clients?limit=500")
status_of = {c["id"]: c["status"] for c in (clients if isinstance(clients, list) else clients["items"])}
check("only active clients are called (never blocked or prospects)", all(status_of.get(o["clientId"]) == "active" for o in opps))
check("no 'late usual order' or 'season' call exists any more", not any(re.search(r"en retard|habituel|saison|anticiper", o["title"] + " " + o["reason"], re.I) for o in opps))

# ── The real cases of the data ──
stock = [o for o in opps if o["kinds"] == ["stock"] and "aujourd'hui" in o["deadline"]]
check("a supplier shortage on today's order is found and comes first", len(stock) > 0 and opps[0]["id"] == stock[0]["id"])
if stock:
    o = stock[0]
    s, b = call("/proactive/opportunities/" + urllib.parse.quote(o["id"], safe=""))
    check("the brief of one mission answers", s == 200 and "brief" in b, str(s))
    text = b["brief"]
    check("the ORDERED quantity is quoted, not the picked one (no '0 ×')", not re.search(r"(^|[^\d.,])0 × ", text))
    check("the brief names the client id, the order id and the product id the agent needs", o["clientId"] in text and o["orderId"] in text and "product_id : prd_" in text)
    check("the brief lists the only facts the agent may quote", "FAITS VÉRIFIÉS" in text and "ÉCHÉANCE" in text)
    check("the brief forbids invented promises, prices, unapproved substitutions and other topics", "INTERDIT" in text and "sans son accord" in text and "d'autre chose que de ce problème" in text)
    check("the brief says what to do if the client has no time (the essential in one sentence)", "n'a pas le temps" in text)
    check("a commercial's note about substitutions reaches the agent", "substitution" in text.lower())
    check("a prepared order is flagged as no longer editable", "DÉJÀ PRÉPARÉE" in text and "record_call_outcome" in text)
    check("the brief tells the agent to record the outcome with the dedicated tool", "record_call_outcome" in text)
    check("no double full stop in the facts", not re.search(r"\.\.", text))

both = [o for o in opps if "delivery" in o["kinds"]]
check("a delivery day without a route is found", len(both) > 0)
for o in both:
    s, b = call("/proactive/opportunities/" + urllib.parse.quote(o["id"], safe=""))
    dates = re.findall(r"\((\d{4}-\d{2}-\d{2})\)", b["brief"])
    check("proposed delivery dates exist", len(dates) > 0)
    check("they fall on a day a route serves (Tue / Thu / Fri for the Bassin)", all(dt.date.fromisoformat(d).weekday() in (1, 3, 4) for d in dates), str(dates))
    check("they are in the future and never a public holiday (no delivery on 25 December)", all(dt.date.fromisoformat(d) > today and d[5:] not in {"12-25", "01-01", "05-01", "07-14", "11-01", "11-11", "08-15"} for d in dates), str(dates))
    check("the brief tells the agent how to change the date", "update_order" in b["brief"])

ids = {m for o in opps for f in o["facts"] for m in re.findall(r"product_id : (prd_\d+)", f)}
check("every product id given to the agent exists", all(call("/products/" + i)[0] == 200 for i in ids))
s, e = call("/proactive/opportunities/does-not-exist")
check("an unknown mission is a 404", s == 404, str(s))

# ───────── the agent places the calls by itself ─────────
call("/proactive/autodial", "POST", {"enabled": False})  # the background loop must not interfere with the checks
call("/proactive/calls", "DELETE")
s, st = call("/proactive/autodial")
check("the agent's initiative can be paused", s == 200 and st["enabled"] is False)
s, d1 = call("/proactive/dispatch", "POST")
check("a cycle makes a call ring for the most urgent mission", s == 200 and d1["status"] == "ringing" and d1["call"]["opportunityId"] == opps[0]["id"], str(d1)[:120])
check("the ringing call carries the problem and the deadline", d1["call"]["title"] == opps[0]["title"] and d1["call"]["deadline"] == opps[0]["deadline"])
s, d2 = call("/proactive/dispatch", "POST")
check("it never rings two calls at once", d2["status"] == "nothing")
s, ringing = call("/proactive/calls?status=ringing")
check("the ringing call is in the journal", [c["id"] for c in ringing] == [d1["call"]["id"]])
first = d1["call"]
s, dec = call(f"/proactive/calls/{first['id']}/decline", "POST")
check("the client can decline", s == 200 and dec["status"] == "declined")
s, _x = call(f"/proactive/calls/{first['id']}/answer", "POST")
check("a call that no longer rings cannot be picked up (409)", s == 409, str(s))
s, d3 = call("/proactive/dispatch", "POST")
if len(opps) > 1:
    check("the next cycle calls someone else (a tried mission is not retried)", d3["status"] == "ringing" and d3["call"]["opportunityId"] != first["opportunityId"])
    second = d3["call"]
else:
    check("with a single mission, a declined one is not called again right away", d3["status"] == "nothing")
    second = None
if second:
    s, ans = call(f"/proactive/calls/{second['id']}/answer", "POST")
    check("picking up marks the call answered and gives the mission to open", s == 200 and ans["status"] == "answered" and ans["opportunityId"] == second["opportunityId"])
    check("an answered call has no outcome until the agent writes one", ans.get("outcome") is None)
    call(f"/clients/{second['clientId']}/events", "POST", {"type": "call", "title": "Appel proactif : le client attend le prochain arrivage", "description": "check_proactive"})
    s, journal = call("/proactive/calls")
    mine = next(c for c in journal if c["id"] == second["id"])
    check("the journal shows what was decided (the line the agent wrote in the client's history)", mine["outcome"] == "le client attend le prochain arrivage", str(mine.get("outcome")))
    s, d4 = call("/proactive/dispatch", "POST")
    check("a client already called today is not called again", d4["status"] == "nothing" or d4["call"]["clientId"] != second["clientId"])
    # the dedicated outcome route (tool record_call_outcome): stored on the call, ONE history line, updated (not duplicated) on a 2nd call
    s, out = call("/proactive/opportunities/" + urllib.parse.quote(second["opportunityId"], safe="") + "/outcome", "POST", {"decision": "Livraison décalée au jeudi 24.", "callId": second["id"]})
    check("record_call_outcome stores the decision on the call", s == 200 and out["call"]["outcome"] == "Livraison décalée au jeudi 24", str(out)[:160])
    s, out2 = call("/proactive/opportunities/" + urllib.parse.quote(second["opportunityId"], safe="") + "/outcome", "POST", {"decision": "Livraison décalée au jeudi 24, confirmée"})
    check("recording again updates the same history line (no duplicate)", s == 200 and out2["eventId"] == out["eventId"])
    s, evs = call(f"/clients/{second['clientId']}/events?type=call&limit=50")
    check("the history line reads « Appel proactif : <decision> »", any(e["id"] == out["eventId"] and e["title"] == "Appel proactif : Livraison décalée au jeudi 24, confirmée" for e in evs))
    s, bad = call("/proactive/opportunities/" + urllib.parse.quote(second["opportunityId"], safe="") + "/outcome", "POST", {"decision": "  "})
    check("an empty decision is refused", s == 400, str(s))
# pausing hangs up a call that is still ringing
call("/proactive/calls", "DELETE")
s, d5 = call("/proactive/dispatch", "POST")
if d5 and d5.get("status") == "ringing":
    call("/proactive/autodial", "POST", {"enabled": False})
    s, c5 = call(f"/proactive/calls/{d5['call']['id']}")
    check("pausing the agent cancels the call that was ringing", c5["status"] == "cancelled" and c5.get("note"), str(c5.get("status")))
s, st0 = call("/proactive/autodial")
check("the phone mode is exposed (simulator or twilio)", st0.get("phoneMode") in ("simulator", "twilio"))
s, _x = call("/proactive/calls/does-not-exist/answer", "POST")
check("an unknown call is a 404", s == 404, str(s))
s, st2 = call("/proactive/autodial")
check("the rules are exposed", st2["intervalSeconds"] > 0 and st2["ringSeconds"] > 0 and st2["cooldownSeconds"] > 0 and st2["minPriority"] >= 0)
call("/proactive/calls", "DELETE")
call("/proactive/autodial", "POST", {"enabled": True})  # leave the agent as it was
s, st3 = call("/proactive/autodial")
check("the agent can be resumed", st3["enabled"] is True)

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
