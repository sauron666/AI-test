# SAURON Agent Intelligence

This document explains **how SAURON thinks** — the senior-pentester
mindset baked into every sub-agent, the false-positive firewall,
the evidence hierarchy, the critic loop, and the rabbit-hole
defences that together make the agent act like a 10-year red-team
lead instead of a script kiddie running nuclei on everything.

If you just want to install SAURON, see [`INSTALL.md`](INSTALL.md).
If you want to understand why it behaves the way it does in an
engagement, read on.

---

## 1. Design goals

SAURON's agent layer was built around four non-negotiable properties:

1. **No fabrication.** Never invent findings, CVEs, versions, or
   payloads. When uncertain, say "uncertain — would require X".
2. **No false positives.** A WAF block is not a vuln. A 404 on a
   traversal attempt is not a vuln. A generic 500 is not SQLi.
3. **No rabbit holes.** When a technique stops producing new
   information, stop and pivot — automatically if the operator
   forgets.
4. **Impact-first.** 30 info findings are less valuable than 1
   exploitable critical. Allocate budget accordingly.

Every mechanism below exists to serve one of those four properties.

---

## 2. The senior mindset system prompt

Every sub-agent is constructed with this layered system prompt:

```
 [ base SAURON prompt (config/prompts/system.md) ]
 [ senior mindset module (config/prompts/senior_mindset.md) ]
 [ Kali tool catalog summary ]
 [ role-specific prompt (recon / scan / exploit / ...) ]
```

The **senior mindset module** enforces 14 principles the agent
must honour before EVERY action:

1. Scope discipline is non-negotiable
2. Hypothesis-driven testing (HYPOTHESIS / TEST / EXPECTED / DISPROOF)
3. Evidence hierarchy
4. False-positive defensive reflex
5. Rabbit-hole guards
6. Read every output carefully
7. Attack-chain thinking
8. Impact-first prioritisation
9. Negative findings matter
10. Noise discipline
11. Never fabricate
12. Self-critique every 3 actions
13. Operator escalation triggers
14. Reporting while testing

The full text lives in `config/prompts/senior_mindset.md`. The
orchestrator loads it automatically on startup and injects it into
every sub-agent's context window.

---

## 3. Hypothesis-first action

Before calling ANY tool, the agent must emit:

```
HYPOTHESIS: <what I believe about the target>
TEST:       <the command/tool that would prove or disprove it>
EXPECTED:   <what confirmation looks like>
DISPROOF:   <what would prove me wrong>
```

If the agent cannot articulate a disproof, it is guessing — and the
reflector will flag the action.

The orchestrator tracks open hypotheses in
`AgentContext.hypotheses`. Each `Hypothesis` has an iteration
budget (default 6). Once exhausted, the agent must either confirm,
abandon, or reframe before spending more budget on it.

```python
@dataclass
class Hypothesis:
    statement: str
    test: str
    expected: str
    disproof: str
    status: str = "open"
    iterations_spent: int = 0
    max_iterations: int = 6
```

---

## 4. Phase budgets (timeboxing)

Every phase has a `PhaseBudget` controlled by the orchestrator:

```python
@dataclass
class PhaseBudget:
    phase: str
    max_iterations: int = 12
    max_seconds: int = 1800
    iterations_used: int = 0
```

The orchestrator consumes one iteration per loop step. When the
budget is exhausted, the loop breaks, the agent emits a truthful
summary of what was not reached, and the orchestrator advances to
the next phase.

This eliminates the classic "10 hours fuzzing /admin behind a WAF"
rabbit hole.

Budgets can be overridden per-engagement via engagement metadata.

---

## 5. The false-positive firewall

### 5.1 Knowledge base

`config/knowledge/false_positives.yaml` is a structured catalogue
of known-noise patterns grouped by category (web, network,
active_directory, api, llm_ai, mobile) plus a `rabbit_holes`
section. Each entry:

```yaml
- id: waf_uniform_response
  pattern: "(cloudflare|akamai|imperva|sucuri|incapsula|barracuda|f5-bigip)"
  reason:  "Target responded with a WAF signature..."
  severity_cap: low
```

### 5.2 The validator

`backend/agents/validator.py` loads the YAML into compiled regexes
and runs every candidate finding through three gates:

1. **Pattern-based FP filter** — if the evidence matches a known
   FP signature, the severity is capped or downgraded and the
   rule id is recorded in `fp_rules_hit`.
