# Step-by-step installation

> English translation of [SETUP.md](SETUP.md). The French original is the reference.

Unknown word? [GLOSSAIRE.en.md](GLOSSAIRE.en.md) · A question? [FAQ.en.md](FAQ.en.md)

This guide takes you from zero to a first voice call that modifies the ERP. Count **20 to 30 minutes** the first
time, including 10 to 15 minutes of waiting (downloads). Do step 1 **before** the hackathon if you can.

You received a `team-XX.zip` file. It contains a `voice-erp-kit/` folder:

| What | Where | Note |
|---|---|---|
| The kit (ERP, AI service, interface) | `voice-erp-kit/` | the code you are going to modify |
| **Your** company's data | `voice-erp-kit/data/` | clients, products, 3 years of history, documents |
| The configuration and your API keys | `voice-erp-kit/.env` | **private**: don't share it, don't commit it. Zip received the day before: no keys yet, see [Real keys or simulated models](#real-keys-or-simulated-models) |
| Your team sheet | `voice-erp-kit/TEAM.md` | your company's name |

There is nothing else to download or clone: everything is in the zip.

---

## Step 1 — Install Docker (≈ 10 min, do it beforehand)

Docker runs the three services (ERP, AI, interface) without installing anything else.

### Mac

1. Install Apple's developer tools (`make`, `git`): in a terminal, `xcode-select --install`, then "Install". If it
   says "already installed", you're fine.
2. Download [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Apple or Intel chip: the site picks
   for you). About 600 MB.
3. Open the `.dmg`, drag Docker into Applications, launch it. Accept the permissions (Mac password).
4. Wait until the whale at the top of the screen stops blinking.
5. In a terminal: `docker run hello-world`. You should see "Hello from Docker!".

### Windows

On Windows, everything happens **inside WSL** (a Linux built into Windows): `make` and the kit's scripts work
neither in PowerShell nor in the command prompt. You need administrator rights to install WSL.

1. In an **administrator** PowerShell: `wsl --install`, then restart. On restart, Ubuntu opens and asks you for a
   username and password (for Linux; choose them yourself).
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/). During installation, keep
   "Use WSL 2". Launch it, then Settings → Resources → WSL integration → enable **Ubuntu**.
3. Open the **Ubuntu** terminal (Start menu), then: `sudo apt update && sudo apt install -y make unzip curl git`.
4. Check in Ubuntu: `docker run hello-world`.

From here on, on Windows, **all commands are typed in the Ubuntu terminal**, and the project lives in Linux
(`~/voice-erp-kit`), not in `C:\`: it's much faster and automatic code reloading works.
To open the project in VS Code: `code .` from Ubuntu ("WSL" extension).

### Linux

Install [Docker Engine](https://docs.docker.com/engine/install/) and the compose plugin, add yourself to the
`docker` group (`sudo usermod -aG docker $USER`, then log in again), install `make`, `unzip`, `curl` and `git`.

### Setting for everyone

Docker Desktop → Settings → Resources: give it at least **4 GB of RAM**.

> No administrator rights? On Mac or Linux, go to [Without Docker](#without-docker). On Windows, WSL requires
> these rights: come and see the Stockline team.

---

## Step 2 — Start the project (5 to 10 min the first time)

```bash
# Mac / Linux: from the folder where the zip is.
# Windows: in Ubuntu, first copy the zip into Linux:
#   cp /mnt/c/Users/<you>/Downloads/team-XX.zip ~ && cd ~
unzip team-XX.zip
cd voice-erp-kit
make setup
```

`make setup` checks Docker and the ports, builds the images, then starts the services. It stops when everything
responds. You will see:

```
  ✓ api, ai and web are up

