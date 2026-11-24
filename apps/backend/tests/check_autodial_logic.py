"""The agent's decision rules for placing a call by itself, with a simulated clock (no data, no network).

    docker exec -i -w /app/apps/backend <backend-container> python - < apps/backend/tests/check_autodial_logic.py
or, with the backend deps installed:  cd apps/backend && python tests/check_autodial_logic.py

Exit code 1 if a check fails.
"""

import os
import sys

sys.path.insert(0, os.getcwd())

from app.services.proactive import plan_dispatch  # noqa: E402

CFG = dict(ring_seconds=90, cooldown=45, retry_minutes=30, min_priority=50)
failures: list[str] = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        failures.append(name)


def opp(i, client, priority):
    return {"id": i, "clientId": client, "clientName": client, "type": "overdue", "title": "t", "reason": "r", "priority": priority}


def call(id_, opp_id, t, status="ringing", end=None):
    c = {"id": id_, "opportunityId": opp_id, "status": status, "_t": t}
    if end:
        c["_end"] = end
    return c


OPPS = [opp("a", "c1", 100), opp("b", "c2", 60), opp("c", "c3", 40)]

# nothing yet: it calls the most urgent
_, new = plan_dispatch([], OPPS, set(), 1000.0, CFG)
check("with nothing ringing it calls the most urgent opportunity", new and new["opportunityId"] == "a" and new["status"] == "ringing")

# one call at a time
_, new = plan_dispatch([call("x", "a", 1000.0)], OPPS, set(), 1030.0, CFG)
check("it never rings a second call while one is ringing", new is None)
_, new = plan_dispatch([call("x", "a", 1000.0)], OPPS, set(), 1030.0, CFG, force=True)
check("even a manual (forced) cycle does not ring two calls at once", new is None)

# a call nobody picks up is missed
changes, new = plan_dispatch([call("x", "a", 1000.0)], OPPS, set(), 1091.0, CFG)
check("a call nobody picks up within 90 s becomes missed", changes == [("x", "missed")])
check("...and the pause starts then: no new call right away", new is None)
_, new = plan_dispatch([call("x", "a", 1000.0, "missed", end=1091.0)], OPPS, set(), 1140.0, CFG)
check("after the pause it calls the next opportunity (the missed one is not retried)", new and new["opportunityId"] == "b")

# pause between calls
done = call("x", "a", 1000.0, "answered", end=1100.0)
_, new = plan_dispatch([done], OPPS, set(), 1120.0, CFG)
check("it waits 45 s after a call before the next one", new is None)
_, new = plan_dispatch([done], OPPS, set(), 1120.0, CFG, force=True)
check("a manual cycle skips only that pause", new and new["opportunityId"] == "b")

# urgency floor
_, new = plan_dispatch([call("x", "a", 0.0, "answered", end=1.0), call("y", "b", 0.0, "answered", end=1.0)], OPPS, set(), 1000.0, CFG)  # both urgent ones were just tried (within 30 min): only the priority-40 one is left
check("it never calls below the minimum urgency (priority 40 is left alone)", new is None)

# once a day per client
_, new = plan_dispatch([], OPPS, {"c1"}, 1000.0, CFG)
check("a client already called today is skipped", new and new["opportunityId"] == "b")
_, new = plan_dispatch([], OPPS, {"c1", "c2", "c3"}, 1000.0, CFG)
check("when everyone was called today it calls nobody", new is None)

# retry delay
tried = call("x", "a", 1000.0, "declined", end=1010.0)
_, new = plan_dispatch([tried], OPPS, set(), 1000.0 + 600, CFG)
check("an opportunity tried 10 minutes ago is not retried", new and new["opportunityId"] == "b")
_, new = plan_dispatch([tried], OPPS, set(), 1000.0 + 31 * 60, CFG)
check("...but it can be retried after 30 minutes", new and new["opportunityId"] == "a")

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'}")
sys.exit(1 if failures else 0)
