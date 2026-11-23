# ERP.md — the guide to the kit's ERP

> English translation of [ERP.md](ERP.md). The French original is the reference. UI labels are given in French
> (as they appear on screen) with an English gloss.

This file explains the kit's ERP: what it covers, how it works, how to use it (screen and API).
Everything written here is verified against the code. If in doubt, the code is authoritative:
`apps/backend/app/services/` (business rules), `apps/backend/app/schemas/domain.py` (data model).

The other docs, not to be confused:

| Doc | For |
|---|---|
| [BRIEF.en.md](BRIEF.en.md) | the challenge, the deliverables, the jury |
| [METIER.en.md](METIER.en.md) | the food wholesale trade and its vocabulary |
| [SETUP.en.md](SETUP.en.md) | step-by-step installation |
| [README.md](README.md) | architecture, configuration, commands |
| [AGENTS.md](AGENTS.md) | rules for coding agents |
| [apps/ai/README.md](apps/ai/README.md) | agent loop, tools, LLM/STT/TTS providers, voice WebSocket protocol |

---

## 1. What the ERP covers

A wholesaler (seafood, fruit and vegetables, dairy, groceries) sells to restaurants, fishmongers, canteens… and buys
from suppliers. The ERP tracks the whole flow, from order to payment.

```
SALES
 client ──▶ order (draft) ──confirm──▶ stock reservation + stop on a delivery run
                                   │
                                   ▼
                       picking (prepared, actual weights)
                                   │
                                   ▼
                  delivery (delivered): lots taken out FEFO
                                   │
                                   ▼
            invoice (FAC-…) ──▶ payment ──▶ allocation to invoices ──▶ receivables / aged balance

PURCHASING
 supplier ──▶ purchase order (draft) ──send──▶ sent ──receive──▶ receipt ──▶ lots (use-by = receipt date + shelf life)

AROUND IT
 prices (negotiated, rules, catalog) · client / supplier history · groups (tags) · context table
 live activity log (who did what: team, AI assistant, voice agent)
```

Three building blocks:

| Block | Where | Port |
|---|---|---|
| ERP API (FastAPI + SQLite) | `apps/backend` | 4000 (`/docs`, `/openapi.json`) |
| AI service (agent, chat, voice) | `apps/ai` | 4100 |
| Web (React) | `apps/web` | 5173 (proxy `/api` → 4000, `/ai` → 4100) |

