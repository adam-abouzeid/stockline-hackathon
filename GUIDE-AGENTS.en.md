# GUIDE-AGENTS.md — building a good agent with the kit

> English translation of [GUIDE-AGENTS.md](GUIDE-AGENTS.md). The French original is the reference.

A guide for learning, not a code reference. Each section explains **the idea**, shows **where it lives in the
kit**, then gives concrete **advice**. For code details (lines, signatures, excerpts), follow the links to
[TECH.en.md](TECH.en.md): this guide doesn't copy them.

Prerequisites: the kit is running ([SETUP.en.md](SETUP.en.md)) and you have read the challenge
([BRIEF.en.md](BRIEF.en.md)). The code paths below start from `apps/ai/app/`.

## Contents

1. [What is an agent?](#1-what-is-an-agent)
2. [The harness](#2-the-harness)
3. [The agent loop](#3-the-agent-loop)
4. [Tools](#4-tools)
5. [Context and memory](#5-context-and-memory)
6. [Models](#6-models)
7. [Jev, the decision model](#7-jev-the-decision-model)
8. [Measuring and improving](#8-measuring-and-improving)
9. [Common pitfalls](#9-common-pitfalls)
10. [Going further](#10-going-further)

## I want… → section

| I want… | Section |
|---|---|
| to understand what an agent is, quickly | [1](#1-what-is-an-agent) |
| to know which file does what in the AI service | [2](#2-the-harness) |
| to understand why a turn takes 3 model calls | [3](#3-the-agent-loop) |
| to write a new tool that works first time | [4](#4-tools) |
| the agent to know the client better | [5](#5-context-and-memory) |
| to reduce cost and latency | [3](#3-the-agent-loop), [5.5](#55-the-prompt-cache), [6](#6-models), [7](#7-jev-the-decision-model) |
| to change model | [6](#6-models) |
| to decide "yes / no" or "which product" without an LLM | [7](#7-jev-the-decision-model) |
| to prove that my agent is improving | [8](#8-measuring-and-improving) |
| to avoid the classic mistakes | [9](#9-common-pitfalls) |

---

## 1. What is an agent?

### The idea

An **LLM** is a function: text goes in, text comes out. It knows nothing about your ERP, doesn't read the database,
doesn't create orders. It predicts the most plausible continuation, which means it will happily **make up** a price
or a stock level if you let it.

An **agent** is an LLM placed in a loop, with **tools** (functions it can ask to call):

```
   perceive             decide                 act                   observe
 (client message) ──► (the model picks ──► (the code runs ──► (the result comes back
                       a tool or answers)     the tool on the ERP)  into the conversation)
        ▲                                                                   │
        └───────────────────────── start again ◄────────────────────────────┘
                     until the model answers without a tool
```

The model never performs the action itself: it **asks for** `get_price(clientId, productId)`, your code runs it and
gives it back the result. That is what makes it reliable (the numbers come from the ERP) and controllable (you
decide which tools exist and what they return).

### Agent or plain code?

| Use an agent when… | Use code when… |
|---|---|
| the input is fuzzy ("le loup comme d'hab', mais moins" — "the sea bass as usual, but less") | the input is structured (a form, an id) |
| the path depends on the answer (stock-out → alternative → client agreement) | the path is always the same |
| you need to talk, rephrase, negotiate | you need to compute (prices, VAT, dates, units) |
| a few hundred ms and a cost per turn are acceptable | every millisecond or cent counts |

The right design is almost always **mixed**: the model understands and converses, the code computes and the ERP
applies the rules. In the kit, no business rule lives in the agent: prices, stock and credit are computed by the
backend (`apps/backend/app/services/`).

### In the kit

- The loop: `agent/loop.py` (`run_agent`).
- The tools: `tools/` (16 tools, `@tool` decorator).
- The mock (`clients/mock_llm.py`) imitates an agent without a key: useful for development, useless for judging
  intelligence.

### Advice

- Before coding, write the ideal call as a dialogue (client / agent) and note **which tool** serves each line.
  Lines with no possible tool are your next tools.
- Everything deterministic (converting "une demi-caisse" — "half a case", computing "vendredi prochain" — "next
  Friday"): in code, not in the prompt.

---

## 2. The harness

### The idea

The model is only one piece. The **harness** is everything around it: building the prompt, the tool registry, the
loop, the history, streaming, error handling and limits. Two teams with the same model get very different agents
depending on their harness. That's where you will gain the most.

### In the kit

```
         Voix page (WS /ai/voice)    assistant ⌘J (POST /ai/chat)    ⌥Space (POST /ai/command)
                    │                          │                              │
        services/voice_session.py        routers/chat.py              services/command.py
        STT → agent → TTS per sentence   history = browser            a single turn, no memory
        history in memory (~40 msgs)               │                              │
                    └──────────────┬───────────────┴──────────────────────────────┘
                                   ▼
                    agent/loop.py   run_agent(messages, llm, tools, mode)
                    ┌──────────────────────────────────────────────────────────┐
                    │ agent/prompts.py  build_system_prompt(mode)              │
                    │   role + BASE_RULES + mode rules + ERP date              │
                    │   + all DATA_DIR/context/*.md                            │
                    │                                                          │
                    │ loop ≤ AGENT_MAX_STEPS:                                  │
                    │   llm.stream(LLMRequest) ──► text (streamed) / calls     │
                    │   calls ──► execute_tool in parallel ──► tool messages   │
                    └───────────┬───────────────────────────────┬──────────────┘
                                ▼                               ▼
               clients/factory.py → get_llm_client()     tools/registry.py  TOOLS, @tool
               clients/anthropic.py · openai.py ·        tools/catalog.py · context.py ·
               gemini.py · mock_llm.py (raw httpx)       history.py · orders.py
                                                                 │ ctx.erp (tools/erp.py, x-actor)
                                                                 ▼
                                                         ERP API :4000 (business rules)
```

| Harness piece | File | Details |
|---|---|---|
| prompt assembly | `agent/prompts.py` | [TECH 4.3](TECH.en.md#prompts) |
| tool registry | `tools/registry.py`, `tools/__init__.py` | [TECH 5.1](TECH.en.md#decorateur) |
| loop, errors, step limit | `agent/loop.py` | [TECH 4.4](TECH.en.md#boucle) |
| history | depends on the mode (browser, voice session, none) | [TECH 4.4](TECH.en.md#boucle) |
| text and voice streaming | `clients/*.py`, `services/voice_session.py` | [TECH 4.5](TECH.en.md#latence), [4.6](TECH.en.md#session-voix) |
| provider choice | `clients/factory.py`, `config.py` | [TECH 4.1](TECH.en.md#config-ia) |

### Advice

- The harness is yours: everything can be changed. The most profitable levers are often the prompt, the tools and
  what goes into the context, not the model.
- Change one piece at a time and measure (section [8](#8-measuring-and-improving)).

---

## 3. The agent loop

### The idea

A **turn** (what the client says → what the agent answers) contains one or more **steps**. Each step is a full
model call, which rereads everything: system prompt, tools, history and tool results already obtained. Each extra
step therefore adds **latency** (a network round trip + generation) and **cost** (the whole context is billed again
as input).

### In the kit, step by step (`agent/loop.py`)

1. `run_agent` builds the system prompt once per turn (`build_system_prompt`) and an `LLMRequest` that points to the
   `messages` list.
2. **Step**: `llm.stream(request)` emits text (`LLMText`, streamed immediately to the UI or the TTS), tool calls
   (`LLMToolCall`, `tool_use` blocks at Anthropic) and usage (`LLMUsage`).
3. **No tool call** → it's the final answer: `done` event, end of the turn.
4. **Calls** → the `assistant` message (with its `tool_calls`) is appended, then **all the requested tools run in
   parallel** (`asyncio.gather`). Each result becomes a `tool` message (compact JSON) and we go back to 2.
5. **Tool errors**: `execute_tool` never raises. Unknown tool, invalid arguments, ERP refusal → the model receives
   `{"error": "…"}` and can explain or retry.
6. **Limit**: beyond `AGENT_MAX_STEPS` (8 by default), a `GIVE_UP` message.
7. **Cancellation**: when the client interrupts (barge-in) or disconnects, the asyncio task is cancelled and the
   loop stops without emitting anything. An ERP write that has already gone out stays done.

Line-by-line details: [TECH 4.4](TECH.en.md#boucle).

### What a step costs (measured)

Real test with the team keys (November 2026), Claude Sonnet 5.5, before prompt caching:

| Turn | Steps | Input tokens |
|---|---|---|
| simple stock question | 2 model calls | ≈ 54,000 (≈ 27,000 per call) |
| order taking | several calls | ≈ 117,000 |

Almost all of it comes from the system prompt (rules + company documents) resent at **every** step. Sonnet 5.5 chose
the right tools, prices and dates every time: quality wasn't the problem, volume was. Prompt caching, now active for
Anthropic, bills that prefix at a reduced rate (section [5.5](#55-the-prompt-cache)); it doesn't reduce the number
of steps.

### Advice

- Count the steps in your scenarios (`tool_call` events in the stream). One step fewer is often better than a
  faster model.
- Ask the model (in the prompt) to call independent tools **at the same time**: the loop already runs them in
  parallel.
- A composite tool (section [4](#4-tools)) replaces two or three steps.
- Don't raise `AGENT_MAX_STEPS` to hide a loop: if a turn goes beyond 4–5 steps, a tool or a prompt rule is
  missing.

---

## 4. Tools

### The idea

For the model, a tool is just three things: a **name**, a **description** and a **JSON schema** of the parameters.
It never sees your code. It decides to call the tool solely from the description, and fills in the arguments from
the schema. Then it reads the result, in full, at every following step.

Consequence: design a tool like an API for a busy colleague who only reads the docs.

### In the kit

- `@tool` (`tools/registry.py`) turns an `async` function into a tool: function name → name, docstring →
  description, annotated parameters → schema (camelCase for the model), `Field(description=…)` → parameter
  description, `Literal[…]` → enum. Received arguments are validated by Pydantic. Details:
  [TECH 5.1](TECH.en.md#decorateur).
- The 16 tools are in `tools/catalog.py`, `context.py`, `history.py`, `orders.py` ([TECH 5.2](TECH.en.md#outils)).
- `curl -s localhost:4100/tools` shows exactly what the model receives.

### Writing a good tool

| Rule | Why | Example in the kit |
|---|---|---|
| The description says **when** to use it, and names neighboring tools | the model chooses based on the description | `save_context`: "Pas pour une réclamation (utilise log_client_event)" ("Not for a complaint (use log_client_event)") |
| Parameters described with an example id | fewer malformed arguments | `client_id: str = Field(description="ex. cli_0012")` |
| `Literal` whenever the values are a closed set | the model can't invent a value | `search(types=…)`, `get_context(entity_type=…)` |
| **Small** output: only the useful fields | every byte is reread at each step, and in voice mode it stays in the history | `pick(...)`, `[:5]`, `summarize_order`, `compact` |
| Return the **ids** the next step needs | the model doesn't invent an id if it has one in front of it | `search` returns `id`; `summarize_order` returns `lineId` |
| A **composite** tool for a frequent sequence | a local HTTP call costs ms, a model step costs hundreds | `quote_product` in [TECH 5.4](TECH.en.md#outil-composite) |
| Writes that are **safe to replay** and in two stages | the model retries after an error; a confirmation can't be undone | `create_draft_order` then `confirm_order` |
| Raise an exception with a French message | the model reads `{"error": …}` and can explain it to the client | `ErpError` (`tools/erp.py`) |
| No business rule in the tool | a single source of truth: the backend | prices come from `/api/prices/resolve` |

**Ids rather than names**: the model finds the entity with `search` (fuzzy search), then works with the id. Don't
create a tool that takes a client name "as spoken" and guesses: fuzzy search returns several candidates, and it's up
to the model (or Jev, section [7](#7-jev-the-decision-model)) to ask "which one?".

### Anti-patterns

- A generic `query_erp(path)` tool: the model invents routes and reads huge raw ERP objects.
- Returning the full ERP object "just in case": thousands of tokens reread at every step.
- Two tools with almost identical descriptions: the model hesitates or alternates.
- A tool that confirms an order without an accepted summary (see [9](#9-common-pitfalls)).
- Returning `{"ok": false}` with no message: the model doesn't know what to say.

### Mini-example: from the bad version to the good one

Bad: vague description, raw object, nothing says when to use it.

```python
@tool
async def client_info(ctx: ToolContext, name: str) -> dict:
    """Infos client."""
    hits = await ctx.erp.get("/api/search", {"q": name, "types": "client"})
    return await ctx.erp.get(f"/api/clients/{hits[0]['id']}")   # guesses the 1st, returns everything
```

Good: takes an id, says when to use it, returns little.

```python
@tool
async def get_client_credit(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Situation de paiement d'un client : encours, retard, plafond, statut. À utiliser avant d'accepter une grosse
    commande ou quand le client demande pourquoi il est bloqué. Pour la fiche complète : get_client. Client credit status.
    """
    c = await ctx.erp.get(f"/api/clients/{enc(client_id)}")
    return pick(c, "status", "outstanding", "overdue", "creditLimit", "paymentTermsDays")
```

(The docstring, in French, says: "A client's payment situation: outstanding balance, overdue, limit, status. Use it
before accepting a large order or when the client asks why they are blocked. For the full profile: get_client.")

Then import it in `tools/__init__.py` and check with `curl -s localhost:4100/tools`. Full step-by-step:
[TECH 5.3](TECH.en.md#ajouter-outil).

### Advice

- Test a tool on its own before giving it to the model: `await TOOLS["name"].run({...}, ctx)`
  ([TECH 8](TECH.en.md#tester-sans-ui)).
- If the model doesn't call your tool, rewrite the description before touching the prompt.
- An irreversible confirmation = a separate tool + an explicit prompt rule (`BASE_RULES` already does this for
  `confirm_order`).

---

## 5. Context and memory

### 5.1 The idea: the context window

The model has no memory between two calls. Everything it "knows" at a step is in the request: system prompt + tool
definitions + history + tool results. That request is measured in **tokens** (≈ 3 to 4 characters in French) and it
has a maximum size, the **context window**. Well before the limit, an oversized context is expensive, slows down the
first token and dilutes attention: the model more easily misses the important rule buried in the middle.

### 5.2 The kit's system prompt

`build_system_prompt(mode, actor_name)` (`agent/prompts.py`) assembles, on every turn:

| Part | Content |
|---|---|
| `ROLE` | "AI assistant of {company}'s ERP", the business |
| `BASE_RULES` | tools for any data, `search` first, `get_price` for a price, context before answering, draft then explicit confirmation, alerts |
| `MODE_RULES[mode]` | `CHAT_RULES` (light markdown), `VOICE_RULES` (1–2 sentences, numbers in words, recap), `COMMAND_RULES` (act right away, one sentence) |
| date | the ERP's `meta.today`, in French (the data has its own simulated date) |
| caller | `actor_name` |
| company context | **all** the top-level `DATA_DIR/context/*.md` files, reread every turn |

Details: [TECH 4.3](TECH.en.md#prompts).

### 5.3 History, by mode

| Mode | Who keeps the history |
|---|---|
| `chat` | the browser, resent in full with every message |
| `voice` | the AI service, in memory, trimmed at ~40 messages (`trim` in `services/voice_session.py`) |
| `command` | nobody: a single message per request |

`run_agent` **appends** its messages to the list it is given: whoever keeps the list keeps the memory. Tool results
stay in it too, hence the value of small outputs.

### 5.4 Retrieve rather than load everything

Two strategies for giving knowledge to the model:

- **Put everything in the prompt** (stuffing): that's what the kit does with `DATA_DIR/context/*.md`. Simple, always
  available, but paid for at every step of every turn.
- **Fetch what's needed** (retrieval): the ERP's **context table**, through three tools in `tools/context.py`:
  - `get_context(entity_type, id)`: everything known about a client, supplier, product or department;
  - `search_context(query, …)`: full-text search in the entries (rules, procedures);
  - `save_context(…)`: remember a durable fact learned during the call (long-term memory shared with the team).

The `data/context/clients/` and `suppliers/` profiles are **not** in the prompt (only the top level is): the agent
sees them through the table, if it thinks of calling `get_context`.

### 5.5 The prompt cache

**The idea.** From one step to the next, the start of the request (tools + system prompt + start of the history) is
identical. The provider's prompt cache keeps that already-processed **prefix**: on the next call, cached tokens are
reread much faster and billed at a fraction of the normal price (about 10% at Anthropic; the initial write costs a
little more than a normal token; see the provider's pricing page). The Anthropic cache used here lasts 5 minutes.

**In the kit.** The `clients/anthropic.py` adapter sets three cache points (`cache_control`): on the last tool, on
the system prompt and on the last block of the conversation (`mark_last_block`). The next step of the same turn
(after a tool) and the next turn therefore reread the whole prefix from the cache. Other providers handle their cache
in their own way (or not at all): check their documentation.

**Why it matters here.** ≈ 27,000 input tokens per call, most of which is the same prefix; an order turn rereads
≈ 117,000. Without the cache, you pay full price for that prefix at every step. With the cache, the 2nd step of a
turn and the following turns of the same call reread it almost for free, and the first token arrives sooner.

**What breaks the cache.** The cache only works on a prefix that is **identical byte for byte**. Any change
invalidates what follows:

- editing a `.md` in `DATA_DIR/context/`, a rule in `prompts.py`, a tool description;
- adding, removing or reordering tools (at Anthropic, the prefix order is: tools, then system, then messages);
- putting in the system prompt something that changes every turn (a time, a counter, the current client's profile
  **before** the stable rules);
- changing mode or caller (`actor_name` is in the prompt).

So put the stable parts first and the variable parts last (in the messages, or in the last part of the prompt).

**Seeing the hits.** Look at `usage` in the `done` event (fields `cache_read_input_tokens` and
`cache_creation_input_tokens` in Python, `cacheReadInputTokens` / `cacheCreationInputTokens` in the `/ai/chat`
JSON); `make chat` displays them ("cache lu … / écrit …" — "cache read … / written …"). Cache-read tokens should be
high from the 2nd step of a turn; if they stay at 0, something in your prefix is changing. Careful: with the cache,
`input_tokens` only counts the **non**-cached part (total = `input_tokens` + written + read).

### Advice

- Measure your prompt's size before enriching it: each KB added is paid for at every step.
- Preload what is sure to be useful (the profile of the client identified at the start of the call) **at the end**
  of the prompt, and leave the rest to retrieval.
- For a long voice call, a summary of the older turns is better than 40 raw messages.
- Use `save_context` for what must survive the call ("livrer par la porte de service" — "deliver through the service
  entrance"); not for a complaint (`log_client_event`).

---

## 6. Models

### The idea

Three dials: **intelligence**, **latency**, **cost**. For a voice agent, latency to the first word matters as much
as intelligence. Recent models "think" before answering (internal reasoning): you no longer tune the temperature,
you tune the thinking **effort**.

### In the kit

| Anthropic model | Profile (`.env.example`) |
|---|---|
| `claude-sonnet-5-5` | default, balanced (`DEFAULT_MODELS` in `clients/factory.py`) |
| `claude-haiku-5-5` | fastest, cheapest |
| `claude-opus-5-5` | most intelligent, slowest |

Prices: the kit doesn't give any, see the provider's pricing page. Cost of a turn ≈ input tokens × input price +
output tokens × output price (+ a reduced rate for tokens read from the cache).

- **Change model**: in `.env`, `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-haiku-5-5`, then `make restart` (Docker)
  or restart `make dev`. `GET /ai/health` shows the active model. Other providers (OpenAI, Gemini, any
  OpenAI-compatible endpoint): [TECH 4.1](TECH.en.md#config-ia).
- **Effort**: `LLM_EFFORT` (`low` by default, `medium`, `high`), sent by `clients/anthropic.py` as
  `output_config.effort`. `low` keeps voice fast; raise it for a hard turn.
- **Streaming**: all clients stream; text goes to the TTS sentence by sentence.
- **Thinking**: the Anthropic adapter sends back the `thinking` blocks with the turn that calls tools (required by
  recent models).

### Routing between models

A single LLM client is built (`get_llm_client()`, cached). To route, build a second one with
`make_llm_client(LLMSettings(...))` and choose per turn:

- small model (Haiku) for simple turns: "il reste du bar ?" ("any sea bass left?"), "merci, au revoir" ("thanks,
  goodbye");
- big model (Sonnet / Opus) for negotiation, complaints, multi-line orders;
- the **router** can be a rule, or a Jev decision (section [7](#7-jev-the-decision-model)).

**Fallback**: if the provider returns an error (quota, outage), `run_agent` emits an `error` event. You can catch
that in the caller and rerun the turn on another client.

### Advice

- Compare models on **your** scenarios (section [8](#8-measuring-and-improving)), not on a hunch.
- Before changing model, reduce the context and the number of steps: it's often a bigger gain.
- The mock (`LLM_PROVIDER=mock`) only calls one tool per step: its latencies say nothing about the real model.

---

## 7. Jev, the decision model

### The idea

Jev (TypeSafe AI, model `jev-latest`) is **not an LLM**: it doesn't write text. You give it a **state** (a sentence
or JSON) and **typed questions**; for each one it returns a decision **with probabilities**. The probability is its
strength: when it's unsure, you know it, and the agent can ask the client instead of guessing.

| Type | You send | You receive |
|---|---|---|
| choice (`choose`) | options `{id: description}` | `choice`, `confidence`, `probabilities` |
| score (`score`) | ordered levels | `score` (e.g. 1.7), `confidence` |
| yes / no (`yes_no`) | a statement to check | probability of "yes", 0..1 |
| several at once (`ask`) | a dict of questions | all the answers in one call |

### When to use it instead of an LLM call

- **Which product the client meant** among the `search` results ("le bar de ligne" — line-caught sea bass, not "le
  bar d'élevage" — farmed sea bass).
- **Yes / no confirmation** after a summary ("ouais vas-y" — "yeah go ahead" = yes; "euh… plutôt le gros" — "uh…
  the big one, rather" = uncertain).
- **Intent routing**: order, stock question, complaint, price → which prompt, which tools, which model.
- **Scoring**: urgency, dissatisfaction, risk.

Keep the LLM for **talking** and for open-ended decisions.

### Measured latency

Real test (November 2026): `choose` ≈ 750 ms (752 ms, first call, cold), `yes_no` ≈ 170 ms (168 ms). Faster than an
LLM step with 27,000 tokens of context, but not free: measure it in your flow, and run it **in parallel** with
something else when possible.

### In the kit

- Client: `clients/jev.py` (`JevClient`: `ask`, `choose`, `score`, `yes_no`; question builders `choice_question`,
  `score_question`, `yes_no_question`).
- Access: `get_jev_client()` returns a `JevClient`, or `None` if `JEV_API_KEY` is empty.
- Examples to copy: `agent/jev_examples.py`
  - `pick_product(jev, utterance, candidates)` → the product id, or `None` if confidence is < 0.6;
  - `is_yes(jev, question, answer)` → `True` / `False` / `None` (≥ 0.8 yes, ≤ 0.2 no, otherwise uncertain).
- **Nothing in the default agent calls Jev**: it's up to you to plug it in. Format and uses:
  [TECH 4.7](TECH.en.md#jev), [apps/ai/README.md, Jev](apps/ai/README.md#jev-decision-model).

### Combining Jev and the LLM: "Jev decides, the LLM talks"

Two simple ways:

1. **Inside a tool**: a composite tool calls `search`, then `pick_product`; if Jev is sure, it returns the product,
   otherwise `{"ambiguous": true, "candidates": [...]}` and the LLM asks "which one?".
2. **Before the loop**: in `services/voice_session.py`, when the agent's last question was a summary, run `is_yes`
   on the client's answer; if `True`, you can confirm directly. If `None`, let the LLM rephrase.

### Advice

- Describe the options (`{"prd_1": "Bar de ligne 1-2 kg, Bretagne"}`) rather than giving bare ids.
- Set a confidence threshold and handle the "uncertain" case: that's where Jev makes the agent safer.
- Always keep the path without Jev working (`if jev:`): the key may be missing.

---

## 8. Measuring and improving

### The idea

Without measurement, you "improve" at random. An agent is measured on three axes, the same as the jury's:
**success** (the right action in the ERP), **latency**, **cost**.

### What the kit already measures

| Measurement | Where to read it |
|---|---|
| the turn's input, output and cache tokens | `usage` in the `done` event (`POST /ai/chat`, `make chat`) |
| total turn duration | `ms` in the `done` event |
| duration of each tool | `ms` in each `tool_result` |
| detailed voice latency | `timings` in `agent_done` (voice) and in `done` (`/command`): `sttMs`, `llmFirstTokenMs`, `llmTotalMs`, `ttsFirstByteMs`, `totalMs` |
| what the agent wrote | the ERP's activity log (in purple), `x-actor` |

The AI service has no logging: if you want a history of measurements, write each `done` event to a JSONL file from
the caller.

### Building a set of scenarios

1. Start from **your** company's documents (`data/context/*.md`, `clients/` profiles): every rule, preference or
   dispute is a potential scenario ("this chef refuses substitutions", "this client is blocked for unpaid
   invoices").
2. Write 5 to 10 scenarios: what the client says, and the **expected result in the ERP** (draft order with these
   lines, no confirmation, a complaint recorded…). Include hard cases: ambiguous client, stock-out, change of mind,
   blocked client.
3. Replay them in text (`make chat`, `curl /ai/chat`): it's faster and more reproducible than voice. Keep voice for
   latency and naturalness.
4. Record for each one: passed yes/no, number of steps, tokens, `ms`. `make reset` resets the ERP between two runs.

### Iterating

- **One change at a time**, then replay **the failing scenario**; the whole set once at the end.
- Attack the worst of the three axes first.
- Log every attempt (kept or dropped) in `DECISIONS.md` with its measurements: the jury reads it.
- Offline automated tests: `apps/ai/tests/` ([TECH 8](TECH.en.md#tests)).

---

## 9. Common pitfalls

| Pitfall | Symptom | Remedy |
|---|---|---|
| **Hallucinated id** | `{"error": "… introuvable"}` ("… not found"), or worse: the wrong entity | always `search` first; tools that return the useful ids; never an id in a prompt example that looks like a real one |
| **Tool loop** | same tool called 3 times, then `GIVE_UP` | clear error message in the tool; rule "if the tool fails twice, tell the client"; composite tool |
| **Huge tool outputs** | tokens explode, slow answers | `pick`, truncated lists, shortened texts |
| **Swelling prompt** | each turn slower and more expensive, rules ignored | context via retrieval, prompt cache intact ([5.5](#55-the-prompt-cache)), regular review of the `.md` files |
| **Order confirmed without read-back** | `confirm_order` called before the client's agreement | spoken summary + explicit agreement (`VOICE_RULES`), or Jev's `is_yes` |
| **Alerts ignored** | order confirmed for a blocked client | the ERP returns `warnings` but **blocks nothing**: the prompt or a tool must refuse ([TECH 9](TECH.en.md#pieges)) |
| **Client preferences ignored** | substitution offered to a client who refuses them | `get_context` on the client at the start of the call (or preloaded) |
| **Wrong date** | "tomorrow" computed from the real date | use `meta.today` (already in the prompt) |
| **Ids and markdown read aloud** | "c, l, i, underscore…" | `VOICE_RULES`; check the text of `agent_done` |
| **Write done despite the interruption** | the client cut in, the line was added anyway | no rollback on barge-in: read the order back at the end of the call |
| **Voice history lost** | the agent forgets everything after a file save | the voice history is in memory; uvicorn's auto-reload wipes it |
| **Measurements in mock** | excellent latencies in dev, bad ones in the demo | measure with the real keys |

Full list of the limits verified in the code: [TECH 9](TECH.en.md#pieges).

---

## 10. Going further

- **Orchestrator and specialized agents**: a main agent that delegates to an "order" agent, a "complaint" agent,
  each with fewer tools and a shorter prompt.
- **Dialogue state**: for order taking, a small structured state (client, lines, date, confirmed?) kept by the code,
  which the model reads and updates, rather than rebuilding everything from the history.
- **Planning**: have the model write a short plan before acting on a complex request, then execute it.
- **Automated evaluations**: replay the scenarios on every change, and have a "judge" model grade the naturalness of
  an answer against a fixed rubric.
- **Faster voice**: streaming STT (`transcribe_stream`, already implemented for Soniox and Deepgram), holding phrases
  during tools ([TECH 4.5](TECH.en.md#latence)).
- **Memory**: summarize a client's past calls into the context table with `save_context`.
