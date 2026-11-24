"""
Proactive calls: the voice agent phones a client FIRST only when it has something that matters to tell it.

A call must serve the client: solve a problem on an order it already has, or give it a serious update. It never phones to sell
or to chase a usual order. The single trigger is therefore an open order (draft, confirmed or prepared) that cannot be delivered as
planned, for one of two reasons:

* stock      a line's product is in shortage (a supplier shortage is open, or the available stock does not cover the line)
* delivery   no route serves the client's zone on the delivery date (ERP warning `no_route`)

One order = one call, even if it has both problems. Everything is computed from the ERP data (no model, no training).
The agent never decides alone to act: it phones, explains, proposes, and applies what the client chooses with its usual tools
(draft -> recap -> explicit "yes"). The brief lists the only facts it may quote and what it must not promise.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import time
import uuid

from app import crud
from app.core.activity import today
from app.core.db import Doc
from app.core.errors import conflict, not_found
from app.core.utils import fr_day, to_date
from app.services.orders import order_warnings
from app.services.stock import stock_levels

OPEN_STATUSES = ("draft", "confirmed", "prepared")
ISSUE_HORIZON_DAYS = 30  # an order is looked at when its delivery is within this many days
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FIXED_HOLIDAYS = {"01-01", "05-01", "05-08", "07-14", "08-15", "11-01", "11-11", "12-25"}  # no delivery proposed on these days


def _open_orders(t: dt.date) -> list[Doc]:
    return [o for o in crud.orders.all() if o["status"] in OPEN_STATUSES and dt.date.fromisoformat(o["deliveryDate"][:10]) >= t]


def _open_shortages() -> dict[str, Doc]:
    """product -> the open supplier shortage that concerns it (newest wins)."""
    out: dict[str, Doc] = {}
    for ev in sorted(crud.supplier_events.all(), key=lambda e: e["at"]):
        if ev["type"] == "shortage" and ev.get("status") == "open":
            for pid in ev.get("productIds") or []:
                out[pid] = ev
    return out


def _contact(client: Doc) -> str | None:
    contacts = client.get("contacts") or []
    return contacts[0]["name"] if contacts else None


def _priority(days: int) -> int:
    """The closer the delivery, the more urgent the call."""
    return 100 if days <= 1 else 90 if days <= 3 else 75 if days <= 7 else 60 if days <= 14 else 50


def _deadline(days: int, delivery: str, status: str) -> str:
    when = "aujourd'hui" if days == 0 else "demain" if days == 1 else fr_day(delivery)
    if status == "prepared" and days <= 1:
        return f"Livraison {when} : à prévenir avant le départ du camion"
    return f"Livraison {when}"


def _route_days(client: Doc) -> list[str]:
    """The weekdays on which a route serves the client's zone."""
    days: set[str] = set()
    for r in crud.routes.all():
        if r.get("zone") == client.get("zone"):
            days.update(r.get("days") or [])
    return [d for d in WEEKDAYS if d in days]


def _next_route_dates(client: Doc, delivery: str, count: int = 3) -> list[str]:
    """The next days (from the requested date, up to 14 days) on which a route serves the zone."""
    served = set(_route_days(client))
    start = dt.date.fromisoformat(delivery[:10])
    out = []
    for k in range(-3, 15):
        d = start + dt.timedelta(days=k)
        if d > dt.date.fromisoformat(today()) and WEEKDAYS[d.weekday()] in served and d.strftime("%m-%d") not in FIXED_HOLIDAYS:
            out.append(d.isoformat())
    return out[:count] if out else []


