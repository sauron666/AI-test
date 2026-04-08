# SAURON — Detailed Installation Guide

> SAURON is an enterprise-grade, autonomous, multi-LLM, MCP-native
> penetration-testing platform. It is designed for authorised
> security testing only. By installing it you accept the rules in
> [`SECURITY.md`](SECURITY.md) and [`RED_TEAM.md`](RED_TEAM.md).

This guide walks you through installing SAURON on every supported
platform, configuring the LLM providers, wiring it to Kali tooling,
and validating the install before your first engagement.

---

## Table of contents

1. [What you are installing](#1-what-you-are-installing)
2. [System requirements](#2-system-requirements)
3. [Prerequisites checklist](#3-prerequisites-checklist)
4. [Install path A — Kali Linux (recommended)](#4-install-path-a--kali-linux-recommended)
5. [Install path B — Ubuntu / Debian](#5-install-path-b--ubuntu--debian)
6. [Install path C — Docker / docker-compose](#6-install-path-c--docker--docker-compose)
7. [Install path D — macOS (dev-only, limited tools)](#7-install-path-d--macos-dev-only-limited-tools)
8. [Install path E — WSL2 on Windows](#8-install-path-e--wsl2-on-windows)
9. [Configure the LLM providers](#9-configure-the-llm-providers)
10. [Running Ollama + WhiteRabbitNeo offline](#10-running-ollama--whiterabbitneo-offline)
11. [First-run verification](#11-first-run-verification)
12. [Firewall, capabilities, and permissions](#12-firewall-capabilities-and-permissions)
13. [Troubleshooting](#13-troubleshooting)
14. [Common pitfalls](#14-common-pitfalls)
15. [Upgrading](#15-upgrading)
16. [Uninstalling](#16-uninstalling)

---

## 1. What you are installing

SAURON is made of:

| Component        | Runs as                          | Default port |
|------------------|----------------------------------|--------------|
| FastAPI backend  | `uvicorn backend.main:app`       | `8000`       |
| WebSocket live   | Same process as backend          | `8000/ws`    |
| MCP server       | Same process as backend          | `8765`       |
| Frontend SPA     | Static files served by backend   | `/`          |
| SQLite database  | File: `runtime/sauron.db`        | —            |
| Kali tool layer  | Kali tools invoked as subprocess | —            |
| LLM providers    | External APIs + optional Ollama  | —            |

A single `uvicorn` process exposes the API, the websocket stream,
the frontend, and the MCP endpoint. No reverse proxy is required
for local use.

---

## 2. System requirements

Minimum:
- 4 CPU cores, 8 GB RAM, 20 GB disk
- Python 3.11 or newer
- Linux kernel ≥ 5.10 (capabilities, cgroups)

Recommended:
- 8 CPU cores, 16 GB RAM, 50 GB SSD
- Kali Linux 2024.x (for the full tool chain)
- A GPU if you plan to run Ollama / WhiteRabbitNeo locally

Supported OS:

| OS                 | Status                                  |
|--------------------|-----------------------------------------|
| Kali Linux 2024.x  | Fully supported, primary target         |
| Ubuntu 22.04/24.04 | Supported (requires tool installation)  |
| Debian 12          | Supported (requires tool installation)  |
| macOS 14+          | Dev / UI only — many tools missing      |
| Windows + WSL2     | Supported via Kali-WSL or Ubuntu-WSL    |
| Docker             | Supported — recommended for isolation   |

---

## 3. Prerequisites checklist

Regardless of platform, have these ready before you start:

- [ ] Python **3.11+** with `pip` and `venv`
- [ ] `git`
- [ ] At least one LLM API key **OR** an Ollama runtime
- [ ] A host you are **authorised** to test (never an unowned target)
- [ ] `xvfb`, `scrot`, `asciinema` (for screenshots + session recording)
- [ ] `weasyprint` system deps (for PDF export — Cairo, Pango, GDK-PixBuf)

Check Python version:

```bash
python3 --version   # must be >= 3.11
```

---

## 4. Install path A — Kali Linux (recommended)

### 4.1 Update the base

```bash
sudo apt update && sudo apt -y full-upgrade
sudo apt -y install python3 python3-venv python3-pip git \
                    build-essential libssl-dev libffi-dev \
                    xvfb scrot asciinema \
                    libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
                    libgdk-pixbuf-2.0-0 shared-mime-info fonts-dejavu
```

### 4.2 Install the Kali offensive tool set

Kali ships with most of what SAURON needs, but explicitly install
the tool categories referenced by the catalog:

```bash
sudo apt -y install \
    nmap masscan \
    amass subfinder theharvester whatweb wappalyzer \
    nuclei nikto wpscan \
    sqlmap xsser wfuzz ffuf gobuster feroxbuster \
    hydra john hashcat medusa \
    metasploit-framework \
    crackmapexec impacket-scripts bloodhound.py responder \
    netexec smbmap enum4linux-ng \
    burpsuite zaproxy \
    tshark wireshark \
    sslscan sslyze testssl.sh \
    dnsrecon dnsenum
```

> Some tools (like `netexec`) are drop-in replacements for
> `crackmapexec`. Install whichever you are used to — SAURON detects
> both at runtime via the tool catalog.

### 4.3 Clone and install SAURON

```bash
git clone https://github.com/sauron666/AI-test.git sauron
cd sauron
./scripts/install.sh
```

The installer is **fully automated and idempotent**. It will:

1. Detect your distro and Python version (3.11 / 3.12 / 3.13 all work).
2. Install the system packages it needs (build tools, Xvfb, scrot,
   optionally Cairo/Pango for PDF).
3. Create a `.venv` and upgrade pip / setuptools / wheel.
4. Install Python dependencies with `--prefer-binary`. If the bulk
   install fails, it retries each package individually so one
   broken wheel doesn't kill the whole run.
5. Try the optional extras (weasyprint, asciinema) best-effort —
   they degrade gracefully if the system libraries are missing.
6. Verify every import before declaring success.
7. Copy `.env.example → .env`.

Installer flags:

| Flag                  | What it does                                         |
|-----------------------|------------------------------------------------------|
| `--no-system`         | Skip all apt/dnf steps (host already set up)         |
| `--no-optional`       | Skip weasyprint + asciinema (minimal mode)           |
| `--with-kali-tools`   | Also install nmap, nuclei, sqlmap, metasploit, …     |
| `--with-ollama`       | Also install ollama + pull WhiteRabbitNeo            |
| `--venv <path>`       | Use a custom venv path (default `.venv`)             |
| `--python <bin>`      | Force a specific interpreter                         |
| `--recreate-venv`     | Wipe and recreate the venv                           |
| `-h` / `--help`       | Show help                                            |

Examples:

```bash
# Fully loaded Kali install
./scripts/install.sh --with-kali-tools --with-ollama

# Minimal (already have tools, just want the backend)
./scripts/install.sh --no-system --no-optional

# Rescue a broken venv after upgrading Python
./scripts/install.sh --recreate-venv
```

### 4.4 Configure LLM keys

Edit `.env` and set at least one LLM provider (see §9). The
installer already created it from `.env.example`.

### 4.5 Start SAURON

```bash
./scripts/start.sh
```

`start.sh` validates the venv first and prints a clear error if the
install is incomplete (instead of crashing on `import uvicorn`).

Open <http://localhost:8000>.

---

## 5. Install path B — Ubuntu / Debian

Ubuntu does not ship with Kali's tools, so you have two options:

### Option B1: install tools from upstream

```bash
sudo apt update
sudo apt -y install python3 python3-venv python3-pip git \
                    build-essential libssl-dev libffi-dev \
                    xvfb scrot asciinema nmap masscan \
                    libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
                    libgdk-pixbuf-2.0-0 shared-mime-info

# Golang-based tools
sudo apt -y install golang
go install -v github.com/owasp-amass/amass/v4/...@master
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
sudo cp ~/go/bin/* /usr/local/bin/

# Python-based
pipx install impacket
pipx install crackmapexec
```

Then follow §4.3 onward.

### Option B2: Docker (cleaner)

Skip straight to §6.

---

## 6. Install path C — Docker / docker-compose

The repo ships a `docker-compose.yml` with a Kali base image that
already has all tools installed. This is the cleanest path.

### 6.1 Install Docker Engine

```bash
# Ubuntu example
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker "$USER"
newgrp docker
```

### 6.2 Clone and run

```bash
git clone https://github.com/sauron666/AI-test.git sauron
cd sauron
cp .env.example .env
# Edit .env to add LLM keys (see §9)
docker compose up -d --build
```

### 6.3 Persistent volumes

`docker-compose.yml` mounts:
- `./runtime`    → engagement DB, reports, screenshots
- `./config`     → prompts, tool catalog, FP knowledge base
- `./.env`       → LLM credentials

### 6.4 Access

Open <http://localhost:8000>.
Logs: `docker compose logs -f sauron`.

### 6.5 Shell into the container

```bash
docker compose exec sauron bash
```

Useful if a Kali tool is missing or you want to run a one-off
command against the shared workdir.

---

## 7. Install path D — macOS (dev-only, limited tools)

macOS is supported for **frontend / backend development**. The Kali
tool surface is limited on macOS, so full engagements should run on
Kali or inside the Docker image.

```bash
brew install python@3.12 git xquartz
brew install nmap masscan nuclei subfinder amass sqlmap nikto
brew install cairo pango gdk-pixbuf libffi

git clone https://github.com/sauron666/AI-test.git sauron
cd sauron
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python3 -m backend.database.init
./scripts/start.sh
```

For `scrot`/`xvfb`-based screenshots, use `screencapture` or run
SAURON inside the Docker image.

---

## 8. Install path E — WSL2 on Windows

Use the Kali-WSL distribution for the best experience:

```powershell
# PowerShell (Admin)
wsl --install -d kali-linux
```

Inside the WSL2 shell, follow **§4 Kali Linux** exactly.

Networking notes:
- WSL2 exposes services on `localhost` of the Windows host.
- If your Windows firewall blocks port 8000, allow it once.
- For stealth engagements, run SAURON inside a Linux VM instead —
  WSL2's shared networking can leak the Windows hostname.

---

## 9. Configure the LLM providers

Edit `.env`. SAURON supports multiple providers and will route
different agent roles to different models (planning vs. execution
vs. parsing). Set at least one.

### 9.1 Anthropic Claude (recommended for planning)

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-6
DEFAULT_LLM_PROVIDER=anthropic
```

Get the key at <https://console.anthropic.com>.

### 9.2 OpenAI ChatGPT

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

### 9.3 Google Gemini

```env
GOOGLE_API_KEY=AIza...
GOOGLE_MODEL=gemini-1.5-pro
```

### 9.4 Ollama (local, offline-capable)

```env
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=whiterabbitneo:13b
```

See §10 for the Ollama install walkthrough.

### 9.5 Role-to-model routing

```env
AGENT_PLANNING_MODEL=anthropic
AGENT_EXECUTION_MODEL=ollama
```

This sends strategic reasoning to Claude and execution/parsing to
a local WhiteRabbitNeo — a common privacy-preserving configuration.

---

## 10. Running Ollama + WhiteRabbitNeo offline

### 10.1 Install Ollama

```bash
# Linux / WSL2
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
```

macOS: `brew install ollama && brew services start ollama`.

### 10.2 Pull the model

```bash
ollama pull whiterabbitneo:13b
```

Other good offline models for SAURON:

| Model                  | Size  | Notes                              |
|------------------------|-------|------------------------------------|
| `whiterabbitneo:13b`   | ~7 GB | Offensive-security tuned           |
| `whiterabbitneo:33b`   | ~19GB | Better reasoning, needs 32GB+ RAM  |
| `llama3.1:70b-instruct`| ~40GB | General reasoning, GPU recommended |
| `qwen2.5:32b-instruct` | ~19GB | Strong tool-use ability            |

### 10.3 GPU acceleration

NVIDIA:
```bash
# Verify CUDA
nvidia-smi
# Ollama picks up CUDA automatically if drivers are present.
```

AMD (ROCm): follow <https://github.com/ollama/ollama/blob/main/docs/gpu.md>.

### 10.4 Verify Ollama is reachable

```bash
curl -s http://127.0.0.1:11434/api/tags | head
```

### 10.5 Air-gapped deployment

SAURON + Ollama + WhiteRabbitNeo runs fully offline once the model
is pulled. No external network call is required. Make sure the
`DEFAULT_LLM_PROVIDER` is `ollama` and the API keys for external
providers are blank in `.env`.

---

## 11. First-run verification

Run through this checklist after your first `start.sh`:

1. Backend health
   ```bash
   curl -s http://localhost:8000/api/health
   # → {"status":"ok","version":"..."}
   ```
2. Frontend loads
   ```bash
   curl -sI http://localhost:8000/ | head -1
   # → HTTP/1.1 200 OK
   ```
3. LLM router sanity
   ```bash
   curl -s http://localhost:8000/api/llm/providers
   # → lists configured providers
   ```
4. Tool catalog populated
   ```bash
   curl -s http://localhost:8000/api/tools | head -c 400
   ```
5. Run the smoke test
   ```bash
   source .venv/bin/activate
   pytest -q tests/test_smoke.py
   ```

If all five pass, open the web UI, create an engagement against a
disposable test target (`scanme.nmap.org` is the traditional one)
and watch the live telemetry.

---

## 12. Firewall, capabilities, and permissions

Some tools need elevated privileges:

- `nmap -sS` (SYN scan) requires `CAP_NET_RAW`.
- `masscan` requires `CAP_NET_RAW` + `CAP_NET_ADMIN`.
- `responder`, ARP spoofing tools require root.
- Screenshots via `scrot` in headless Xvfb need no root.

Recommended: run the backend as a non-root user and grant specific
capabilities to individual binaries:

```bash
sudo setcap cap_net_raw,cap_net_admin=eip $(which nmap)
sudo setcap cap_net_raw,cap_net_admin=eip $(which masscan)
```

If you prefer sudoers, add a narrowly-scoped rule:

```
sauron ALL=(root) NOPASSWD: /usr/bin/nmap, /usr/bin/masscan
```

SAURON will honour `SUDO_REQUIRED_TOOLS` in `.env` and call `sudo`
only for the whitelisted binaries.

Firewall:

- Bind SAURON to `127.0.0.1` unless you deliberately expose the UI.
- Never expose port 8000 to the public internet without TLS + auth.

---

## 13. Troubleshooting

### 13.1 `ModuleNotFoundError` when starting

The venv is missing or broken. The safe path is to recreate it —
`requirements.txt` uses version floors so pip will pick the right
wheels for your Python automatically:

```bash
./scripts/install.sh --recreate-venv
```

If you get a source-build error for `pillow`, `pyyaml`, or
`psutil`, you are on a Python version that is newer than the
pinned wheels. The current `requirements.txt` already uses `>=`
floors for these, so `--recreate-venv` fixes it. If you are on an
exotic Python like 3.14 alpha, install a 3.13 interpreter and use
`--python python3.13`.

### 13.2 `weasyprint` errors about Cairo / Pango

Install the system libraries again:

```bash
sudo apt -y install libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
                    libgdk-pixbuf-2.0-0 shared-mime-info fonts-dejavu
```

### 13.3 LLM provider errors

- `401 Unauthorized` — wrong API key in `.env`.
- `429` — quota exhausted. Switch provider or wait.
- `connection refused` on Ollama — `sudo systemctl start ollama`.

### 13.4 A Kali tool is "not found"

Check the catalog discovery log:

```bash
curl -s http://localhost:8000/api/tools/missing
```

Install the missing tool or set its path in `config/tools/overrides.yaml`.

### 13.5 Screenshots are blank

Xvfb is not running. Start it:

```bash
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
```

SAURON's `scripts/start.sh` does this for you when
`EXECUTOR_SCREENSHOTS=true`.

### 13.6 "Permission denied" on raw sockets

Grant capabilities (see §12) or run nmap in Docker with
`--cap-add=NET_RAW --cap-add=NET_ADMIN`.

### 13.7 High memory usage with Ollama

Model is too big for your RAM. Downgrade to `whiterabbitneo:13b`
or enable GPU offload.

### 13.8 The agent keeps hitting "rabbit hole" warnings

That is working as designed — the senior-mindset validator is
catching wasted effort. Read the warnings and either:

- Pivot to a different technique, or
- Raise `phase_budgets.max_iterations` in the engagement metadata
  if you genuinely need more time on that phase.

---

## 14. Common pitfalls

- **Targeting `example.com` or `localhost` by accident** — SAURON
  halts automatically via the rabbit-hole detector. Fix the scope.
- **Running outside the authorised window** — the critic will
  escalate, but the human operator is still responsible.
- **Cranking severity to look impressive** — the validator will
  demote and the critic will reject. Don't.
- **Feeding a single LLM all roles** — works, but you lose the
  planning/execution separation that makes SAURON resilient.
- **Forgetting to redact** — credentials found in post-ex must be
  redacted before they touch the report. SAURON does this by
  default; do not disable it.

---

## 15. Upgrading

```bash
cd sauron
git pull
source .venv/bin/activate
pip install -r requirements.txt --upgrade
python3 -m backend.database.init --migrate
./scripts/start.sh
```

Docker:

```bash
docker compose pull
docker compose up -d --build
```

---

## 16. Uninstalling

```bash
# stop
./scripts/stop.sh
# remove runtime
rm -rf runtime .venv
# remove repo
cd .. && rm -rf sauron
```

Docker:

```bash
docker compose down -v
docker image rm sauron:latest
```

---

That's it. For agent design and the senior mindset see
[`AGENT_INTELLIGENCE.md`](AGENT_INTELLIGENCE.md); for day-to-day
operation see [`USAGE.md`](USAGE.md); for legal boundaries see
[`SECURITY.md`](SECURITY.md).
