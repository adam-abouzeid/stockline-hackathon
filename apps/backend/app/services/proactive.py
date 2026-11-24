"""
Proactive calls: find the clients the agent should phone FIRST, and write the brief it is given for the call.

Four kinds of occasion, all computed from the ERP data (no model, no training):
* shortage_order     a supplier shortage is open on a product that a client already has on an open order
* shortage_heads_up  the same shortage, for clients who buy that product regularly (before they order it)
* overdue            a regular client late against its own ordering rhythm (not a seasonal business that is closed)
* seasonal           a demand peak is coming (season radar) for a product the client bought in the same weeks last year

The agent never decides alone to act: it phones, proposes, and any order goes through the usual draft -> recap ->
explicit "yes" flow. The brief lists the only facts it may quote and what it must not promise.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import statistics
import time
import uuid
from collections import defaultdict

from app import crud
from app.core.activity import today
from app.core.db import Doc, per_data_version
from app.core.errors import conflict, not_found
from app.core.utils import fr_day, to_date
from app.services.clients import is_sale
from app.services.predictions import season_radar
from app.services.stock import stock_levels

OPEN_STATUSES = ("draft", "confirmed", "prepared")
MIN_ORDERS_YEAR = 8  # a "regular" client has at least this many delivery days in the last 12 months
OVERDUE_FACTOR = 1.5  # late = longer than 1.5 x its typical gap (and at least 2 days more)
MAX_OVERDUE_DAYS = 60  # beyond that it is churn, not a forgotten order
SEASONAL_DAYS = 28  # a peak counts when its ramp week starts within this many days
BUYER_DAYS = 90
FESTIVE_RULE = "Règle de la maison : les réservations de fêtes (champagnes, coffrets) se prennent avant le 10 décembre."


@per_data_version
def _deliveries() -> dict[str, list[tuple[dt.date, Doc]]]:
    """client -> [(delivery date, order)] of every sale order, oldest first. Shared: never mutate."""
    out: dict[str, list[tuple[dt.date, Doc]]] = defaultdict(list)
    for o in crud.orders.all():
        if is_sale(o):
            out[o["clientId"]].append((dt.date.fromisoformat(o["deliveryDate"][:10]), o))
    for v in out.values():
        v.sort(key=lambda x: x[0])
    return out


def _open_orders(t: dt.date) -> dict[str, list[Doc]]:
    out: dict[str, list[Doc]] = defaultdict(list)
    for o in crud.orders.all():
        if o["status"] in OPEN_STATUSES and dt.date.fromisoformat(o["deliveryDate"][:10]) >= t:
            out[o["clientId"]].append(o)
    return out


def line_qty(line: Doc) -> float:
    """What the client ordered (not what was picked: an order short of stock has a picked quantity of 0)."""
    return line["qty"]


def _contact(client: Doc) -> str | None:
    contacts = client.get("contacts") or []
    return contacts[0]["name"] if contacts else None


def _product_label(pid: str) -> str:
    p = crud.products.get(pid)
    return p["name"] if p else pid


def _opp(type_: str, priority: int, client: Doc, key: str, title: str, reason: str, facts: list[str], objective: str, **extra) -> Doc:
    return {
        "id": f"{type_}~{client['id']}~{key}", "type": type_, "priority": priority, "clientId": client["id"],
        "clientName": client["name"], "contactName": _contact(client), "title": title, "reason": reason, "facts": facts,
        "objective": objective, "productIds": extra.get("productIds", []), **({"orderId": extra["orderId"]} if extra.get("orderId") else {}),
    }  # fmt: skip


# ───────── shortages ─────────


def _shortages(t: dt.date) -> list[Doc]:
    levels = stock_levels()
    open_orders = _open_orders(t)
    since = t - dt.timedelta(days=BUYER_DAYS)
    out = []
    for ev in crud.supplier_events.all():
        if ev["type"] != "shortage" or ev.get("status") != "open":
            continue
        supplier = crud.suppliers.get(ev["supplierId"])
        for pid in ev.get("productIds") or []:
            product = crud.products.get(pid)
            if not product:
                continue
            avail = levels.get(pid, {}).get("available", 0)
            head = f"Rupture annoncée par {supplier['name'] if supplier else 'le fournisseur'} {fr_day(ev['at'])} : « {ev['title']} »."
            stock_fact = f"Stock disponible de {product['name']} : {max(0, avail):g} {product['unit']}."
            affected = set()
            for cid, orders in open_orders.items():
                client = crud.clients.get(cid)
                if not client or client["status"] != "active":
                    continue
                for o in orders:
                    line = next((l for l in o["lines"] if l["productId"] == pid), None)
                    if line:
                        affected.add(cid)
                        locked = o["status"] == "prepared"  # the ERP no longer lets anyone edit a prepared order's lines
                        out.append(_opp(
                            "shortage_order", 100, client, o["id"],
                            f"Rupture de {product['name']} sur sa commande {o['number']}",
                            f"Sa commande {o['number']} contient {line_qty(line):g} × {product['name']}, que le fournisseur ne livre plus pour le moment.",
                            [head, stock_fact, f"Commande {o['number']} ({o['status']}), livraison prévue {fr_day(o['deliveryDate'])} : {line_qty(line):g} × {product['name']}.", f"order_id : {o['id']} ; product_id : {pid}",
                             *(["La commande est DÉJÀ PRÉPARÉE : tu ne peux plus la modifier toi-même (l'ERP le refuse)."] if locked else [])],
                            ("Le prévenir AVANT le départ du camion et écouter ce qu'il préfère (produit équivalent seulement s'il est d'accord, attendre, ou retirer la ligne). "
                             "Comme la commande est déjà préparée, tu ne peux pas la changer toi-même : enregistre SA DÉCISION avec log_client_event pour que l'équipe l'applique, et ne dis jamais que c'est déjà fait.")
                            if locked else "Le prévenir AVANT la livraison et trouver une solution avec lui (produit équivalent seulement s'il est d'accord, ou attendre, ou retirer la ligne) en modifiant la commande avec tes outils.",
                            productIds=[pid], orderId=o["id"],
                        ))  # fmt: skip
            counts: dict[str, int] = defaultdict(int)
            for cid, ds in _deliveries().items():
                for d, o in ds:
                    if since < d <= t and any(l["productId"] == pid for l in o["lines"]):
                        counts[cid] += 1
            for cid, n in sorted(counts.items(), key=lambda x: -x[1])[:3]:
                client = crud.clients.get(cid)
                if cid in affected or not client or client["status"] != "active" or n < 3:
                    continue
                out.append(_opp(
                    "shortage_heads_up", 60, client, pid, f"Prévenir de la rupture de {product['name']}",
                    f"Il achète régulièrement {product['name']} ({n} commandes ces {BUYER_DAYS} derniers jours) et il est en rupture chez le fournisseur.",
                    [head, stock_fact, f"{n} commandes de {product['name']} ces {BUYER_DAYS} derniers jours.", f"product_id : {pid}"],
                    "Le prévenir avant sa prochaine commande et lui proposer une alternative (il décide).",
                    productIds=[pid],
                ))  # fmt: skip
    return out


# ───────── overdue regulars ─────────


def _overdue(t: dt.date) -> list[Doc]:
    open_orders = _open_orders(t)
    out = []
    for client in crud.clients.all():
        if client["status"] != "active" or open_orders.get(client["id"]):
            continue
        ds = _deliveries().get(client["id"], [])
        days = sorted({d for d, _ in ds if d <= t and (t - d).days <= 365})
        if len(days) < MIN_ORDERS_YEAR:
            continue
        typical = statistics.median((b - a).days for a, b in zip(days, days[1:]))
        since = (t - days[-1]).days
        if not (since >= max(OVERDUE_FACTOR * typical, typical + 2) and since <= MAX_OVERDUE_DAYS):
            continue
        last_year = [d for d, _ in ds if t - dt.timedelta(days=364 + 28) < d <= t - dt.timedelta(days=364)]
        if len(last_year) < 2:
            continue  # it did not order at this time last year either: a seasonal business that is closed, not a forgotten order
        last = next(o for d, o in reversed(ds) if d == days[-1])
        lines = ", ".join(f"{line_qty(l):g} × {_product_label(l['productId'])}" for l in last["lines"][:4])
        delivery_days = ", ".join(client.get("deliveryDays") or [])
        out.append(_opp(
            "overdue", 70 + min(20, round(since / max(typical, 1) * 3)), client, "-", "Commande habituelle en retard",
            f"Il commande d'habitude tous les {typical:g} jours et sa dernière livraison date d'il y a {since} jours.",
            [f"Rythme habituel : une commande tous les {typical:g} jours (environ).", f"Dernière commande {last['number']} livrée {fr_day(last['deliveryDate'])}, il y a {since} jours : {lines}.",
             f"Jours de livraison habituels : {delivery_days}." if delivery_days else "", "Aucune commande en cours pour ce client."],
            "Prendre de ses nouvelles et lui proposer de reprendre « comme la dernière fois » (outil reorder_last_order), à ajuster selon ce qu'il dit.",
        ))  # fmt: skip
        out[-1]["facts"] = [f for f in out[-1]["facts"] if f]
    return out


# ───────── seasonal reminders ─────────


def _seasonal(t: dt.date) -> list[Doc]:
    out = []
    peaks = [p for p in season_radar(horizon_weeks=8)["peaks"] if p["daysUntilRamp"] <= SEASONAL_DAYS]
    peaks.sort(key=lambda p: -p["peakIndex"] * p["usualWeekQty"])
    for p in peaks[:4]:
        product = crud.products.get(p["productId"])
        ramp = dt.date.fromisoformat(p["rampWeekStart"])
        lo, hi = ramp - dt.timedelta(days=364 + 7), ramp - dt.timedelta(days=364) + dt.timedelta(days=35)
        bought: dict[str, float] = defaultdict(float)
        for cid, ds in _deliveries().items():
            for d, o in ds:
                if lo <= d <= hi:
                    bought[cid] += sum(line_qty(l) for l in o["lines"] if l["productId"] == p["productId"])
        for cid, qty in sorted(bought.items(), key=lambda x: -x[1])[:2]:
            client = crud.clients.get(cid)
            if qty <= 0 or not client or client["status"] != "active":
                continue
            facts = [
                f"La demande de {product['name']} devrait être environ ×{p['peakIndex']:g} à partir de la semaine du {fr_day(p['rampWeekStart']).removeprefix('le ')} (d'après les ventes des années passées).",
                f"L'an dernier à la même période, ce client avait pris {qty:g} {product['unit']} de {product['name']}.",
                f"Stock disponible : {p['available']:g} {product['unit']} (+ {p['incoming']:g} attendus des commandes fournisseurs confirmées).",
                f"product_id : {p['productId']}",
            ]
            if product["category"] == "bulles":
                facts.append(FESTIVE_RULE)
            out.append(_opp(
                "seasonal", 50 + min(10, round(p["peakIndex"])), client, p["productId"], f"Anticiper la saison : {product['name']}",
                f"{product['name']} va fortement monter et il en avait pris {qty:g} l'an dernier à cette période.",
                facts, "Lui rappeler la période à venir et lui proposer de préparer une commande (brouillon) maintenant, sans le presser.",
                productIds=[p["productId"]],
            ))  # fmt: skip
    return out


# ───────── public ─────────


def opportunities() -> list[Doc]:
    t = dt.date.fromisoformat(today())
    items = _shortages(t) + _overdue(t) + _seasonal(t)
    items.sort(key=lambda o: (-o["priority"], o["clientName"]))
    return items


def _brief(opp: Doc, client: Doc) -> str:
    notes = [n["text"] for n in (client.get("notes") or [])[-3:]]
    contact = next(iter(client.get("contacts") or []), None)
    who = f"{contact['name']} ({contact.get('role', 'contact')})" if contact else "le contact habituel"
    lines = [
        "APPEL SORTANT : c'est TOI qui appelles ce client, il n'a rien demandé.",
        f"Client : {client['name']} (client_id : {client['id']}). Tu demandes {who}.",
        f"Préférences connues : {(client.get('preferences') or 'aucune').rstrip('. ')}.",
        *(f"Note d'un commercial : {n}" for n in notes),
        "",
        f"POURQUOI TU APPELLES : {opp['reason']}",
        "FAITS VÉRIFIÉS (tu ne cites QUE ces faits et ce que renvoient tes outils) :",
        *(f"- {f}" for f in opp["facts"]),
        "",
        f"OBJECTIF : {opp['objective']}",
        "",
        "COMMENT TU PROCÈDES :",
        "1. Ouvre en une ou deux phrases courtes : bonjour, qui tu es (le Comptoir des Chartrons), la raison de l'appel, et demande s'il a une minute.",
        "2. S'il n'a pas le temps ou refuse : remercie, propose de rappeler plus tard s'il le souhaite, et conclus. N'insiste jamais.",
        "3. S'il accepte : fais UNE proposition à la fois, écoute, adapte-toi à ce qu'il dit.",
        "4. Toute commande ou modification passe par tes outils habituels : brouillon, récapitulatif, accord explicite avant de confirmer. Jamais de confirmation sans « oui » clair.",
        "5. Pour remplacer un produit, utilise find_alternatives et respecte ses préférences : seulement avec son accord explicite.",
        f"6. En fin d'appel, enregistre l'issue avec log_client_event (client_id {client['id']}, type call, titre « Appel proactif : … », description courte de ce qui a été dit et décidé).",
        "INTERDIT : promettre une heure de livraison, un e-mail ou un rappel que tu ne peux pas assurer ; inventer un prix, un stock, une date ; proposer une remise ; changer un produit sans son accord.",
    ]
    return "\n".join(lines)


def opportunity_brief(opp_id: str) -> Doc:
    opp = next((o for o in opportunities() if o["id"] == opp_id), None)
    if not opp:
        raise not_found("Occasion d'appel", opp_id)
    return {**opp, "brief": _brief(opp, crud.clients.require(opp["clientId"]))}


# ───────── The agent decides to call by itself ─────────
#
# A background loop looks for the most urgent opportunity and makes the call "ring" on the client's side; the agent speaks first
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
CALLS: list[Doc] = []  # newest first; keys starting with "_" are internal timestamps and never leave the API


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
            "contactName": o.get("contactName"), "type": o["type"], "title": o["title"], "reason": o["reason"],
            "priority": o["priority"], "status": "ringing", "createdAt": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "_t": now,
        }  # fmt: skip
    return changes, None


def _called_today() -> set[str]:
    t = today()
    return {
        e["clientId"] for e in crud.client_events.all()
        if e["type"] == "call" and e["title"].startswith("Appel proactif") and to_date(e["at"]) == t
    }  # fmt: skip


def dispatch_once(force: bool = False) -> Doc | None:
    now = time.time()
    changes, new = plan_dispatch(CALLS, opportunities(), _called_today(), now, CONFIG, force)
    for call_id, status in changes:
        _end(call_id, status, now)
    if new:
        CALLS.insert(0, new)
        del CALLS[100:]
        log.info("proactive: the agent is calling %s (%s)", new["clientName"], new["type"])
    return new


def _end(call_id: str, status: str, now: float) -> None:
    c = next(c for c in CALLS if c["id"] == call_id)
    c["status"], c["_end"] = status, now
    c["endedAt"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def calls(status: str | None = None) -> list[Doc]:
    now = time.time()
    for c in CALLS:  # a call nobody picks up is missed, even between two cycles of the loop
        if c["status"] == "ringing" and now - c["_t"] >= CONFIG["ring_seconds"]:
            _end(c["id"], "missed", now)
    return [c for c in CALLS if not status or c["status"] == status]


def answer_call(call_id: str, status: str = "answered") -> Doc:
    call = next((c for c in calls() if c["id"] == call_id), None)
    if not call:
        raise not_found("Appel", call_id)
    if call["status"] != "ringing":
        raise conflict("not_ringing", "Cet appel ne sonne plus")
    _end(call_id, status, time.time())
    return call


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
