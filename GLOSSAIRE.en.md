# Glossary

> English translation of [GLOSSAIRE.md](GLOSSAIRE.md). The French original is the reference. French trade terms
> are kept in the first column (with an English equivalent) because they are the words callers will use.

The words you will come across in the kit, in plain language: first the **trade terms** of food wholesale
(calibre, DLC, franco, encours, tournée…), then the **technical terms**. The trade is explained in detail in
[METIER.en.md](METIER.en.md).

A practical question rather than a word? [FAQ.en.md](FAQ.en.md).

| Topic | Words |
|---|---|
| [1. Terminal and tools](#terminal) | terminal, folder, `cd`, `make`, Docker, image, container, port, localhost, `.env` |
| [2. Git and GitHub](#git) | git, repo, commit, push, GitHub |
| [3. Programs and networking](#reseau) | frontend, backend, service, API, endpoint, HTTP request, JSON, WebSocket, SSE, Python, async, FastAPI, React |
| [4. LLMs and agents](#llm) | LLM, prompt, token, context, prompt cache, agent, harness, loop, tool, Jev |
| [5. Voice and latency](#voix) | STT, TTS, streaming, latency, TTFT, first sound, barge-in, VAD |
| [6. The kit](#kit) | mock, ERP |
| [7. Trade terms](#metier) | calibre, DLC, FEFO, encours, franco, tournée, avoir, mercuriale… |

<a id="terminal"></a>
## 1. Terminal and tools

| Word | Definition | In the kit |
|---|---|---|
| **Terminal** | A window where you type commands instead of clicking. On Windows: the **Ubuntu** terminal (WSL), not PowerShell. | All the `make …` commands in [SETUP.en.md](SETUP.en.md) |
| **Current folder**, **`cd`** | The terminal is always "in" a folder. `cd voice-erp-kit` goes into it, `cd ..` goes up one level, `pwd` shows where you are. | `make` commands are run from `voice-erp-kit/` (where the `Makefile` is) |
| **`make`** | A shortcut: `make up` runs a series of commands written in the `Makefile`. | `make help` lists everything: `setup`, `up`, `down`, `logs`, `chat`, `reset`… |
| **Docker** | Software that runs programs in isolated boxes, with everything they need. Nothing else to install. | Docker Desktop, step 1 of [SETUP.en.md](SETUP.en.md) |
| **Image** | The "template" of a Docker box: the program and its dependencies, ready to run. | Built by `make setup` / `make rebuild`, or loaded from the USB stick (`make offline`) |
| **Container** | A running image. The kit starts three: `backend` (ERP), `ai` (agent), `web` (interface). | `make ps` lists them, `make logs` shows what they write |
| **Port** | The "door" number through which you talk to a program on a machine. | 5173 = interface, 4000 = ERP, 4100 = AI service |
| **localhost** | "My own machine". `http://localhost:5173` = the program listening on port 5173 of your computer. | Open http://localhost:5173 in Chrome |
| **Environment variable** | A setting (name = value) read by a program at startup, outside the code. | `LLM_PROVIDER=anthropic`, `AI_PORT=4100` |
| **`.env`** | The file that contains all these variables. Private: never in git. | A single `.env` at the root for all three services; after changing it: `make restart` |
| **API key** | A password that identifies you to a provider (Anthropic, Soniox…) and lets it bill you. | `LLM_API_KEY`, `STT_API_KEY`, `TTS_API_KEY`, `JEV_API_KEY` in `.env` |
| **Logs** | What programs write while they run: requests, errors. The first thing to check when something breaks. | `make logs` (Ctrl-C to exit) |

<a id="git"></a>
## 2. Git and GitHub

| Word | Definition | In the kit |
|---|---|---|
| **git** | A tool that keeps the version history of your code, file by file. | `git init`, step 4 of [SETUP.en.md](SETUP.en.md) |
| **Repo** (repository) | A folder tracked by git, with its whole history. | Your team repo = the `voice-erp-kit/` folder |
| **Commit** | A saved snapshot of your changes, with a message. | `git add . && git commit -m "filler before tools"` |
| **Push** | Sending your commits to an online repo. | `git push` to your private GitHub repo |
| **GitHub** | A site that hosts git repos online and lets you share them. | The "GitHub repo" deliverable in [BRIEF.en.md §8](BRIEF.en.md#8-deliverables-and-final-demo) |
| **`.gitignore`** | The list of files git does not track. | `.env` and `data/seed/` are in it, on purpose |

<a id="reseau"></a>
## 3. Programs and networking

| Word | Definition | In the kit |
|---|---|---|
| **Frontend** | The part you see: pages, buttons, in the browser. | `apps/web` (port 5173) |
| **Backend** | The invisible server part: data, rules, calculations. | `apps/backend` = the ERP (port 4000) |
| **Service** | A program that runs continuously and answers requests. | Three services: ERP, AI, web |
| **API** | The list of requests a program accepts from other programs. | The ERP's API: http://localhost:4000/docs; the AI service's: http://localhost:4100/docs |
| **Endpoint** (route) | A specific API address that does one thing. | `GET /api/products`, `POST /ai/chat`, `GET /tools` |
| **HTTP request** | A message sent to a web address. `GET` = read, `POST` = create or act, `PATCH` = modify. | `curl localhost:4100/tools` sends one from the terminal |
| **JSON** | A text format for exchanging data: `{"produit": "bar", "kilos": 5}`. | What the ERP and the agent's tools return |
| **WebSocket** | A connection that stays open between browser and server, in both directions. Ideal for streaming audio continuously. | `WS /ai/voice` (Voix page), `WS /ai/voice/command` (⌥Space) |
| **SSE** (*server-sent events*) | An HTTP response that arrives piece by piece, from server to browser. | `POST /ai/chat`: the agent's text appears as it is written |
| **Python** | The language of the backend and the AI service. Readable, lots of libraries. | `apps/backend`, `apps/ai` |
| **async** (asynchronous) | Code that can wait (for a network response) without blocking everything: meanwhile, something else moves forward. Keywords `async def` and `await`. | The whole AI service: several tools run in parallel (`asyncio.gather`) |
| **FastAPI** | A Python library that turns functions into API endpoints. | `routers/` of the ERP and the AI service |
| **React** | A JavaScript library for building the interface out of components. | `apps/web/src` (TypeScript) |
| **TypeScript** | JavaScript with checked types. | The frontend; `make check` verifies that it compiles |

<a id="llm"></a>
## 4. LLMs and agents

To go further: [GUIDE-AGENTS.en.md](GUIDE-AGENTS.en.md).

| Word | Definition | In the kit |
|---|---|---|
| **LLM**, **model** | *Large language model*: a program that predicts the continuation of a text, and can therefore answer, reason, call tools. | Anthropic by default: `claude-sonnet-5-5` (`LLM_MODEL` in `.env`) |
| **Prompt** | The text sent to the model: instructions + conversation. | Built by `agent/prompts.py` |
| **System prompt** | The fixed part of the prompt, which tells the model who it is and how to behave. | `build_system_prompt`: role, rules (`BASE_RULES`, `VOICE_RULES`…), company context |
| **Token** | A piece of a word (≈ ¾ of a word on average). Models read, write and bill in tokens. | The kit's prompt is ≈ 27,000 tokens per model call |
| **Context** | Everything the model sees at a given moment: system prompt, history, tool results. Its size is limited. | `data/context/*.md` (your company's knowledge) + the call history |
| **Prompt cache** | The provider remembers an identical prompt prefix from one call to the next: cheaper and faster. Changing a single byte at the start breaks it. | `clients/anthropic.py` (`cache_control`); `cache_read_input_tokens` in `usage` |
| **Agent** | An LLM that acts: it reads the request, calls tools, reads the results, repeats, then answers. | `agent/loop.py` (`run_agent`) |
| **Loop** | The "model → tools → model…" cycle until the final answer. | `AGENT_MAX_STEPS=8` turns at most |
| **Tool** | A function the model can ask to call, with a name, a description and parameters. | `@tool` functions in `apps/ai/app/tools/*.py` (`search`, `get_price`, `create_draft_order`…) |
| **Harness** | All the code around the model: the loop, the tools, the prompt, error handling. That's where you work. | `apps/ai/app/agent/` + `tools/` |
| **Jev** | A decision model from TypeSafe AI: not a chat model, it quickly answers closed questions (choice, yes/no, score) with a probability. Used **alongside** the LLM. | `get_jev_client()`, examples in `agent/jev_examples.py`; key `JEV_API_KEY` |

<a id="voix"></a>
## 5. Voice and latency

To go further: [GUIDE-VOIX.en.md](GUIDE-VOIX.en.md).

| Word | Definition | In the kit |
|---|---|---|
| **STT** (*speech-to-text*) | Transcription: voice becomes text. | Soniox by default with your keys (`STT_PROVIDER`); `services/utterance.py` |
| **TTS** (*text-to-speech*) | Speech synthesis: text becomes voice. | ElevenLabs (`TTS_PROVIDER`); `Speaker` in `services/voice_session.py` |
| **Streaming** | Processing data as it arrives instead of waiting for the end. | Audio goes to the STT while you speak; the LLM's text goes to the TTS sentence by sentence |
| **Partial transcript** | The provisional text the STT returns during speech, corrected afterwards. | Shown in grey italics on the Voix page |
| **Push-to-talk** | You hold a key while you speak; releasing it marks the end of speech. | Space on the Voix page, ⌥Space everywhere |
| **VAD** (*voice activity detection*) | Automatically detecting when someone is speaking and when they have finished. | Not in the kit: lead 4.2 in [GUIDE-VOIX.en.md](GUIDE-VOIX.en.md#vad) |
| **Latency** | The waiting time. Here: from the end of your sentence to the agent's first sound. | **Total** and **Perçu** (Perceived) columns on the Voix page |
| **TTFT** (*time to first token*) | Time between sending to the model and its first piece of response. | `llmFirstTokenMs` in each turn's measurements |
| **First sound** | The moment the caller hears the agent. It is the metric for the "fastest" prize. | `totalMs` (server) and `perceivedMs` (browser) |
| **Barge-in** | The caller interrupts the agent: the audio must stop and the agent must listen. | `interrupt()` in `voice_session.py` |

<a id="kit"></a>
## 6. The kit

| Word | Definition | In the kit |
|---|---|---|
| **Mock** | A fake provider, free and offline, that imitates the real one. For developing without a key. | `*_PROVIDER=mock`; the mock STT always hears "Bonjour, il vous reste du bar ?" ("Hello, do you have any sea bass left?") (`MOCK_STT_TEXT`) |
| **ERP** | The company's management software: clients, products, stock, orders, invoices. | `apps/backend` + the interface pages; see [ERP.en.md](ERP.en.md) |
| **Seed** | The starting data loaded into the ERP. | `data/seed/`; `make reset` reloads it |
| **`x-actor`** | A header that says who made a write in the ERP (`user`, `ai_chat`, `voice_agent`). | In purple in the interface: what the agent did |

<a id="metier"></a>
## 7. Trade terms

The vocabulary of food wholesale, and where it appears in the ERP (entities, fields, routes).

| Term (French — English) | Definition | In the ERP |
|---|---|---|
| Affrètement — chartering | Renting a truck or handing a delivery to a carrier | absent |
| Alias | Common name of a product ("loup" for sea bass / "bar") | `Product.aliases` |
| AOP, Label Rouge — PDO, Red Label | Official quality or origin marks | `Product.tags` (`labels`) |
| Arrivage, débarque — arrivals, landing | Goods coming in, what the boats bring back | `PurchaseOrder`, `Lot` |
| Avoir — credit note | Negative invoice after a return or a dispute | `credit_note` event |
| Balance âgée — aged balance | Receivables broken down by how late they are | `GET /api/receivables` |
| BL (bon de livraison) — delivery note | Document that accompanies the delivery | — |
| Bordereau de prix — price schedule | Prices fixed by a public contract | `ClientPrice`, `PriceRule` (`marche-public`) |
| Bourriche — oyster basket | Basket of oysters (e.g. 4 dozen) | unit `dozen` |
| Brouillon, pré-commande — draft, pre-order | Order not yet confirmed by the client | `Order.status = "draft"` |
| Calibre — size grade | Size of a product (1-2 kg, 15/20, no. 3) | `Product.caliber` |
| Chaîne du froid — cold chain | Continuous temperature control | — |
| Colis, caisse — parcel, case | Packaging unit | unit `box` (≈ 5 kg) |
| Commande d'achat — purchase order | Order placed with a supplier | `PurchaseOrder` |
| Commercial attitré — assigned sales rep | Salesperson responsible for a client | `Client.salesRep` |
| Complément — balance delivery | Remainder of an incomplete delivery, delivered later | `partially_received` |
| Couverture — stock cover | Number of days of sales the stock can sustain | — |
| Criée — fish auction | Hall where the catch is sold at auction | — |
| Cut-off, heure limite — cut-off time | Time after which the order goes to the next day | context only |
| DDM — best-before date | Minimum durability date, "best before" | — |
| Déclassement — downgrading | Product sold cheaper or processed because it looks less good | — |
| Démarque, perte, casse — shrinkage, loss, breakage | What gets thrown away | `waste` movement |
| DLC — use-by date | Use-by date, "use by" | `Lot.expiresAt`, `Product.shelfLifeDays` |
| Disponible — available | Physical stock minus reserved stock | `StockLevel.available` |
| DSO | Average client payment delay (days sales outstanding) | `GET /api/receivables` |
| Échéance — due date | Date by which the invoice must be paid | `Invoice.dueDate` |
| Échu, en retard — overdue | Invoice unpaid after its due date | computed status `overdue` |
| Encours — outstanding balance | Total owed by a client, € incl. VAT | `outstanding` |
| Extra — one-off | One-off order outside the usual pattern | — |
| FEFO | First expired, first out | `fefo_lots` in `services/stock.py` |
| Franco — free-shipping threshold | Amount above which transport is free | `Supplier.notes` |
| Geste commercial — goodwill gesture | Discount granted to fix a problem | event + `resolution` |
| HACCP | Hazard analysis method for food hygiene | — |
| L'habituel — the usual | What the client almost always orders | `GET /api/clients/{id}/usual` |
| Lot | One arrival of a product, with its expiry date | `Lot` |
| Mareyeur — fish wholesaler | First buyer of the fish at the auction, who prepares and ships it | `Supplier.tags` (`mareyeur`) |
| Marché public — public contract | A public body's purchasing contract after a tender | client tag `marche-public` |
| Mercuriale — price list | A supplier's price list of the day | `SupplierPrice` |
| MIN — national wholesale market | Marché d'intérêt national (Rungis, Lyon, Marseille…) | — |
| Minimum de commande — minimum order | Minimum amount to order from a supplier | `Supplier.minOrderAmount` |
| Plafond de crédit — credit limit | Maximum outstanding balance allowed | `Client.creditLimit` |
| Plan d'apurement — repayment plan | Schedule for paying off a debt | `payment_plan` event |
| Poids réel — actual weight | What the delivered goods actually weigh | `OrderLine.preparedQty` |
| Prix liste, catalogue — list price | Base price | `Product.price` |
| Prix négocié — negotiated price | A product's price for a specific client | `ClientPrice` |
| Prospect | Potential client | `Client.status = "prospect"` |
| Relance — reminder | Reminder for an unpaid invoice | `late_payment` event |
| Réservé — reserved | Stock promised to confirmed orders | `StockLevel.reserved` |
| RHD — food service | Restauration hors domicile (out-of-home catering) | — |
| Rupture — stock-out | No more stock available | `insufficient_stock` alert |
| Substitution | Product delivered instead of another, with agreement | `OrderLine.substituteFor` |
| Tournée — delivery run | A truck's circuit over a zone, on certain days | `Route`, `RouteRun` |
| Zone | A client's delivery area | `Client.zone` = `Route.zone` |