Ready → http://localhost:5173
```

The first time, it downloads 1 to 2 GB then builds the images: that's the long step. You can safely rerun it if
it stops. After that, `make up` starts in a few seconds.

**Check that everything works:**

| Open | You should see |
|---|---|
| http://localhost:5173 (wait ~10 s after "Ready") | the ERP, with **your** company's name at the top left |
| http://localhost:4000/docs | the ERP's API docs |
| http://localhost:4100/health | `"ok": true` and the active providers (`llm`, `stt`, `tts`); `mock` = simulated model |

---

## Step 3 — First call (≈ 5 min)

1. In the ERP, open **Voix** (Voice) (left menu, AI section).
2. Allow the microphone when the browser asks (Chrome recommended).
3. **Hold Space**, speak like a client ("Bonjour, c'est le restaurant…, vous avez quoi ce matin ?" — "Hello, it's
   the restaurant…, what have you got this morning?"), release. While you speak, your words appear live (in grey
   italics while they are provisional); on release, the final text goes to the agent. You can also type the
   sentence instead of speaking.
4. Watch: the transcription, the tools called by the agent, the answer spoken aloud, and on the right the ERP
   updating (in purple: what the agent did).
5. Also try **⌥ Space** (Alt + Space) anywhere in the ERP: a one-sentence voice command ("crée une commande
   pour …" — "create an order for …").

### Real keys or simulated models

Everything is set in `.env` (a single file for all three services):

- **Zip received on the day**: your keys are already in `.env`, the chosen providers are active.
- **Zip received the day before**: `.env` uses the simulated models (`mock`), with no key. On the day, you are
  given your `.env` file: replace the one in the folder with the new one (keep the name `.env`), then
  `make restart`.

With the simulated models, everything works offline and the agent calls the real ERP, but:

- the fake LLM only understands a few simple sentences;
- the fake transcription **always** hears the same sentence ("Bonjour, il vous reste du bar ?" — "Hello, do you
  have any sea bass left?"), whatever you say: type your text to test something else;
- the browser reads the answer aloud.

It's useful for developing without spending credits. To go back to it at any time: `LLM_PROVIDER=mock`,
`STT_PROVIDER=mock`, `TTS_PROVIDER=mock`, then `make restart`.

### Changing model or voice

At the bottom of your `.env`, commented out, are all of your team's keys. To change provider, edit the
`*_PROVIDER` and copy the matching key into the `*_API_KEY` just below, then `make restart`. Example:

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=              # empty = the provider's default model
LLM_API_KEY=<the value of the line # ANTHROPIC_KEY=…>
```

| Role | Providers | Variables |
|---|---|---|
| LLM (the brain) | `openai`, `anthropic`, `gemini`, `openai-compatible`, `mock` | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |
| Transcription (STT) | `soniox`, `deepgram`, `gradium`, `openai`, `mock` | `STT_PROVIDER`, `STT_MODEL`, `STT_API_KEY` |
| Speech synthesis (TTS) | `elevenlabs`, `gradium`, `openai`, `mock` | `TTS_PROVIDER`, `TTS_MODEL`, `TTS_VOICE`, `TTS_API_KEY` |
| Jev (decision model, optional) | TypeSafe AI | `JEV_API_KEY` |