2. **Dual-source confirmation** — any finding promoted to
   `high`/`critical` must be corroborated by **at least two
   independent tools** OR a successful manual PoC. Single-source
   high findings are demoted to `medium` / `possible`.
3. **Evidence-quality scoring** — a 0..1 score factoring in
   distinct sources, PoC presence, evidence length, and FP hits.

```python
result = validator.validate(
    title=title,
    severity="high",
    evidence_text=evidence,
    sources=["nmap", "nuclei"],
    category="web",
    confirmed_by_poc=False,
)
# result.severity  = "high"
# result.status    = "confirmed"   (two distinct sources)
# result.quality_score = 0.6
# result.fp_rules_hit = []
```

If `accepted=False`, the candidate goes to `ctx.rejected_findings`
with a reason. Rejected findings appear in the report appendix so
the operator can audit the filter.

### 5.3 Evidence hierarchy

Findings are tagged with one of four statuses. The validator
refuses to promote a finding above its evidence level:

| Level         | Criteria                                                |
|---------------|---------------------------------------------------------|
| **suspected** | one indicator from one tool, no manual confirmation     |
| **possible**  | one indicator + plausible code path / version match    |
| **confirmed** | independently reproduced by ≥2 tools OR manual PoC      |
| **exploited** | read-only PoC executed, impact demonstrated safely      |

High / Critical findings **must** reach `confirmed` or `exploited`
before they enter the final report.

---

## 6. The critic sub-agent

`backend/agents/critic_agent.py` is a dedicated reviewer whose only
job is to **destroy weak findings** before they reach the client.

The critic does NOT execute tools. It reasons over the existing
history and emits one of four verdicts:

```
VERDICT: <ACCEPT | DEMOTE | REJECT | ESCALATE>
NEW_SEVERITY: <info|low|medium|high|critical>
NEW_STATUS: <suspected|possible|confirmed|exploited>
REASON: <one paragraph, specific and technical>
ADVICE: <what the junior should do next, if anything>
```

The orchestrator wires the critic in at two points:

- **Per-finding** — every medium+ candidate that passed the
  validator is handed to `critic.review_finding()`. A `REJECT`
  verdict moves the candidate to `rejected_findings`; a `DEMOTE`
  verdict lowers severity one step.
- **End-of-phase** — after every phase, `critic.review_phase()`
  looks at the phase summary, active hypothesis, findings, and
  recent history, and answers:
    1. Did the phase achieve its goal?
    2. What was the biggest wasted effort and why?
    3. What critical question remains unanswered?
    4. What is the single most valuable next action?
    5. Which findings are likely false positives?

The phase review is emitted as an `agent.reflection` event on the
websocket so the operator can see it live.

---

## 7. Rabbit-hole defences

Three layers of defence:

### 7.1 Static patterns in the YAML

```yaml
rabbit_holes:
  - id: waf_infinite_loop
    trigger: "same WAF block response received 5+ times on same endpoint"
    advice:  "Stop fuzzing this endpoint. Rotate to a different entry point."
  - id: rate_limit_backoff_needed
    trigger: "429 responses 3+ times within 60s"
    advice:  "Apply exponential backoff or switch stealth profile to silent."
  - id: placeholder_vs_real_target
    trigger: "target contains 'example.com' or 'localhost'"
    advice:  "Almost certainly a misconfigured scope. Halt and escalate."
```

### 7.2 Runtime detector

`FindingValidator.detect_rabbit_hole(history_text)` scans the
recent `AgentContext.history` for these signatures each iteration.
Matches become `agent.rabbit_hole` telemetry events and are logged
in the decision journal.

### 7.3 Budget-driven cut-off

When `PhaseBudget.exhausted` becomes True, the orchestrator cuts
the loop. This is the last-resort guard against runaway phases.

---

## 8. The orchestrator pipeline

Full flow per iteration:

```
PLAN       → sub-agent LLM emits thought + optional tool calls
ACT        → MCP tool call (budget gated)
OBSERVE    → tool result captured, piped back to history
PARSE      → scan thought for ```finding blocks
VALIDATE   → FindingValidator.validate() — FP firewall
CRITIQUE   → CriticAgent.review_finding() for medium+
REFLECT    → reflection LLM critiques the latest action
BUDGET     → PhaseBudget.consume(1)
RABBIT-HOLE → validator.detect_rabbit_hole() on history
```

The loop terminates when any of:
- the agent emits no tool calls (phase complete from its view)
- the phase budget is exhausted
- an unrecoverable LLM or tool error occurs
- the operator marks the context `done`

---

## 9. Inline finding format

Sub-agents signal a candidate finding by emitting a fenced JSON
block with the `finding` language tag inside their thought:

```finding
{
  "title": "SSRF on /api/v1/preview",
  "severity": "high",
  "sources": ["nuclei", "curl"],
  "evidence": "HTTP 200, body contained ami-id ami-12345...",
  "poc": true,
  "category": "web",
  "cwe": "CWE-918",
  "recommendation": "Validate scheme + host allow-list"
}
```

The orchestrator parses this block, runs it through the validator
and critic, and on acceptance appends it to `ctx.findings`. This
is the ONLY path by which a finding enters the report — there is
no way for the agent to push raw findings into the database.

---

## 10. Decision journal

`AgentContext.decisions` records every override, budget cut,
rabbit-hole warning, and hypothesis status change with a timestamp
and a rationale. The report appendix dumps this journal so the
client can audit the agent's reasoning after the fact.

Example entries:

```json
[
  {"iteration": 14, "decision": "rabbit-hole detected",
   "rationale": "Stop fuzzing this endpoint. Rotate...", "ts": 1712345678},
  {"iteration": 27, "decision": "cut phase exploit",
   "rationale": "phase budget exhausted", "ts": 1712345999},
  {"iteration": 31, "decision": "hypothesis abandoned",
   "rationale": "disproof condition met", "ts": 1712346100}
]
```

---

## 11. Operator escalation

The agent stops and calls `request_operator_input` when:

- PII, credentials, or crown-jewel data are discovered
- Signs of a prior compromise appear on the target
- About to touch a system outside the authorised window
- Cannot decide between ≥2 reasonable next steps with equal merit
- A finding would cause service disruption if exploited further
- A scope ambiguity is detected
- A tool fails identically three times (environment problem)

Escalation is a first-class action, not a failure mode.

---

## 12. What SAURON deliberately will NOT do

- Fabricate vulnerabilities, CVEs, versions, or payloads.
- Write malware, droppers, C2 implants, or persistence code.
- Disable target security controls.
- Exfiltrate real business data (hashes and redactions only).
- Operate outside the written scope or ROE window.
- Promote a finding above its evidence level.
- Inflate severity for effect.
- Hammer a blocked endpoint.
- Chase an endless subdomain list when the target is already mapped.
- Rewrite a public exploit "until it works" when the version doesn't
  match.

These refusals are not hacks bolted on top — they are load-bearing
properties of the system.

---

## 13. Extending the intelligence

### 13.1 Adding a false-positive rule

Append to `config/knowledge/false_positives.yaml`:

```yaml
web:
  - id: graphql_introspection_disabled
    pattern: "GraphQL introspection is disabled"
    reason: "Server explicitly rejected introspection — not a leak."
    severity_cap: info
```

Restart SAURON — the `@lru_cache` reloads on boot.

### 13.2 Adding a rabbit-hole pattern

Append to the `rabbit_holes:` section. Then extend
`FindingValidator.detect_rabbit_hole()` if you need custom logic
(most are regex-friendly).

### 13.3 Adding a new sub-agent

1. Create `backend/agents/<role>_agent.py` extending `BaseAgent`.
2. Import the senior mindset principles in your prompt —
   reference `config/prompts/senior_mindset.md` in the role-specific
   instructions (the orchestrator already loads it once globally).
3. Register the phase in `PHASE_SEQUENCE` in `orchestrator.py`.
4. Add the role to `_build_agent()` mapping.

### 13.4 Tuning budgets

Override per-engagement through the API:

```json
{
  "profile": "web_application",
  "scope": {...},
  "phase_budgets": {
    "recon":   {"max_iterations": 20, "max_seconds": 3600},
    "exploit": {"max_iterations": 30, "max_seconds": 5400}
  }
}
```

---

## 14. TL;DR for operators

> SAURON thinks before it acts, validates before it files, critiques
> before it reports, and cuts its own loop when it stops learning.
> It will under-report before it over-reports, because a rejected
> false positive is a win and a fabricated finding is a catastrophe.

That is the senior mindset, encoded.
