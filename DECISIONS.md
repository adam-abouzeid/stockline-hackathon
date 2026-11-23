# DECISIONS.md — Team 07 · Comptoir des Chartrons

## 1. The problem we chose

**The Unbreakable Sales Agent**: a stateful, exception-aware voice agent that takes the phone orders of a Bordeaux
wine & drinks wholesaler (bars, brasseries, restaurants) and ends every call with **exactly one correct order** in the
ERP — no duplicate, no unauthorized delivery, no invented promise.

Why this one:
- Orders are the highest-volume call (phone 39 %, WhatsApp 25 %, e-mail 22 %, portal 14 %); today Nathalie retypes them.
- The house rules are strict and testable: substitutions only with the client's agreement, blocked accounts get no
  delivery without Martine, credit overruns go to Martine's validation, minimum order 150 € HT.
- The baseline already shows the happy path; what breaks is state and safety, which is what a live jury will probe.

Personas used for tests: Brasserie Le Régent Gambetta (`cli_0002`, good client), Le Zinc de la Victoire (`cli_0007`,
blocked), Le Comptoir Bastide (`cli_0011`, refuses substitutions), Les Salons de Pey-Berland (`cli_0024`, near its limit).

## 2. Measured baseline weaknesses (details in AUDIT.md)

- No tool to edit a line, remove a line, change the delivery date or cancel → a correction after creation produced a
  duplicate line; "cancel everything" was impossible.
- No session state: nothing prevents two orders for one call; repeated create → two drafts.
- Business rules are LLM-only: the ERP confirmed an order for a blocked client, over the credit limit, over the stock.
- Latency: 0.9–9.3 s of LLM time per turn, dominated by sequential LLM round-trips (tools ≤ 160 ms in total).
- Unsupported promises (delivery hour, e-mail confirmation).

## 3. Roadmap

### V1 — Reliability foundation (done, see §4)
Order edit/remove/cancel/date tools · per-session active-order state · server-side guards (blocked client, credit
limit → human approval) · recap + explicit approval gate · tests that assert the real ERP state.

### V2 — Exception-aware intelligence (not started — needs team review)
Delivery-date validation (client `deliveryDays`, 16:00 cutoff, route), context-sensitive substitutions, ambiguity
handling, no unsupported promises, recovery after failed tools, stock guard.

### V3 — Latency and naturalness (not started)
Per-stage latency baseline, fewer LLM round-trips (composite tool, preloaded client context), holding sentence,
interruption recovery, cost per successful scenario.

## 4. V1 decisions

### What V1 changed

| Decision | Why |
|---|---|
| 4 new tools (`update_order_line`, `remove_order_line`, `update_order`, `cancel_order`) in a new file `tools/order_edit.py`, wrapping existing ERP routes | the ERP already had the routes; the agent only lacked the tools |
| The active order is **derived from the conversation history** each turn (`tools/order_state.py`), not stored | the history already carries every order tool result, so it works for voice, chat and CLI with no new storage |
| One active order per call: `create_draft_order` refuses a second one; `add_order_line` refuses a product already in the order; naming another order id is refused | removes duplicate orders / duplicate lines / wrong-order edits by construction |
| Confirmation gate in code (`tools/approval.py`), voice mode only: a recap turn after the last change, then the customer's next message must be an unconditional "yes" | the prompt alone cannot be trusted; a false "no" costs one question, a false "yes" books a wrong order |
| ERP guard on `confirm_order` for the AI actors only (`ai_chat`, `voice_agent`): blocked client → 409 `client_blocked`; credit limit → 409 `credit_approval_required` | the LLM can never authorize its own override; a human (web UI, actor `user`) can still confirm |
| On those refusals the tool leaves the order a draft and logs a `special_request` event on the client for Martine | follows the house process (05-prix-et-credit.md); no override parameter exists |
| Command mode (salesperson voice command) is not gated by the recap rule | an explicit instruction by staff is itself the order; the ERP guards still apply |

### V1 test evidence

- `tests/test_approval.py`: 45 deterministic cases (consent classifier, confirmation gate, state derivation).
- `tests/test_order_v1_erp.py`: 20 integration tests, scripted model + **real ERP**, asserting the resulting ERP state
  (corrections, removal, cancel, duplicates, date change, recap/consent, blocked client, credit limit, direct API bypass).
  Mutation check: with the ERP guard and the gate disabled, 11 of the 20 fail.
- Full AI suite: 148 passed. Real-LLM replay: see the V1 report in the team chat (S1, S2, S4, S6, S7, S8).
- These tests prove the safeguards, **not** that a real LLM always picks the right tool.

### Known limits after V1 (to review before V2)

- Any assistant message after the last change counts as "the recap": its content is not checked against the order.
- A confirm that precedes the modifying tool in the same parallel step is not caught (the flag is set when the modifying tool starts).
- The state comes from the history: the voice session keeps ~40 messages, so a very long call can forget the active order.
- Still LLM-only: delivery-date promises ("avant 10 h"), "I will send the e-mail", substitution consent, stock-out handling.
- A blocked client's request is traced for Martine only if a draft exists or the model logs it.
- Not measured: the effect on latency and token cost of 4 more tools and a longer prompt.
