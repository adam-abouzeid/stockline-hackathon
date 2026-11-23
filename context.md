# Context: Stockline × X-Forum Hackathon

> Living doc. Updated as new info arrives (subject, data, team, rules).
> Last updated: 2026-11-23 (before the launch talk).

---

## 1. The hackathon

**Theme:** voice AI for food wholesalers (*l'IA vocale pour les grossistes alimentaires*).

> Today, most orders arrive by phone or voice message and are copied out by hand. You will build agents that listen, understand and act.

The exact brief and the data are revealed at the launch talk (TBD below).

### Schedule

| When | What |
|---|---|
| **Mon 23/11, 19:00** | Launch talk in a lecture hall (venue shared on the WhatsApp group): brief, data, teams, then pizza |
| Mon → Tue | 24 hours of non-stop coding, anywhere on campus |
| During the 24 h | Stockline staff on hand in **Titus** to answer questions and unblock teams |
| **Tue 24/11, 18:00** | Closing talk: coding stops, projects are submitted |
| **Wed 25/11, 15:00** | Finalists pitch to the jury at the X-Forum, then the award ceremony |

### Prizes
- 1st: **€3,000**, 2nd: **€2,000**, 3rd: **€1,000**
- Tickets to the Bal de l'X
- Stockline goodies for everyone

### Food (all provided)
Pizza Monday evening · breakfast Tuesday morning · bo bun Tuesday lunch · afternoon snack Tuesday · food and drinks in Titus around the clock.

---

## 2. Stockline: who's behind it

- **What:** an "AI-native ERP for food wholesalers". AI agents remove repetitive work, **starting with order entry**.
- **Website:** https://stockline.ai · contact@stockline.ai · LinkedIn `stocklineai` · X `@StocklineAI`
- **YC:** Summer 2025 batch (S25). Founded in 2025, team of 2 (per YC). YC partner: Brad Flora.
- **Location:** founders from Paris (YC lists San Francisco).
- **Founders** (both from Polytechnique, which explains the X-Forum partnership):
  - **Mariem Ould Ismail**, CEO. Master's in Applied Maths from l'X, left MIT. **Her father is a fish wholesaler** and she helped him every summer, which is where the idea came from. Her line: *"disrupt old clunky ERPs with AI."*
  - **Moncef Djafri**, CTO. From l'X, left Stanford. Has coded since he was 13.

### Product (from their public pitch)
- **Communication:** captures orders from **WhatsApp, SMS, email and phone calls** into a single unified inbox.
- **Operations:** billing, inventory, CRM. "All in one platform. Admin disappears."
- Long-term goal: **replace** the legacy ERP rather than sit on top of it. Order entry is the entry point. Later steps would be inventory, invoicing, route planning and procurement.
- Target customers: food wholesalers, suppliers, fish markets, butchers, supermarkets (US + EU).
- No public figures (customers, revenue, pricing). Their voice/phone pipeline isn't documented publicly, which makes it probably the most open technical area and explains the theme.

### Customer pain points (in their own words + press)
- Orders arrive through WhatsApp, SMS, email and phone, **then get retyped by hand** into a 90s-era ERP.
- On the phone: the customer calls, the wholesaler **writes the order on paper**, then someone keys it in.
- "Prices are set by instinct": no real-time visibility on stock or margins.
- Consequences: input errors, tight margins, **food waste**.
- One typo can deliver **50 cases instead of 5**.
- **Catalog matching is the hard part:** customers use their own jargon, abbreviations and inconsistent names. "10 cs roma" means Roma tomatoes only if you know *that customer's* vocabulary and *that wholesaler's* catalog. Choosing between SKU 4412 and SKU 4415 often depends on what the customer ordered before.
- Example order message (US): `20 cs chicken breast boneless 10lb, 15 bg yellow onion 50lb, 5 cs avocado 48ct`. Fields to extract: **product → SKU, quantity, unit (case/bag/kg/piece), packaging/size, price (customer-specific)**.
- Legacy ERPs cited in the US: BlueLink, Produce Pro, Edible Software. Some still run on Access or paper ledgers.

### Competitors / prior art (useful for the pitch)
- **Choco** (Berlin): *OrderAgent* turns email/voicemail/app orders into structured orders (200+ ERP integrations, claims ~99% accuracy). Matches products **using order history** and only flags real exceptions. Since Dec 2025, *VoiceAgent* (built with OpenAI's Realtime API): a live multilingual phone agent that replaces night-time voicemail, checks stock, suggests substitutes when items are out, and pushes promos on short-dated products.
- **GrubMarket** (AI Orders), **Fresho** (email/SMS/voicemail/PDF → orders), **Silo** (US).
- → To stand out: the **French** market (Rungis, French-speaking/multilingual customers, fast phone calls, trade jargon), integration and reliability, a strong UX for human validation.

---

## 3. Likely technical angles (assumptions until the brief is out)

Typical pipeline for a voice ordering agent:

1. **Audio in:** live phone call (telephony: Twilio / Vonage / SIP) or voice messages (WhatsApp voice notes, voicemail).
2. **STT (speech-to-text):** French with accents, background noise (warehouse, kitchen), trade jargon. Options include Whisper / gpt-4o-transcribe, Deepgram, ElevenLabs Scribe, Gladia (French), Voxtral (Mistral). Custom vocabulary/boosting with the catalog's product names.
3. **Understanding (LLM):** extract structured lines `{product, qty, unit, notes}`, then **match to the catalog** (fuzzy + embeddings + the customer's order history), resolve ambiguities, and detect modifications/cancellations ("same as last week but no salmon").
4. **Action:** create the order in the ERP/back-office, confirm to the customer (SMS/WhatsApp/voice), flag low-confidence lines for a human to check.
5. **Real-time voice agent (optional):** full conversation in which the agent picks up, confirms each line, checks stock, suggests a substitute, and reads back a summary. Options: OpenAI Realtime, ElevenLabs Agents, Vapi, Pipecat, LiveKit Agents.

Things to measure and demo: **line-level accuracy**, end-to-end latency, % of orders processed without a human, and handling of edge cases (out-of-stock, unknown product, ambiguous quantity).

---

## 4. Brief & data (to fill in after the launch talk)

- **Exact brief:** _TBD_
- **Data provided:** _TBD_ (audio? transcripts? product catalog? order history? customer list?)
- **APIs / credits provided:** _TBD_
- **Judging criteria:** _TBD_
- **Submission format:** _TBD_ (repo, demo video, slides?)
- **Team:** _TBD_
- **Constraints / rules:** _TBD_

---

## Sources
- YC Launch: https://www.ycombinator.com/launches/O2j-stockline-ai-native-erp-for-food-wholesalers
- YC profile: https://www.ycombinator.com/companies/stockline
- HUGE Magazine feature (Feb 2026, partly editorial opinion): https://huge-magazine.pages.dev/feature/stockline
- Choco OrderAgent: https://choco.com/us/orderagent
- Choco VoiceAgent (OpenAI): https://choco.com/us/press/choco-and-openai-join-forces-to-launch-the-first-ai-voice-agent-for-the-food-service-industry