def _order_issues(t: dt.date) -> list[Doc]:
    shortages = _open_shortages()
    out = []
    for o in _open_orders(t):
        client = crud.clients.get(o["clientId"])
        if not client or client["status"] != "active":
            continue
        delivery = o["deliveryDate"][:10]
        days = (dt.date.fromisoformat(delivery) - t).days
        if days > ISSUE_HORIZON_DAYS:
            continue
        stock_facts, product_ids, kinds = [], [], []
        levels = stock_levels(exclude_order_id=o["id"]) if o["status"] in ("draft", "confirmed") else {}
        for line in o["lines"]:
            pid, qty = line["productId"], line["qty"]
            product = crud.products.get(pid)
            if not product:
                continue
            event = shortages.get(pid)
            available = max(0, levels.get(pid, {}).get("available", 0))
            if event:
                supplier = crud.suppliers.get(event["supplierId"])
                stock_facts.append(f"{qty:g} × {product['name']} : rupture annoncée par {supplier['name'] if supplier else 'le fournisseur'} {fr_day(event['at'])} (« {event['title']} »). product_id : {pid}")
            elif o["status"] in ("draft", "confirmed") and available < qty:
                stock_facts.append(f"{qty:g} × {product['name']} : stock insuffisant, {available:g} disponible(s). product_id : {pid}")
            else:
                continue
            product_ids.append(pid)
        if stock_facts:
            kinds.append("stock")
        delivery_fact = None
        if o["status"] in ("draft", "confirmed"):
            route = next((w for w in order_warnings(o) if w["code"] == "no_route"), None)
            if route:
                kinds.append("delivery")
                options = _next_route_dates(client, delivery)
                days_served = ", ".join(WEEKDAYS_FR[WEEKDAYS.index(d)] for d in _route_days(client))
                delivery_fact = f"{route['message'].rstrip('.')}. Les tournées de sa zone passent le : {days_served}."
                if options:
                    delivery_fact += " Dates possibles : " + ", ".join(fr_day(d).removeprefix("le ") + f" ({d})" for d in options) + "."
        if not kinds:
            continue
        number = o["number"]
        first = crud.products.require(product_ids[0])["name"] if product_ids else None
        if kinds == ["stock"]:
            title = f"{first} indisponible : sa commande {number} est à adapter" + (f" (+{len(product_ids) - 1} autre(s))" if len(product_ids) > 1 else "")
            reason = f"Sa commande {number} contient un produit que nous ne pouvons pas lui livrer comme prévu."
        elif kinds == ["delivery"]:
            title = f"Aucune tournée le {fr_day(delivery).removeprefix('le ')} : livraison de {number} à décaler"
            reason = f"Sa commande {number} est demandée pour un jour où aucune tournée ne dessert sa zone."
        else:
            title = f"Commande {number} : livraison impossible à cette date et stock insuffisant"
            reason = f"Sa commande {number} est demandée un jour sans tournée, et un produit ne peut pas être livré comme prévu."
        facts = [f"Commande {number} (statut : {o['status']}), livraison demandée {fr_day(delivery).rstrip('.')}. order_id : {o['id']}"]
        facts += stock_facts + ([delivery_fact] if delivery_fact else [])
        if o["status"] == "prepared":
            facts.append("La commande est DÉJÀ PRÉPARÉE : tu ne peux plus la modifier toi-même (l'ERP le refuse).")
        steps = []
        if "stock" in kinds:
            steps.append("Lui dire quels produits manquent et trouver avec lui la solution : attendre, retirer la ligne, ou un produit équivalent (find_alternatives) SEULEMENT s'il est d'accord.")
        if "delivery" in kinds:
            steps.append("Lui dire qu'aucune tournée ne dessert sa zone ce jour-là et lui proposer les dates possibles ; s'il en choisit une, change la date avec update_order.")
        steps.append(
            "Comme la commande est déjà préparée, tu ne peux pas la changer toi-même : enregistre SA DÉCISION avec log_client_event pour que l'équipe l'applique, et ne dis jamais que c'est déjà fait."
            if o["status"] == "prepared" else "Applique ce qu'il décide avec tes outils (order_id ci-dessus), puis récapitule ce qui est modifié."
        )
        out.append({
            "id": f"order_issue~{client['id']}~{o['id']}", "type": "order_issue", "priority": _priority(days), "clientId": client["id"],
            "clientName": client["name"], "contactName": _contact(client), "title": title, "reason": reason, "facts": facts,
            "objective": " ".join(steps), "kinds": kinds, "deadline": _deadline(days, delivery, o["status"]), "productIds": product_ids, "orderId": o["id"],
        })  # fmt: skip
    return out


# ───────── public ─────────


def opportunities() -> list[Doc]:
    items = _order_issues(dt.date.fromisoformat(today()))
    items.sort(key=lambda o: (-o["priority"], o["clientName"]))
    return items


