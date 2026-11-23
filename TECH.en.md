# TECH.md — the kit's technical guide

> English translation of [TECH.md](TECH.md). The French original is the reference. Code is unchanged; only code
> comments are translated. `file:line` references point to the original code.

How **everything** works, and how to extend it. For engineers and their coding agents. Every name, path and route
cited here exists in the code; the `file:line` references point to the excerpts.

What this guide doesn't repeat: installation ([SETUP.en.md](SETUP.en.md)), the challenge ([BRIEF.en.md](BRIEF.en.md)),
the trade ([METIER.en.md](METIER.en.md)), how the ERP works functionally, its pages and rules
([ERP.en.md](ERP.en.md)), the configuration summary ([README.md](README.md)), the rules for coding agents
([AGENTS.md](AGENTS.md)), the design system ([DESIGN.md](DESIGN.md)), the AI service summary
([apps/ai/README.md](apps/ai/README.md)).

## Contents

1. [Overview: 3 services, 4 flows](#vue-ensemble)
2. [ERP backend](#backend)
3. [Endpoint reference](#endpoints)
4. [AI service](#service-ia)
5. [Tools (`@tool`) in detail](#outils)
6. [Frontend](#frontend)
7. [Data](#donnees)
8. [Tests and quality](#tests)
9. [Known pitfalls and limits](#pieges)

## I want… → where to look

| I want… | Section | Files |
|---|---|---|
| to understand a voice call end to end | [1.3](#parcours-voix) | `apps/web/src/features/assistant/useVoiceSession.ts`, `apps/ai/app/services/voice_session.py`, `apps/ai/app/agent/loop.py` |
| to add a tool to the agent | [5](#outils) | `apps/ai/app/tools/registry.py`, `apps/ai/app/tools/*.py`, `apps/ai/app/tools/__init__.py` |
| to add a composite tool (several ERP calls) | [5.4](#outil-composite) | `apps/ai/app/tools/catalog.py` (template), `apps/ai/app/tools/erp.py` |
| to change model, STT or TTS | [4.1](#config-ia) | `.env`, `apps/ai/app/clients/factory.py` |
| to add an LLM / STT / TTS provider | [4.2](#clients) | `apps/ai/app/clients/base.py`, `apps/ai/app/clients/factory.py` |
| to transcribe while the caller speaks | [Live transcription](#stt-direct) | `apps/ai/app/services/utterance.py`, `apps/ai/app/services/vocabulary.py`, `apps/ai/app/clients/soniox.py` |
| to reduce latency | [4.5](#latence), [9](#pieges) | `apps/ai/app/services/voice_session.py`, `apps/ai/app/clients/*`, `apps/ai/app/agent/prompts.py`, `apps/ai/app/tools/erp.py` |
| to change what the model reads (prompt) | [4.3](#prompts) | `apps/ai/app/agent/prompts.py`, `DATA_DIR/context/*.md` |
| to modify the agent loop | [4.4](#boucle) | `apps/ai/app/agent/loop.py` |
| to add an endpoint to the ERP | [2.6](#ajouter-endpoint) | `apps/backend/app/schemas/inputs.py`, `services/`, `routers/`, `packages/shared/src/`, `apps/web/src/lib/api.ts` |
| to change a business rule (price, stock, credit) | [2](#backend) | `apps/backend/app/services/*.py` |
| to modify or add a page | [6.6](#ajouter-page) | `apps/web/src/pages/`, `apps/web/src/app/routes.tsx`, `apps/web/src/app/nav.ts` |
| the UI to update when the agent writes | [6.4](#live) | `apps/web/src/lib/queries.ts` (`INVALIDATE`) |
| to modify the chat, the Voix page or ⌥Space | [6.5](#surfaces-ia) | `apps/web/src/features/assistant/`, `apps/web/src/features/voice-command/`, `apps/web/src/pages/voice/` |
| to test a tool without the UI | [8](#tester-sans-ui) | `make chat`, `curl /chat`, `apps/ai/tests/` |
| to reset the data | [7](#donnees) | `make reset` → `apps/backend/app/core/datapack.py` |
| to use Jev (fast decisions) | [4.7](#jev) | `apps/ai/app/clients/jev.py`, `apps/ai/app/agent/jev_examples.py` |

Each section follows the same outline: **What it is** (2–3 lines), **Key files**, **How it works**, **Extending**,
**Pitfalls**.

---

<a id="vue-ensemble"></a>
## 1. Overview: 3 services, 4 flows

### What it is

Three processes: the ERP (`apps/backend`, port 4000), the AI service (`apps/ai`, port 4100) and the web
(`apps/web`, port 5173). The AI service is **an HTTP client of the ERP like any other**: every business rule lives
in the ERP.

### Key files

- `docker-compose.yml`: the 3 services, the volumes (code mounted live, `DATA_DIR` read-only, database in the
  `erp-db` volume).
- `scripts/dev.sh`: the same thing without Docker (`uvicorn --reload` ×2 + `vite`).
- `apps/web/vite.config.ts:24-29`: the proxy `/api` → ERP, `/ai` → AI, `/ai/voice` → AI WebSocket.
- `Makefile`: all the commands (`make help`).

### How it works

```
 browser :5173 (React)
   │  /api/*  (fetch, x-actor: user)            ┌──────────────────────────────────────┐
   ├──────────────────────────────────────────▶ │ ERP  apps/backend  :4000             │
   │  /api/events/stream (SSE, ActivityEvent) ◀─┤ routers → services → crud → db       │
   │                                            │ memory + SQLite (write-through)      │
   │  /ai/chat (SSE)   /ai/command (SSE)        └──────────────────────────────────────┘
   │  /ai/voice (WebSocket)                                   ▲ HTTP /api/*
   ▼                                                          │ x-actor: ai_chat | voice_agent
 ┌─────────────────────────────────────────┐                  │
 │ AI  apps/ai  :4100                      │──────────────────┘ (each tool = 1+ HTTP call)
 │ routers → services → agent/loop → tools │
 │ clients/: LLM · STT · TTS · Jev         │────▶ providers (OpenAI, Anthropic, Gemini,
 └─────────────────────────────────────────┘      Soniox, Deepgram, ElevenLabs, Gradium) or mocks
```

Ports and URLs: `WEB_PORT`, `API_PORT`, `AI_PORT` in `.env`. In Docker, the AI reaches the ERP at
`http://backend:4000` and Vite proxies to `backend` / `ai` (`VITE_API_TARGET`, `VITE_AI_TARGET`). Locally,
`ERP_API_URL=http://localhost:4000`.

<a id="parcours-clic"></a>
#### 1.1 A click in the UI (e.g. "Confirmer" an order)

```
Button → useApiMutation(api.orders.confirm)            apps/web/src/lib/queries.ts:205
  → fetch POST /api/orders/{id}/confirm                 apps/web/src/lib/api.ts:47 (x-actor: user, x-actor-name: Moi)
  → Vite proxy → ERP router confirm_order               apps/backend/app/routers/orders.py:58
  → get_ctx() reads x-actor → Ctx(actor="user")         apps/backend/app/dependencies.py:20
  → services.orders.confirm_order (@transactional)      apps/backend/app/services/orders.py:273
      crud.orders.put(...)  → memory + SQLite
      log_event(ctx, "order.confirmed", …)              apps/backend/app/core/activity.py:71
  → COMMIT → bus.publish(ev) → SSE "activity" to all tabs
  → OrderDetail response (with warnings) → toast + react-query invalidations
```

<a id="parcours-chat"></a>
#### 1.2 A message in the assistant (⌘J)

```
chat.send(text)                                       apps/web/src/features/assistant/chat-store.ts:67
  → POST /ai/chat {messages: full history + new one, mode:"chat"}          ai-client.ts:38
  → routers/chat.py:16 → run_agent(messages, mode="chat")                 apps/ai/app/agent/loop.py:41
      build_system_prompt("chat")  (rules + business date + DATA_DIR/context/*.md)
      LLM.stream → text… / tool_call…
      tools in parallel → ErpClient("ai_chat") → /api/*                   apps/ai/app/tools/erp.py:44
      … until an answer without a tool call (max AGENT_MAX_STEPS=8)
  ← SSE: text · tool_call · tool_result · done | error   (one data: JSON line per event)
  → TurnRecorder rebuilds the assistant/tool messages     ai-client.ts:82
  → the history stays in the browser and is resent in full on the next turn
```

<a id="parcours-voix"></a>
#### 1.3 A push-to-talk voice turn (Voix page) end to end

```
BROWSER (useVoiceSession.ts)                   AI SERVICE (voice_session.py)                         ERP
ws = new WebSocket(/ai/voice)          :192
onopen → {type:"start", sessionId, actorName:"Agent vocal"} ──▶ open() → ReadyMessage {sessionId, stt, tts, llm}
Space pressed:
  MediaRecorder(webm/opus).start(100)
  {type:"audio_start", mime}           ──▶ interrupt() (barge-in), recording = Utterance(...)  → STT stream opened
  binary frames every 100 ms           ──▶ utterance.feed(frame) → sent to the STT right away
                                      ◀── transcript {final:false, text, stable}  (live text, grey/italic)
Space released:
  {type:"audio_end"}                   ──▶ start_turn(utterance) → asyncio.Task run_turn()
                                           1. STT: await utterance.text()  (finalize: only the last words)
                                      ◀── transcript {track:"caller", text, final:true}
                                           2. run_agent(working, mode="voice")                   :190
                                      ◀── agent_text {delta}  (each delta)
                                           Speaker.push(delta) → sentence done? → TTS queue      :241
                                      ◀── agent_tool {name, args}   …tool → HTTP ───────────────▶ /api/*
                                      ◀── agent_tool {name, ok, ms}                 ◀── JSON ── (log_event → SSE)
                                           TTS worker: synthesize(sentence) streaming            :273
                                      ◀── agent_audio_start {mime}  (once per turn)
                                      ◀── mp3 audio bytes (binary), sentence after sentence
                                           3. speaker.finish() → rest of the buffer              :208
                                      ◀── agent_audio_end
                                      ◀── agent_done {text, timings}
SegmentPlayer (MediaSource) plays the mp3 from the first byte; mock mime → speechSynthesis fr-FR
In parallel, the tab receives ActivityEvents through /api/events/stream → right column, purple lines.
```

`timings` (`apps/ai/app/schemas/chat.py:55`): `sttMs`, `llmFirstTokenMs`, `llmTotalMs`, `ttsFirstByteMs`,
`totalMs` = end of speech → the agent's first audio byte. The browser adds `perceivedMs` (release → audio played).

**Barge-in**: a new `audio_start` or `text` during a turn calls `interrupt()` (`voice_session.py:158`): the task is
cancelled, the running TTS is closed (`aclosing`), what was heard and said is kept in the history with "…".

<a id="parcours-commande"></a>
#### 1.4 An ⌥Space command

```
⌥Space held (VoiceCommand.tsx:28) → MediaRecorder (100 ms frames) → WS /ai/voice/command?speak=1
  ← transcript {final:false} during speech (live text in the HUD) → released → audio_end
  (typed command: POST /ai/command?speak=1, JSON {text}, SSE response)
  → services/command.py:73 run_command
      STT → TranscriptEvent
      run_agent([a single user message], mode="command")   (no history)
      ToolResultEvent → entity_of(result) remembers the last entity seen
      if the sentence contains montre/affiche/ouvre/voir… → NavigateEvent {path:"/products/prd_…"}   :40, :121
      speak=1 → TTS of the whole answer → SpeechEvent (base64)
      DoneEvent {timings}
  ← SSE: transcript · text · tool_call · tool_result · navigate? · speech? · done | error
  → the web navigates (except on /voice) and plays the audio
```

<a id="activite"></a>
#### 1.5 The activity feed and `x-actor`

- Every ERP write calls `log_event(ctx, type, entity, entity_id, summary)` in the service (`core/activity.py:71`).
  The event is published on the bus **after the COMMIT** (`on_commit`, `core/db.py:153`).
- `GET /api/events/stream` (`routers/system.py:54`): `event: ready` once, then `event: activity` + JSON per write,
  `event: ping` every 15 s.
- The actor comes from the `x-actor` header (`user` | `ai_chat` | `voice_agent`, otherwise `user`) and the optional
  name `x-actor-name` (URI-encoded): `dependencies.py:20-26`. The web sends `user`/"Moi"; the AI tools send
  `ai_chat` (chat mode) or `voice_agent` (voice and command modes): `agent/loop.py:51-52`.
- On the web side, `useActivityStream()` (mounted once in `AppShell`) invalidates the queries of the touched entity
  and flashes the row in purple (`lib/queries.ts:259-299`).

### Pitfalls

- The AI service has no database: everything it "knows" comes from the ERP or the prompt.
- The agent's writes are **not** cancelled by a barge-in: an HTTP call that has already gone out stays done.

---

<a id="backend"></a>
## 2. ERP backend (`apps/backend/app`)

### What it is

A FastAPI JSON API under `/api`. The data is JSON documents (camelCase) kept in memory and written to SQLite at the
same time. Business rules are in `services/`.

### Key files

| File | Role |
|---|---|
| `main.py` | FastAPI app, loading at startup (`lifespan`, `:44`), list of routers (`:72`), error format (`:97-154`), cleaned-up OpenAPI (`:160-196`) |
| `dependencies.py` | `get_ctx` / `CtxDep` (actor), `data(body)`, `iso_date_query`, `ERROR_RESPONSES` |
| `core/listing.py` | paginated lists: `ListDep` (`limit`, `offset`, `sort`, `order`, `envelope`), `apply_sort`, `respond`, `Page[T]` ([Pagination](#pagination)) |
| `core/config.py` | `DATA_DIR`, `SEED_DIR`, `DB_PATH`, `API_PORT` (reads the root `.env`) |
| `core/db.py` | `JsonTable`, `transaction()` / `@transactional`, `on_commit`, `get_meta`, id sequences, `@per_data_version` (aggregate cache invalidated on every write) |
| `core/datapack.py` | reading the pack (`DATA_DIR/seed/*.json`), `reset_from_pack()` |
| `core/activity.py` | `Ctx`, `today()` / `now()` (business clock), `EventBus`, `log_event`, `list_events` |
| `core/errors.py` | `HttpError`, `not_found`, `bad_request`, `conflict`, `validation_error` |
| `crud/__init__.py`, `crud/base.py` | one `CRUDBase` per table (`crud.orders`, `crud.clients`…), `PACK` (seed file → table) |
| `schemas/domain.py` · `views.py` · `inputs.py` | stored entities · computed responses · request bodies |
| `routers/*.py` | thin routes, one per resource |
| `services/*.py` | business rules, one per domain |

### How it works

**Layers** — each layer only calls the one below:

```
routers/orders.py      parses the request (camelCase Query alias, Input body), injects ctx: CtxDep, declares response_model
   ↓
services/orders.py     business rules, @transactional, log_event(...); returns dicts (Doc)
   ↓
crud (crud.orders)     get / require (404) / all / filter / put / delete / next_id / next_number
   ↓
core/db.py JsonTable   rows: in-memory dict  +  SQLite (id TEXT PRIMARY KEY, data TEXT JSON)
```

Real example, creating an order:

```python
# apps/backend/app/routers/orders.py:31-34
@router.post("", response_model=OrderDetail, status_code=201)
async def create_order(body: OrderInput, ctx: CtxDep):
    """Draft order; line prices resolved (client price > rules > list price)."""
    return orders.create_order(ctx, body.data())
```

```python
# apps/backend/app/services/orders.py:181-201 (excerpt)
@transactional
def create_order(ctx: Ctx, input: Doc) -> Doc:
    client = crud.clients.require(input["clientId"])
    t = today()
    order = {
        "id": crud.orders.next_id("ord_"),
        "number": crud.orders.next_number("CMD", t[:4]),
        ...
    }
    saved = _save(order)
    log_event(ctx, "order.created", "order", order["id"], f"Commande {order['number']} créée pour …")
    return order_detail(saved["id"])
```

**In-memory tables + SQLite write-through** (`core/db.py:36-68`). At startup, `lifespan` (`main.py:44`) loads all
the tables (`load_all`) or, if the database is empty, the data pack (`reset_from_pack`). All reads hit memory;
`put` / `remove` write to memory **and** to SQLite. Database: `apps/backend/data/erp.db` locally, `/db/erp.db`
(`erp-db` volume) in Docker.

**`@transactional`** (`core/db.py:117-150`): the function runs inside an SQLite transaction; nested blocks join the
outermost one. On an exception: `ROLLBACK` **and** reloading memory from disk (`load_all`), so the two never diverge.
`on_commit` callbacks (SSE broadcast) only fire on COMMIT. Every service function that writes takes `ctx` first and
carries `@transactional`.

**Ids and numbers**: `crud.X.next_id("ord_")` → `ord_000124` (follows the largest existing one);
`next_number("CMD", "2026")` → `CMD-2026-000124` (`crud/base.py:62-74`). Line ids (`lin_…`, `pol_…`) are random.

**Business clock** (`core/activity.py:33-41`): `today()` = the pack's `meta.today`, never `date.today()`; `now()` =
that day + the real time. Every "late", "tomorrow", "last 30 days" is computed from it.

**Schemas** (`schemas/base.py`): `Schema` serializes to camelCase without `None` fields; `Input` (request body) is
**strict** (no `"5"` → 5) and ignores unknown keys; `body.data()` → camelCase dict for the service. Services handle
camelCase dicts, not Pydantic objects.

**Errors**: always `{"error": {"code", "message"}}`.

| Case | Status | `code` | Where from |
|---|---|---|---|
| invalid body (Pydantic) | 400 | `validation_error` (`"field: message; …"`) or `invalid_json` | `main.py:132` |
| business rule (`bad_request`) | 400 | any, e.g. `product_inactive`, `invalid_qty` | `core/errors.py:17` |
| missing entity (`crud.X.require`) | 404 | `not_found` ("Commande introuvable : ord_1" — "Order not found: ord_1") | `crud/base.py:43` |
| unknown route / wrong method | 404 | `not_found` | `main.py:144` |
| forbidden transition (`conflict`) | 409 | e.g. `empty_order`, `invalid_transition` | `core/errors.py:21` |
| unexpected exception | 500 | `internal_error` | `main.py:151` |

**Data pack and reset**: `make reset` = `POST /api/admin/reset` (`routers/system.py:80`) → `reset_from_pack()`
(`core/datapack.py:49`): empties all tables and the log, reloads `DATA_DIR/seed/*.json`, clears the sequences.
Without `DATA_DIR/seed/meta.json`, a small built-in fixture (`core/dev_fixture.json`) is loaded.

<a id="ajouter-endpoint"></a>
### Extending: adding an endpoint end to end (2.6)

Worked example: **"repeat the same order"** (`POST /api/orders/{id}/repeat`), useful on the phone ("comme la
dernière fois" — "same as last time").

1. **Input schema** — `apps/backend/app/schemas/inputs.py` (next to `OrderPatch`):

   ```python
   class RepeatOrderInput(Input):
       delivery_date: IsoDateStr | None = None  # default: the client's next delivery day
   ```

   If the response has a new shape, add a model in `schemas/views.py`; here we reuse `OrderDetail`.

2. **Service** — `apps/backend/app/services/orders.py` (reuses `create_order`, which recomputes today's prices,
   logs `order.created` and joins the transaction):

   ```python
   @transactional
   def repeat_order(ctx: Ctx, id: str, input: Doc) -> Doc:
       src = crud.orders.require(id)
       lines = [
           {"productId": l["productId"], "qty": l["qty"], **({"note": l["note"]} if l.get("note") else {})}
           for l in src["lines"]
       ]
       return create_order(ctx, {
           "clientId": src["clientId"],
           "deliveryDate": input.get("deliveryDate"),
           "lines": lines,
           "note": f"Reprise de {src['number']}",
       })
   ```

3. **Route** — `apps/backend/app/routers/orders.py` (import `RepeatOrderInput`):

   ```python
   @router.post("/{id}/repeat", response_model=OrderDetail, status_code=201)
   async def repeat_order(id: str, ctx: CtxDep, body: RepeatOrderInput | None = None):
       """New draft with the same lines as order `id` (prices resolved today)."""
       return orders.repeat_order(ctx, id, data(body))
   ```

   A new router file must be added to the list in `main.py:72-91`.

4. **Check**: uvicorn reloads by itself. `curl -s -X POST localhost:4000/api/orders/ord_000001/repeat -H 'content-type: application/json' -H 'x-actor: voice_agent' -d '{}'`,
   then http://localhost:4000/docs. The row appears in purple in **Activité**.

5. **TypeScript type** — the web's types are **hand-written** in `packages/shared/src/` (`domain.ts`, `api.ts`,
   `ai.ts`). New body or new response → add the matching interface (nothing here: `OrderDetail` exists).
   `make types` also generates `packages/shared/src/generated/` from `/openapi.json`, but that folder isn't exported
   by `index.ts`: it serves as a reference (see [Pitfalls](#pieges)).

6. **Web call** — `apps/web/src/lib/api.ts`, `orders` object (`:137`):

   ```ts
   repeat: (id: Id, body?: { deliveryDate?: IsoDate }) => post<OrderDetail>(`/orders/${id}/repeat`, body),
   ```

   then in a page: `useApiMutation(api.orders.repeat, { success: "Commande dupliquée", invalidate: [qk.orders.all] })`.

7. **Tool for the agent** (optional): see [5.3](#ajouter-outil).

### Pitfalls

- A single process: the in-memory database isn't shared between workers. Don't run uvicorn with `--workers`.
- Editing `erp.db` by hand while the ERP is running desynchronizes memory: restart the backend.
- Routes are `async` but services are synchronous: a long calculation blocks the whole API (including SSE).
- Don't forget `log_event` in a service that writes: without it, the UI doesn't update live.
- Query parameters arrive as `str` and are converted in the router (`int_param`, `js_number`); lists =
  comma-separated strings (`status=draft,confirmed`). `limit` / `offset` / `sort` / `order` / `envelope`: add
  `lq: ListDep` to the route and return `respond(rows, lq, view, extras)` ([Pagination](#pagination)).
- A new list must never build the views of all rows: filter → sort → `respond` (which slices the page then calls
  `view`). An aggregate over the whole table? `@per_data_version` (never mutate the cached value).

---

<a id="endpoints"></a>
## 3. Endpoint reference

### What it is

The ERP's 80 routes (generated from `http://localhost:4000/openapi.json`) and the AI service's 7 routes. Live
testing: http://localhost:4000/docs and http://localhost:4100/docs. curl examples and business semantics:
[ERP.en.md §7 and §8](ERP.en.md#8-api-cheat-sheet).

### Key files

`apps/backend/app/routers/*.py`, `apps/ai/app/routers/*.py`, `apps/ai/app/schemas/*.py`.

### How it works: ERP (`/api`, port 4000)

All writes accept `x-actor` and `x-actor-name`. Response = a model from `schemas/views.py` or `domain.py`.

<a id="pagination"></a>
**Pagination.** All lists are paginated, filtered and sorted **on the server side** (`app/core/listing.py`), because
the data packs go up to ~48,000 orders, ~25,000 invoices and ~420,000 stock movements per company. Common parameters
(marked "+ list" below): `limit` (default **100**, max **500**), `offset` (default 0), `sort` (a sortable field of
the route, listed in its `/docs` description and in `packages/shared/src/api.ts`), `order` (`asc` | `desc`).
Response format:

- **by default, a JSON array** (the requested page): the AI tools and existing scripts work unchanged, but an array
  is **truncated to `limit`** — pass `limit=500` or `envelope=1` to know how many rows exist;
- **with `envelope=1`** (what the UI sends): `{items, total, limit, offset, …extras}` — `total` = rows matching the
  filters, and extras computed over the **whole** filtered set (not just the page): `counts` (rows per status / tab /
  category **ignoring that particular filter** → tab badges), `sums` (table footer totals), `sumsByStatus`
  (invoices), `countsByType` (history), `countsBySource` (context), `facets` (filter menu options). TS type:
  `Page<T>` in `packages/shared/src/api.ts`.

On the services side: filter the raw documents, sort with a simple key, slice the page, and **only then** build the
views (`order_summary`, `invoice_summary`…) of the page's rows. Expensive aggregates (stock levels, outstanding per
client, pre-sorted lists, FEFO index, dashboard) are cached by **data version** (`@per_data_version` in
`core/db.py`, invalidated on every write); stock movements (append-only) have an incremental index. On the web side:
`useServerList` (page + sort in the URL) → `use…Page` hook → `<DataTable server={{ list, total }}>` with `sortKey`
columns (see `pages/clients/index.tsx`, the reference page). Exceptions bounded by nature, not paginated:
`GET /api/receivables` (one row per client), `/api/prices/grid` (one row per product), `/api/tags`.

**System** (`routers/system.py`)

| Method | Path | Role | Parameters | Response |
|---|---|---|---|---|
| GET | `/api/health` | alive + business date | — | `Health` |
| GET | `/api/meta` | company, `today`, `trade`, `region` (sidebar) | — | `Meta` |
| GET | `/api/categories` | the company's product categories (`seed/categories.json`) | — | `Category[]` (`{id, label}`) |
| GET | `/api/dashboard` | home page KPIs | — | `Dashboard` |
| GET | `/api/search` | fuzzy search (accents, aliases, filler words) | `q`, `types`, `limit` (default 20, max 500) | `SearchResult[]` |
| GET | `/api/events` | activity log, most recent first | `actor` (`ai`, `user,system`…), `entity` + list (default `limit` 50); envelope: `counts` {ai, user} | `ActivityEvent[]` |
| GET | `/api/events/stream` | live log (SSE) | — | `text/event-stream` |
| POST | `/api/admin/reset` | reloads the data pack | — | `Ok` |

**Clients** (`routers/clients.py`, `routers/client_events.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/clients` | list with KPIs | `q`, `type`, `zone`, `status`, `tag` + list; sort `name` `code` `type` `tags` `zone` `rep` `city` `outstanding` `overdue` `last` `revenue30d` `status`; envelope: `counts` per status, `facets.zone`, `facets.salesRep` | `ClientSummary[]` |
| POST | `/api/clients` | create | `ClientInput` | `Client` (201) |
| GET | `/api/clients/{id}` | full profile (last 20 orders, ≤ 100 open invoices + `openInvoiceCount`) | — | `ClientDetail` |
| PATCH | `/api/clients/{id}` | modify | `ClientPatch` | `Client` |
| GET | `/api/clients/{id}/usual` | usual basket (60 days) | — | `UsualBasketLine[]` |
| GET | `/api/clients/{id}/events` | the client's history, most recent first (`sort=open`: open cases first) | `type`, `status`, `q` + list | `ClientEventSummary[]` |
| POST | `/api/clients/{id}/events` | add an event | `ClientEventInput` | `ClientEvent` (201) |
| PUT | `/api/clients/{id}/prices/{product_id}` | set a negotiated price | `ClientPriceInput` | `ClientPrice` |
| DELETE | `/api/clients/{id}/prices/{product_id}` | remove the negotiated price | — | `Ok` |
| POST | `/api/clients/{id}/notes` | add a note | `ClientNoteInput` | `Client` (201) |
| GET | `/api/client-events` | history across all clients | `type`, `status`, `clientId`, `q`, `from`, `to` + list; envelope: `counts` per status, `countsByType`, `sums.amount` | `ClientEventSummary[]` |
| PATCH | `/api/client-events/{id}` | modify, resolve | `ClientEventPatch` | `ClientEvent` |

**Catalog, suppliers, stock** (`routers/products.py`, `suppliers.py`, `supplier_events.py`, `stock.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/products` | catalog with stock | `q`, `category`, `tag`, `active` + list; sort `name` `sku` `category` `tags` `price` `cost` `margin` `available` `expiry`; envelope: `counts` per category | `ProductSummary[]` |
| GET | `/api/products/{id}` | detail, lots, supplier prices, movements, 30-day sales | — | `ProductDetail` |
| PATCH | `/api/products/{id}` | price, cost, tags… | `ProductPatch` | `Product` |
| GET | `/api/products/{id}/alternatives` | replacements in stock | — | `ProductSummary[]` |
| GET | `/api/suppliers` | list | `q`, `category`, `tag` + list; sort `name` `city` `tags` `lead` `terms` `min` | `Supplier[]` |
| GET | `/api/suppliers/{id}` | detail (last 60 purchase orders + `purchaseStats` over all) | — | `SupplierDetail` |
| PATCH | `/api/suppliers/{id}` | modify | `SupplierPatch` | `Supplier` |
| GET | `/api/suppliers/{id}/usual` | usual purchases (60 days) | — | `UsualBasketLine[]` |
| GET | `/api/suppliers/{id}/events` | supplier history (`sort=open`: open first) | `type`, `status`, `q` + list | `SupplierEventSummary[]` |
| POST | `/api/suppliers/{id}/events` | add an event | `SupplierEventInput` | `SupplierEvent` (201) |
| GET | `/api/supplier-events` | history across all suppliers | `type`, `status`, `supplierId`, `q`, `from`, `to` + list; envelope as for `/api/client-events` | `SupplierEventSummary[]` |
| PATCH | `/api/supplier-events/{id}` | modify, resolve | `SupplierEventPatch` | `SupplierEvent` |
| GET | `/api/stock` | stock levels | `q`, `tab` (`out` \| `low` \| `expiring`) + list; sort `product` `sku` `category` `onHand` `reserved` `available` `incoming` `expiry` `state`; envelope: `counts` per tab | `StockItem[]` |
| GET | `/api/stock/movements` | movements, most recent first (`order=asc`: oldest first) | `productId` + list | `StockMovement[]` |
| POST | `/api/stock/adjust` | adjustment, loss | `StockAdjustInput` | `StockLevel` |

**Sales** (`routers/orders.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/orders` | list, most recent delivery first | `status`, `clientId`, `date`, `q`, `source`, `ids` + list; sort `number` `client` `date` `createdAt` `lines` `total` `status`; envelope: `counts` per status, `sums.totalHt` | `OrderSummary[]` |
| POST | `/api/orders` | draft | `OrderInput` | `OrderDetail` (201) |
| GET | `/api/orders/{id}` | detail + alerts | — | `OrderDetail` |
| PATCH | `/api/orders/{id}` | date, note | `OrderPatch` | `OrderDetail` |
| POST | `/api/orders/{id}/lines` | add a line | `OrderLineInput` | `OrderDetail` (201) |
| PATCH | `/api/orders/{id}/lines/{line_id}` | modify a line | `OrderLinePatch` | `OrderDetail` |
| DELETE | `/api/orders/{id}/lines/{line_id}` | remove a line | — | `OrderDetail` |
| POST | `/api/orders/{id}/confirm` | confirm, reserve, assign to a delivery run | — | `OrderDetail` |
| POST | `/api/orders/{id}/prepare` | prepare (actual weights) | `PrepareInput` | `OrderDetail` |
| POST | `/api/orders/{id}/deliver` | deliver (FEFO) | — | `OrderDetail` |
| POST | `/api/orders/{id}/invoice` | invoice | — | `InvoiceDetail` (201) |
| POST | `/api/orders/{id}/cancel` | cancel | — | `OrderDetail` |

**Purchasing** (`routers/purchase_orders.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/purchase-orders` | list, most recent first | `status`, `supplierId`, `date` (expected), `q` + list; sort `number` `supplier` `date` `createdAt` `lines` `total` `status`; envelope: `counts`, `sums.totalHt` | `PurchaseOrderSummary[]` |
| POST | `/api/purchase-orders` | draft | `PurchaseOrderInput` | `PurchaseOrderDetail` (201) |
| GET | `/api/purchase-orders/{id}` | detail | — | `PurchaseOrderDetail` |
| PATCH | `/api/purchase-orders/{id}` | expected date, note | `PurchaseOrderPatch` | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/lines` | add a line | `PurchaseOrderLineInput` | `PurchaseOrderDetail` (201) |
| PATCH | `/api/purchase-orders/{id}/lines/{line_id}` | modify a line | `PurchaseOrderLinePatch` | `PurchaseOrderDetail` |
| DELETE | `/api/purchase-orders/{id}/lines/{line_id}` | remove a line | — | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/send` | send | — | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/receive` | receive (creates lots) | `ReceiveInput` | `PurchaseOrderDetail` |
| POST | `/api/purchase-orders/{id}/cancel` | cancel | — | `PurchaseOrderDetail` |

**Invoicing** (`routers/billing.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/invoices` | list without lines (`lineCount`); `status` accepts `open` and `overdue` (computed) | `status`, `clientId`, `q` + list; sort `number` `client` `issued` `due` `ttc` `paid` `balance` `status`; envelope: `counts`, `sums` (totalTtc, amountPaid, balance), `sumsByStatus` | `InvoiceSummary[]` |
| GET | `/api/invoices/{id}` | detail + payments | — | `InvoiceDetail` |
| GET | `/api/payments` | list, most recent first; each allocation carries `invoiceNumber` | `clientId`, `method`, `q` (client, reference, invoice no.) + list; sort `date` `client` `method` `ref` `amount`; envelope: `sums.amount` | `PaymentSummary[]` |
| POST | `/api/payments` | record (auto-allocation to the oldest) | `PaymentInput` | `PaymentSummary` (201) |
| GET | `/api/receivables` | aged balance, risk, DSO (one row per client, not paginated) | `q`, `tag`, `rep`, `zone`, `onlyOverdue` | `Receivables` |

**Prices and groups** (`routers/pricing.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/tags` | groups + counters | `scope` | `TagWithCount[]` |
| POST | `/api/tags` | create | `TagInput` | `TagDef` (201) |
| PATCH | `/api/tags/{scope}/{id}` | modify | `TagPatch` | `TagDef` |
| DELETE | `/api/tags/{scope}/{id}` | delete | — | `Ok` |
| GET | `/api/price-rules` | rules | `active`, `clientId`, `productId` + list | `PriceRuleSummary[]` |
| POST | `/api/price-rules` | create | `PriceRuleInput` | `PriceRule` (201) |
| PATCH | `/api/price-rules/{id}` | modify | `PriceRulePatch` | `PriceRule` |
| DELETE | `/api/price-rules/{id}` | delete | — | `Ok` |
| GET | `/api/prices/resolve` | price chosen + why + candidates | `clientId`, `productId`, `qty`, `date` | `ResolvedPrice` |
| GET | `/api/prices/grid` | price grid | `clientId` or `clientTag`, `productTag`, `category`, `q` | `PriceGridRow[]` |

**Logistics** (`routers/logistics.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/routes` | delivery run definitions | + list | `Route[]` |
| GET | `/api/route-runs` | runs, most recent date first (the UI always filters by `date`) | `date`, `routeId` + list | `RouteRunDetail[]` |
| POST | `/api/route-runs/plan` | plan a date | `PlanInput` | `RouteRunDetail[]` |
| PATCH | `/api/route-runs/{id}/stops` | reorder the stops | `ReorderStopsInput` | `RouteRunDetail` |

**Context** (`routers/context.py`)

| Method | Path | Role | Parameters / body | Response |
|---|---|---|---|---|
| GET | `/api/context` | search / list (relevance with `q`) | `entityType`, `entityId`, `kind`, `source`, `tag`, `q` + list; sort `title` `entity` `kind` `tags` `source` `updated`; envelope: `counts` per type, `countsBySource` | `ContextEntrySummary[]` |
| POST | `/api/context` | create (`source` = actor) | `ContextEntryInput` | `ContextEntry` (201) |
| GET | `/api/context/for` | all the context of an entity + linked entries | `entityType`, `id` | `ContextForEntity` |
| GET | `/api/context/{id}` | one entry | — | `ContextEntrySummary` |
| PATCH | `/api/context/{id}` | modify | `ContextEntryPatch` | `ContextEntry` |
| DELETE | `/api/context/{id}` | delete | — | `Ok` |

### How it works: AI service (port 4100, proxied as `/ai/*`)

| Route | File | Input | Output |
|---|---|---|---|
| `GET /health` | `routers/health.py:13` | — | `HealthResponse {ok, llm:{provider,model}, stt:{provider}, tts:{provider}, erpApiUrl}` |
| `GET /tools` | `routers/health.py:25` | — | `ToolInfo[] {name, description, parameters}` |
| `POST /chat` | `routers/chat.py:15` | `ChatRequest {messages, mode?, actorName?}` | SSE of `ChatStreamEvent` |
| `POST /command[?speak=1]` | `routers/command.py:26` | raw audio (`content-type` = mime, `x-mock-text` / `x-stt-hint`) or JSON `CommandRequest {text, actorName?}` | SSE of `CommandStreamEvent` |
| `POST /stt` | `routers/speech.py:18` | raw audio, `x-stt-hint` or `x-mock-text` | `SttResponse {text, ms}`; 502 `stt_failed` |
| `POST /tts` | `routers/speech.py:37` | `TtsRequest {text, voice?}` | streamed audio bytes, `x-ms` header; 502 `tts_failed` |
| `WS /voice` | `routers/voice.py:10` | `VoiceClientMessage` + binary frames | `VoiceServerMessage` + binary frames |

Errors: `400 {error: {code: "bad_request", message}}` (invalid body, `main.py:45`).

**SSE events** (`schemas/chat.py`, `schemas/command.py`) — one `data: <JSON>` line per event, discriminated by
`type`:

| `type` | Fields | `/chat` | `/command` |
|---|---|---|---|
| `transcript` | `text`, `ms` (STT time), `final` (default true), `stable?` | | the final one before the others; `WS /voice/command` also sends `final:false` during speech |
| `text` | `delta` | ✓ | ✓ |
| `tool_call` | `call {id, name, arguments}` | ✓ | ✓ |
| `tool_result` | `callId`, `name`, `ok`, `result`, `ms` | ✓ | ✓ |
| `navigate` | `path`, `label?` | | if the user wants to *see* |
| `speech` | `mime`, `audio` (base64), `ms` | | if `speak=1` |
| `done` | `message`, `usage?`, `ms`, `timings?` | last | last (with `timings`) |
| `error` | `message` | instead of `done` | same |

**`/voice` WebSocket messages** (`schemas/voice.py`):

| Direction | `type` | Fields | Effect |
|---|---|---|---|
| client → server | `start` | `sessionId?`, `actorName?` | opens / resumes a conversation |
| | `audio_start` | `mime`, `hint?` (STT hint; mock STT: the text heard) | interrupts the agent (barge-in), starts recording |
| | *(binary)* | audio frames (every 100–250 ms) | sent to the STT on arrival (live transcription) |
| | `audio_end` | — | starts the turn |
| | `text` | `text` | typed turn (debug, scripts) |
| | `reset` | — | clears the history, sends back `ready` |
| server → client | `ready` | `sessionId`, `stt`, `tts`, `llm` | |
| | `transcript` | `track: "caller"`, `text`, `final`, `stable?` | `final:false` during speech (text heard so far; `stable` = final words), then one `final:true` |
| | `agent_text` | `delta` | |
| | `agent_tool` | `name` + `args` (call) then `name`, `ok`, `ms` (end) | |
| | `agent_audio_start` | `mime` | followed by binary frames (one segment per turn) |
| | `agent_audio_end` | — | |
| | `agent_done` | `text`, `timings` | |
| | `error` | `message` | |

All these models are published in `http://localhost:4100/openapi.json` (`main.py:54-81`).

### Extending

One more ERP endpoint: [2.6](#ajouter-endpoint). One more SSE event or WS message: add the model in
`apps/ai/app/schemas/` **and** in the union (`ChatStreamEvent`, `CommandStreamEvent`, `VoiceServerMessage`…), then
the type in `packages/shared/src/ai.ts`.

### Pitfalls

- `limit`, `qty`, etc. are strings on the ERP side; lists are comma-separated.
- A list without `envelope=1` is an array **truncated to `limit` (100 by default)**: for "all" the rows of a small
  table, `limit=500`; for the big ones (orders, invoices, movements), filter or paginate.
- `/api/invoices?status=overdue` filters on the **computed** status (never stored).

---

<a id="service-ia"></a>
## 4. AI service (`apps/ai/app`)

### What it is

An agent harness: a model ⇄ tools loop, three modes (`chat`, `voice`, `command`), interchangeable LLM / STT / TTS
clients written in raw `httpx` (no SDK), and three surfaces (`/chat`, `/command`, `WS /voice`).

### Key files

| File | Role |
|---|---|
| `config.py` | `settings` (read once at startup) |
| `clients/base.py` | `LLMClient`, `STTClient`, `TTSClient` interfaces + event types |
| `clients/factory.py` | `.env` → one client of each kind (`get_llm_client()`…), default models |
| `clients/{openai,anthropic,gemini}.py` | LLM adapters |
| `clients/{soniox,deepgram,gradium,elevenlabs}.py` | speech adapters; `openai.py` also has STT + TTS |
| `clients/mock_llm.py`, `mock_speech.py` | offline fake providers |
| `clients/jev.py` | Jev decision model |
| `clients/http.py`, `ws.py`, `audio.py` | shared HTTP pool, SSE, errors; WebSocket; webm→ogg, PCM→mp3 |
| `agent/loop.py` | `run_agent` |
| `agent/prompts.py` | `build_system_prompt` |
| `tools/` | the tools (section 5) |
| `services/voice_session.py`, `services/command.py` | push-to-talk voice, the ⌥Space command |
| `routers/` | thin routes |
| `schemas/` | the contract (events, WS messages) |
| `cli.py` | `make chat` |

### How it works

<a id="config-ia"></a>
#### 4.1 Configuration

`config.py` loads the root `.env` (real environment variables win) into `settings`, **only once**. The clients are
built once (`@cache`, `factory.py:103-121`) and at startup (`main.py:27-36`): a missing key makes startup fail with
`configuration error`. After changing `.env`: `make restart` (Docker) or restart `make dev`.

| Variable | Default | Read in |
|---|---|---|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_BASE_URL` | `mock`; models: `factory.py:24` | `make_llm_client` (`factory.py:44`) |
| `LLM_EFFORT` | `low` | Anthropic (`output_config.effort`) |
| `AGENT_MAX_STEPS` | 8 | `loop.py:60` |
| `STT_*`, `MOCK_STT_TEXT` | `mock`, `fr` | `make_stt_client` (`factory.py:66`) |
| `TTS_*` | `mock`, `fr` | `make_tts_client` (`factory.py:82`) |
| `JEV_*` | empty key → no Jev | `make_jev_client` (`factory.py:97`) |
| `ERP_API_URL`, `DATA_DIR`, `AI_PORT` | `http://localhost:4000`, `../hackathon-data` (team zip: `./data`), 4100 | `config.py:71-75` |

Change model without code: `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL=https://api.groq.com/openai/v1`,
`LLM_MODEL=…`, `LLM_API_KEY=…`. Full list: [apps/ai/README.md#environment](apps/ai/README.md#environment).

<a id="clients"></a>
#### 4.2 The clients (`clients/`)

**Interfaces** (`clients/base.py`):

```python
# LLM — clients/base.py:51-57
class LLMClient(ABC):
    provider: str
    model: str
    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        """Stream one model response. Implement it as an `async def` generator (with `yield`)."""
```

- `LLMRequest {system, messages: list[ChatMessage], tools: list[ToolInfo], max_tokens}`; the generator emits
  `LLMText(delta)` as it goes, `LLMToolCall(call)` (once the arguments are complete) and `LLMUsage`. The adapter
  translates the `ChatMessage`s (`user`, `assistant` with `tool_calls`, `tool` with `tool_call_id` + `name`) into
  the provider's format (`to_openai_message`, `to_anthropic_messages`, `to_gemini_contents`).
- `STTClient.transcribe(audio, mime, hint) -> str`; **`transcribe_stream(audio_chunks, mime, hint)`** emits
  `STTUpdate(text, final, stable)` (full text each time). By default: waits for the end then a single final update.
  Soniox, Deepgram and the mock override it (`streams = True`): see [Live transcription](#stt-direct).
- `TTSClient.synthesize(text, voice) -> TTSResult(mime, chunks)`: raises on HTTP error, then streams the bytes. All
  real TTS providers return `audio/mpeg` (the web player concatenates a turn's mp3); PCM → `audio.Mp3Encoder`.

**Factory** (`factory.py:44-63`): one `match` per kind. `DEFAULT_MODELS`, `DEFAULT_STT_MODELS`, `DEFAULT_TTS` give
the defaults.

**Shared HTTP** (`clients/http.py`): a single `httpx.AsyncClient` (`http_client()`, reuses TLS connections),
`post_stream` (POST without reading the body), `sse_json` (iterates over the `data:` lines), `body_chunks`,
`parse_args`, `provider_error` which formats `"<who> HTTP <status>: <body> — <hint>"` (key refused, quota, audio
format).

**Extending: adding a provider** (TTS example; LLM and STT follow the same pattern):

1. `apps/ai/app/clients/montts.py` — replace the URL, headers and body with the provider's:

   ```python
   from .base import TTSClient, TTSResult
   from .http import body_chunks, http_client, post_stream

   class MonTTS(TTSClient):
       name = "montts"

       def __init__(self, api_key: str, model: str, voice: str):
           self.api_key, self.model, self.voice = api_key, model, voice

       async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
           res = await post_stream(
               http_client(), "https://api.example.com/v1/tts/stream", who="montts tts",
               headers={"authorization": f"Bearer {self.api_key}"},
               json={"text": text, "model": self.model, "voice": voice or self.voice, "format": "mp3"},
           )
           return TTSResult("audio/mpeg", body_chunks(res))   # mp3 required by the web player
   ```

2. `factory.py`: import the class, add a default in `DEFAULT_TTS` and a `case`:

   ```python
   case "montts":
       return MonTTS(need("TTS_API_KEY", cfg.api_key), model, voice)
   ```

3. `.env`: `TTS_PROVIDER=montts`, `TTS_API_KEY=…`; `make restart`; check `GET /ai/health` then
   `curl -s localhost:4100/tts -H 'content-type: application/json' -d '{"text":"Bonjour"}' -o /tmp/t.mp3`.
4. An "OpenAI-compatible" LLM needs no code (`openai-compatible`). A different LLM: copy `anthropic.py` (the shortest
   one that handles streaming tool calls). Tests: modeled on `tests/test_clients.py` (recorded SSE responses, no
   network).

<a id="prompts"></a>
#### 4.3 The prompts (`agent/prompts.py`)

```python
# agent/prompts.py:54-67
async def build_system_prompt(mode: ChatMode, actor_name: str | None = None) -> str:
    meta = await get_meta()
    today = meta.get("today") or datetime.now(UTC).date().isoformat()
    company = meta.get("company") or "un grossiste alimentaire"
    trade = meta.get("trade") or company_trade()
    parts = [
        ROLE.format(company=company, trade=f"Activité : {trade}" if trade else "C'est un grossiste alimentaire"),
        BASE_RULES,
        MODE_RULES[mode],
        f"Entreprise : {meta.get('company') or '(ERP injoignable)'}. Aujourd'hui : {french_date(today)} ({today}).",
        f"Interlocuteur : {actor_name}." if actor_name else "",
        f"# Contexte entreprise\n\n{context}" if (context := read_context_files()) else "",
    ]
    return "\n\n".join(p for p in parts if p)
```

| Part | Content | Source |
|---|---|---|
| `ROLE` (`:19-20`) | "assistant of {company}'s ERP. Business: {trade}": `company` from `GET /api/meta`, `trade` from `meta.trade`, otherwise the 1st sentence of `DATA_DIR/context/*entreprise*.md` (`company_trade()`) | ERP + pack |
| `BASE_RULES` (`:22-32`) | "tools for any data", `search` first, `get_price`, `get_context`, draft then explicit confirmation, alerts, concise French | code |
| `CHAT_RULES` (`:34`) | light markdown | code |
| `VOICE_RULES` (`:36-41`) | 1–2 sentences, no markdown or ids, numbers in words, at most "Je regarde." before the first tool then nothing between tools (all text is spoken in order), recap before confirming | code |
| `COMMAND_RULES` (`:43-49`) | act right away, one sentence, an explicit request counts as agreement | code |
| company + date | `meta.company`, `meta.today` in French | `GET /api/meta`, 60 s cache (`:64-80`) |
| caller | `actorName` ("Agent vocal", "Commande vocale", "CLI") | request |
| company context | all the `DATA_DIR/context/*.md` (top level, sorted), reread on **every** turn | `read_context_files` (`:83-90`) |

Extending: change the rules in `prompts.py` or the context in `data/context/*.md` (taken into account on the next
turn, without a restart). To inject the caller's profile, add a part to `parts` (e.g. the result of
`GET /api/context/for` for a client known to the session).

<a id="boucle"></a>
#### 4.4 The agent loop (`agent/loop.py`)

```python
# agent/loop.py:60-91 (excerpt)
for _step in range(max_steps or settings.max_steps):
    text = ""; calls = []
    async for ev in llm.stream(request):
        match ev:
            case LLMText(delta=delta):      text += delta; yield TextEvent(delta=shown)
            case LLMToolCall(call=call):    calls.append(call); yield ToolCallEvent(call=call)
            case LLMUsage(...):             usage.input_tokens += i or 0 ...
    if not calls:                                            # final answer
        messages.append(ChatMessage(role="assistant", content=text))
        yield DoneEvent(message=message, usage=usage, ms=ms_since(started)); return
    messages.append(ChatMessage(role="assistant", content=text, tool_calls=calls))
    results = await asyncio.gather(*(execute_tool(call, tools, ctx) for call in calls))
    for r in results:
        messages.append(ChatMessage(role="tool", tool_call_id=r.call_id, name=r.name, content=to_json(r.result)))
        yield r
```

Step by step:

1. `ctx = ToolContext(erp=ErpClient(actor, actor_name), actor=actor)`; `actor` = `ai_chat` in chat mode, otherwise
   `voice_agent` (`:51-52`).
2. The system prompt is built once per turn; the same `LLMRequest` is resent at each step (it references the
   `messages` list, which grows).
3. Text is streamed **while** the model generates; tool calls are collected.
4. No call → `DoneEvent`, end. Otherwise the tools run **in parallel** (`asyncio.gather`), their results are added
   as `tool` messages (compact JSON, accents kept) and the model is called again.
5. Beyond `AGENT_MAX_STEPS` (8): a `GIVE_UP` message ("Désolé, je n'ai pas réussi à aller au bout…" — "Sorry, I
   couldn't get to the end…").
6. `execute_tool` (`:102-112`) never raises: unknown tool or exception → `ok=false`, `result={"error": "…"}`; the
   model reads the error and explains or retries.
7. Any other exception (provider down, key refused) → `ErrorEvent`. Cancellation (`CancelledError`) is not an
   `Exception`: the loop stops without emitting anything. That's the mechanism behind barge-in and an SSE client's
   disconnection (Starlette cancels the generator, `routers/sse.py:15`).

**`run_agent` modifies the `messages` list it is given**: whoever keeps the list keeps the history.

| Mode | Who keeps the history | Where |
|---|---|---|
| `chat` | the **browser**: `history` in `chat-store.ts:23`, resent in full with each `POST /chat` (rebuilt by `TurnRecorder`); lost when the page reloads | `apps/web/src/features/assistant/` |
| `voice` | the **AI service**: `conversations: dict[sessionId, Conversation]` in memory (`voice_session.py:68`), working copy committed at the end of the turn, trimmed at ~40 messages by `trim()` (`:296-301`, always starts on a `user` message); lost on restart | `services/voice_session.py` |
| `command` | nobody: a single `user` message per request (`services/command.py:104`) | |
| CLI | the `messages` list in `cli.py` (`/reset` empties it) | `app/cli.py` |

<a id="latence"></a>
#### 4.5 Latency: where every millisecond is spent

| Step | What the kit does | Lever |
|---|---|---|
| STT | transcription **while** the key is held ([Live transcription](#stt-direct)): on release, only the last words remain to be finalized | LLM started on a stable partial, hands-free mode (`<end>`) |
| prompt | rules + all of `DATA_DIR/context/*.md` (≈ 44 KB in the reference pack) resent at every step; Anthropic: reread from the cache ([4.8](#cache-prompt)) | reduce the context, keep the prefix stable |
| LLM | one call per step; tools in parallel | composite tool ([5.4](#outil-composite)), fast model, `LLM_EFFORT=low` |
| tools | `ErpClient` reuses a shared `httpx.AsyncClient` (`erp_http()`, keep-alive, 10 s timeout, closed on shutdown) (`tools/erp.py:23-41`) | composite tool, fewer ERP calls |
| TTS | sentence by sentence: as soon as a sentence ends with `. ! ? …` + space (`Speaker.SENTENCE`, `:230`), it goes to the TTS; a single mp3 segment per turn | split earlier (commas), filler during tools |
| playback | `SegmentPlayer` (MediaSource) plays from the first byte | — |

<a id="session-voix"></a>
#### 4.6 The voice session (`services/voice_session.py`)

- `VoiceConnection.serve()` reads the frames; binary → `recording.feed()` (sent to the STT live, see
  [Live transcription](#stt-direct)); text → `handle_text`.
- Each turn is an `asyncio.Task` (`start_turn`); `interrupt()` cancels it and waits for its cleanup.
- `run_turn` (`:168-229`): STT → `transcript` → `run_agent(mode="voice")` on a copy of the history → text to
  `Speaker` → `speaker.finish()` → `agent_done`. Errors become `error` messages.
- `Speaker` (`:231-294`): a text buffer, a sentence queue, a worker that synthesizes and sends the bytes in order.
  `agent_audio_start` goes out on the first byte; `tts_first_byte_ms` is measured there.
- Reconnecting with the same `sessionId` → same `Conversation`.

<a id="stt-direct"></a>
#### Live transcription (`services/utterance.py`, `services/vocabulary.py`)

```
audio_start ─▶ Utterance(stt, mime, hint, on_partial)    opens the STT stream (if stt.streams)
frame       ─▶ feed(frame) ─▶ provider                    ◀─ on_partial(STTUpdate) ─▶ transcript {final:false}
audio_end   ─▶ await text()   Soniox: {"type":"finalize"} ─▶ <fin> token ─▶ transcript {final:true} ─▶ agent
barge-in    ─▶ cancel()       closes the provider's stream
```

- Each frame is also kept: if the stream breaks or doesn't return its final words within `FINAL_TIMEOUT_S` (5 s),
  `text()` transcribes the full recording (`transcribe`). The utterance is never lost.
- Soniox tokens: non-final = resent in full with each message, may change; final = sent once. `stable` = the final
  words. `<end>` (pause detected) and `<fin>` (response to finalize) aren't text.
- Vocabulary: client names, then products, then their aliases (`/api/clients`, `/api/products`), 5 min cache,
  `MAX_TERMS` = 500 → `context.terms` (Soniox, capped at `MAX_TERMS_CHARS`), `keyterm` (Deepgram). To enrich it:
  `company_terms()` (e.g. contact names, or the usual basket of the client on the line). The mock STT doesn't
  receive any.
- The mock STT simulates partials (one word every 3 frames): the display can be tested without a key.

**Extending**: start the LLM on a stable partial (GUIDE-VOIX 4.3); hands-free mode on the `<end>` tokens; per-call
vocabulary (usual basket of the identified client).

<a id="jev"></a>
#### 4.7 Jev (typed decisions)

`get_jev_client()` returns a `JevClient`, or `None` without `JEV_API_KEY`. Methods: `choose`, `score`, `yes_no`,
`ask` (several questions in one call). Ready-to-copy examples: `agent/jev_examples.py` (`pick_product`, `is_yes`).
**Nothing in the default agent calls it.** Format and uses:
[apps/ai/README.md#jev-decision-model](apps/ai/README.md#jev-decision-model).

<a id="cache-prompt"></a>
#### 4.8 Prompt cache (Anthropic)

A request's prefix (tools → system prompt → messages) weighs ≈ 27k tokens in the reference pack (≈ 44 KB of
`DATA_DIR/context/*.md` + tool schemas). `clients/anthropic.py` sets 3 cache points `cache_control:
{"type": "ephemeral"}` (the API accepts 4): on the **last tool**, on the **system block**, and on the **last block of
the last message**. The next step of the same turn (after a tool result) and the next turn therefore reread the whole
already-seen prefix from the cache: ≈ 10% of the input price and a faster first token. Lifetime: 5 min after last
use; writing the cache costs ≈ 1.25× the normal price, once.

- **Seeing the hits**: the `done` event of `POST /chat` carries `usage.cacheReadInputTokens` (read from the cache)
  and `usage.cacheCreationInputTokens` (written); `make chat` displays them ("cache lu … / écrit …" — "cache read …
  / written …"). At Anthropic, `inputTokens` only counts the **non-cached** part (total = input + cacheCreation +
  cacheRead).
- **What breaks the cache** (any changed byte invalidates what follows): a timestamp, an id or a counter in the
  system prompt; editing a file in `DATA_DIR/context/` (normal: the next turn rewrites the cache); adding, removing
  or reordering tools, or changing a docstring / an argument; changing model or `LLM_EFFORT`; rewriting an old
  message in the history. The date comes from `GET /api/meta` (stable), not from the clock.

### Pitfalls

See [9](#pieges): voice history in memory, optional STT hint (`hint` in `audio_start`, not sent by the Voix page).
Prompt cache: only the Anthropic adapter sets it ([4.8](#cache-prompt)).

---

<a id="outils"></a>
## 5. Tools (`@tool`) in detail

### What it is

A tool is an `async` Python function the model can call. The `@tool` decorator derives from it the name, the
description and the JSON schema sent to the model. Each tool calls the ERP over HTTP; it contains no business rule.

### Key files

| File | Content |
|---|---|
| `apps/ai/app/tools/registry.py` | `@tool`, `Tool`, `ToolContext`, `ToolArgs`, `TOOLS`, `json_schema` |
| `apps/ai/app/tools/erp.py` | `ErpClient` (`get`, `post`, `patch`, `delete`, shared pool `erp_http()`), `ErpError`, `enc`, `pick` |
| `apps/ai/app/tools/catalog.py` · `context.py` · `history.py` · `orders.py` | the 16 tools |
| `apps/ai/app/tools/__init__.py` | imports the modules (= registers the tools), `all_tools()` |
| `apps/web/src/features/assistant/tools.tsx` | `TOOL_LABEL`: French label shown in the UI |

### How it works

<a id="decorateur"></a>
#### 5.1 The decorator

```python
# apps/ai/app/tools/registry.py:69-83
def tool(fn=None, *, name=None):
    def register(fn) -> Tool:
        params = list(inspect.signature(fn).parameters.values())[1:]  # skip ctx
        fields = {p.name: (p.annotation, ... if p.default is inspect.Parameter.empty else p.default) for p in params}
        args_model = create_model(f"{fn.__name__}_args", __base__=ToolArgs, **fields)
        description = " ".join(line.strip() for line in inspect.cleandoc(fn.__doc__ or "").splitlines() if line.strip())
        t = Tool(name=name or fn.__name__, description=description, args_model=args_model, fn=fn)
        TOOLS[t.name] = t
        return t
    return register(fn) if fn else register
```

| Python element | Becomes, for the model | Example |
|---|---|---|
| function name (or `@tool(name="…")`) | tool name | `get_product_stock` |
| docstring (lines joined with spaces) | `description` | "Stock d'un produit : …" ("A product's stock: …") |
| 1st parameter | **nothing**: it's the `ToolContext` | `ctx: ToolContext` |
| other parameters | `parameters` (JSON schema), camelCase names (`ToolArgs`, `alias_generator=to_camel`) | `product_id` → `productId` |
| no default, or `= Field(description=…)` without default | `required` | `client_id: str = Field(description="ex. cli_0012")` |
| `X \| None = None` or `Field(None, …)` | optional, without `null` in the schema | `qty: float \| None = Field(None, …)` |
| `Literal["a", "b"]` | `enum` | `entity_type: Literal["client", "supplier", …]` |
| `list[Literal[…]]` | `array` of `enum` | `types` of `search` |
| subclass of `ToolArgs` | nested object, inlined (no `$ref`) | `lines: list[OrderLine]` (`orders.py:10`) |
| `Field(description=…)` | the parameter's `description` | |

`json_schema` (`registry.py:89-111`) removes titles, defaults, `$defs`/`$ref` and `| null`: the schema looks like
what you'd write by hand. Check it with `curl -s localhost:4100/tools`.

**Validation** (`Tool.run`, `registry.py:57-63`): the model's arguments are validated by the generated Pydantic
model (camelCase or snake_case accepted). Failure → `ValueError("Arguments invalides : qty: …")`, which the loop
sends back to the model as `{"error": …}`. The function then receives typed Python values (nested objects are
`ToolArgs` instances, hence `line.to_erp()` in `orders.py`).

**`ToolContext`** (`registry.py:34-37`): `ctx.erp` is an `ErpClient` already tagged with `x-actor` (`ai_chat` or
`voice_agent`) and `x-actor-name`; `ctx.actor` lets you adapt the behavior (e.g. an order's `source`,
`orders.py:55`). `ctx.erp.get(path, query)` removes `None`/empty parameters; `ctx.erp.post(path, body)`; an ERP
refusal raises `ErpError` with its French message (`erp.py:76-81`), which the model will read.

**Registration**: importing the module is enough (`tools/__init__.py:14`). `all_tools()` is reread on every
request; all modes receive all the tools. A badly declared tool (not `async def`, no `ctx: ToolContext`, parameter
without a type, no docstring, duplicate name) makes startup fail with a French message; the full trace is shown in
the server's terminal.

**Return value**: any JSON-serializable value (dict, list, str, number). It is serialized as compact JSON and added
to the conversation: the model rereads it **at every following step** of the turn, and in voice mode it stays in the
history. Hence the `pick(...)` and `[:5]` everywhere.

#### 5.2 The 16 tools

| Tool | File | Calls | Returns (reduced) |
|---|---|---|---|
| `search(query, types?)` | `catalog.py:12` | `GET /api/search` | first 8 `{type, id, label, sublabel}` |
| `get_client(client_id)` | `catalog.py:31` | `GET /api/clients/{id}` | status, terms, outstanding, 5 notes, 10 lines of the usual, `openIssues`, 5 events, 5 orders |
| `get_product_stock(product_id)` | `catalog.py:55` | `GET /api/products/{id}` | `available`, `onHand`, `reserved`, `incoming`, `nextExpiry`, price |
| `find_alternatives(product_id)` | `catalog.py:70` | `GET /api/products/{id}/alternatives` | 5 products |
| `get_price(client_id, product_id, qty?)` | `catalog.py:80` | `GET /api/prices/resolve` | `price`, `listPrice`, `source`, `explanation`, `betterPriceWithVolume?` |
| `search_context(query, entity_type?, entity_id?, kind?, limit?)` | `context.py:36` | `GET /api/context?q=` | compact entries (body ≤ 500 chars) |
| `get_context(entity_type, id)` | `context.py:56` | `GET /api/context/for` | `{about, entries, related}` |
| `save_context(entity_type, kind, title, body, entity_id?, tags?)` | `context.py:75` | `POST /api/context` | `{id, saved, title}` |
| `get_client_history(client_id, types?, limit?)` | `history.py:49` | `GET /api/clients/{id}/events` | open first, ≤ 20 |
| `log_client_event(client_id, type, title, …)` | `history.py:65` | `POST /api/clients/{id}/events` | the compact event |
| `get_supplier_history(supplier_id, types?, limit?)` | `history.py:96` | `GET /api/suppliers/{id}/events` | open first, ≤ 20 |
| `log_supplier_event(supplier_id, type, title, …)` | `history.py:111` | `POST /api/suppliers/{id}/events` | the compact event |
| `create_draft_order(client_id, delivery_date?, lines?, note?)` | `orders.py:38` | `POST /api/orders` | `summarize_order`: id, number, status, lines with `lineId`, `warnings` |
| `add_order_line(order_id, product_id, qty, note?, substitute_for?)` | `orders.py:60` | `POST /api/orders/{id}/lines` | same |
| `confirm_order(order_id)` | `orders.py:74` | `POST /api/orders/{id}/confirm` | same |
| `get_order(order_id)` | `orders.py:83` | `GET /api/orders/{id}` | same |

What the agent can't do for lack of a tool (the routes exist): modify/remove a line, change the date, cancel,
prepare, deliver, invoice, collect payment, purchase, manage prices, stock, delivery runs.

<a id="ajouter-outil"></a>
#### 5.3 Extending: adding a simple tool

`list_overdue_invoices` — the ERP already computes `overdue` and `daysOverdue` (`services/invoices.py:25-41`):

```python
# apps/ai/app/tools/billing.py  (new file)
"""Billing tools: what a client owes."""

from pydantic import Field

from .erp import pick
from .registry import ToolContext, tool


@tool
async def list_overdue_invoices(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Factures échues (en retard) d'un client, avec le total dû. À utiliser quand le client demande ce qu'il doit,
    pourquoi il est bloqué, ou avant d'accepter une grosse commande. Overdue invoices of a client.
    """
    invoices = await ctx.erp.get("/api/invoices", {"clientId": client_id, "status": "overdue"})
    return {
        "count": len(invoices),
        "totalDue": round(sum(i["balance"] for i in invoices), 2),
        "invoices": [pick(i, "number", "dueDate", "balance", "daysOverdue") for i in invoices[:5]],
    }
```

(The French docstring says: "A client's overdue invoices, with the total due. Use it when the client asks what they
owe, why they are blocked, or before accepting a large order.")

Then:

1. `apps/ai/app/tools/__init__.py`: `from . import billing, catalog, context, history, orders`.
2. `curl -s localhost:4100/tools | grep -A3 list_overdue` (uvicorn has reloaded).
3. `make chat` → "qu'est-ce que doit le Zinc des Halles ?" ("what does Le Zinc des Halles owe?").
4. Optional: `TOOL_LABEL.list_overdue_invoices = "Factures en retard"` in
   `apps/web/src/features/assistant/tools.tsx:21`.
5. If the tool changes the expected behavior, add a one-line rule in `BASE_RULES` (`agent/prompts.py`).

**A write tool**: `ErpClient` has `get`, `post`, `patch` and `delete`. For `PUT`, add a method in `tools/erp.py`
modeled on `patch`:

```python
async def put(self, path: str, body: Any = None) -> Any:
    return await self._request("PUT", path, json={} if body is None else body)
```

Example: `update_order_line` → `await ctx.erp.patch(f"/api/orders/{enc(order_id)}/lines/{enc(line_id)}", {"qty": qty})`.
With the `repeat` route from [2.6](#ajouter-endpoint): `await ctx.erp.post(f"/api/orders/{enc(order_id)}/repeat", {})`.

<a id="outil-composite"></a>
#### 5.4 Extending: a composite tool

A model round trip costs far more than a local HTTP call. A tool that chains several ERP calls saves steps in the
loop:

```python
# in apps/ai/app/tools/catalog.py (search, pick, enc, format_number are already there)
import asyncio

@tool
async def quote_product(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    product_query: str = Field(description="Ce que le client a dit, ex. « bar de ligne », « loup »"),
    qty: float | None = Field(None, description="Quantité (défaut 1)"),
) -> dict:
    """
    Trouve un produit à partir de ce que dit le client et renvoie en un seul appel son stock et SON prix.
    À utiliser quand un client connu demande « vous avez du … ? » ou « c'est combien le … ? ».
    Product lookup + stock + client price in one call.
    """
    hits = await ctx.erp.get("/api/search", {"q": product_query, "types": "product", "limit": 3})
    if not hits:
        return {"found": False, "query": product_query}
    product_id = hits[0]["id"]
    product, price = await asyncio.gather(
        ctx.erp.get(f"/api/products/{enc(product_id)}"),
        ctx.erp.get("/api/prices/resolve", {"clientId": client_id, "productId": product_id,
                                            "qty": format_number(qty) if qty else None}),
    )
    return {
        "found": True,
        "product": pick(product, "id", "name", "unit", "available", "nextExpiry"),
        "price": pick(price, "price", "source", "explanation"),
        "otherMatches": [pick(h, "id", "label") for h in hits[1:]],
    }
```

(The French strings: `product_query` = "What the client said, e.g. 'bar de ligne', 'loup'"; `qty` = "Quantity
(default 1)"; the docstring = "Finds a product from what the client says and returns its stock and THEIR price in a
single call. Use it when a known client asks 'do you have …?' or 'how much is the …?'.")

Keep `otherMatches`: the model can ask "which one?" when the search is unsure.

#### 5.5 Good practices

- **Description = when to use it.** First sentence in French (what the tool does), then "À utiliser quand…" ("Use it
  when…"), then a short English sentence (models route better). Name the neighboring tools ("pas pour une
  réclamation : `log_client_event`" — "not for a complaint: `log_client_event`", `context.py:87`).
- **Parameters described with an example id** (`ex. cli_0012`) and `Literal` whenever the values are a closed set.
- **Small outputs**: `pick` the useful fields, truncate lists, shorten texts (`compact`, `compact_event`). No raw ERP
  object.
- **Errors**: raise an exception with a French message; don't return a silent `{"ok": false}`.
- **Writes**: make them safe to replay when possible (the model retries after an error), return the created id for
  the next steps, and leave confirmation to the prompt ("ne confirme qu'après accord explicite" — "only confirm after
  explicit agreement", `BASE_RULES`) or to a separate tool (`create_draft_order` then `confirm_order`).
- **No business rule in the tool**: if a calculation is missing, add it in `apps/backend/app/services/`.

### Pitfalls

- `@tool` **replaces the function with a `Tool` object**: `await get_price(...)` doesn't work. Call
  `await TOOLS["get_price"].run({...}, ctx)` or `tool.fn(ctx, ...)`.
- The function must be `async` and its parameters **annotated** (otherwise the schema is wrong).
- Python ordering: a parameter without a default can't follow a parameter with a default. `Field(description=…)`
  without a value counts as a Python default but stays required for the model: use it to keep the order.
- A return value that isn't JSON-serializable (object, `datetime`) becomes `{"error": "… non sérialisable en JSON
  …"}` ("… not JSON serializable …") for that call only (`execute_tool`, `loop.py`): return `str` / numbers / lists
  / dicts.
- Two tools with the same name: the last one imported overwrites the first in `TOOLS`.

---

<a id="frontend"></a>
## 6. Frontend (`apps/web/src`)

### What it is

A React 18 + Vite + Tailwind + react-router + TanStack Query SPA. It talks to the ERP (`/api`) and the AI service
(`/ai`) through the Vite proxy. Shared types: `@kit/shared` (`packages/shared/src`).

### Key files

| Path | Role |
|---|---|
| `main.tsx` | `QueryClient` (staleTime 15 s, retry 1), business clock loaded before the first render |
| `app/routes.tsx` | all the routes (one page = `pages/<name>/index.tsx`, default export) |
| `app/nav.ts` | side menu + ⌘K "Aller à" (Go to) commands |
| `app/AppShell.tsx` | sidebar · page · Assistant panel; mounts SSE, ⌘K, toasts, voice command; shortcuts ⌘J, ⌘\ / ⌘B |
| `lib/api.ts` | typed client: one function per ERP route, errors → toast + `ApiRequestError` |
| `lib/queries.ts` | `qk` query keys, one hook per read, `useApiMutation`, SSE stream, `INVALIDATE` |
| `lib/url-state.ts` | filters in the URL (`useUrlState`, `useUrlPatch`, `useDebounced`) |
| `lib/clock.ts` | `businessNow()` / `businessToday()` aligned with `meta.today` |
| `ui/` | the design system (`@/ui`) — [DESIGN.md](DESIGN.md), `ui/README.md` |
| `features/assistant/` | chat (⌘J), voice session, audio player, tool display |
| `features/voice-command/` | ⌥Space: engine, HUD, button |
| `features/document/` | shared blocks for document pages (order, purchase) |
| `pages/voice/` | Voix page (call + command mode, timeline, metrics, live activity) |

### How it works

<a id="donnees-web"></a>
#### 6.1 Reading and writing data

```ts
// read
const { data, isLoading } = useOrders({ status: "draft" });          // lib/queries.ts:148
// write
const confirm = useApiMutation(api.orders.confirm, { success: "Commande confirmée", invalidate: [qk.orders.all] });
confirm.mutate(order.id);
```

- `request()` (`lib/api.ts:47-78`) adds `x-actor: user` / `x-actor-name: Moi` to writes, turns
  `{error:{code,message}}` into `ApiRequestError` and shows a toast (`{silent:true}` to turn it off).
- `qk` keys are prefixed: invalidating `qk.orders.all` (`["orders"]`) refreshes all order lists and detail pages.
- `useApiMutation` (`queries.ts:205-221`) toasts the success, toasts each `warnings[]` of the response, invalidates
  the given keys.

#### 6.2 State in the URL

`const [q, setQ] = useUrlState("q")`: filters live in `?q=&type=`, survive a reload, can be shared. Changing a filter
resets pagination to 1 (unless `{keepPage:true}`). Several setters in the same tick are merged
(`url-state.ts:15-40`). Large lists are paginated by the API ([Pagination](#pagination)): `useServerList({
defaultSort })` reads `?page=` and `?sort=-field` and gives `params` (`limit`, `offset`, `sort`, `order`) to pass to
the `use…Page` hook, which returns `{items, total, counts, sums…}`; `<DataTable server={{ list, total }}>` displays
the page and the pagination bar. Reference lists (clients, products, suppliers for the pickers) are loaded in full
with `useClients()` / `useProducts()` / `useSuppliers()` (`limit=500`, `LIST_MAX` in `lib/api.ts`).

#### 6.3 Clock

Never use `new Date()` for "today": `businessToday()` / `businessNow()` (`lib/clock.ts`).

<a id="live"></a>
#### 6.4 Live updates

`useActivityStream()` (`queries.ts:273-299`) opens `EventSource("/api/events/stream")`, reconnects with backoff, and
for each `ActivityEvent`: adds it to the cached event lists, invalidates the keys in `INVALIDATE[entity]`
(`queries.ts:232-243`), marks the id for the purple flash (`useRecentlyChanged`, `DataTable` does it on its own) and
notifies `useOnActivity` subscribers. Pages never poll.

<a id="surfaces-ia"></a>
#### 6.5 The three AI surfaces

| Surface | Code | Transport | State |
|---|---|---|---|
| Assistant (⌘J) | `features/assistant/AssistantPanel.tsx`, `chat-store.ts`, `ai-client.ts` | `fetch POST /ai/chat`, SSE read by hand (`ai-client.ts:59-75`) | module store: survives closing the panel, not a reload |
| Voix · Appel (`/voice`) | `pages/voice/index.tsx`, `features/assistant/useVoiceSession.ts`, `audio-player.ts` | `WebSocket /ai/voice`, MediaRecorder in 100 ms slices (live STT) | `sessionId` in the hook; history on the server side |
| Voix · Commande (⌥Space, `/voice?mode=command`) | `features/voice-command/engine.ts`, `VoiceCommand.tsx`, `pages/voice/command.tsx` | voice: `WS /ai/voice/command?speak=1` (100 ms frames, live STT); keyboard: `fetch POST /ai/command?speak=1` (JSON), SSE | module singleton shared by HUD / page |

- Mock audio: mime `audio/x-mock-wav` (`MOCK_TTS_MIME`) → the browser reads the text with `speechSynthesis` fr-FR.
- Tool calls are displayed with `features/assistant/tools.tsx` (`TOOL_LABEL`, links to the entity).
- Space = push-to-talk on `/voice` outside a text field (`pages/voice/index.tsx:50-75`); ⌥Space everywhere, even in a
  field (`VoiceCommand.tsx:23-40`).

<a id="ajouter-page"></a>
### Extending: adding a page (6.6)

1. `apps/web/src/pages/overdue/index.tsx`:

   ```tsx
   import { Link } from "react-router-dom";
   import type { InvoiceSummary } from "@kit/shared";
   import { useInvoices } from "@/lib/queries";
   import { DataTable, Money, Page, PageBody, PageHeader, type Column } from "@/ui";

   const columns: Column<InvoiceSummary>[] = [
     { id: "number", header: "Facture", mono: true, cell: (i) => <Link to={`/invoices/${i.id}`}>{i.number}</Link> },
     { id: "client", header: "Client", sortValue: (i) => i.clientName, cell: (i) => i.clientName },
     { id: "days", header: "Retard (j)", numeric: true, sortValue: (i) => i.daysOverdue, cell: (i) => i.daysOverdue },
     { id: "balance", header: "Reste dû", numeric: true, sortValue: (i) => i.balance, cell: (i) => <Money value={i.balance} /> },
   ];

   export default function OverduePage() {
     const { data, isLoading } = useInvoices({ status: "overdue" });
     return (
       <Page>
         <PageHeader title="Retards" count={data?.length} />
         <PageBody flush>
           <DataTable columns={columns} rows={data ?? []} getRowId={(i) => i.id} loading={isLoading} />
         </PageBody>
       </Page>
     );
   }
   ```

2. `app/routes.tsx`: `import OverduePage from "@/pages/overdue";` and `{ path: "overdue", element: <OverduePage /> }`.
3. `app/nav.ts`: an entry in the "Finance" group (`{ to: "/overdue", label: "Retards", icon: … }`).
4. A new entity written by the ERP? Add its row in `INVALIDATE` (`queries.ts:232`) and its entity type in
   `ActivityEvent["entity"]` (`packages/shared/src/domain.ts:316`).
5. `make check` (typecheck + guardrails). Components: only `@/ui`, never `<select>` or `<input type="date">`.

Reference pages to copy: `pages/clients` (list), `pages/client-detail` (detail), `pages/activity` (feed).

### Pitfalls

- A type changed on the Python side doesn't break the web build: `packages/shared/src/*.ts` must be updated by hand.
- `AppShell` enforces `min-w-[1024px]`: the UI isn't made for mobile.
- The chat keeps its history in module memory: reloading the page loses it (the AI service doesn't know it).

---

<a id="donnees"></a>
## 7. Data

### What it is

Your company's pack: `DATA_DIR/seed/*.json` (the ERP's tables) and `DATA_DIR/context/` (business documents).
`DATA_DIR=./data` in the team zip; mounted read-only in Docker (`/data`).

### Key files

`DATA_DIR/seed/*.json`, `DATA_DIR/context/*.md`, `DATA_DIR/context/clients/`, `DATA_DIR/context/suppliers/`,
`apps/backend/app/crud/__init__.py` (`PACK`), `apps/backend/app/core/datapack.py`,
`apps/backend/app/services/context.py`.

### How it works

**Seed files → tables** (`crud/__init__.py:31-50`). Orders of magnitude for the reference pack:

| File | Table | Content | ≈ rows |
|---|---|---|---|
| `meta.json` | `meta` | `{company, today, currency, generatedAt}` | 1 object |
| `clients.json` | `clients` | contacts, zone, delivery days, terms, limit, status, preferences, notes, tags | 46 |
| `products.json` | `products` | catalog, unit, price, cost, aliases, shelf life | 66 |
| `suppliers.json` / `supplierPrices.json` | `suppliers` / `supplier_prices` | | 10 / 94 |
| `clientPrices.json` | `client_prices` (key `clientId\|productId`) | negotiated prices | 63 |
| `priceRules.json` | `price_rules` | price rules (groups, volume) | 16 |
| `lots.json` / `stockMovements.json` | `lots` / `stock_movements` | stock per lot, movements | 3,270 / 15,833 |
| `orders.json` / `purchaseOrders.json` | `orders` / `purchase_orders` | 3 years of sales / purchases | 2,192 / 696 |
| `invoices.json` / `payments.json` | `invoices` / `payments` | | 1,780 / 544 |
| `routes.json` / `routeRuns.json` | `routes` / `route_runs` | delivery runs | 6 / 80 |
| `clientEvents.json` / `supplierEvents.json` | `client_events` / `supplier_events` | relationship history | 2,015 / 500 |
| `tags.json` | `tags` (key `scope\|id`) | groups | 23 |
| `contextEntries.json` | `context_entries` | context entries | 641 |

The activity log (`events`) isn't in the pack: it's empty after a reset. Missing file = empty table.

**Context table**: an entry = `{id, entityType, entityId?, kind, title, body (markdown), tags, source}`.

- `entityType`: `company` (no `entityId`) | `client` (`cli_…`) | `supplier` (`sup_…`) | `product` (`prd_…`) |
  `category` (an id from `seed/categories.json`, specific to each company; `GET /api/categories`). Checked on write
  (`services/context.py:_check_target`).
- `kind`: `policy`, `procedure`, `preference`, `fact`, `relationship`, `pricing`, `logistics`, `risk`.
- `source`: `seed` or the actor that wrote it (`user`, `ai_chat`, `voice_agent`, `services/context.py:153`).
- Older packs call `entityType` "`scope`": converted on load (`datapack.py:32-36`).
- `GET /api/context/for?entityType=client&id=…` = the entity's entries + linked entries (what `get_context` loads).

**`DATA_DIR/context/` documents**:

- Top-level `*.md` (company, typical day, product glossary, client playbook, prices and credit, deliveries):
  **pasted in full into the system prompt** on every turn (`prompts.py:89-96`). Can be edited live.
- `clients/*.md`, `suppliers/*.md`: persona profiles for **the human playing the client** on the phone. They are
  **not** read by the agent; what the agent knows about a client is in the context table.

**Reset**: `make reset` (= `POST /api/admin/reset`) reloads the seed and clears the log; all writes are lost.
`make clean` also deletes the Docker database volume.

### Extending

Adding knowledge for the agent: an entry via the **Contexte** UI, `POST /api/context`, the `save_context` tool, or
one more `.md` in `DATA_DIR/context/` (watch the prompt size). Edit the seed then `make reset` to start from your own
data.

### Pitfalls

- In Docker, `DATA_DIR` is mounted read-only: edit the seed on the host, then `make reset`.
- `make reset` also erases everything the agent has learned (`save_context`) and the activity log.
- The team zip uses `DATA_DIR=./data` (already set in your `.env`).

---

<a id="tests"></a>
## 8. Tests and quality

### What it is

Offline Python tests for the AI service, a typecheck and guardrails for the web.

### Key files

`apps/ai/tests/` (`test_clients.py`, `test_speech_providers.py`, `test_tools_and_mock.py`, `test_jev.py`),
`scripts/check-no-native-controls.sh`, `scripts/check-no-native-date.sh`, `apps/backend/tests/parity.py`.

### How it works

| Command | Does | Prerequisites |
|---|---|---|
| `make test` | `cd apps/ai && uv run pytest -q`: adapters against recorded streams, tool schemas, mock, Jev — no network | uv on the machine |
| `make check` | `pnpm --filter @kit/web typecheck` + `scripts/check-no-native-controls.sh` (no native `<select>` or `<input type="date">`) | Node 22 + pnpm |
| `make types` | generates `packages/shared/src/generated/{backend,ai}.ts` from both `/openapi.json` | services running, Node + pnpm |

`apps/backend/tests/parity.py` compared the Python ERP with an old TypeScript API: it isn't useful during the
hackathon. There are no backend unit tests.

<a id="tester-sans-ui"></a>
### Extending: testing a tool or the agent without the UI

```bash
make chat                                   # terminal: tool calls and results shown, /reset, /exit
curl -s localhost:4100/tools | python3 -m json.tool | less          # schemas seen by the model
curl -N localhost:4100/chat -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"il reste du bar ?"}],"mode":"voice"}'
curl -N localhost:4100/command -H 'content-type: application/json' -d '{"text":"montre-moi le stock de turbot"}'
curl -s localhost:4100/stt -H 'content-type: audio/webm' -H 'x-mock-text: test' --data-binary @/dev/null
```

A single tool, in Python (from `apps/ai`, ERP running):

```python
# uv run python -c "import asyncio; from app.tools import TOOLS, ToolContext, ErpClient; ..."
import asyncio
from app.tools import TOOLS, ErpClient, ToolContext

ctx = ToolContext(erp=ErpClient("ai_chat", "test"), actor="ai_chat")
print(asyncio.run(TOOLS["get_product_stock"].run({"productId": "prd_0001"}, ctx)))
```

A test without the ERP: modeled on `test_tool_validates_arguments` (`tests/test_tools_and_mock.py:35`), which calls
`tool.run({...}, ctx=None)` on a tool that doesn't use `ctx`. Scripted WebSocket: send `{"type":"start"}` then
`{"type":"text","text":"…"}` (no mic needed).

**Mock providers** (no key): `MockLLM` understands a few French intents ("c'est la Poissonnerie Lemoine", "il reste
du bar ?", "4 kg de bar", "confirme la commande"…) and calls the **real** tools, one per step
(`clients/mock_llm.py`); it isn't an agent model. `MockSTT` returns the `x-mock-text` header if provided (`/stt`,
`/command`), otherwise `MOCK_STT_TEXT`. `MockTTS` returns a silent WAV with mime `audio/x-mock-wav`.

---

<a id="pieges"></a>
## 9. Known pitfalls and limits (verified in the code)

| # | Pitfall | Where | Consequence / workaround |
|---|---|---|---|
| 1 | **Voice history in memory** (`conversations`) | `services/voice_session.py:68` | lost on every restart of the AI service, including uvicorn's auto-reload when you save a file in `apps/ai/app` |
| 2 | **Alerts block nothing**: blocked client, credit limit, insufficient stock, unserved zone, price below cost = `warnings` | `services/orders.py:85-139`, `:274-276` | `confirm_order` succeeds anyway; it's up to the prompt or a tool to refuse |
| 3 | **Optional voice STT hint**: `audio_start` accepts `hint`, but the Voix page doesn't send one | `services/voice_session.py`, `features/assistant/useVoiceSession.ts` | without `hint`: no vocabulary (client, product names) and the mock STT hears `MOCK_STT_TEXT`; send `hint` in `audio_start` to enable it |
| 4 | **STT after release**: `transcribe_stream` isn't wired in | `clients/base.py:81-88` | no partial text while the caller is speaking |
| 5 | Only the **top-level** `*.md` of `DATA_DIR/context/` go into the prompt | `agent/prompts.py:92-94` | the `clients/` and `suppliers/` profiles aren't seen by the agent |
| 6 | `meta` (company, date) **cached for 60 s** on the AI side; `settings` read only once | `agent/prompts.py:70-86`, `config.py` | changing `.env` requires a restart |
| 7 | **Hand-written TS types**; `make types` writes to `generated/`, not exported | `packages/shared/src/index.ts` | update `domain.ts` / `api.ts` / `ai.ts` on every schema change |
| 8 | **Barge-in without rollback** | `services/voice_session.py:158-164` | an ERP write that went out before the interruption stays done |
| 9 | **Max 8 steps** then a give-up message | `agent/loop.py:38`, `:93-97` | `AGENT_MAX_STEPS` or composite tools |
| 10 | ⌥Space command **without memory**; navigation via a regex of French verbs + last entity seen | `services/command.py:40`, `:121` | "et ajoute 2 kilos" ("and add 2 kilos") doesn't know which order is meant |
| 11 | The TTS waits for **an end of sentence followed by a space** | `services/voice_session.py:235` | a long first sentence delays the first sound; the last sentence goes out on `finish()` |
| 12 | `thinking` blocks (Anthropic) and `thoughtSignature` (Gemini) kept **in process memory**, without limit | `clients/anthropic.py:22`, `clients/gemini.py` | after a restart, an old chat history is resent without them |
| 13 | ERP database **single-process**, synchronous services | `core/db.py` | no `--workers`; a heavy calculation blocks the API |
| 14 | The mock LLM calls **only one tool per step** | `clients/mock_llm.py` | latency measurements in mock say nothing about real parallelism |
| 15 | The chat history is **resent in full** with every message | `features/assistant/chat-store.ts:86` | it grows without limit; "Nouvelle conversation" (New conversation) clears it |
