# FAQ

> English translation of [FAQ.md](FAQ.md). The French original is the reference.

The questions we get asked most. Unknown word? [GLOSSAIRE.en.md](GLOSSAIRE.en.md). Still stuck after
20 minutes? Come and see the Stockline team.

1. [Installation](#installation)
2. [Understanding the project](#comprendre)
3. [Coding](#coder)
4. [Keys and costs](#cles)
5. [Deliverables and demo](#livrables)

<a id="installation"></a>
## Installation

**I've never used Python / Docker, how do I do this?**
No need to know how to install Python: Docker does everything. Follow [SETUP.en.md](SETUP.en.md) line by line,
copy the commands as they are. For coding, the kit's Python is simple (functions, dictionaries): start from an
existing tool in `apps/ai/app/tools/` and modify it. A coding agent (Claude Code, Cursor…) with
[AGENTS.md](AGENTS.md) will save you a lot of time.

**The terminal says `command not found` or `No such file or directory`.**
You are probably not in the right folder. `pwd` shows where you are; `cd voice-erp-kit` to go into it (the folder
that contains the `Makefile`). On Windows, use the **Ubuntu** terminal, not PowerShell. Other common errors:
[SETUP.en.md, "If something goes wrong"](SETUP.en.md#if-something-goes-wrong).

**I'm on Windows and ⌥Space doesn't work.**
That's expected: Alt+Space is a Windows system shortcut (it opens the window menu). Go to the **Voix** (Voice)
page, **Commande** (Command) tab: hold Space (or the big mic button), speak, release. It's the same voice command.

**How do I start from scratch?**
- The ERP data is messed up by your tests: `make reset` (reloads the starting data; the services must be running).
- Everything is broken: `make clean` (deletes the containers **and** the database), then `make up`.
- Your code is broken: `git status` to see what changed, `git checkout -- <file>` to restore a file to its last
  commit.

**I changed `.env` and nothing happens.**
`make restart` (without Docker: Ctrl-C then `make dev`). `curl localhost:4100/health` shows the active providers.

<a id="comprendre"></a>
## Understanding the project

**What does the kit do, in one sentence?**
A wholesaler ERP (port 4000), an AI service that drives it with tools (port 4100) and a web interface (port 5173)
with a chat, a Voix page and a voice command. Detailed map: [README.md](README.md) and [TECH.en.md](TECH.en.md).

**Which document should I read first?**
[BRIEF.en.md](BRIEF.en.md) (the challenge), then [METIER.en.md](METIER.en.md) if you don't know the trade. Then
[GUIDE-AGENTS.en.md](GUIDE-AGENTS.en.md) (LLM agents) or [GUIDE-VOIX.en.md](GUIDE-VOIX.en.md) (speed,
naturalness) depending on your angle of attack.

**What is `mock` mode?**
Fake providers, free and offline. The mock agent really calls the ERP, but it understands nothing; the mock STT
always hears the same sentence. Perfect for installing and building the interface, useless for judging the agent.

**What happens during a voice turn?**
Your voice goes to the STT while you speak (the text is displayed live), the final text goes to the agent, which
calls ERP tools, then its answer is read by the TTS sentence by sentence.
Details: [GUIDE-VOIX.en.md §1](GUIDE-VOIX.en.md#anatomie).

<a id="coder"></a>
## Coding

**Where do I code?**

| Change | For |
|---|---|
| `apps/ai/app/agent/prompts.py` | what the agent knows and how it speaks (rules, tone, voice mode) |
| `apps/ai/app/tools/*.py` | what the agent can do in the ERP (new tools, faster tools) |
| `data/context/*.md` | your company's knowledge given to the agent |
| `apps/ai/app/agent/loop.py` | the agent loop (order of steps, parallelism, limits) |

| Leave as is (unless you have a specific reason) | Why |
|---|---|
| `apps/ai/app/clients/` | the connections to the providers: already tuned |
| `apps/ai/app/services/utterance.py` | live transcription: fragile, already optimized |
| `apps/ai/app/agent/sanitize.py` | cleans the history so the provider accepts it |
| `apps/ai/app/schemas/`, `apps/ai/app/routers/` | the contract with the interface: change it and the web breaks |

**How do I know my change worked?**
- `make chat`: talk to the agent in the terminal, no mic. It shows the tools called, the time and the tokens.
- **Voix** page (http://localhost:5173): a real voice turn, with latency measurements.
- `make logs`: Python errors show up there (Ctrl-C to exit).
- `curl localhost:4100/tools`: the list of tools the agent sees. Yours must be in it.
The code reloads by itself when you save (the voice conversation history is then lost).

**How do I add a tool?**
An `@tool` function in `apps/ai/app/tools/`, imported in `tools/__init__.py`. Step-by-step example:
[TECH.en.md, "Tools"](TECH.en.md#outils) (section 5.3 for a simple tool, 5.4 for a composite tool).

**I need an action the ERP can't do.**
First add the endpoint in the backend (`apps/backend/app/services/` + `routers/`), then the tool that calls it.
End-to-end example: [TECH.en.md 2.6](TECH.en.md#ajouter-endpoint). Business rules stay in the backend.

**`git commit` refuses / `git push` asks me for a password.**
- Commit refused ("Please tell me who you are"): once and for all,
  `git config --global user.name "First Last"` and `git config --global user.email "you@example.com"`.
- Push: GitHub no longer accepts the account password. The simplest: `gh auth login` (GitHub CLI tool), or
  create a *personal access token* in GitHub (Settings → Developer settings) and paste it instead of the password.

<a id="cles"></a>
## Keys and costs

**How do I see usage / cost?**
- Every chat response (`POST /ai/chat`) ends with a `done` event that contains `usage`: input tokens, output
  tokens, and cache tokens (`cache_read_input_tokens` read, `cache_creation_input_tokens` written).
- `make chat` displays it after each answer.
- The voice session does not return `usage`: log it if you need it.
- The providers' dashboards are on the organizers' side: ask us if you want an overall figure.

**I'm out of credits / error 401 / 429.**
- **401**: key refused. Check it in `.env` (no spaces, no quotes), then `make restart`.
- **429** or "quota": too many requests or cap reached. Wait a minute; if it persists, come and see us.
- In the meantime: switch back to `mock` to code, and keep the real keys for testing.

**Can I change the model?**
Yes, in `.env`: `LLM_MODEL=claude-sonnet-5-5` (default, balanced), `claude-haiku-5-5` (fastest and cheapest) or
`claude-opus-5-5` (strongest, slower). Then `make restart`. Check your scenarios afterwards: faster but wrong
doesn't win.

**Can I use another provider?**
The code supports others (OpenAI, Gemini, Deepgram, Gradium, any OpenAI-compatible endpoint), but we only provide
keys for **Anthropic** (LLM), **Soniox** (STT), **ElevenLabs** (TTS) and **Jev**. Using your own key is allowed:
say so in `DECISIONS.md`.

<a id="livrables"></a>
## Deliverables and demo

**What do I have to hand in?**
The GitHub repo, `DECISIONS.md`, the slides (5 min), a video (2 min) and the live demo:
[BRIEF.en.md §8](BRIEF.en.md#8-deliverables-and-final-demo).

**How do we show that our agent is fast?**
**Voix** page: the **Total** and **Perçu** (Perceived) columns of each turn. Record the median and the worst case,
before/after each change, in `DECISIONS.md`. Method: [GUIDE-VOIX.en.md §8](GUIDE-VOIX.en.md#plan).

**Will the jury be able to run our project?**
Yes, if it starts with `make setup` once the `data/` folder is put back in place. Test it on a fresh copy before
handing in. Never put `.env` in the repo.

**My tool crashes startup (TypeError `@tool ...`).**
Read the message: it says what to fix (missing `async def`, first parameter not `ctx`, parameter without a type,
missing docstring or name already taken).