Jev is not an LLM: it quickly answers closed questions (choice, score, yes/no) and is used **alongside** the LLM.
The baseline agent doesn't use it: it's up to you to plug it in (see
[apps/ai/README.md](apps/ai/README.md#jev-decision-model)). Default models and voices, and the details of each
variable: [README, Configuration](README.md#configuration-one-env).

---

## Step 4 — Your team repo (≈ 3 min)

```bash
git init -b main && git add . && git commit -m "start"
```

Create a **private** repo on GitHub, push the code to it (`git remote add origin … && git push -u origin main`),
then add the jury's accounts as collaborators. It's your deliverable.

`.env` (your keys) and `data/seed/` (the data, too heavy for GitHub) are ignored by git, on purpose.

---

## Step 5 — Code

- The files to read first: `apps/ai/app/agent/loop.py` (the agent loop) and `apps/ai/app/tools/` (what the agent
  can do in the ERP). The project map is just below.
- The code reloads by itself when you save. After changing `.env`: `make restart`.
- Using a coding agent (Claude Code, Cursor…)? Give it [AGENTS.md](AGENTS.md).
- To read: [BRIEF.en.md](BRIEF.en.md) (the challenge), [METIER.en.md](METIER.en.md) (the trade),
  [ERP.en.md](ERP.en.md) (the ERP).

### How the project is organized

```
voice-erp-kit/
├── apps/
│   ├── backend/app/     the ERP (Python, FastAPI, SQLite), port 4000
│   │   ├── routers/       the API routes (/api/clients, /api/orders…)
│   │   ├── services/      the business rules: prices, stock, credit, invoices
│   │   └── schemas/       the shape of the data (Pydantic) = the API contract
│   ├── ai/app/          the AI service (Python, FastAPI), port 4100
│   │   ├── agent/         loop.py (the agent loop), prompts.py (what the model reads)
│   │   ├── tools/         the agent's tools (@tool): search for a product, create an order…
│   │   ├── clients/       one file per LLM / STT / TTS provider (+ Jev)
│   │   └── services/      voice_session.py (the voice call), command.py (⌥ Space)
│   └── web/src/         the interface (React), port 5173: pages/ and ui/ components
├── data/                your company: seed/ (ERP data), context/ (documents read by the agent)
├── packages/shared/     the TypeScript types shared by the interface
├── docker/, docker-compose.yml, Makefile, scripts/   startup (you don't need to touch them)
└── .env                 the configuration and your keys
```

The path of a call: the interface sends the sound to the AI service → transcription (STT) → the agent (LLM) calls
tools → each tool is an HTTP call to the ERP → the answer is read aloud (TTS) and the ERP updates on screen.
Business rules live only in the ERP. Diagram: [README, Architecture](README.md#architecture); details and
examples for extending the kit: [TECH.en.md](TECH.en.md).

| You want… | Look at |
|---|---|
| the agent to answer faster | `apps/ai/app/services/voice_session.py`, `apps/ai/app/clients/`, `agent/loop.py` |
| it to know more about the client | `agent/prompts.py`, `tools/context.py`, `data/context/` |
| to give it a new action in the ERP | a route in `apps/backend/app/routers/` + a tool in `apps/ai/app/tools/` ([README, Add a tool](README.md#add-a-tool)) |
| to change the interface | `apps/web/src/pages/`, components from `apps/web/src/ui/` ([DESIGN.md](DESIGN.md)) |

### Useful commands

| Command | Effect |
|---|---|
| `make up` / `make down` | start / stop (data is kept) |
| `make restart` | apply a change to `.env` |
| `make logs` | see the logs of the 3 services (Ctrl-C to exit) |
| `make reset` | reset the ERP data (erases your changes) |
| `make rebuild` | after adding a Python or npm dependency |
| `make chat` | talk to the agent in the terminal |
| `make clean` | delete everything, database included (`make setup` to start over) |
| `make help` | all commands |

`make test`, `make types` and `make check` run on your machine, outside Docker: they need the tools from
[Without Docker](#without-docker) (uv for `test`, Node 22 and pnpm for `types` and `check`).

---

## Without Docker

For a machine without administrator rights (Mac or Linux), or if Docker refuses to start. You need:

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.12 by itself. `make local`
  installs it if it's missing.
- **Node 22 or later.** Without administrator rights, go through [nvm](https://github.com/nvm-sh/nvm):
  `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash`, reopen the terminal, then
  `nvm install 22`.
- `pnpm`: `make local` enables it via corepack (shipped with Node).

```bash
cd voice-erp-kit
make local        # installs everything (≈ 5 min) and starts the 3 services (Ctrl-C to stop)
make dev          # the following times
```

Everything else is identical: http://localhost:5173, `make reset`, `make chat`. Only the Docker commands
(`make up`, `make restart`, `make logs`…) don't apply: after changing `.env`, stop (Ctrl-C) and run `make dev`
again. If you change `API_PORT`, put the same port in `ERP_API_URL`.

---

## Without Internet (USB stick)

If the Wi-Fi isn't enough for `make setup`, the Stockline team has a USB stick with the Docker images already
built. Copy **the** file that matches your machine:

| Your machine | File |
|---|---|
| Apple Silicon Mac (M1, M2, M3, M4…) | `voice-erp-kit-images-arm64.tar.gz` |
| Everything else (Intel Mac, Windows/WSL, Linux) | `voice-erp-kit-images-amd64.tar.gz` |

Then, in the project folder (after `unzip team-XX.zip` and `cd voice-erp-kit`):

```bash
make offline IMAGES=/path/to/voice-erp-kit-images-arm64.tar.gz   # or -amd64.tar.gz; the uncompressed .tar works too
```

Nothing is downloaded or built: the services start directly (wait ~20 s before opening http://localhost:5173).
Then `make up` / `make down` as usual.

---

## If something goes wrong

| Symptom | Solution |
|---|---|
| `Docker is installed but not running` | launch Docker Desktop and wait until the whale is steady |
| `port 5173 is already used` (or 4000, 4100) | another program is using that port: stop it, or change `WEB_PORT` / `API_PORT` / `AI_PORT` in `.env` |
| `make: command not found` (Windows) | you're in PowerShell: open the **Ubuntu** terminal (step 1) |
| `make: command not found` or a "developer tools" window (Mac) | `xcode-select --install` (step 1) |
| `Permission denied` on `./scripts/…` | the zip was extracted by Windows: `chmod +x scripts/*.sh`, or extract it again with `unzip` in Ubuntu |
| `no data at ./data` | the `data/` folder must be next to the `Makefile`, and `.env` must contain `DATA_DIR=./data` |
| The page stays blank right after "Ready" | wait 10–20 s then reload |
| The first `make setup` is very long or fails while downloading | it's the download (1–2 GB); on the venue's Wi-Fi, ask the Stockline team for the USB stick with the images, then `make offline IMAGES=<file path>` (section "Without Internet") |
| The ERP shows strange data after your tests | `make reset` |
| The microphone doesn't work | allow it in the browser (icon to the left of the address), use Chrome |
| The agent always understands "il vous reste du bar ?" | transcription is in `mock`: see [Real keys or simulated models](#real-keys-or-simulated-models) |
| `HTTP 401` / `HTTP 429` / `quota` in the responses | key refused or cap reached: check the key in `.env`, then `make restart`; if the cap is reached, come and see us |
| A change to `.env` isn't taken into account | `make restart` (without Docker: Ctrl-C then `make dev`) |
| `corepack enable` fails (`EACCES`) in no-Docker mode | install Node with nvm (see [Without Docker](#without-docker)), or `npm install -g pnpm@10` |
| Something else | `make logs` shows the error; otherwise come and see the Stockline team (stuck for more than 20 min = come) |