def _brief(opp: Doc, client: Doc) -> str:
    notes = [n["text"] for n in (client.get("notes") or [])[-3:]]
    contact = next(iter(client.get("contacts") or []), None)
    who = f"{contact['name']} ({contact.get('role', 'contact')})" if contact else "le contact habituel"
    lines = [
        "APPEL SORTANT : c'est TOI qui appelles ce client parce qu'il doit être prévenu d'un problème sur sa commande.",
        f"Client : {client['name']} (client_id : {client['id']}). Tu demandes {who}.",
        f"Préférences connues : {(client.get('preferences') or 'aucune').rstrip('. ')}.",
        *(f"Note d'un commercial : {n}" for n in notes),
        "",
        f"POURQUOI TU APPELLES : {opp['reason']}",
        "FAITS VÉRIFIÉS (tu ne cites QUE ces faits et ce que renvoient tes outils) :",
        *(f"- {f}" for f in opp["facts"]),
        "",
        f"ÉCHÉANCE : {opp['deadline'].rstrip('.')}.",
        f"CE QUE TU FAIS : {opp['objective']}",
        "",
        "COMMENT TU PROCÈDES :",
        "1. Ouvre en une ou deux phrases courtes : bonjour, qui tu es (le Comptoir des Chartrons), le problème, et demande s'il a une minute.",
        "2. S'il n'a pas le temps : dis l'essentiel en une phrase (le problème et ce qui est urgent) et conclus. Ne le retiens pas.",
        "3. Propose UNE solution à la fois, écoute, adapte-toi à ce qu'il dit.",
        "4. Toute modification passe par tes outils habituels. Après une modification, récapitule ce qui change. Tu ne confirmes une commande en brouillon que s'il dit « oui » clairement.",
        "5. Pour remplacer un produit, utilise find_alternatives et respecte ses préférences : seulement avec son accord explicite. Ajoute D'ABORD la nouvelle ligne (add_order_line avec substitute_for), PUIS retire l'ancienne (l'ERP refuse de retirer la dernière ligne d'une commande). Ne raconte jamais une erreur technique au client : corrige-la en silence.",
        f"6. En fin d'appel : enregistre D'ABORD le résultat avec log_client_event (client_id {client['id']}, type call, titre « Appel proactif : <ce qui a été décidé, en une phrase> », description courte), SANS rien dire avant, puis dis UNE seule phrase de conclusion. Dis « j'ai noté votre décision dans votre dossier » : jamais « j'ai transmis à l'équipe » ni « l'équipe va l'appliquer » (personne n'est prévenu automatiquement).",
        "INTERDIT : promettre une heure de livraison, un e-mail ou un rappel que tu ne peux pas assurer ; inventer un prix, un stock, une date ; proposer une remise ; changer un produit sans son accord ; parler d'autre chose que de ce problème (ne cite pas les alertes de l'ERP qui n'en font pas partie : date limite d'un lot, crédit, etc.).",
    ]
    return "\n".join(lines)


def opportunity_brief(opp_id: str) -> Doc:
    opp = next((o for o in opportunities() if o["id"] == opp_id), None)
    if not opp:
        raise not_found("Occasion d'appel", opp_id)
    return {**opp, "brief": _brief(opp, crud.clients.require(opp["clientId"]))}


# ───────── The agent decides to call by itself ─────────
#
# A background loop looks for the most urgent order issue and makes the call "ring" on the client's side; the agent speaks first
# when someone picks up. The decision is made by auditable rules, not by the model: one call at a time, a pause between calls,
# never below a minimum urgency, never the same client twice in a day (an "Appel proactif" line in its history), and an
# opportunity that was already tried is not retried for 30 minutes. Calls live in memory (a live journal, not records).

log = logging.getLogger("api")


def _env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


CONFIG: dict = {
    "enabled": os.environ.get("PROACTIVE_AUTODIAL", "1") != "0",
    "interval": _env("PROACTIVE_INTERVAL_SECONDS", 30),
    "ring_seconds": _env("PROACTIVE_RING_SECONDS", 90),
    "cooldown": _env("PROACTIVE_COOLDOWN_SECONDS", 45),
    "retry_minutes": 30,
    "min_priority": _env("PROACTIVE_MIN_PRIORITY", 50),
}
CALLS: list[Doc] = []  # newest first; keys starting with "_" are internal and never leave the API


