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
- **Senior-pentester mindset** — 14 non-negotiable principles baked into every sub-agent (scope discipline, hypothesis-first action, evidence hierarchy, no-fabrication) — see [`docs/AGENT_INTELLIGENCE.md`](docs/AGENT_INTELLIGENCE.md)
- **False-positive firewall** — every finding runs through a YAML-driven FP knowledge base, a dual-source confirmation gate, and an evidence-quality scorer before it can enter the report
- **Critic sub-agent** — a dedicated second-pass reviewer whose only job is to destroy weak findings and catch rabbit holes
- **Hypothesis journal + phase budgets** — every action must serve a stated hypothesis with a disproof condition; the orchestrator times out phases that stop producing new information
- **Autonomous agent loop** — ReAct-style planning with reflection, self-critique, rabbit-hole detection, and replanning
- **Specialised sub-agents** — Recon, Scanner, Exploiter, Post-Ex, Red-Team, Reporter, Critic
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

> **For a detailed, platform-specific walkthrough (Kali / Ubuntu / Debian / Docker / macOS / WSL2), see [`docs/INSTALL.md`](docs/INSTALL.md).** The quick start below is the happy path; the install guide covers prerequisites, tool setup, troubleshooting, and common pitfalls.

### 1. Clone & install
```bash
git clone https://github.com/sauron666/AI-test.git sauron
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
- Web dashboard served by the backend (`:8000/`)
- Ollama daemon if configured
- Background worker for long-running scans

Open **http://localhost:8000** and the Eye of Sauron is watching.

### Docker one-liner
```bash
cp .env.example .env   # add your LLM keys
docker compose up -d --build
```

See [`docs/INSTALL.md`](docs/INSTALL.md) §6 for the full Docker walkthrough.

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

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full breakdown and [`docs/AGENT_INTELLIGENCE.md`](docs/AGENT_INTELLIGENCE.md) for how the agent thinks.

---

## Why SAURON doesn't hallucinate findings

Most "AI pentester" demos look impressive and then file 40 false positives the moment they meet a WAF. SAURON was built to avoid exactly that. Three mechanisms work together:

1. **Senior mindset prompt** — the agent is told, before every action, to behave like a 10-year consultant: scope-strict, hypothesis-first, evidence-bound, no-fabrication. See [`config/prompts/senior_mindset.md`](config/prompts/senior_mindset.md).
2. **False-positive firewall** — [`backend/agents/validator.py`](backend/agents/validator.py) runs every candidate finding through a YAML knowledge base of known-noise patterns ([`config/knowledge/false_positives.yaml`](config/knowledge/false_positives.yaml)), a dual-source confirmation gate (no single-tool HIGHs), and an evidence-quality scorer.
3. **Critic loop** — [`backend/agents/critic_agent.py`](backend/agents/critic_agent.py) is a dedicated reviewer. It never runs tools — it only tries to destroy weak findings with `VERDICT: REJECT / DEMOTE / ESCALATE`. Phase-level reviews catch rabbit holes after the fact.

On top of that, **phase budgets** cut any loop that stops producing new information, a **hypothesis journal** tracks what the agent believes and what would disprove it, and **rabbit-hole detectors** fire on WAF loops, rate-limiting, and placeholder-target misconfigurations.

The full design is documented in [`docs/AGENT_INTELLIGENCE.md`](docs/AGENT_INTELLIGENCE.md).

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
