# Voice hackathon — Participant brief

> English translation of [BRIEF.md](BRIEF.md). The French original is the reference.

24 hours to build a voice agent that does real work in a food wholesaler's ERP.
This brief explains the context, what we give you, what we expect and how to go about it.
Installation is in [SETUP.en.md](SETUP.en.md), the technical details of the kit in the [README](README.md).
Unknown word? [GLOSSAIRE.en.md](GLOSSAIRE.en.md) · A question? [FAQ.en.md](FAQ.en.md)

---

## 1. The context

Stockline builds software for food wholesalers: seafood, fruit and vegetables, meat, dairy, fine groceries,
beverages. These companies buy from their suppliers at night and deliver in the morning to hundreds of
restaurants, fishmongers, canteens, hotels and caterers.

In this trade, almost everything goes through voice:

- **Clients** call to order ("the usual", at 2 a.m.), ask whether the wild turbot has arrived, complain about a
  delivery, discuss a price.
- **Suppliers** are called to compare prices, negotiate, reserve a lot.
- **Carriers**, to book the fastest delivery run at the best price.
- **Prospects**, to sell and present the day's arrivals.
- **Colleagues**: "how much sea bass do we have left?", "how many days does this client pay at?", "what's going
  on with Ostréa?".

Every call ends up in the ERP: an order, a price, a complaint, a payment, a delivery run. Today, someone types
it in again by hand. A good voice agent listens, understands the trade, acts in the ERP during the call and
answers the way the company's best salesperson would.

## 2. The trade

A food wholesaler buys in bulk every night, keeps stock cold for a few days and delivers in the morning to
hundreds of professionals, with thin margins and products that spoil quickly. Clients, order taking, catalog,
prices, purchasing, stock and lots, picking, delivery runs, invoicing and receivables, complaints, seasons: each
part has its own vocabulary and its own pitfalls.

**Read the full reference: [METIER.en.md](METIER.en.md).** It is the best source of ideas for choosing your
problem, and it covers what your agent must understand to be credible.

## 3. The challenge

**Build the most useful voice agent you can on top of this ERP.**

There is no imposed topic. Your first step is to **pick a real problem** in this trade and **justify** why it is
that one: who calls whom, when, what it costs today, what the agent changes. Start from the context above and
from your company's data.

Your agent will be judged on three axes:

| Axis | What it means | How we see it |
|---|---|---|
| **Smart** | It knows the company, the client, the products, the history. It makes no mistakes, offers alternatives, handles ambiguity, acts correctly in the ERP. | It knows this chef refuses substitutions, suggests the right replacement, finds "le loup" (sea bass) in the catalog, creates the right order. |
| **Fast** | The answer comes quickly, with no awkward silence. | Delay from end of speech → first sound, number of model/tool round trips, cost per call. |
| **Natural** | You forget it is a machine. | Short sentences, the right tone, interruptions handled, numbers spoken aloud, order read back, background noise. |

The jury will test your agent **live**, on scenarios you will not know in advance.

## 4. What we give you

| What | Details |
|---|---|
| **The kit (code repo)** | A complete, simple ERP: clients, suppliers, products, stock and lots, pre-orders, orders, invoices, payments, receivables, delivery runs, negotiated prices, client/supplier history, context table. Python backend (FastAPI), Python AI service, React frontend. |
| **The ERP guide** | [ERP.en.md](ERP.en.md): every page, the lifecycles, the business rules (prices, stock, credit), the data model, the agent's tools and the API. |
| **A baseline agent** | A simple agent loop, ~16 tools that read and write the ERP, interchangeable LLM / STT / TTS clients (OpenAI, Anthropic, Gemini, Deepgram, Soniox, ElevenLabs, Gradium, or any OpenAI-compatible endpoint), a chat, a push-to-talk voice mode and a voice command mode. |
| **Call simulation** | No phone number: a **Voix** (Voice) page with two audio tracks. Hold Space to speak as the client, release, the agent answers. The ERP updates live before your eyes. |
| **The data (in your zip, `./data`)** | One fictional company per team (24 in total), with ~100 clients, its suppliers, its catalog and 3 years of history: orders at varied rhythms, seasons, complaints, late payments, detailed personas, company documents. |
| **Keys** (already in your `.env`) | LLM (Anthropic), transcription (Soniox), voice (ElevenLabs), Jev (fast decision model). With caps: watch your usage. |
| **Help** | The Stockline team on site all night to get you unstuck. |

Everything also runs **without keys**: fake models (mocks) answer deterministically and call the real ERP.
Useful for developing and testing without burning your credits.

## 5. Getting started

Each team receives a **zip**: the kit, its company's data (`./data`) and its configuration (`.env`, private).
**Follow [SETUP.en.md](SETUP.en.md)**: install Docker (do it before the hackathon), `make setup`, first call, team
repo. Count 20 to 30 minutes the first time.

