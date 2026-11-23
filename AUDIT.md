# AUDIT.md — Baseline audit of the voice agent (Team 07, Comptoir des Chartrons)

Date of audit: baseline kit, before any change. Business date of the ERP pack: **mardi 24 novembre 2026**.
Method: code reading + 9 real conversations (real LLM, voice mode, real ERP) driven through `POST :4100/chat`,
then ERP state inspected; backend rules checked directly through the API. The ERP was reset to the seed afterwards.

**Not tested**: real STT/TTS latency (needs a microphone), browser barge-in, `make test` (uv not installed on the host).

## 1. Verification of the initial findings

| # | Finding | Verdict |
|---|---|---|
| 1 | `create_draft_order`, `add_order_line`, `confirm_order`, `get_order` exist | True (`apps/ai/app/tools/orders.py`) |
| 2 | Edit / delete / cancel routes exist, no AI tool | True: `PATCH/DELETE /api/orders/{id}/lines/{lineId}`, `PATCH /api/orders/{id}`, `POST /api/orders/{id}/cancel` have no tool |
| 3 | Warnings never block confirmation | True, verified: a blocked client, an exceeded credit limit and a 100 000-keg order were all `confirmed` by the API (`services/orders.py`: "Warnings never block") |
| 4 | Explicit approval is prompt-only | True (`prompts.py`, BASE_RULES) — no server-side check |
| 5 | Parallel tool execution | True (`asyncio.gather`, `agent/loop.py`) |
| 6 | Streaming TTS + interruption | Mostly: sentence-level TTS and server-side cancellation exist; input is push-to-talk (no VAD) |

## 2. Feature audit (A complete · B unreliable · C partial · D missing · E unnecessary)

| Capability | Class | Evidence | Effort | Decision |
|---|---|---|---|---|
| Create draft, several lines | A | S1, S6 correct | 0 | keep |
| Modify a line quantity | **C** | no tool; S6: "four → six" produced a second line of 2 (right total, duplicate lines); cannot reduce | 1 h | add tool |
| Remove line / change date / cancel | **D** | S6: "annule tout" → agent could only log a note; draft stays | 1 h | add tools |
| One active order per conversation | **D** | no state; two identical creates → two orders (API verified); seed draft for the client ignored | 2 h | session state |
| Customer identification | A/B | resolved correctly in all runs | 0 | keep |
| Blocked customer | **B** | S2: LLM refused correctly, but only the LLM: the backend would confirm | 2 h | server guard |
| Credit limit | **B** | warning only; API confirms at 400 bottles over the limit | 1 h | server guard + human approval |
| Honest stock answers | A | S3 | 0 | keep |
| Substitution consent | A/B | S3 respected the no-substitution rule | 1 h | test |
| Delivery date / cutoff / client days | **B/C** | S5 refused Saturday from the LLM's reading of the docs; backend only warns on zone-day, not on the client's own `deliveryDays` or the 16:00 cutoff | 3 h | V2 |
| Unsupported promises | **B** | S1: "livré avant 10 h" stated as fact; "je préviens Thomas d'envoyer le mail" (no such tool) | 2 h | V2 |
| Explicit final confirmation | A (S1, S4) / untested ambiguous | recap then "OK vas-y" worked | 2 h | gate + tests |
| Latency / cost | B | see §3 | 4 h | V3 |

## 3. Baseline measurements

| Scenario | Result | LLM time |
|---|---|---|
| S1 Régent: order, correction before creation, "vas-y" | pass (1 order, 4 kegs, confirmed) | 9.2 s / 4 turns |
| S2 Zinc (blocked) | pass (no order) — LLM-only protection | 7.7 s / 2 turns |
| S3 Bastide, out-of-stock keg | pass | 5.8 s |
| S4 Pey-Berland, 150 bottles | pass (test did not exceed the credit limit) | 13 s / 2 turns |
| S5 Saturday delivery | pass (LLM-only) | 7.2 s |
| S6 correction after creation + cancel | **partial** (duplicate line workaround; cancel impossible) | 12.4 s / 3 turns |

- One turn: 0.9 s (no tool) to 9.3 s (6 tools). All tools together: ≤ 160 ms. The sequential LLM round-trips dominate.
- The first text arrives at the end of the LLM turn: 2–9 s of silence on tool-heavy turns.
- ~24 k input tokens per LLM step (company context re-sent; prompt caching on).
- Existing tests are mocked (history pairing, barge-in); none check ERP state.

## 4. Critical assessment

1. Differentiation: the baseline already handles the happy path; the gap is robustness (state, guards) and speed.
2. Already good: client lookup, honest stock, substitution consent, blocked-client wording, honest failure messages.
3. Three most consequential gaps: line editing / cancellation, no code-level guard on confirmation, delivery-date validation.
4. Impressive live: clean mid-call corrections, a blocked client refused with no order created, latency on screen.
5. Avoid: WhatsApp integration, rewriting the loop, new providers.
6. Alternative use cases (after-hours orders, stock-out outbound calls) are variations of the same core.
