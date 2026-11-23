# GUIDE-VOIX.md — building a fast, natural voice agent

> English translation of [GUIDE-VOIX.md](GUIDE-VOIX.md). The French original is the reference. Spoken examples
> stay in French (the agent talks to French callers), with an English gloss.

This guide explains how a voice agent "on the phone" works, what the kit does today, what it measures, and
**where to change the kit** to go faster and sound more human. The jury judges on *smart, fast, natural*, with a
special prize for the fastest (end of speech → first sound, measured during the demo): this guide mostly covers
*fast* and *natural*.

What this guide does not repeat: installation ([SETUP.en.md](SETUP.en.md)), the challenge
([BRIEF.en.md](BRIEF.en.md)), code details ([TECH.en.md](TECH.en.md), sections 1.3, 4 and 9), LLM agent concepts
(loop, tools, context, cache, models, Jev: [GUIDE-AGENTS.en.md](GUIDE-AGENTS.en.md)), the WebSocket protocol
([apps/ai/README.md](apps/ai/README.md#ws-voice-protocol)).

How to read the numbers: **measured** numbers come from a real test on the kit (November 2026). Any other number is
marked **order of magnitude**: it is a hypothesis to measure on your side, not a promise.

## Contents

1. [Anatomy of a speaking turn](#anatomie)
2. [The metrics](#metriques)
3. [What the kit measures today](#mesures)
4. [Speeding up, technique by technique](#accelerer)
5. [Sounding natural](#naturel)
6. [Robustness](#robustesse)
7. [The kit's providers](#fournisseurs)
8. [Plan of attack for 24 h](#plan)

## I want… → section

| I want… | Section | Files |
|---|---|---|
| to understand where a turn's time goes | [1](#anatomie), [3](#mesures) | `apps/ai/app/services/voice_session.py` |
| to know what to measure and how to prove it to the jury | [2](#metriques), [8](#plan) | `apps/web/src/pages/voice/metrics.tsx`, `DECISIONS.md` |
| to transcribe while the caller speaks (done) | [4.1](#stt-streaming) | `services/utterance.py`, `services/vocabulary.py`, `clients/soniox.py` |
| to remove push-to-talk (VAD) | [4.2](#vad) | `apps/web/src/features/assistant/useVoiceSession.ts` |
| to reduce the model's time | [4.4](#cache) to [4.6](#outils) | `clients/anthropic.py`, `clients/factory.py`, `tools/` |
| to keep the caller waiting without silence | [4.7](#fillers) | `voice_session.py` (`Speaker`) |
| numbers and dates to be spoken properly | [4.10](#deterministe), [5](#naturel) | `agent/prompts.py`, `tools/` |
| to handle interruptions | [5.2](#barge-in) | `voice_session.py` (`interrupt`), `useVoiceSession.ts` |
| to change voice or provider | [7](#fournisseurs) | `.env`, `clients/factory.py` |

---

<a id="anatomie"></a>
## 1. Anatomy of a speaking turn

### Two architectures

**Cascade** (what the kit does): three models in sequence.

```
caller's voice ─▶ STT (speech → text) ─▶ LLM (+ ERP tools) ─▶ TTS (text → speech) ─▶ speaker
```

**Speech-to-speech** (native audio "realtime" models): a single model listens to audio and produces audio.

| | Cascade | Speech-to-speech |
|---|---|---|
| Latency | sum of the steps, unless they overlap (streaming) | one step fewer, often shorter |
| Control | you read and fix each step (transcript, text, tool calls) | more of a black box; text available depending on the provider |
| Tools / ERP | any LLM with tool calling | depends on the realtime model |
| Voice | you choose the best French voice on the market | the model's voice |
| In the kit | ready, with your keys | **not provided**, and no realtime key is handed out |

Advice for 24 h: keep the cascade and **overlap the steps**. That's where the seconds are won.

### The kit's pipeline, over time

A voice turn on the Voix page (`WS /ai/voice`, `services/voice_session.py`, `VoiceConnection.run_turn`):

```
time ──────────────────────────────────────────────────────────────────────────────────▶
caller    [■■■■ speaks (Space held) ■■■■]│release = t0
browser   MediaRecorder webm/opus, frame every 100 ms ─▶ server ─▶ streaming STT (Soniox)
          ◀── partial transcript shown live ──│
server                                     │[finalize]│ final text
                                           │          │[── LLM ─▶ ERP tool(s) ─▶ LLM ──]
                                           │          │                     text ─▶ Speaker
                                           │          │                     │[TTS sentence 1]─▶ 1st mp3 byte
browser                                    │          │                     │   SegmentPlayer (MediaSource) plays
          ◀──────────────── totalMs: t0 → first audio byte sent by the server ──────────────▶
```

Key points in the code:

- **Push-to-talk**: Space pressed = `audio_start`, released = `audio_end` (`useVoiceSession.ts`, `startTalking` /
  `stopTalking`). No end-of-speech detection: the release provides it.
- **Live STT**: on `audio_start`, the session opens an `Utterance` (`services/utterance.py`) which opens the STT
  stream; each 100 ms frame (`rec.start(100)` in `useVoiceSession.ts`) is forwarded to it as soon as it arrives.
  Partial transcripts are displayed while the key is held. On release, Soniox receives `finalize` and returns the
  last words; `run_turn` starts the agent on that final text. If the stream breaks, the full recording is
  transcribed as before (`transcribe`). Client and product names are added to the STT hint
  (`services/vocabulary.py`).
- **Streaming LLM**: `run_agent(..., mode="voice")` (`agent/loop.py`) emits text as it goes; the tools of a single
  step run in parallel (`asyncio.gather`).
- **Sentence-by-sentence TTS**: `Speaker.push` splits as soon as a sentence ends with `. ! ? …` followed by a space
  (`Speaker.SENTENCE`) and sends it to the TTS; a worker synthesizes the sentences in order; the whole turn forms a
  single mp3 segment.
- **Playback**: `SegmentPlayer` (`features/assistant/audio-player.ts`) plays the mp3 from the first byte via
  MediaSource.
- **⌥Space command** (`WS /ai/voice/command` by voice, `POST /ai/command` by keyboard; `services/command.py`):
  same live STT, agent without history, but the TTS covers the **whole** answer once finished (no sentence
  splitting). On Windows, Alt+Space is taken by the system: use the **Commande** (Command) tab of the Voix page
  (Space or the mic button).

---

<a id="metriques"></a>
## 2. The metrics

### The one the user feels

**End of speech → the agent's first sound.** It's the metric for the "fastest" prize. Everything else is just its
breakdown:

| Metric | Definition | What drives it |
|---|---|---|
| Endpointing | actual end of speech → the system *decides* the caller has finished | push-to-talk: 0 (the release); VAD: the silence waited for |
| STT latency | end of speech → final transcript available | streaming STT or not, provider |
| LLM TTFT (*time to first token*) | start of the model call → first text token | prompt size, cache, model, effort |
| Tool round trips | each tool call = one more model call + the ERP call | number of steps, composite tools |
| TTS TTFB (*time to first byte*) | text sent to TTS → first audio byte | provider, warm connection, length of the 1st sentence |
| Playback | first byte received → audible sound | player buffer, network |

### Speaking turns

- **VAD** (*voice activity detection*): detecting that there is voice. **Endpointing**: deciding that a turn is
  over (long enough silence, complete sentence). Too short = you cut the caller off; too long = awkward silence.
- **Barge-in**: the caller speaks while the agent is speaking. The agent's audio must be cut immediately, the work
  in progress cancelled, and the agent must listen.

### How the kit measures them

`TurnTimings` (`apps/ai/app/schemas/chat.py`) is filled on each turn and sent in `agent_done` (voice) or `done`
(command):

| Field | Measured where | Meaning |
|---|---|---|
| `sttMs` | `run_turn` / `run_command` | release (t0) → final transcript |
| `llmFirstTokenMs` | first `TextEvent` | agent start → first **text** token (including tools if they come first) |
| `llmTotalMs` | end of `run_agent` | the whole agent, tools included |
| `ttsFirstByteMs` | `Speaker._speak_queued` | TTS call for the 1st sentence → first byte |
| `totalMs` | `Speaker.first_byte_at - t0` | **t0 → first audio byte sent** (voice); in command mode: t0 → end of everything |
| `perceivedMs` (browser) | `useVoiceSession.ts`, `markPerceived` | release → audio **playing** in the browser |

The **Voix** page shows these values per turn and their average (`pages/voice/metrics.tsx`): green under 1.5 s,
orange under 3 s, red above for `Total` and `Perçu` (Perceived).

Careful: in `command` mode, `totalMs` includes all the TTS (the complete synthesis), so it can't be compared with
voice mode's `totalMs`.

### Measuring during the demo

- Show the **Perçu** column of the Voix page: it's the ear-side metric.
- If you switch to VAD, **t0 changes**: it's the last moment voice was detected, not the moment the VAD decides.
  Count the endpointing silence in your figure, otherwise the jury will notice.
- Independent cross-check: record the call (mic + speaker) and measure the gap on the waveform in any audio editor.
- Record the median **and** the worst case over your scenarios (5 to 10 calls), not the best turn.

---

<a id="mesures"></a>
## 3. What the kit measures today

Real test, November 2026, **before live transcription** (4.1): LLM Anthropic Sonnet 5.5, STT Soniox, TTS
ElevenLabs, a caller sentence of about 4 seconds, one tool call. The totals below therefore include the old STT;
since then, they are lower by roughly the duration of that STT.

| Step | Measured | Reading |
|---|---|---|
| STT | **3.4 to 4.9 s** (before live transcription) | Soniox only started after `audio_end`. **Since 4.1, audio is sent during speech**: on release only the last words remain to be finalized, and the final text arrives a few hundred ms later. Not yet re-measured: measure `sttMs` on your side. |
| LLM, first token | **≈ 4.2 to 4.4 s**, tool round trip included | the model calls a tool before saying anything |
| TTS, first byte | **170 to 370 ms** warm; **≈ 1.9 s** on the first call (cold) | ElevenLabs is fast once the connection is open |
| `/command` total | **8.4 s** | |
| Voice total (WS) | **9.6 s** | |
| Prompt | **≈ 27,000 input tokens per model call**, before cache | rules + all of `DATA_DIR/context/*.md` + tool schemas, resent at every step |

What this means:

1. **The LLM's text arrives almost in one block after the tools**: first token ≈ last token. Sentence-by-sentence
   splitting to the TTS already exists but gains little as long as the answer only arrives at the end.
2. There were **two big items**: the STT (≈ 4 s) and the LLM with its tools (≈ 4 s). The STT has been dealt with
   (live transcription, 4.1). **The big remaining item is the LLM and its tools.** The TTS (≈ 0.3 s) is already
   good once warm.
3. The next "easy" gain: make the agent speak **before** the tools (4.7).

---

<a id="accelerer"></a>
## 4. Speeding up, technique by technique

Summary:

| # | Technique | Expected gain | Where in the kit | Difficulty |
|---|---|---|---|---|
| 4.1 | Streaming STT during speech — **done**; remaining: vocabulary, Deepgram Finalize | most of the STT's 3.4–4.9 s (done) | `services/utterance.py`, `services/vocabulary.py` | easy (the rest) |
| 4.2 | VAD / endpointing instead of push-to-talk | naturalness; latency = silence waited for | `useVoiceSession.ts`, or the STT's endpointing | medium |
| 4.3 | Start the LLM on a stable partial transcript | part of the TTFT | `voice_session.py` | hard |
| 4.4 | Prompt cache — **in place** | TTFT and cost on ≈ 27k tokens | `clients/anthropic.py` (to verify) | easy |
| 4.5 | Smaller model / routing | TTFT | `.env`, `clients/factory.py`, Jev | easy to medium |
| 4.6 | Fewer tool round trips | one model call per avoided tool | `tools/`, `agent/prompts.py` | medium |
| 4.7 | Fillers during tools | first sound before the tools | `Speaker`, `agent/prompts.py` | easy |
| 4.8 | Streaming TTS and earlier splitting | small today | `Speaker`, `clients/elevenlabs.py` | easy to medium |
| 4.9 | Warm connections | ≈ 1.6 s on the 1st turn (1.9 s cold vs ≈ 0.3 s warm) | `VoiceConnection.open` | easy |
| 4.10 | Short answers, deterministic code | fewer generated tokens | `agent/prompts.py`, `tools/` | easy |
| 4.11 | Data cache, preloading | ERP calls avoided | `tools/`, `prompts.py` | medium |
| 4.12 | Regions / colocation | network | infra | depends |

<a id="stt-streaming"></a>
### 4.1 Streaming STT while the caller speaks

**Done.** The browser sends a frame every 100 ms; the server forwards it to the STT as soon as it arrives
(`services/utterance.py`). During speech, the Voix page (Call and Command) and the ⌥Space HUD display the text
heard live: final words in normal color, provisional words in grey italics (`transcript` with `final: false`). On
release, Soniox receives `{"type": "finalize"}` and returns the last words right away; the agent's turn starts on
that final text. If the stream breaks, the full recording is transcribed as before. The mock STT simulates
partials: the display can be tested without a key. Details: TECH.en.md, "Live transcription".

**Vocabulary matters.** A generic STT hears "le moine" for "Lemoine", "turbos" for "turbot". So the server adds to
the STT hint the names of clients, products and their aliases read from the ERP (`services/vocabulary.py`):
Soniox receives them as `context.terms`, Deepgram as `keyterm`. Your clients' proper names come first. A misheard
name means the wrong client or the wrong product in the order.

**What you can still improve.**

- Start the LLM on a stable partial before the release ([4.3](#llm-partiel)).
- Hands-free mode: end the turn on Soniox's `<end>` tokens or a VAD ([4.2](#vad)).
- Finer vocabulary: contact names, the client's usual basket once identified, your trade's terms.
- Deepgram still ends with `CloseStream` (waits for closing): `{"type": "Finalize"}` would be faster.

<a id="vad"></a>
### 4.2 Endpointing / VAD instead of push-to-talk

**Idea.** On the phone, nobody presses a key. Two options:

- **Browser side**: the mic level is already computed (`meter()` in `useVoiceSession.ts`, `AnalyserNode`). Fire
  `audio_start` above a threshold, send `audio_end` after N ms of silence.
- **STT side**: realtime STTs can signal the end of an utterance (endpointing). The Deepgram client currently
  ignores `UtteranceEnd` messages; Soniox returns control tokens (`<end>`, `<fin>`) that `soniox.py` skips. Those
  are the two entry points.

**Gain.** Mostly *natural*. For *fast*, the waiting silence adds to latency: order of magnitude 300 to 800 ms
depending on the setting. Measure with noise (market, kitchen): a threshold that's too low never ends the turn.

**Difficulty.** Medium. Keep Space as a fallback mode for the demo.

<a id="llm-partiel"></a>
### 4.3 Starting the LLM on a partial transcript (speculative)

**Idea.** With 4.1, the text is almost complete before speech ends (partials already reach the server:
`on_partial` in `Utterance`). When the partial hasn't changed for a short moment, start the agent; if the final
transcript differs, cancel and restart.

**Where.** `voice_session.py`: the turn task already cancels cleanly (`interrupt()`, asyncio cancellation).

**Safeguard.** An ERP write that has gone out cannot be undone (TECH.en.md, pitfall 9). Only speculate on read
steps (`search`, `get_product_stock`, `get_price`…), never on `create_draft_order` / `confirm_order`.

**Difficulty.** Hard; do it after 4.7 and after verifying the cache (4.4).

<a id="cache"></a>
### 4.4 Prompt cache

**Idea.** ≈ 27,000 identical tokens (rules, company context, tools) are resent on **every** model call, including
after each tool. The provider's prompt cache rereads that prefix instead of reprocessing it.

**Where.** `clients/anthropic.py` now sets three cache points (`cache_control`): last tool, system prompt, last
block of the conversation. Check that it takes effect: `cache_read_input_tokens` in the `usage` of the `done`
event of `POST /ai/chat` (the voice session doesn't return `usage`: log it if needed).

**What breaks the cache** (byte-for-byte prefix): editing a `DATA_DIR/context/*.md` during the call (reread every
turn), adding the time or an id to the system prompt, changing the order or list of tools, changing model. The
cache expires after a few minutes without a call.

**Gain.** Cost, for sure; TTFT: measure before/after on your scenarios. Reducing the context (only putting in what
the turn needs) helps on top.

<a id="modele"></a>
### 4.5 Smaller model, routing

- **Change model without code**: `LLM_MODEL=` in `.env`, then `make restart`. The kit's Anthropic default:
  `claude-sonnet-5-5` (`DEFAULT_MODELS`, `clients/factory.py`). A Haiku (`claude-haiku-5-5`) answers faster and
  cheaper; check that it calls the tools properly on your hard scenarios.
- **`LLM_EFFORT=low`** (the kit's default) keeps thinking short; only raise it if hard turns fail.
- **Routing**: a small model for simple turns ("oui", "c'est tout", "merci" — "yes", "that's all", "thanks"), the
  big one when reasoning is needed. To classify the turn, **Jev** answers closed questions (choice, yes/no, score)
  with probabilities: `get_jev_client()`, examples in `agent/jev_examples.py` (`pick_product`, `is_yes`). Nothing
  in the default agent calls it: plug it into `run_turn` before `run_agent`.

<a id="outils"></a>
### 4.6 Fewer tool round trips

Each tool call costs one more model call (the model rereads the whole prompt), plus the ERP call.

- **Composite tools**: one tool that does "find the product + stock + client price" in a single call. Full example
  in [TECH.en.md 5.4](TECH.en.md#outil-composite).
- **Preload the client at the start of the call**: if you know who's calling, load their profile
  (`GET /api/context/for`, `get_client`) at `start` and add it to `parts` in `build_system_prompt`
  (`agent/prompts.py`). The model no longer needs `search` + `get_client` + `get_context` on the first turn. Put it
  **at the end** of the system prompt so as not to break the cache for the rest.
- **Parallel tools**: the loop already runs in parallel the tools requested in the same step (`asyncio.gather` in
  `loop.py`). Tell the model in the prompt ("call independent tools together"). The mock LLM only calls one per
  step: measure with a real model.
- **Small returns**: a tool that returns little JSON is reread faster at each step.

<a id="fillers"></a>
### 4.7 Fillers and prompts during tools

**Idea.** Without a holding phrase, the agent is silent during the tools (≈ 4 s measured) then answers in one
block. A short phrase **before** the tools ("Je regarde." — "Let me look.", "Deux secondes, je vérifie le stock." —
"Two seconds, I'm checking the stock.") gives an early first sound.

**Where.**

- Via the prompt: `VOICE_RULES` (`agent/prompts.py`) reminds the model that any text written is spoken in order,
  even between two tool calls. It allows **at most one very short holding phrase before the first tool**
  ("Je regarde."), then nothing between tools; the real answer comes only once, at the end. That pre-tool text goes
  to the TTS as soon as it's punctuated (`Speaker`). The model doesn't do it every time: measure.
- Via code (more reliable, faster): on the turn's first `ToolCallEvent`, if nothing has been said yet,
  `speaker.speak("Je regarde.")` in `run_turn`. Even faster: a small mp3 **pre-synthesized** at startup (no TTS call
  at the moment it's needed), sent in the turn's audio segment.

**Honesty.** A filler counts as the first sound, but a systematic "euh, je regarde" ("uh, let me look") is
noticeable. Vary it, keep it short, and say in `DECISIONS.md` what your figure measures (useful first sound or
filler).

### 4.8 TTS: split earlier, stream

- **Already done**: sentence by sentence, one mp3 segment per turn, playback from the first byte.
- **Split earlier**: `Speaker.SENTENCE` waits for `. ! ? …` followed by a space; the last sentence only goes out on
  `finish()`. Also splitting on commas for the **first** sentence shortens the first sound (at the cost of sometimes
  choppy prosody: listen).
- **WebSocket TTS**: open a connection, send the text as it comes, the audio comes back as a stream. ElevenLabs
  offers such a streaming-input API (see their documentation); the kit's client uses the REST `/stream` route
  (`clients/elevenlabs.py`). The gain is mostly useful when the LLM really streams its text (after 4.6 and 4.7).

### 4.9 Warm connections

**Measured**: first TTS call ≈ 1.9 s, then 170–370 ms. The kit already shares an HTTP client (`clients/http.py`,
`http_client()`) that keeps TLS connections open.

**Where.** In `VoiceConnection.open()`, launch in the background a tiny synthesis (one word) and, if you like, a
short model call: the first real turn finds everything open. Same idea for the ERP (`erp_http()` in
`tools/erp.py`, already keep-alive).

<a id="deterministe"></a>
### 4.10 Short answers and deterministic code

- **Short**: every generated token is paid for in time and audio. `VOICE_RULES` asks for 1 to 2 sentences; stick
  to it.
- **Code rather than model** for what needs no thinking: unit conversion, computing totals, dates ("jeudi prochain"
  — "next Thursday" → ISO date from the ERP's `today`), turning numbers into words. A tool or a Python function is
  faster and doesn't make mistakes. The kit has no "number → spoken French" function (`format_number` in
  `tools/catalog.py` only does `5.0 → "5"`): write one if your answers read out prices.

### 4.11 Data cache, preloading

A client's catalog and negotiated prices change little during a call. Keep in memory, for the session, what the
agent has already read (client profile, products mentioned) and serve it from the tool without calling the ERP
again. Careful with stock, which changes during the demo (the ERP is live).

### 4.12 Regions and colocation

Each provider adds a network round trip. During the demo you're on the venue's Wi-Fi: test on site, keep a
phone hotspot as backup. If a provider offers a European region, prefer it (order of magnitude: tens of
milliseconds per transatlantic round trip).

---

<a id="naturel"></a>
## 5. Sounding natural

### 5.1 Speaking turns

- One idea, one question per turn (`VOICE_RULES`: "Une seule question à la fois" — "One question at a time").
- Short sentences: they go to the TTS earlier **and** are easier to listen to.
- No "Autre chose ?" ("Anything else?") on every turn: on the phone, you let the other person talk.

<a id="barge-in"></a>
### 5.2 Barge-in

**What the kit does**: a new `audio_start` or `text` calls `interrupt()` (`voice_session.py`): the turn is
cancelled, the TTS stream is closed (`aclosing`), what was heard and said stays in the history with "…". On the
browser side, `startTalking` stops playback (`stopPlayback`).

**Good to know**:

- With push-to-talk, interruption only exists if the caller presses Space. With a VAD (4.2), you must detect voice
  **while** the agent is speaking: the mic is opened with `echoCancellation: true`, but test with a loudspeaker,
  otherwise the agent interrupts itself.
- The history keeps the **generated** text, not what was **heard**: if the caller cuts in mid-way, the model thinks
  it said everything. To do it properly, only keep the sentences whose audio was sent.
- An ERP write that has already gone out stays done: read the order back on the next turn.

### 5.3 Numbers, units, dates spoken aloud

- "12 kilos", "18 euros 50 le kilo", "jeudi 26", never "18.50 €/kg" or "2026-11-26".
- The prompt asks for it (`VOICE_RULES`), but the safest is to **format in code** (4.10) and give the model values
  that are ready to be spoken.
- Size grades and trade codes ("30/40", "T3"): say them the way the trade says them (see
  [METIER.en.md](METIER.en.md) and the glossary in your `data/context/`).

### 5.4 Read-back and confirmation

- An order is created as a draft and only confirmed after explicit agreement on the summary (`BASE_RULES`). Spoken:
  a **short** summary, quantities and products, then a closed question.
- "ouais vas-y", "c'est bon", "non attends" ("yeah go ahead", "that's fine", "no wait"): a reliable yes/no is a good
  spot for Jev (`is_yes` in `agent/jev_examples.py`); low confidence = ask again.

### 5.5 Never read out identifiers

`cli_0020`, `prd_…`, `CMD-2026-…`: the model sees them in tool results. `VOICE_RULES` forbids technical ids; for an
order number that's useful to the caller, say only the last digits.

### 5.6 Voice and prosody

- ElevenLabs `eleven_flash_v2_5` (default) is the fast choice. The default voice is a multilingual premade voice:
  choose a **French** voice in your ElevenLabs library and put its id in `TTS_VOICE`.
- Gradium (fr-FR voice, default "Armand") is supported in the code, but you don't have a Gradium key (section 7).
- Punctuation drives prosody: commas for pauses, periods to finish. Avoid parentheses, slashes, abbreviations.

### 5.7 Tone suited to the caller

The `data/context/clients/*.md` profiles describe each client: temperament, "Comment il/elle parle" ("How he/she
speaks"), verbal tics (for example a boss who has been on first-name *tu* terms with his sales rep for ten years).
**They are not in the prompt by default** (only the top-level `*.md` files of `data/context/` go in, TECH.en.md
pitfall 6). Load the caller's profile (4.6) and tell the model to adapt register and *tu*/*vous*.

---

<a id="robustesse"></a>
## 6. Robustness

| Problem | What to do | Where |
|---|---|---|
| Misheard names ("loup" / "bar", client names) | the **STT hint** already contains the ERP's client names, products and aliases (Soniox `context.terms`, Deepgram `keyterm`); add your own terms | `services/vocabulary.py`, or the `hint` of `audio_start` |
| Ambiguous product or client | `search` is fuzzy; if there are several candidates, ask which one (`BASE_RULES`); Jev `pick_product` gives a confidence | `tools/catalog.py`, `agent/jev_examples.py` |
| Doubtful critical slot (quantity, date, unit) | repeat the value and ask for confirmation **before** the write; "cinq" and "cinquante" (five / fifty) get confused | prompt + tool |
| Nothing heard | the kit returns "Rien entendu — réessayez." ("Nothing heard — try again."); with VAD, prefer a natural prompt ("Allô ? Vous m'entendez ?" — "Hello? Can you hear me?") | `run_turn` |
| Caller silence | prompt again after a delay, then a polite close | to add (timer on the session side) |
| Provider error (401, 429, outage) | readable `error` message (`provider_error`); plan a fallback: another model, a pre-recorded apology phrase | `clients/http.py`, `clients/factory.py` |
| Noise, accents, hesitations | the mic is opened with noise reduction and gain control; test your scenarios with real background noise | `ensureMic` in `useVoiceSession.ts` |
| Call dropped mid-order | the history lives in memory, per `sessionId`; the browser reconnects with the same id. The draft order stays in the ERP: on return, find it rather than creating a second one | `conversations` in `voice_session.py` |
| AI service restart | the voice history is lost (including on automatic reload when you save a file in `apps/ai/app`) | TECH.en.md pitfall 2 |

---

<a id="fournisseurs"></a>
## 7. The kit's providers

**Your keys**: each team received keys for **Soniox** (STT), **ElevenLabs** (TTS), **Anthropic** (LLM) and
**Jev** (decisions). Deepgram, Gradium and OpenAI are **supported in the code** but **no key is provided** for
them: don't count on them without your own key.

| Role | Provider | Kit default | Transport | Key provided |
|---|---|---|---|---|
| STT | **Soniox** | `stt-rt-v6`, `language_hints: ["fr"]`, hint terms | realtime WebSocket, `transcribe_stream` used live, `finalize` on release | yes |
| STT | Deepgram | `nova-3`, `language=fr`, `keyterm` | live WebSocket (`transcribe_stream`, ended by `CloseStream`); REST as fallback | no |
| STT | Gradium | `default` | REST; webm re-wrapped as Ogg (`clients/audio.py`) | no |
| STT | OpenAI | `gpt-4o-mini-transcribe` | REST | no |
| TTS | **ElevenLabs** | `eleven_flash_v2_5`, voice `JBFqnCBsd6RMkjVDRZzb`, `language_code=fr` | REST `/stream`, mp3 | yes |
| TTS | Gradium | `default`, fr-FR voice `F7Iib4MAyHIRed0x` | REST NDJSON, PCM → mp3 (`Mp3Encoder`) | no |
| TTS | OpenAI | `gpt-4o-mini-tts`, `alloy` | REST, mp3 | no |
| LLM | **Anthropic** | `claude-sonnet-5-5`, `LLM_EFFORT=low` | SSE | yes |
| Decision | **Jev** | `jev-latest` | REST | yes |

**Configuration** (`.env`, then `make restart`): `STT_PROVIDER`, `STT_MODEL`, `STT_API_KEY`, `STT_LANGUAGE`;
`TTS_PROVIDER`, `TTS_MODEL`, `TTS_VOICE`, `TTS_API_KEY`, `TTS_LANGUAGE`; `LLM_PROVIDER`, `LLM_MODEL`,
`LLM_API_KEY`, `LLM_EFFORT`; `JEV_API_KEY`. Details: [apps/ai/README.md](apps/ai/README.md#environment) and
[SETUP.en.md](SETUP.en.md#changing-model-or-voice).

**Audio formats**:

- Input: the browser records in `audio/webm;codecs=opus` (Safari: `audio/mp4`). Soniox accepts it as is
  (`audio_format: "auto"`, not mp4). Test on Chrome.
- Output: **all TTS providers return `audio/mpeg`** (mp3): the player concatenates a turn's sentences into one
  segment. A new TTS that returns PCM must go through `audio.Mp3Encoder`.
- Mock: `audio/x-mock-wav`, the browser reads the text with `speechSynthesis`; latencies measured in mock say
  nothing about the real providers.

---

<a id="plan"></a>
## 8. Plan of attack for 24 h

### Latency budget

Target: **under 1.5 s** from end of speech to first sound (the green on the Voix page). This table is a budget to
**verify** on your side, not a measurement: only the "Today" column is measured, and those measurements predate
live transcription.

| Step | Today (measured) | Target (order of magnitude) | Techniques |
|---|---|---|---|
| Endpointing | 0 (push-to-talk) | 0 with push-to-talk; 300–800 ms with VAD | 4.2 |
| STT after end of speech | 3.4–4.9 s **before live transcription**; now: final text a few hundred ms after release (to re-measure) | ≈ 0.2–0.5 s | 4.1 (done), vocabulary |
| Agent's first sound after the transcript | ≈ 4.2–4.4 s (LLM + tool) | ≈ 0.5–0.8 s | filler 4.7, cache 4.4, model 4.5, preloading 4.6 |
| TTS first byte | 170–370 ms (warm), 1.9 s (cold) | ≈ 0.2–0.3 s, never cold | 4.9 |
| **Total** | **8.4 s (command), 9.6 s (voice)**, before live transcription | **< 1.5 s** | |

Reading: the STT is already streaming; with a holding phrase spoken **before** the tools, the first sound no longer
depends on tool time. The useful answer comes afterwards; reduce it with 4.4 to 4.6.

### Recommended order

1. **Measure first** (H3–H8): your 5–10 scenarios, real keys, record `sttMs`, `llmFirstTokenMs`,
   `ttsFirstByteMs`, `totalMs`, `perceivedMs` in `DECISIONS.md`.
2. **Warm connections** (4.9) and **filler** (4.7): one hour, visible gain right away.
3. **Refine the STT** (4.1, already streaming): enrich the vocabulary (`services/vocabulary.py`: contacts, usual
   basket, trade terms), switch Deepgram to `Finalize` if you use it, then start the LLM on stable partials (4.3).
4. **Client preloading + composite tool** (4.6), **cache verification** (4.4).
5. **Model / routing** (4.5): only if your scenarios stay correct.
6. **VAD** (4.2) if there's time left; keep Space as a fallback for the live demo.
7. After **every** change: replay the scenarios, compare the figures and the success rate. Faster but wrong
   doesn't win.

### Proving it during the demo

In `DECISIONS.md`, a before/after table per technique:

| Technique | sttMs | llmFirstTokenMs | ttsFirstByteMs | totalMs | perceivedMs | scenarios passed |
|---|---|---|---|---|---|---|
| original kit | | | | | | |
| + … | | | | | | |

Give the median and the worst case, say what your t0 measures (release or detected end of voice) and whether the
first sound is a filler. Live, keep the Voix page open: the **Total** and **Perçu** chips speak for themselves.