def plan_dispatch(calls: list[Doc], opps: list[Doc], called_today: set[str], now: float, cfg: dict, force: bool = False) -> tuple[list[tuple[str, str]], Doc | None]:
    """Pure decision (testable without any data): (status changes to apply, the new call to place or None).
    `force` skips only the pause between calls (a manual cycle): never the one-call-at-a-time rule, the daily limit per client or the retry delay."""
    changes = [(c["id"], "missed") for c in calls if c["status"] == "ringing" and now - c["_t"] >= cfg["ring_seconds"]]
    expired = {cid for cid, _ in changes}
    if any(c["status"] == "ringing" and c["id"] not in expired for c in calls):
        return changes, None
    ends = [c["_end"] for c in calls if c.get("_end")] + [now for _ in expired]
    if not force and ends and now - max(ends) < cfg["cooldown"]:
        return changes, None
    recent = {c["opportunityId"] for c in calls if now - c["_t"] < cfg["retry_minutes"] * 60}
    for o in opps:  # most urgent first
        if o["priority"] < cfg["min_priority"]:
            break
        if o["clientId"] in called_today or o["id"] in recent:
            continue
        return changes, {
            "id": uuid.uuid4().hex[:12], "opportunityId": o["id"], "clientId": o["clientId"], "clientName": o["clientName"],
            "contactName": o.get("contactName"), "type": o["type"], "title": o["title"], "reason": o["reason"], "deadline": o.get("deadline", ""),
            "priority": o["priority"], "status": "ringing", "createdAt": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "_t": now,
        }  # fmt: skip
    return changes, None


def _called_today() -> set[str]:
    t = today()
    return {
        e["clientId"] for e in crud.client_events.all()
        if e["type"] == "call" and e["title"].startswith("Appel proactif") and to_date(e["at"]) == t
    }  # fmt: skip


def _last_event_id() -> str:
    return max((e["id"] for e in crud.client_events.all()), default="")


def dispatch_once(force: bool = False) -> Doc | None:
    now = time.time()
    changes, new = plan_dispatch(CALLS, opportunities(), _called_today(), now, CONFIG, force)
    for call_id, status in changes:
        _end(call_id, status, now)
    if new:
        CALLS.insert(0, new)
        del CALLS[100:]
        log.info("proactive: the agent is calling %s (%s)", new["clientName"], new["title"])
    return new


def _end(call_id: str, status: str, now: float) -> None:
    c = next(c for c in CALLS if c["id"] == call_id)
    c["status"], c["_end"] = status, now
    c["endedAt"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    if status == "answered":
        c["_mark"] = _last_event_id()  # the call's outcome is the first "Appel proactif" line written in the client's history after this


def _outcome(c: Doc) -> str | None:
    """What was decided: the title of the history line the agent wrote at the end of the call."""
    if c["status"] != "answered":
        return None
    for e in sorted(crud.client_events.all(), key=lambda e: e["id"]):
        if e["clientId"] == c["clientId"] and e["id"] > c.get("_mark", "") and e["type"] == "call" and e["title"].startswith("Appel proactif"):
            return e["title"].removeprefix("Appel proactif").lstrip(" :")
    return None


def calls(status: str | None = None) -> list[Doc]:
    now = time.time()
    for c in CALLS:  # a call nobody picks up is missed, even between two cycles of the loop
        if c["status"] == "ringing" and now - c["_t"] >= CONFIG["ring_seconds"]:
            _end(c["id"], "missed", now)
    return [{**c, "outcome": _outcome(c)} for c in CALLS if not status or c["status"] == status]


def answer_call(call_id: str, status: str = "answered") -> Doc:
    call = next((c for c in calls() if c["id"] == call_id), None)
    if not call:
        raise not_found("Appel", call_id)
    if call["status"] != "ringing":
        raise conflict("not_ringing", "Cet appel ne sonne plus")
    _end(call_id, status, time.time())
    return next(c for c in calls() if c["id"] == call_id)


def clear_calls() -> None:
    CALLS.clear()


def autodial_state() -> Doc:
    return {
        "enabled": CONFIG["enabled"], "intervalSeconds": CONFIG["interval"], "ringSeconds": CONFIG["ring_seconds"],
        "cooldownSeconds": CONFIG["cooldown"], "minPriority": CONFIG["min_priority"], "ringing": len(calls("ringing")),
    }  # fmt: skip


def set_autodial(enabled: bool) -> Doc:
    CONFIG["enabled"] = enabled
    return autodial_state()


async def autodial_loop() -> None:
    """Started with the API: every `interval` seconds, if enabled, the agent decides whether to place a call."""
    while True:
        await asyncio.sleep(CONFIG["interval"])
        if CONFIG["enabled"]:
            try:
                dispatch_once()
            except Exception:  # never let the loop die
                log.exception("proactive: dispatch failed")
