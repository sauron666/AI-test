# SAURON — Usage Guide

## 1. Boot the platform

### Option A — native on Kali / Debian / Ubuntu
```bash
./scripts/install.sh
cp .env.example .env    # fill in at least one LLM key
./scripts/start.sh
```

### Option B — docker compose (recommended for teams)
```bash
docker compose up --build
```

### Option C — fully offline (no internet)
```bash
./scripts/setup_ollama.sh     # pulls WhiteRabbitNeo
# edit .env: DEFAULT_LLM_PROVIDER=ollama
./scripts/start.sh
```

Open **http://localhost:8000** (or `:8080` if you split front/back).
Default credentials: `operator` / `change-me`.

## 2. Launch an engagement

1. Click **Dashboard → + New Engagement**.
2. Pick a profile (Web / API / Mobile / Infra / Network / AD / LLM / RedTeam).
3. Paste the scope JSON:
   ```json
   { "targets": ["https://target.example.com"], "out_of_scope": [] }
   ```
4. Fill in the Rules of Engagement — client, window, limits.
5. Pick a stealth profile.
6. Pick the LLM provider.
7. **Launch**.

SAURON streams live thoughts, actions, observations, and reflections
into the Live Terminal and the Activity feed. Each phase lights up on
the phase graph.

## 3. Review findings

The Findings view lists everything SAURON has confirmed, with CVSS,
CWE, OWASP, and MITRE ATT&CK mapping.

## 4. Build the report

From the Engagements view, click **📄 report** on any engagement.
SAURON produces:
- `reports/output/<id>/report.md`
- `reports/output/<id>/report.html`
- `reports/output/<id>/report.pdf` (requires weasyprint)

The report includes every command, screenshot, and agent decision,
making it fully auditable for enterprise customers.

## 5. Operator intervention

If `AGENT_AUTO_APPROVE_COMMANDS=false` (default), SAURON will pause
before executing any command and wait for your approval through the
WebSocket channel. This is the recommended setting for production
engagements — the AI proposes, the human disposes.

## 6. Air-gapped mode

SAURON is designed to operate without internet. With Ollama + a local
model such as WhiteRabbitNeo, the only external traffic is whatever
the Kali tools themselves generate against the authorised target.

## 7. Multi-LLM routing

The router picks the best available brain per role:

| Role       | Preferred order               |
|---|---|
| planning   | claude → openai → gemini → ollama |
| execution  | ollama → claude → openai          |
| parsing    | ollama → claude → gemini          |
| reporting  | claude → gemini → openai          |

Override any role via env vars or `config/llm_providers.yaml`.