Global web shortcuts: `⌘K` search and "Aller à" (Go to), `⌘J` AI assistant, `⌥ Space` (held) voice command,
`⌘B` or `⌘\` sidebar.

---

## 2. The pages (menu order)

Every page reads the ERP API. Filters are in the URL (you can share a filtered link).

### Accueil (Home) — `/`
- **Shows**: today's revenue, this month's revenue, today's orders, pre-orders to process, to deliver today, overdue
  unpaid invoices; revenue for the last 30 days; top 10 clients over 30 days; low stock; upcoming use-by dates; live
  activity.
- **Actions**: "Nouvelle commande" (New order); each row leads to its object.
- **API**: `GET /api/dashboard`, `GET /api/events/stream`.

### Commandes (Orders) — `/orders`
- **Shows**: sales orders (no., client, delivery date, lines, total, status), totals in the footer.
- **Filters**: status tabs (All, Pre-orders, Confirmed, Prepared, Delivered, Invoiced, Cancelled) with counters;
  search by no. / client; delivery date (Yesterday, Today, Tomorrow, or a date); channel; `?clientId=` filters by
  client.
- **Actions**: "Nouvelle commande" → choose the client → empty draft → order page.
- **API**: `GET /api/orders`, `POST /api/orders`.

### Commande (Order) — `/orders/:id`
- **Shows**: header bar (client, date, total excl. VAT, total incl. VAT, creation), alerts, editable lines, note;
  right column: client, usual basket, invoice, delivery run.
- **Lines**: quantity, price, note editable inline; available stock per line; ⓘ icon on the price = where this price
  comes from (Negotiated / Rule "…" / Catalog); "Alternatives" button = replacement products. After picking, the
  "préparé" (prepared) column receives the actual weights.
- **Actions**: Confirm → Prepare → Deliver → Invoice; Cancel (two clicks); "Voir la facture" (See the invoice).
- **API**: `GET /api/orders/{id}`, `PATCH /api/orders/{id}`, `POST|PATCH|DELETE /api/orders/{id}/lines…`,
  `POST /api/orders/{id}/confirm|prepare|deliver|invoice|cancel`, `GET /api/products/{id}/alternatives`,
  `GET /api/prices/resolve`, `GET /api/clients/{id}/usual`.

### Clients — `/clients`
- **Shows**: name, type, groups, zone, sales rep, outstanding, overdue, last order, status.
- **Filters**: search (name, code, city, contact), type, zone, group.
- **Actions**: "Nouveau client" (New client) (side panel; created with status `prospect`).
- **API**: `GET /api/clients`, `POST /api/clients`.

### Client — `/clients/:id`
- **Tabs**: Vue d'ensemble (Overview) · Historique (History) · Contexte (Context).
- **Overview**: KPIs (outstanding, overdue, credit limit, 30-day revenue, last order), recent orders, open invoices,
  usual basket, negotiated prices, information, contacts, CRM notes, recent history, groups.
- **Actions**: Block / Unblock, add a note, new event, new context entry.
- **API**: `GET /api/clients/{id}`, `PATCH /api/clients/{id}`, `POST /api/clients/{id}/notes`,
  `GET|POST /api/clients/{id}/events`, `GET /api/context/for?entityType=client&id=…`.

### Prix (Prices) — `/prices`
Four tabs:
- **Matrice** (Matrix): products × client groups (or up to 8 chosen clients). Each cell = resolved price; a click
  opens the details and lets you create a rule or a negotiated price. `GET /api/prices/grid`.
- **Règles** (Rules): list of price rules, create / edit in a panel with preview, delete.
  `GET|POST|PATCH|DELETE /api/price-rules`.
- **Prix négociés** (Negotiated prices): all client × product prices, inline editing, add, delete.
  `PUT|DELETE /api/clients/{id}/prices/{productId}`.
- **Simulateur** (Simulator): client + product + quantity (+ date) → price chosen, all the candidates and why each one
  was applied or not. `GET /api/prices/resolve`.

### Historique (History) — `/history`
- **Shows**: all of the company's client and supplier events, most recent first.
- **Filters**: Clients / Suppliers tabs; family (Complaints & quality, Returns & credit notes, Payments, Sales,
  Relationship, Notes); status; from / to; full-text search.
- **Actions**: "Marquer résolu" (Mark resolved) inline; link to the client / supplier.
- **API**: `GET /api/client-events`, `GET /api/supplier-events`, `PATCH /api/client-events/{id}`,
  `PATCH /api/supplier-events/{id}`.

### Produits (Products) — `/products` and `/products/:id`
- **List**: tabs per category; search by name / SKU / alternative name (alias); group. Price, cost, margin, stock,
  next use-by date. `GET /api/products?q=…&category=…&tag=…` (the text filter is called `q`, not `search`).
- **Detail page**: KPIs, lots in FEFO order, compared supplier prices, recent movements, 30-day sales, context;
  "Ajuster le stock" (Adjust stock) (panel). `GET /api/products/{id}`, `POST /api/stock/adjust`,
  `PATCH /api/products/{id}`.

### Stocks — `/stock`
- **Shows**: each product: physical, reserved, available, incoming, next use-by date, state.
- **Tabs**: All · Out of stock (available ≤ 0) · Low stock (dashboard rule, see §3.3) · Use-by soon (next use-by in
  2 days or less).
- **Actions**: click a row → panel with the lots and the adjustment.
- **API**: `GET /api/stock`, `GET /api/stock/movements`, `POST /api/stock/adjust`.

### Achats (Purchasing) — `/purchase-orders` and `/purchase-orders/:id`
- **List**: tabs All, Drafts, Sent, Partial, Received, Cancelled; search; expected date; supplier
  (`?supplierId=`). "Nouvelle commande d'achat" (New purchase order) → choose the supplier → empty draft.
- **Detail page**: editable lines (in draft), difference from the supplier's usual price, alerts, expected date,
  note, received lots; actions Send, Receive (line-by-line receiving mode, partial receipt possible), Cancel.
- **API**: `GET|POST /api/purchase-orders`, `GET|PATCH /api/purchase-orders/{id}`, lines,
  `POST /api/purchase-orders/{id}/send|receive|cancel`, `GET /api/suppliers/{id}/usual`.

### Fournisseurs (Suppliers) — `/suppliers` and `/suppliers/:id`
- **List**: name, city, categories, lead time, terms, minimum order. Filters: search, category, group.
- **Detail page** (tabs Overview · History · Context): info, contacts, supplier price list, purchase orders;
  "Commander" (Order) creates a purchase draft for this supplier.
- **API**: `GET /api/suppliers`, `GET|PATCH /api/suppliers/{id}`, `GET|POST /api/suppliers/{id}/events`.

### Encours (Receivables) — `/receivables`
- **Shows**: aged balance per client as of the business date; KPIs (outstanding, overdue, DSO, late clients); stacked
  bar per bucket (click = filter).
- **Filters**: search, group, sales rep, zone, "En retard uniquement" (Overdue only).
- **Client panel** (click on a row): open invoices, payments, open disputes, latest reminders; actions Record a
  payment, Record the reminder (creates a `late_payment` event), Block / Unblock, Client page.
- **API**: `GET /api/receivables`, `POST /api/payments`, `POST /api/clients/{id}/events`, `PATCH /api/clients/{id}`.

### Factures (Invoices) — `/invoices` and `/invoices/:id`
- **List**: tabs To pay, Overdue, Paid, All; search by no. / client; totals.
- **Detail page**: the invoice as a document (lines with VAT, totals), status, due date, linked orders, allocated
  payments, "Enregistrer un paiement" (Record a payment).
- **API**: `GET /api/invoices`, `GET /api/invoices/{id}`, `POST /api/payments`.

### Paiements (Payments) — `/payments`
- **Shows**: payments received. Filters: search (client, reference, invoice), payment method.
- **Actions**: record a payment, with manual or automatic allocation (oldest invoices first).
- **API**: `GET /api/payments`, `POST /api/payments`.

### Tournées (Delivery runs) — `/routes`
- **Tabs**: Today's runs · Definitions.
- **Today's runs**: date (Today, Tomorrow, Other); one card per run with stops, ETA, weight; Up / Down arrows to
  reorder; "Planifier" (Plan).
- **API**: `GET /api/routes`, `GET /api/route-runs?date=`, `POST /api/route-runs/plan`,
  `PATCH /api/route-runs/{id}/stops`.

### Assistant — `⌘J` (not a page)
Chat panel on the right. See §6.

### Voix (Voice) — `/voice`
Two modes (header, `?mode=command`): Appel (Call) and Commande (Command). See §6.

### Contexte (Context) — `/context`
- **Shows**: all context entries. Tabs: All, Company, Clients, Suppliers, Products, Departments.
- **Filters**: search, kind (`kind`), source, entity.
- **Actions**: click = edit panel (autosave); "Nouvelle fiche" (New entry). Entries written by the AI in purple.
- **API**: `GET|POST /api/context`, `GET|PATCH|DELETE /api/context/{id}`.

### Activité (Activity) — `/activity`
- **Shows**: the log of all writes, live. Tabs All · AI & voice · Team; filter by object.
- **API**: `GET /api/events`, `GET /api/events/stream`.

### Groupes (Groups) — `/groups`
- **Shows**: three columns (clients, products, suppliers); number of members per group.
- **Actions**: create a group; click = edit, add / remove members.
- **API**: `GET|POST /api/tags`, `PATCH|DELETE /api/tags/{scope}/{id}`, `PATCH /api/clients|products|suppliers/{id}`
  with `{tags}`.

---

## 3. Lifecycles and business rules

Errors always have the shape `{"error": {"code", "message"}}`. A forbidden transition returns
`409 invalid_transition`. Alerts (`warnings`) never block: they are recomputed on every read.

### 3.1 Sales orders

```
draft ──confirm──▶ confirmed ──prepare──▶ prepared ──deliver──▶ delivered ──invoice──▶ invoiced
  │                    │   └────────────deliver────────────────▲
  └──────cancel────────┴──────────cancel──────────┘ (from draft, confirmed, prepared)
