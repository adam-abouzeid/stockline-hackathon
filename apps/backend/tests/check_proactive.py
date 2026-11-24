"""Checks of /api/proactive against the running ERP (like check_predictions.py: plain asserts, no framework).
It writes ONE client-history line ("Appel proactif : test") and pauses/resumes the agent's autodial: run it on a throwaway ERP.

    API=http://localhost:4000 python apps/backend/tests/check_proactive.py

Exit code 1 if a check fails.
"""

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


s, opps = call("/proactive/opportunities")
check("opportunities answer", s == 200 and isinstance(opps, list) and len(opps) > 0, str(s))
check("most urgent first", [o["priority"] for o in opps] == sorted((o["priority"] for o in opps), reverse=True))
check("ids are unique", len({o["id"] for o in opps}) == len(opps))
check("every opportunity has a reason, facts and an objective", all(o["reason"] and o["facts"] and o["objective"] for o in opps))

# Only clients we can sell to are phoned
s, clients = call("/clients?limit=500")
status_of = {c["id"]: c["status"] for c in (clients if isinstance(clients, list) else clients["items"])}
check("only active clients are called (never blocked or prospects)", all(status_of.get(o["clientId"]) == "active" for o in opps))

# The real case of the data: a supplier shortage on an order already in progress
shortage = [o for o in opps if o["type"] == "shortage_order"]
check("a supplier shortage on a client's open order is found", len(shortage) > 0)
if shortage:
    o = shortage[0]
    check("the shortage order comes first (most urgent)", opps[0]["id"] == o["id"])
    s, b = call("/proactive/opportunities/" + urllib.parse.quote(o["id"], safe=""))
    check("the brief of one opportunity answers", s == 200 and "brief" in b, str(s))
    text = b["brief"]
    check("the ORDERED quantity is quoted, not the picked one (no '0 ×')", not re.search(r"(^|[^\d.,])0 × ", text), text[:0])
    check("the brief names the client id and the order id the agent needs", o["clientId"] in text and (o.get("orderId") or "?") in text)
    check("the brief lists the only facts the agent may quote", "FAITS VÉRIFIÉS" in text)
    check("the brief forbids invented promises, prices and unapproved substitutions", "INTERDIT" in text and "sans son accord" in text)
    check("the brief requires a recap and an explicit yes before any order", "accord explicite" in text and "« oui » clair" in text)
    check("a commercial's note about substitutions reaches the agent", "substitution" in text.lower())
    if "préparée" in " ".join(o["facts"]).lower():
        check("a prepared order is flagged as no longer editable", "DÉJÀ PRÉPARÉE" in text and "log_client_event" in text)

# Seasonal businesses that are closed in winter must not be called as 'overdue'
closed = {"La Cabane de l'Aiguillon", "Le Bistrot de la Dune", "La Guinguette du Port", "Le Kiosque de la Plage", "La Cabane à Huîtres", "Camping Les Platanes"}
check("closed seasonal businesses are not called 'overdue'", not any(o["type"] == "overdue" and o["clientName"] in closed for o in opps))

# Seasonal reminders: the house rule only for champagnes, and the product ids exist
for o in [x for x in opps if x["type"] == "seasonal"]:
    s, p = call("/products/" + o["productIds"][0])
    festive = any("10 décembre" in f for f in o["facts"])
    check(f"festive rule only on sparkling wines ({p['name'][:30]})", festive == (p["category"] == "bulles"), f"{p['category']} {festive}")
ids = {m for o in opps for f in o["facts"] for m in re.findall(r"product_id : (prd_\d+)", f)}
check("every product id given to the agent exists", all(call("/products/" + i)[0] == 200 for i in ids))

s, e = call("/proactive/opportunities/does-not-exist")
check("an unknown opportunity is a 404", s == 404, str(s))


# ───────── the agent places the calls by itself ─────────
call("/proactive/autodial", "POST", {"enabled": False})  # the background loop must not interfere with the checks
call("/proactive/calls", "DELETE")
s, st = call("/proactive/autodial")
check("the agent's initiative can be paused", s == 200 and st["enabled"] is False)
s, d1 = call("/proactive/dispatch", "POST")
check("a cycle makes a call ring for the most urgent opportunity", s == 200 and d1["status"] == "ringing" and d1["call"]["opportunityId"] == opps[0]["id"], str(d1)[:120])
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
check("the next cycle calls someone else (a tried opportunity is not retried)", d3["status"] == "ringing" and d3["call"]["opportunityId"] != first["opportunityId"])
second = d3["call"]
s, ans = call(f"/proactive/calls/{second['id']}/answer", "POST")
check("picking up marks the call answered and gives the opportunity to open", s == 200 and ans["status"] == "answered" and ans["opportunityId"] == second["opportunityId"])
s, _x = call("/proactive/calls/does-not-exist/answer", "POST")
check("an unknown call is a 404", s == 404, str(s))

# a client already phoned today (an "Appel proactif" line in its history) is not called again
tried = {first["opportunityId"], second["opportunityId"]}
skip = next((o for o in opps if o["id"] not in tried and o["priority"] >= st["minPriority"] and o["clientId"] not in {first["clientId"], second["clientId"]}), None)
if skip:
    call(f"/clients/{skip['clientId']}/events", "POST", {"type": "call", "title": "Appel proactif : test", "description": "check_proactive"})
    s, d4 = call("/proactive/dispatch", "POST")
    check("a client already called today is skipped", d4["status"] == "nothing" or d4["call"]["clientId"] != skip["clientId"], str(d4)[:120])
else:
    check("(skipped: no third client to test the daily limit)", True)

s, st2 = call("/proactive/autodial")
check("the rules are exposed", st2["intervalSeconds"] > 0 and st2["ringSeconds"] > 0 and st2["cooldownSeconds"] > 0 and st2["minPriority"] >= 0)
call("/proactive/calls", "DELETE")
call("/proactive/autodial", "POST", {"enabled": True})  # leave the agent as it was
s, st3 = call("/proactive/autodial")
check("the agent can be resumed", st3["enabled"] is True)

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
