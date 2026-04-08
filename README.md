```
  ███████╗ █████╗ ██╗   ██╗██████╗  ██████╗ ███╗   ██╗
  ██╔════╝██╔══██╗██║   ██║██╔══██╗██╔═══██╗████╗  ██║
  ███████╗███████║██║   ██║██████╔╝██║   ██║██╔██╗ ██║
  ╚════██║██╔══██║██║   ██║██╔══██╗██║   ██║██║╚██╗██║
  ███████║██║  ██║╚██████╔╝██║  ██║╚██████╔╝██║ ╚████║
  ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
```

# SAURON — Security Autonomous Universal Reconnaissance & Offensive Network

> **The All-Seeing AI for Autonomous Penetration Testing**
>
> Enterprise-grade, multi-LLM, MCP-native autonomous pentesting platform built for Red Teams, Offensive Security Engineers, and AI Security researchers.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)](https://fastapi.tiangolo.com/)
[![MCP](https://img.shields.io/badge/MCP-native-purple)](https://modelcontextprotocol.io/)
[![Kali](https://img.shields.io/badge/Kali-integrated-red)](https://www.kali.org/)
[![AI Hackathon](https://img.shields.io/badge/AI%20Hackathon-Ruse%202026-ff4d4d)](#)

---

## What is SAURON?

SAURON is a **fully autonomous, AI-driven penetration testing orchestrator**. It turns any LLM (Claude, GPT, Gemini, or a local Ollama model such as *WhiteRabbitNeo*) into a battle-ready red-team operator that can run an **entire engagement end-to-end**:

```
  Recon  →  Scanning  →  Enumeration  →  Exploitation  →  Post-Ex  →  Reporting
     ▲                                                                      │
     └──────────────────── continuous feedback loop ───────────────────────┘
```

Every command the agent issues is executed inside a hardened sandbox against **the full Kali Linux toolchain**, captured with **screenshots and terminal recordings**, and streamed live to a beautiful cyberpunk-styled web dashboard.

## Key Features

### AI & Agent Engine
- **Multi-LLM abstraction** — swap brains without touching code
  - Anthropic Claude (Opus / Sonnet / Haiku 4.x)
  - OpenAI GPT (4o, 4.1, o-series)
  - Google Gemini (1.5 / 2.x)
  - **Ollama + WhiteRabbitNeo** for fully offline, air-gapped ops
- **Autonomous agent loop** — ReAct-style planning with reflection, self-critique, and replanning
- **Specialised sub-agents** — Recon, Scanner, Exploiter, Post-Ex, Red-Team, Reporter
- **MCP-native** — every capability exposed as a Model Context Protocol tool
- **Tool arbitration** — the LLM router picks the right model for the right job (cheap model for triage, heavy model for exploitation reasoning)

### Pentest Coverage
| Domain | Engines |
|---|---|
| **Web App** | burpsuite, zap, nikto, wpscan, ffuf, gobuster, sqlmap, dalfox, nuclei |
| **API** | postman-cli, kiterunner, arjun, nuclei-api, mitmproxy |
| **Mobile** | mobsf, apktool, frida, objection, drozer, jadx |
| **Infrastructure** | nmap, masscan, rustscan, naabu, shodan-cli |
| **Network** | wireshark/tshark, bettercap, responder, impacket-suite |
| **Active Directory** | bloodhound, crackmapexec, rubeus, certipy, kerbrute, adrecon |
| **LLM / AI** | garak, llm-guard, promptmap, jailbreak test suites, custom prompt-injection harness |
| **Red Team** | stealth profiles, jitter/sleep, domain fronting config, C2 interop (no offensive payloads shipped) |

### Enterprise-Grade Platform
- **FastAPI** backend, **WebSocket** live telemetry, **SQLite/Postgres** persistence
- **Beautiful dark cyberpunk UI** — no framework, zero build step, boots instantly
- **Docker / docker-compose** deployment
- **Screenshot engine** — every command, every response, auto-inserted into the report
- **Auto-generated reports** — Markdown to HTML to PDF with CVSS, CWE, MITRE ATT&CK mapping
- **Audit log** of every AI decision (crucial for engagement deliverables)
- **RBAC** for multi-operator teams
- **Plugin SDK** — add your own tools in ~20 lines

### Responsible Red Team
SAURON ships with **stealth configuration primitives** (jitter, sleep, user-agent rotation, DNS-over-HTTPS egress, EDR-safe scan timing) so blue teams and pentesters can realistically test detection coverage. **No weaponised code, no payload generators, no malware** — SAURON orchestrates *existing Kali tooling* and lets the operator bring their own C2. Always use under written authorisation.

---

## Quick Start

### 1. Clone & install
```bash
git clone https://github.com/sauron666/ai-test.git sauron
cd sauron
./scripts/install.sh
```

### 2. Configure LLM providers
```bash
cp .env.example .env
# edit .env and add at least ONE of:
#   ANTHROPIC_API_KEY=...
#   OPENAI_API_KEY=...
#   GOOGLE_API_KEY=...
#   OLLAMA_HOST=http://localhost:11434
```

### 3. (Optional) Pull the local offline brain
```bash
./scripts/setup_ollama.sh   # installs ollama + pulls WhiteRabbitNeo
```

### 4. Launch the whole stack
```bash
./scripts/start.sh
```

This single command boots:
- SAURON backend API (`:8000`)
- MCP server (`:8765`)
- Web dashboard (`:8080`)
- Ollama daemon if configured
- Background worker for long-running scans

Open **http://localhost:8080** and the Eye of Sauron is watching.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         WEB DASHBOARD                            │
│   (cyberpunk SPA — live terminal, graph, reports, settings)     │
└───────────────────────────┬──────────────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼──────────────────────────────────────┐
│                     FastAPI BACKEND                              │
│  auth · sessions · engagements · reports · settings · audit     │
└─────┬─────────────────┬────────────────┬─────────────────────────┘
      │                 │                │
┌─────▼────────┐ ┌──────▼─────────┐ ┌────▼─────────────────────┐
│ LLM ROUTER   │ │ AGENT ORCHESTR │ │ MCP SERVER               │
│ claude/gpt/  │◄┤  ReAct loop +  │►│ Model Context Protocol   │
│ gemini/      │ │  sub-agents    │ │ exposes every tool       │
│ ollama       │ └──────┬─────────┘ └──────────────────────────┘
└──────────────┘        │
                 ┌──────▼───────────────────────────────────────┐
                 │              TOOL EXECUTOR                    │
                 │   sandboxed shell · screenshot · log · PTY   │
                 └──────┬───────────────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │    KALI ARSENAL    │
              │  500+ integrated   │
              │       tools        │
              └────────────────────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full breakdown.

---

## Project Layout

```
sauron/
├── backend/          # FastAPI service + agents + tool executor
│   ├── agents/       # orchestrator + specialised sub-agents
│   ├── llm/          # claude/openai/gemini/ollama providers
│   ├── mcp/          # MCP server exposing every capability
│   ├── tools/        # Kali wrappers & shell executor
│   ├── pentest/      # web/api/mobile/infra/network/AD/LLM playbooks
│   ├── reporting/    # MD/HTML/PDF generators, screenshot engine
│   ├── api/          # REST + WebSocket routes
│   └── database/     # models + session
├── frontend/         # zero-build cyberpunk SPA
├── config/           # yaml profiles (tools, LLMs, engagements)
├── scripts/          # install / start / ollama / bootstrap
├── docs/             # architecture, usage, red-team, security
└── docker-compose.yml
```

---

## Hackathon — AI Hackathon Ruse 2026

SAURON is being built for the **AI Hackathon in Ruse**. The goal: demonstrate that a single AI operator can execute a full professional pentest — from recon to client-ready PDF — faster and more thoroughly than a human junior, while remaining auditable and responsible.

---

## Legal & Ethics

SAURON is a **defensive security research & authorised penetration testing tool**. You **must** have explicit written permission to test any target. Unauthorised use is illegal in virtually every jurisdiction. The authors accept no liability for misuse. See [`docs/SECURITY.md`](docs/SECURITY.md).

---

## License

MIT — see [`LICENSE`](LICENSE).