```

| Action | From | Effect |
|---|---|---|
| `POST /api/orders` | — | Creates in `draft`. Each line's price is resolved (§3.4). Default `deliveryDate` = the client's next delivery day strictly after today (tomorrow if they have none). Default `source` = `voice_agent` if the actor is `voice_agent`, otherwise `manual`. |
| `PATCH /api/orders/{id}` | `draft`, `confirmed` | Delivery date, note. A confirmed order whose date changes moves to another delivery run. |
| Add / remove a line | `draft`, `confirmed` | Removing the last line of a confirmed order: `409 empty_order` (cancel instead). |
| Edit a line | `draft`, `confirmed`; in `prepared` only `preparedQty` and `note` | Changing `productId` recomputes the price. |
| `confirm` | `draft` | Requires ≥ 1 line (`409 empty_order`). Reserves the stock (computed, see §3.3). Puts the order on the delivery run of the client's zone on the delivery date. |
| `prepare` | `confirmed` | Records actual weights (`preparedQty`); an unlisted line = prepared as ordered. The total follows the actual weights. |
| `deliver` | `confirmed`, `prepared` | Takes the stock out of the lots FEFO (`sale` movements). If physical stock is short, the delivery still goes through and the log flags it. The run stop becomes `delivered`. |
| `invoice` | `delivered` | Creates an invoice (`issued`) and moves the order to `invoiced`. |
| `cancel` | `draft`, `confirmed`, `prepared` | The reservation disappears; the stop leaves its delivery run. |

A line: `productId`, `qty`, `unitPrice` (€ excl. VAT), `preparedQty`, `note` ("bien frais" — "nice and fresh"),
`substituteFor` (product replaced). The quantity that counts (stock, total, invoice) = `preparedQty` if known,
otherwise `qty`.

**Order alerts** (only in `draft`, `confirmed`, `prepared`):

| Code | Trigger |
|---|---|
| `client_blocked` | the client has status `blocked` |
| `credit_limit` | `creditLimit` > 0 and outstanding incl. VAT + this order incl. VAT > `creditLimit` |
| `no_route` | no delivery run for the client's zone runs on that weekday |
| `insufficient_stock` | available (not counting this order's reservation) < quantity ordered of the product |
| `expiring_soon` | the product's first FEFO lot expires no later than the day after delivery |
| `price_below_cost` | line price < the product's reference cost |

### 3.2 Purchase orders and receipts

```
draft ──send──▶ sent ──receive──▶ partially_received ──receive──▶ received
draft | sent | partially_received ──cancel──▶ cancelled   (lots already received stay in stock)
```

- Created in `draft`; lines optional. Default price = the supplier's price (`SupplierPrice`), otherwise the
  product's reference cost. Default `expectedDate` = today + the supplier's `leadTimeDays`.
- Lines editable in `draft` only; `expectedDate` and `note` in `draft` or `sent`.
- `send` requires ≥ 1 line (`409 empty_order`).
- `receive` (from `sent` or `partially_received`): `receivedQty` = quantity received **now**, added to what was
  already received. Without a body: everything still to be received. Each received line creates **a lot**:
  `receivedAt` = today, `expiresAt` = today + the product's `shelfLifeDays`, plus a `receipt` movement. Status
  `received` if all lines are complete, otherwise `partially_received`. Nothing received: `400 nothing_received`.

**Purchase alerts** (only in `draft`, `sent`):

| Code | Trigger |
|---|---|
| `below_min_order` | total excl. VAT < the supplier's `minOrderAmount` |
| `not_in_supplier_catalog` | the product has no price at this supplier |
| `price_above_usual` | line price > 110% of the supplier's usual price |

### 3.3 Stock

Stock is made of **lots** (`Lot`). A lot = one arrival of a product, with a use-by date (`expiresAt`).

| Quantity | Calculation |
|---|---|
| `onHand` (physical) | Σ `qtyRemaining` of the lots |
| `reserved` | Σ line quantities of `confirmed` and `prepared` orders |
| `available` | `onHand` − `reserved` |
| `incoming` | Σ (`qty` − `receivedQty`) of `sent` and `partially_received` purchases |
| `nextExpiry` | use-by date of the first lot still in stock |

- The reservation is not stored: it follows from the orders' status. Cancelling or delivering releases it.
- **FEFO** (first expired, first out): the lot that expires soonest goes out first (then the oldest received).
- **Adjustment** (`POST /api/stock/adjust`, `reason` = `adjustment` or `waste`): `qty` > 0 creates a new lot
  (use-by = today + shelf life); `qty` < 0 takes stock out FEFO. `waste` (loss) always takes out, whatever sign is
  sent.
- Movements (`StockMovement.reason`): `receipt`, `sale`, `adjustment`, `waste`, `return`.
- **Low stock** (dashboard): available ≤ 0, or available < 2 days of average sales (average over 14 days).
- **Use-by soon** (dashboard): lots in stock that expire in 2 days or less (already expired included).
- **Alternatives** (`GET /api/products/{id}/alternatives`): same category, active, available > 0, closest price
  first, 10 maximum.

### 3.4 Prices: who wins

Resolution order (`apps/backend/app/services/pricing.py`):

1. **Negotiated price** (`ClientPrice`, client × product): always wins.
2. **Price rule** (`PriceRule`): the most specific applicable rule wins. Specificity, from strongest to weakest:
   client + product > client + group/category > client + all products > client group + product >
   client group + group/category > client group + all products > all clients + product >
   all clients + group/category > all clients + all products.
   On a tie: highest `priority`, then the most recent.
   A rule applies if `active`, if the date is within `validFrom`…`validTo`, and if quantity ≥ `minQty`.
3. **List price** (`Product.price`).

A rule's methods: `fixed` (fixed price), `discount_pct` (% discount on the list price, between 0 and 100),
`markup_pct` (% markup on cost).

**See why a price was chosen**: `GET /api/prices/resolve?clientId=…&productId=…&qty=…[&date=…]` returns `price`,
`source` (`client_price` | `rule` | `list`), `ruleId`, `marginPct`, `explanation` (a sentence in French) and
`candidates`: each possible price, `applied`, and `reason` when it wasn't chosen ("règle inactive" — "inactive
rule", "à partir de 10 unités" — "from 10 units", "le prix négocié du client prime" — "the client's negotiated price
takes precedence"…). In the web: the ⓘ icon on an order line, or Prix → Simulateur.

A line's price is frozen when it is created. Changing a rule doesn't modify existing orders.

### 3.5 Credit, blocked clients, receivables risk

- `Client.status`: `active`, `blocked`, `prospect`. Blocking is manual (`PATCH /api/clients/{id}` with
  `{"status": "blocked"}`, Block button). A blocked client **can** still order: the ERP adds the `client_blocked`
  alert. It's up to the agent to decide what to say.
- `creditLimit`: authorized outstanding balance incl. VAT. `0` = no check.
- **Outstanding** (`outstanding`) = Σ (`totalTtc` − `amountPaid`) of open invoices. **Overdue** (`overdue`) = the
  part whose due date has passed.
- Aged balance **buckets** (days past due): `current` (not due), `d1_30`, `d31_60`, `d61_90`, `d90plus`.
- **Risk** (`GET /api/receivables`, field `risk`):

| Level | If at least one condition holds |
|---|---|
| `high` (Élevé) | client `blocked`; outstanding > `creditLimit` (if > 0); more than 60 days late; average payment delay > 60 days **and** something overdue |
| `watch` (À surveiller — to watch) | outstanding > 80% of the limit; more than 30 days late; an **open** `late_payment` event; average payment delay > 45 days |
| `ok` | otherwise |

- `avgDaysToPay`: paid invoices whose last payment is less than 90 days old (date of last payment − issue date).
- **DSO** = outstanding / revenue incl. VAT invoiced over 90 days × 90.
- Only clients with at least one open invoice appear in `/api/receivables`.

### 3.6 Invoices, payments, allocation

- An invoice is born from a delivered order (`POST /api/orders/{id}/invoice`). Lines = prepared quantities, VAT per
  product (`vatRate`, 0.055 for food). `issuedAt` = today; `dueDate` = today + the client's `paymentTermsDays`
  (0 = cash).
- Stored statuses: `issued`, `partially_paid`, `paid` (and `draft`, `cancelled`). `overdue` is **never stored**: it
  is computed on read (open invoice whose `dueDate` < today).
- `GET /api/invoices?status=open`: pseudo-status = all invoices with a balance.
- **Payment** (`POST /api/payments`): amount incl. VAT, `method` (`transfer`, `card`, `cheque`, `cash`,
  `direct_debit`).
  - Without `allocations`: allocated to open invoices **oldest first**; any excess stays unallocated.
  - With `allocations`: each invoice must belong to this client (`400 wrong_client`), each amount ≤ the invoice's
    balance, the sum ≤ the payment amount (`400 over_allocated`).
  - The invoice status follows: `paid` if balance ≤ 0, otherwise `partially_paid`.

### 3.7 Delivery runs

- A **route** (`Route`) serves a `zone` on certain days (`days`), with a departure time and a capacity.
- A **run** (`RouteRun`, `run_…`) = a route on a date. Status `planned` → `in_progress` (one stop delivered) →
  `done` (no stops pending).
- Confirming an order puts it on the run for the client's zone on its date (created if needed). If there is no route
  that day, the ERP still picks a route for the zone (and the order carries the `no_route` alert).
- `POST /api/route-runs/plan {date}`: places all `confirmed` / `prepared` orders for the date, adds new ones sorted
  by city then name, removes cancelled or moved stops.
- `PATCH /api/route-runs/{id}/stops {orderIds}`: these orders first, in this order; the others follow.
- A stop's ETA = departure time + 12 min × rank. Weight: a `box` ≈ 5 kg, any other unit ≈ 1 kg.

### 3.8 Client and supplier history

The long-term record of the relationship: complaints, returns, disputes, calls, visits, negotiations…

- **Client types** (`ClientEventType`): `onboarding`, `call`, `visit`, `complaint`, `quality_issue`,
  `delivery_issue`, `return`, `credit_note`, `dispute`, `late_payment`, `payment_plan`, `price_negotiation`,
  `special_request`, `menu_change`, `contact_change`, `compliment`, `churn_risk`, `won_back`, `note`.
- **Supplier types** (`SupplierEventType`): `onboarding`, `call`, `visit`, `quality_issue`, `delivery_issue`,
  `shortage`, `return`, `credit_note`, `dispute`, `price_change`, `price_negotiation`, `invoice_issue`, `payment`,
  `contract`, `certification`, `contact_change`, `compliment`, `note`.
- **Status** (`open` | `resolved`): "problem" types are created `open` automatically.
  Client: `complaint`, `quality_issue`, `delivery_issue`, `return`, `dispute`, `late_payment`, `churn_risk`.
  Supplier: `quality_issue`, `delivery_issue`, `shortage`, `return`, `dispute`, `invoice_issue`.
  The others have no status. Switching to `resolved` fills `resolvedAt`; switching back to `open` clears it.
- **Severity** (`severity`): `low`, `medium`, `high`.
- **Channel** (`channel`): `phone`, `email`, `whatsapp`, `visit`, `voice_agent`, `sms`, `other`. Defaults to
  `voice_agent` when the actor is the voice agent. Default author: the actor's name, otherwise "Équipe" (Team),
  "Assistant IA" (AI assistant), "Agent vocal" (Voice agent).
- Optional links: `orderId`, `invoiceId` (must belong to this client), `productIds`, `amount` (€), `tags`.
- `at`: now by default; a date alone = 09:00.
- Client page stats (`eventStats`): total, open, complaints over 12 months (`complaint`, `quality_issue`,
  `delivery_issue`), returns over 12 months.

### 3.9 Groups (tags)

- A group (`TagDef`) has an `id` (slug, unique per `scope`), a `scope` (`client`, `supplier`, `product`), a
  `label`, a color and a description.
- Entities carry group ids in their `tags` field. An undefined tag is rejected (`400 unknown_tag`).
- Price rules target a client group and / or a product group.
- Deleting a group removes it from all entities; rules that target it no longer apply.

### 3.10 The context table

What the agents need to know, as short, editable entries.

- An entry (`ContextEntry`, `ctx_…`) is attached via `entityType` + `entityId`:
  - `company`: no `entityId`;
  - `client`, `supplier`, `product`: an existing id (`cli_…`, `sup_…`, `prd_…`);
  - `category`: the id of a product category of your company (a list specific to each company:
    `GET /api/categories` → `[{id, label}]`).
- **Kinds** (`kind`): `policy` (rule), `procedure` (how to do / say it), `preference` (what they like), `fact`
  (context), `relationship` (the people), `pricing` (agreements), `logistics` (delivery, storage), `risk`
  (irritants, credit, churn risk).
- **Source** (`source`): `seed` (data pack), `user` (web), `ai_chat`, `voice_agent`. Set by the `x-actor` header on
  write.
- Search: `GET /api/context?q=…` accent-insensitive full text, ranked by relevance (title > tags and entity > body).
  Filters `entityType`, `entityId`, `kind`, `source`, `tag`; `limit` (default 100).
- **`GET /api/context/for?entityType=client&id=cli_0010`**: everything to load before talking about an entity.
  `entries` = its entries; `related` = linked entries (product → its category; supplier → its categories; any
  entity → the `company` or `category` entries whose text mentions its id).
- In addition to the table, the agent reads the `DATA_DIR/context/*.md` files on every turn (see
  `apps/ai/app/agent/prompts.py`).

---

## 4. Data model

Prefixed ids, amounts in euros excl. VAT except `*Ttc`, dates `YYYY-MM-DD`, full ISO timestamps. JSON in camelCase.
Source: `apps/backend/app/schemas/domain.py`.

| Entity | Id | Key fields |
|---|---|---|
| `Client` | `cli_0010` (code `C0010`) | `name`, `type`, `contacts`, `zone`, `deliveryDays`, `paymentTermsDays`, `creditLimit`, `status`, `salesRep`, `preferences`, `notes`, `tags` |
| `Product` | `prd_0015` | `sku`, `name`, `aliases` (what people say: "loup"), `category`, `unit` (`kg`, `piece`, `box`, `dozen`, `liter`), `price`, `cost`, `vatRate`, `shelfLifeDays`, `mainSupplierId`, `active`, `tags` |
| `Supplier` | `sup_0001` | `name`, `categories`, `leadTimeDays`, `paymentTermsDays`, `minOrderAmount`, `notes`, `tags` |
| `ClientPrice` | key client × product | `clientId`, `productId`, `price` |
| `SupplierPrice` | key supplier × product | `supplierId`, `productId`, `price`, `updatedAt` |
| `PriceRule` | `prl_0001` | `name`, `active`, `priority`, `clientScope`, `productScope`, `method`, `minQty`, `validFrom`, `validTo` |
| `Order` | `ord_002063`, no. `CMD-2026-016935` | `clientId`, `status`, `source`, `deliveryDate`, `routeRunId`, `totalHt`, `lines[]`, `invoiceId`, `createdBy` |
| `OrderLine` | `lin_…` | `productId`, `qty`, `unitPrice`, `preparedQty`, `note`, `substituteFor` |
| `PurchaseOrder` | `po_000697`, no. `ACH-2026-003650` | `supplierId`, `status`, `expectedDate`, `totalHt`, `lines[]` (`pol_…`: `qty`, `unitPrice`, `receivedQty`) |
| `Lot` | `lot_003273` | `productId`, `supplierId`, `purchaseOrderId`, `qtyReceived`, `qtyRemaining`, `receivedAt`, `expiresAt` |
| `StockMovement` | `mov_015840` | `productId`, `lotId`, `qty` (+ in, − out), `reason`, `refType`, `refId`, `note` |
| `Invoice` | `inv_001630`, no. `FAC-2026-011440` | `clientId`, `orderIds`, `status`, `issuedAt`, `dueDate`, `lines`, `totalHt`, `totalVat`, `totalTtc`, `amountPaid` |
| `Payment` | `pay_000545` | `clientId`, `amount` (incl. VAT), `method`, `receivedAt`, `reference`, `allocations[]` (`invoiceId`, `amount`) |
| `Route` | `rte_0001` | `name`, `zone`, `driver`, `vehicle`, `capacityKg`, `days`, `departureTime` |
| `RouteRun` | `run_000075` | `routeId`, `date`, `status`, `stops[]` (`orderId`, `clientId`, `seq`, `eta`, `status`) |
| `ClientEvent` | `cev_002017` | `clientId`, `at`, `type`, `title`, `description`, `channel`, `author`, `severity`, `status`, `resolution`, `orderId`, `invoiceId`, `productIds`, `amount` |
| `SupplierEvent` | `sev_000500` | same, with `supplierId` and `purchaseOrderId` |
| `TagDef` | slug (`gastro`, `premium`) | `scope`, `label`, `color`, `description` |
| `ContextEntry` | `ctx_0001` | `entityType`, `entityId`, `kind`, `title`, `body` (short markdown), `tags`, `source` |
| `ActivityEvent` | `evt_0000029` | `at`, `actor`, `actorName`, `type`, `entity`, `entityId`, `summary` |

Document numbers: `CMD-<year>-<6 digits>` (sale), `ACH-…` (purchase), `FAC-…` (invoice). The ids of new lines
(`lin_…`, `pol_…`) are random; all other ids continue the sequence.

---

## 5. The business clock and the activity feed

### The clock: `meta.today`
- The data is anchored on a fixed date: `GET /api/meta` → `{company, today, currency, generatedAt, trade, region}`
  (`trade` and `region`: the business and the area, shown in the sidebar).
- "Today", "tomorrow", "late", "overdue", "last 30 days" are **always** computed from `meta.today`, never from the
  real date.
- New records get the date `meta.today` and the real wall-clock time.
- The agent receives this date in its system prompt ("Aujourd'hui : mardi 24 novembre 2026" — "Today: Tuesday
  24 November 2026").

### The activity feed
- Every write adds an `ActivityEvent` (`type` such as `order.confirmed`, `payment.recorded`,
  `client_event.created`, `context.created`…) with a `summary` sentence in French.
- **Who writes**: header `x-actor` = `user` | `ai_chat` | `voice_agent` (unknown or missing value = `user`), plus
  optional `x-actor-name` (display name, URI-encoded). The web sends `user` / "Moi" (Me). The agent's tools send
  `ai_chat` (chat) or `voice_agent` (voice, voice command).
- **Live**: `GET /api/events/stream` (Server-Sent Events) sends `ready` once, then one `activity` event per
  committed write, and `ping` every 15 s. `GET /api/events?limit=50` = the history, most recent first.
- **Purple**: in the web, everything coming from `ai_chat` or `voice_agent` is tinted purple (Activity, Home, right
  column of the Voix page, context entries written by the AI, tool calls in the assistant).
- `make reset` clears the log.

---

## 6. The AI side of the ERP

### The three surfaces

| Surface | How | What it does | AI route |
|---|---|---|---|
| **Assistant** | `⌘J`, right panel on every page | Text chat with the agent (`chat` mode, light markdown). Tool calls are shown as purple lines with a link to the object. | `POST /ai/chat` (SSE) |
| **Voix · Appel** (Voice · Call) | `/voice` page | Phone call simulation: hold Space (or the big button) to speak as the client, release; the agent answers in text and audio (`voice` mode: 1–2 sentences, no ids, rounded numbers). Two-track timeline, per-turn latencies, the agent's writes live on the right. | `WS /ai/voice` |
| **Voix · Commande** (Voice · Command) | `/voice?mode=command` page, or `⌥ Space` held on any page (HUD), or the "Voix" button in the header | A salesperson drives the ERP by voice, one sentence at a time, without history (`command` mode: acts right away, answers in one sentence). If the sentence asks to *see* something ("montre", "ouvre", "affiche" — "show", "open", "display"…), the web navigates to the object's page. A short click on the button opens the HUD to type the command. | `POST /ai/command[?speak=1]` (SSE) |

The system prompt (`apps/ai/app/agent/prompts.py`) = base rules + mode rules + company and today's date + the
caller's name + all the `DATA_DIR/context/*.md` files. Detailed protocols: [apps/ai/README.md](apps/ai/README.md).

### The agent's tools

16 tools, in `apps/ai/app/tools/`. They call the ERP API with `x-actor`; they contain no business rules.
Up-to-date list: `GET http://localhost:4100/tools`.

| Tool | What it does | ERP route |
|---|---|---|
| `search` | Finds a client, product, supplier or order from what was said (fuzzy, accent-insensitive, aliases, filler words ignored) | `GET /api/search` |
| `get_client` | Client profile: status, terms, outstanding, preferences, notes, usual basket, open issues, last 5 events | `GET /api/clients/{id}` |
| `get_product_stock` | Available, incoming, next use-by date, list price | `GET /api/products/{id}` |
| `find_alternatives` | 5 replacement products in stock | `GET /api/products/{id}/alternatives` |
| `get_price` | Price for a client and a quantity, with the explanation; flags a better volume price | `GET /api/prices/resolve` |
| `search_context` | Searches the context entries (rules, procedures, habits…) | `GET /api/context` |
| `get_context` | All the context of a client, supplier, product or department | `GET /api/context/for` |
| `save_context` | Remembers a durable fact (preference, contact, constraint) | `POST /api/context` |
| `get_client_history` | A client's history, filterable by type | `GET /api/clients/{id}/events` |
| `log_client_event` | Records a complaint, a call, a request… | `POST /api/clients/{id}/events` |
| `get_supplier_history` | A supplier's history | `GET /api/suppliers/{id}/events` |
| `log_supplier_event` | Records a supplier event | `POST /api/suppliers/{id}/events` |
| `create_draft_order` | Creates a pre-order (`draft`) with or without lines | `POST /api/orders` |
| `add_order_line` | Adds a line to an order | `POST /api/orders/{id}/lines` |
| `confirm_order` | Confirms (after explicit agreement on the summary); returns the alerts | `POST /api/orders/{id}/confirm` |
| `get_order` | An order's details: lines, status, total, alerts | `GET /api/orders/{id}` |

What the agent **cannot** do today (no tool): edit or remove a line, cancel, prepare, deliver, invoice, record a
payment, manage purchasing, prices, stock, delivery runs. The routes exist in the API: one more tool is enough (see
[apps/ai/README.md, "Add a tool"](apps/ai/README.md#add-a-tool-about-10-lines)).

---

## 7. Step by step

In the API examples, `B=http://localhost:4000/api`. Add `-H 'x-actor: voice_agent'` to see the write in purple in
the web.

### 7.1 Taking an order end to end
**Web**
1. Commandes → "Nouvelle commande" → type the client → Enter. A draft opens.
2. Add the lines (product search, aliases included) or pick from the usual basket on the right.
3. Read the alerts, then Confirm. The stock is reserved, the order is on a delivery run.
4. Prepare (enter the actual weights if needed) → Deliver → Invoice.
5. On the invoice: "Enregistrer un paiement" (Record a payment).

**API**
```bash
curl -s -X POST $B/orders -H 'content-type: application/json' \
  -d '{"clientId":"cli_0010","lines":[{"productId":"prd_0015","qty":4,"note":"bien frais"}]}'   # → draft, ord_…
curl -s -X POST $B/orders/ord_…/confirm
curl -s -X POST $B/orders/ord_…/prepare -H 'content-type: application/json' \
  -d '{"lines":[{"lineId":"lin_…","preparedQty":4.3}]}'
curl -s -X POST $B/orders/ord_…/deliver
curl -s -X POST $B/orders/ord_…/invoice                                                       # → inv_…, FAC-…
curl -s -X POST $B/payments -H 'content-type: application/json' \
  -d '{"clientId":"cli_0010","amount":86.19,"method":"transfer"}'
```

### 7.2 Handling a stock-out with a replacement product
1. Check the client's notes and context first (some refuse any substitution):
   `GET $B/context/for?entityType=client&id=cli_…`.
2. On the order, an out-of-stock line carries `insufficient_stock`. The line's "Alternatives" button → "Remplacer"
   (Replace). Via the API: `GET $B/products/prd_…/alternatives`, then
   `PATCH $B/orders/ord_…/lines/lin_… {"productId":"prd_NEW","substituteFor":"prd_OLD"}`. The price is recomputed
   for the new product.
3. Possible in `draft` or `confirmed`.

### 7.3 Partially receiving a purchase order
1. Achats → the order (`sent` or `partially_received`) → Réceptionner (Receive) → enter the quantity received per
   line → confirm.
2. API: `POST $B/purchase-orders/po_…/receive {"lines":[{"lineId":"pol_…","receivedQty":6}]}`.
3. Result: one lot per received line (use-by = today + shelf life), status `partially_received` as long as something
   remains to be received. A second receipt adds to what was already received. What remains to be received counts in
   `incoming`.

### 7.4 Recording a complaint
1. Client page → Historique → "Nouvel événement" (New event) → type Réclamation (Complaint), title, description,
   severity, linked order or products.
2. API: `POST $B/clients/cli_…/events {"type":"complaint","title":"Raie pas fraîche","severity":"medium","orderId":"ord_…"}`
   ("Raie pas fraîche" = "Skate not fresh"). It is created `open`.
3. To close it: "Marquer résolu" (History) or
   `PATCH $B/client-events/cev_… {"status":"resolved","resolution":"Avoir de 20 €"}` ("€20 credit note").

### 7.5 Understanding why a client is blocked (or at risk)
1. `GET $B/clients/cli_…`: `status`, `creditLimit`, `outstanding`, `overdue`, `notes`, `recentEvents`, `openIssues`.
2. Encours → filter on the client → panel: buckets, open invoices, latest reminders, disputes, risk.
   API: `GET $B/receivables?q=<name>` (fields `risk`, `maxDaysOverdue`, `creditUsedPct`, `avgDaysToPay`,
   `openDisputes`, `lastReminderAt`).
3. The client's history, Payments filter: `GET $B/clients/cli_…/events?type=late_payment,payment_plan,dispute`.
4. The `blocked` status is set by hand: the `client.updated` event ("Client … bloqué" — "Client … blocked") in the
   log says when and by whom.

### 7.6 Setting a negotiated price
1. Prix → Prix négociés → "Nouveau prix négocié" (New negotiated price); or Matrice → click a client cell → "Fixer ce
   prix" (Set this price).
2. API: `PUT $B/clients/cli_…/prices/prd_… {"price":17.5}` (replaces it if it exists). Delete:
   `DELETE $B/clients/cli_…/prices/prd_…`.
3. Check: `GET $B/prices/resolve?clientId=cli_…&productId=prd_…` → `source: "client_price"`. Orders already created
   keep their old price.

### 7.7 Seeing what the agent knows about a client
1. Client page → Contexte tab (own entries + linked entries).
2. API: `GET $B/context/for?entityType=client&id=cli_…` (what the `get_context` tool loads), plus
   `GET $B/clients/cli_…` (what `get_client` returns).
3. What it learned during conversations: `GET $B/context?source=ai_chat,voice_agent`.
4. The company context always present in the prompt: `DATA_DIR/context/*.md`.

### 7.8 Resetting the data
`make reset` (= `POST /api/admin/reset`). Empties the database, reloads the data pack from `DATA_DIR`, clears the
log. All your writes are lost.

### 7.9 Your data
Your company's data is in `./data` (`DATA_DIR=./data` in `.env`). If you break it, `make reset` reloads it. Check:
`GET $B/meta` → `company` and `today`.

---

## 8. API cheat sheet

All routes are under `/api`. All writes accept `x-actor` and `x-actor-name`. Full schemas and live testing:
http://localhost:4000/docs.

**Lists (all GET routes that return a list).** Pagination, filters and sorting on the server side:
`limit` (default **100**, max **500**), `offset`, `sort` (a sortable field of the route, see `/docs`),
`order=asc|desc`. Response: a JSON **array** — the requested page, so **truncated to `limit`** — or, with
`envelope=1`, `{items, total, limit, offset, counts?, sums?, …}` where `total` says how many rows match the filters
and the extras (`counts` per status, `sums`…) cover the whole filtered set. An agent almost never needs everything:
filter (`clientId`, `status`, `date`, `q`…) and keep `limit` small. Details:
[TECH.en.md · Pagination](TECH.en.md#pagination).

```bash
curl -s 'localhost:4000/api/orders?clientId=cli_0012&limit=5'                       # the last 5 orders (array)
curl -s 'localhost:4000/api/invoices?status=overdue&sort=balance&order=desc&limit=10' # the 10 biggest overdue
curl -s 'localhost:4000/api/orders?status=delivered&envelope=1&limit=1' | jq .total   # how many delivered orders
```

**System**
| Method | Path | Role |
|---|---|---|
| GET | `/health` | `{ok, today}` |
| GET | `/meta` | company, business date |
| GET | `/dashboard` | home page KPIs |
| GET | `/search?q=&types=&limit=` | fuzzy search; `types` = `client,product,supplier,order` (+ `context` on request) |
| GET | `/events?actor=&entity=` | activity log (`actor=ai`: assistant + voice agent; default `limit` 50) |
| GET | `/events/stream` | live log (SSE) |
| POST | `/admin/reset` | reloads the data pack |

**Clients**
| Method | Path | Role |
|---|---|---|
| GET | `/clients?q=&type=&zone=&status=&tag=` | list with KPIs; `sort` = `name`, `outstanding`, `overdue`, `last`… |
| GET | `/clients/{id}` | full profile (negotiated prices, last 20 orders, open invoices, payments, usual, recent history) |
| GET | `/clients/{id}/usual` | usual basket (last 60 days) |
| POST | `/clients` | create |
| PATCH | `/clients/{id}` | modify (status, limit, tags…) |
| POST | `/clients/{id}/notes` | add a note `{text, author}` |
| GET / POST | `/clients/{id}/events?type=&status=&q=` | the client's history (`sort=open`: open cases first) / add an event |
| GET | `/client-events?type=&status=&clientId=&q=&from=&to=` | history across all clients, most recent first |
| PATCH | `/client-events/{id}` | modify, resolve |
| PUT / DELETE | `/clients/{id}/prices/{productId}` | negotiated price |

**Catalog, suppliers, stock**
| Method | Path | Role |
|---|---|---|
| GET | `/products?q=&category=&tag=&active=` | catalog with stock; `sort` = `name`, `price`, `margin`, `available`… |
| GET | `/products/{id}` | detail: stock, lots, supplier prices, movements, 30-day sales |
| GET | `/products/{id}/alternatives` | replacement products |
| PATCH | `/products/{id}` | price, cost, tags… |
| GET | `/suppliers?q=&category=&tag=` · `/suppliers/{id}` | suppliers (the detail embeds the last 60 purchase orders) |
| PATCH | `/suppliers/{id}` | modify |
| GET | `/suppliers/{id}/usual` | usual purchases (60 days) |
| GET / POST | `/suppliers/{id}/events` | supplier history |
| GET / PATCH | `/supplier-events` · `/supplier-events/{id}` | history across all suppliers / modify |
| GET | `/stock?q=&tab=` | stock levels (`tab` = `out`, `low`, `expiring`) |
| GET | `/stock/movements?productId=` | movements, most recent first |
| POST | `/stock/adjust` | adjustment or loss `{productId, qty, reason, note}` |

**Sales**
| Method | Path | Role |
|---|---|---|
| GET | `/orders?status=&clientId=&date=&q=&source=` | list, most recent delivery first (`status` = comma-separated list); `sort` = `date`, `number`, `total`, `client`… |
| GET | `/orders/{id}` | detail with alerts |
| POST | `/orders` | create a draft `{clientId, deliveryDate?, lines?, note?, source?}` |
| PATCH | `/orders/{id}` | delivery date, note |
| POST / PATCH / DELETE | `/orders/{id}/lines[/{lineId}]` | lines |
| POST | `/orders/{id}/confirm` · `/prepare` · `/deliver` · `/invoice` · `/cancel` | lifecycle |

**Purchasing**
| Method | Path | Role |
|---|---|---|
| GET | `/purchase-orders?status=&supplierId=&date=&q=` | list, most recent first |
| GET | `/purchase-orders/{id}` | detail with received lots and alerts |
| POST | `/purchase-orders` | create a draft `{supplierId, lines?, expectedDate?, note?}` |
| PATCH | `/purchase-orders/{id}` | expected date, note |
| POST / PATCH / DELETE | `/purchase-orders/{id}/lines[/{lineId}]` | lines (draft) |
| POST | `/purchase-orders/{id}/send` · `/receive` · `/cancel` | lifecycle |

**Invoicing**
| Method | Path | Role |
|---|---|---|
| GET | `/invoices?status=&clientId=&q=` | list without lines (`status=open` and `overdue` accepted); `sort` = `issued`, `due`, `balance`… |
| GET | `/invoices/{id}` | detail with payments |
| GET | `/payments?clientId=&method=&q=` | list, most recent first (`q`: client, reference or invoice no.) |
| POST | `/payments` | record `{clientId, amount, method, receivedAt?, reference?, allocations?}` |
| GET | `/receivables?q=&tag=&rep=&zone=&onlyOverdue=` | aged balance, risk, DSO |

**Prices and groups**
| Method | Path | Role |
|---|---|---|
| GET | `/prices/resolve?clientId=&productId=&qty=&date=` | price chosen and why |
| GET | `/prices/grid?clientId=` or `?clientTag=` (+ `productTag`, `category`, `q`) | price grid |
| GET / POST | `/price-rules` | rules (`active`, `clientId`, `productId` as filters) / create |
| PATCH / DELETE | `/price-rules/{id}` | modify / delete |
| GET / POST | `/tags?scope=` · `/tags` | groups with counters / create |
| PATCH / DELETE | `/tags/{scope}/{id}` | modify / delete |

**Logistics**
| Method | Path | Role |
|---|---|---|
| GET | `/routes` | delivery run definitions |
| GET | `/route-runs?date=&routeId=` | runs with stops, ETA, weight |
| POST | `/route-runs/plan` | plan a date `{date}` |
| PATCH | `/route-runs/{id}/stops` | reorder `{orderIds}` |

**Context**
| Method | Path | Role |
|---|---|---|
| GET | `/context?entityType=&entityId=&kind=&source=&tag=&q=` | search / list (by relevance with `q`) |
| GET | `/context/for?entityType=&id=` | all the context of an entity |
| GET / PATCH / DELETE | `/context/{id}` | one entry |
| POST | `/context` | create `{entityType, entityId?, kind, title, body, tags?}` |
