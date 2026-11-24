# Real phone calls (Twilio): setup and rehearsal

The « Appels du jour » agent can make a **real phone ring**: the ERP decides to call, the demo phone rings, someone picks up,
the agent speaks first, fixes the order by voice, and the audience watches the order change on the « Appels du jour » page.

**Hard rule:** the only number ever dialled is `DEMO_PHONE_TO`. Whatever client the agent calls, the demo phone rings.
Without `DEMO_PHONE_TO` no call leaves.

The browser simulator stays one setting away (`PHONE_MODE=simulator`): it is the stage fallback.

## 1. What you need (once)

| Item | Why | Where |
|---|---|---|
| A **paid** Twilio account (upgrade the trial) | A trial only calls verified numbers and plays a trial message, then waits for a key press | console.twilio.com → Billing |
| A Twilio phone number with Voice | The caller ID (`TWILIO_FROM`). A US number is fine (a French number needs a regulatory bundle, which takes days) | Phone Numbers → Buy a number |
| France enabled in **Voice geographic permissions** | Otherwise calls to +33 are refused | Voice → Settings → Geo permissions |
| The Account SID and Auth Token | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | console home page |
| A tunnel to port 4100 | Twilio must reach the AI service over `https://` / `wss://` | `ngrok http 4100` or `cloudflared tunnel --url http://localhost:4100` |
| `STT_PROVIDER=soniox` + key | Hands-free listening with end-of-sentence detection, μ-law 8 kHz | console.soniox.com |
| `TTS_PROVIDER=elevenlabs` + key | Speaks μ-law 8 kHz directly (no transcoding) | elevenlabs.io |
| `LLM_PROVIDER=anthropic` + key | The agent | console.anthropic.com |

## 2. `.env`

```
PHONE_MODE=twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=+1...            # your Twilio number
DEMO_PHONE_TO=+336...        # the phone that rings on stage
PUBLIC_URL=https://xxxx.ngrok-free.app   # the tunnel URL, no trailing slash
PROACTIVE_AUTODIAL=0         # the presenter starts the calls
```

Then `make restart` (Docker) or restart `make dev`. **A new ngrok URL means a new `PUBLIC_URL` and a restart.**
Never commit `.env`.

Optional knobs: `PHONE_ENDPOINT_DELAY_MS` (800: how long a pause ends the caller's sentence; raise to 1000–1200 if the agent
cuts people off, lower to 600 if it feels slow), `PHONE_BARGE_IN_WORDS` (2: words needed to interrupt the agent),
`PHONE_RING_TIMEOUT` (30 s), `PHONE_MACHINE_DETECTION=1` (hang up on a voicemail, shown as « Manqué »).

## 3. Check the line (before every rehearsal)

1. `make reset` (there are only 2 missions, and a client called today is never called again).
2. Open « Appels du jour ». The « Appel en cours » section must say **Ligne prête**. Click **Tester la ligne**: it asks Twilio
   whether the account works and calls your own tunnel. Every problem is listed in plain words.
   Same from a terminal: `curl "localhost:4100/phone/config?check=1"`.
3. Click **Vérifier maintenant**: the demo phone rings within ~3 s. If it does not, the journal shows « Manqué » **with the
   reason** (Twilio refused, tunnel down, AI service unreachable…).

## 4. How a call flows (what to say on stage)

1. The ERP picks the most urgent order problem (rules, not the model) and asks the AI service to call.
2. **While the phone rings**, the agent already reads the call brief and writes and speaks its first sentence. The audio waits.
3. Pickup: the first words play at once (measured and shown in the panel: « premiers mots x s après le décroché »).
4. The caller just talks: no button. Each pause ends a sentence; talking over the agent stops it. « Allô ? », « oui », « hm »
   said while the agent talks are ignored, so they don't cut the opening.
5. Every change goes through the agent's usual tools; a draft is confirmed only after a clear « oui ».
6. The agent records the decision (`record_call_outcome`), says goodbye once, and **hangs up by itself**.
7. The journal shows the decision; the client's history gets one « Appel proactif : … » line.

## 5. Stage tips

- Run on a **phone hotspot** if the venue Wi-Fi blocks the tunnel. Rehearse on the venue network.
- The demo phone on speaker held to the room mic is fine (phones cancel their own echo). Use the phone's own mic, not a
  second mic in front of the speaker.
- Lead with **Château Benoît** (the order really changes: Thursday 24 Dec, orange juice down to 67, then « oui »).
  Bastide rings first (priority 100) but its order is already prepared: the agent can only note the decision.
- Fallback in 10 seconds: set `PHONE_MODE=simulator`, `make restart`. The simulator window comes back.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Journal: « Manqué — service IA HTTP 400 : … manquants » | A `.env` setting is missing: the message names it |
| Journal: « Twilio a refusé l'appel : … 21215 / 21408 » | Geo permissions: enable France |
| The phone rings, silence after pickup | Tunnel down, or `PUBLIC_URL` not the current tunnel. `Tester la ligne` |
| A trial message plays | Upgrade the Twilio account |
| The agent cuts the caller off | Raise `PHONE_ENDPOINT_DELAY_MS` (1000–1200) |
| The agent stops for every noise | Raise `PHONE_BARGE_IN_WORDS` to 3 |
| Twilio callbacks refused (403 in the AI logs) | `PUBLIC_URL` must be exactly the URL Twilio calls (signature check). Last resort: `TWILIO_VALIDATE_SIGNATURE=0` |

Tests: `apps/ai/tests/test_phone_bridge.py` replays Twilio's events offline (no account, no cost).
