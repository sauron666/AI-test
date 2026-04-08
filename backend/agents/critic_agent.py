"""Critic / second-pass reviewer.

Runs after every phase and after every HIGH/CRITICAL finding. Its
only job is to try to break the current hypothesis.

Inspired by how senior consultants review a junior's work:
  - "What if this is a WAF fake response?"
  - "Did you confirm with a second tool?"
  - "Is this actually in scope?"
  - "What would make me wrong?"

The critic does NOT execute tools. It only reasons over the existing
agent history and can force:
  - severity downgrade
  - status rollback to 'suspected'
  - a new hypothesis to test
  - an escalation to the human operator
"""
from __future__ import annotations

from .base import BaseAgent


CRITIC_SYSTEM = """\
You are the CRITIC of the SAURON engagement — a 15-year senior red
team lead reviewing a junior's findings. Your mandate is to DESTROY
weak findings before they reach the client.

For every candidate finding you are shown, answer these questions
in order and then give a verdict:

1. **Scope check** — is the target in the written scope? If not,
   verdict=REJECT.
2. **Evidence check** — does the cited output actually prove the
   vulnerability, or is it a generic error, a WAF block, a 404,
   or a banner-grab?
3. **Reproduction check** — was the finding reproduced by a second
   independent tool or a manual PoC? If not, verdict ≤ POSSIBLE.
4. **Impact check** — even if real, does this actually chain to
   business impact? A self-XSS on a dev subdomain is not P1.
5. **False-positive reflex** — search memory for the most common
   FP patterns (see senior_mindset.md §4). If ANY match, downgrade.
6. **Rabbit-hole check** — did the operator spend disproportionate
   effort for the evidence collected? If yes, advise them to pivot.

Output strictly in this format:

```
VERDICT: <ACCEPT | DEMOTE | REJECT | ESCALATE>
NEW_SEVERITY: <info|low|medium|high|critical>
NEW_STATUS: <suspected|possible|confirmed|exploited>
REASON: <one paragraph, specific and technical>
ADVICE: <what the junior should do next, if anything>
```

Be ruthless. A rejected false positive is a win; a fabricated
finding in the report is a catastrophe.
"""


class CriticAgent(BaseAgent):
    name = "critic"
    phase = "critique"

    def __init__(self, llm, system_prompt: str):
        super().__init__(llm=llm, system_prompt=system_prompt + "\n\n" + CRITIC_SYSTEM)

    async def review_finding(self, ctx, finding: dict) -> str:
        """One-shot review of a single finding candidate."""
        prompt = (
            "Review this candidate finding:\n\n"
            f"TITLE: {finding.get('title', '')}\n"
            f"SEVERITY (proposed): {finding.get('severity', '')}\n"
            f"SOURCES: {', '.join(finding.get('sources', []))}\n"
            f"EVIDENCE (truncated):\n{str(finding.get('evidence', ''))[:3000]}\n\n"
            "Apply the senior mindset checklist and emit your verdict."
        )
        return await self.think(ctx, prompt)

    async def review_phase(self, ctx, phase: str, summary: str) -> str:
        """End-of-phase review — checks whether the phase actually
        accomplished its goal or just burned iterations."""
        prompt = (
            f"End-of-phase review for phase '{phase}'.\n\n"
            f"Phase summary (agent's own words):\n{summary[:4000]}\n\n"
            "Questions you must answer:\n"
            "1. Did the phase achieve its declared goal?\n"
            "2. What was the biggest wasted effort and why?\n"
            "3. What critical question remains unanswered?\n"
            "4. What is the single most valuable next action?\n"
            "5. Are any findings likely to be false positives? Which ones and why?\n"
        )
        return await self.think(ctx, prompt)