Then:

1. Open **http://localhost:5173** and browse the ERP: clients, orders, stock, Contexte (Context). This is **your**
   company's data.
2. **Voix** page: hold Space and speak like a client. Watch the transcription, the tools called, the response
   times, and the ERP updating.
3. Read `apps/ai/app/agent/loop.py` (the loop) and `apps/ai/app/tools/` (the tools). That is where you will spend
   most of your time. The project map: [SETUP.en.md, How the project is organized](SETUP.en.md#how-the-project-is-organized).

## 6. How to approach it

A breakdown that works well over 24 h:

1. **Pick the problem (H0 → H2).** Read the client profiles (`data/context/clients/`) and the company documents
   (`data/context/`). Who calls? What for? What goes wrong today? Choose **one** use case and write it down in
   `DECISIONS.md` with your justification.
2. **Write your test scenarios (H2 → H3).** 5 to 10 realistic calls, including hard cases: ambiguous client,
   out-of-stock product, client blocked for unpaid invoices, change of mind mid-call, noise. These are your
   regression tests for the whole night.
3. **Get the end-to-end flow working (H3 → H8).** Real keys, real mic, one complete call that ends with the right
   action in the ERP. Ugly but complete.
4. **Measure, then improve (H8 → H20).** Record the latency, cost and errors of each scenario. Attack the worst of
   the three axes first. Retest after every change.
5. **Prepare the demo (H20 → H24).** Freeze the code, record the video, prepare the slides, rehearse the live
   demo.

Write down every important choice in `DECISIONS.md` as you go (what, why, what you tried and dropped). The jury
will read it.

## 7. Technical leads

These are not topics, just directions that make a difference. New to LLM agents? Read
[GUIDE-AGENTS.en.md](GUIDE-AGENTS.en.md): loop, tools, context, prompt caching, model choice, Jev, measurement,
pitfalls. For voice (end of speech → first sound latency, the kit's measurements, techniques to go faster and
sound natural, and where to plug them in): [GUIDE-VOIX.en.md](GUIDE-VOIX.en.md).

**To be fast**

- Streaming models everywhere: STT with partial transcripts, streaming LLM, sentence-by-sentence TTS.
- Speech-to-speech (native audio models) to remove steps.
- Parallelize: run independent tools together, preload the client's profile at the start of the call, anticipate
  the next tool call.
- A small fast model for simple turns (Jev for decisions), a big one only when needed.
- Deterministic code for what does not need a model: quantities, units, dates.

**To be smart**

- Context management: put in the prompt only what the turn needs.
- The **context table**: each fact is attached to a client, a supplier, a product or a category. Build on it:
  semantic search, a graph between entities, memory of what the agent learns during calls.
- Retrieval over history: open complaints, buying habits, negotiated prices.
- Orchestration: a main agent driving specialized agents, composite tools (search + stock + client price in a
  single call), a dialogue state for order taking.

**To be natural**

- Short speaking turns, interruptions (barge-in), small holding phrases while tools run.
- Read the order back before confirming, say numbers and units aloud ("douze kilos" — twelve kilos, "dix-huit euros
  cinquante" — eighteen euros fifty).
- Test with background noise (market, kitchen, truck) and accents.
- The right tone for each caller: the client profiles say how each one speaks.

## 8. Deliverables and final demo

To hand in before the end of the 24 h:

- [ ] **Your team's GitHub repo**, which runs with `make setup` once the `data/` folder from your zip is put back
  in place (`data/seed/` is not in git).
- [ ] **`DECISIONS.md`**: the problem chosen and why, your technical choices, what worked and what did not, your
  measurements (latency, cost, scenario success rate).
- [ ] **The slides**: 5 minutes maximum.
- [ ] **A demo video**: 2 minutes maximum, a real end-to-end call.
- [ ] **The live demo**: the jury calls your agent, live, on its own scenarios.

**Main prize**: the best agent on smart, fast and natural, plus the relevance of the problem chosen.

**Special prizes**:

| Prize | For |
|---|---|
| Fastest | the lowest end of speech → first sound latency, measured during the demo |
| Cheapest | the lowest cost per successful call |
| Most natural | the one mistaken for a human |
| Smartest | the one that best handles the jury's hard cases |

## 9. Rules and help

- You may change anything in the kit: ERP, tools, prompts, frontend, data. Keep it startable with `make setup` so
  the jury can launch it.
- All data is fictional. Never put an API key in the repo: keys go in `.env`, which git ignores.
- Keys have a cap. Develop with the mocks, test with the real keys.
- Stuck for more than 20 minutes? Come and see the Stockline team. That's what we're here for.
- Installation and common problems: [SETUP.en.md](SETUP.en.md). Architecture, configuration, adding a tool or a
  model provider: [README](README.md).
