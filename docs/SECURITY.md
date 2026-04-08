# SAURON — Security & Ethics

## Intended use

SAURON is a **defensive security research tool** and **authorised
penetration testing orchestrator**. It is intended for:

- Authorised penetration testing engagements under written contract.
- Red-team / purple-team detection testing with client consent.
- CTF challenges and security training labs.
- Academic research on autonomous security agents.
- The AI Hackathon Ruse 2026.

## Unauthorised use is illegal

Running SAURON (or any pentest tool) against systems you do not own
or have explicit, written permission to test is a crime in virtually
every jurisdiction. The authors disclaim all liability for misuse.

## Hard guarantees

1. **No offensive code generation.** SAURON will not write malware,
   persistence implants, droppers, or evasion payloads. The agent
   system prompts explicitly forbid it and the reviewers enforce it.
2. **Destructive command filter.** `backend/utils/security.py`
   contains a hard block-list that refuses obviously destructive
   shell patterns regardless of who asks (including the LLM).
3. **Human-in-the-loop default.** `AGENT_AUTO_APPROVE_COMMANDS=false`
   by default — the AI proposes every command and a human operator
   approves it through the WebSocket channel.
4. **Scope enforcement prompt.** The base system prompt instructs
   every sub-agent to refuse targets outside the declared scope.
5. **Audit everything.** Every LLM call, tool call, stdout, and
   stderr is persisted to the database and appended to the report.

## Reporting vulnerabilities in SAURON itself

Please open a GitHub security advisory rather than a public issue.

## Data handling

SAURON stores everything locally by default — SQLite database,
artifacts, screenshots, reports — nothing is sent to a third party
except the LLM API calls you configure. When you use Ollama +
WhiteRabbitNeo, even the LLM traffic is local.
