"""Base agent scaffolding."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..llm.base import BaseLLMProvider, LLMMessage


BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class Hypothesis:
    """A single working hypothesis the agent is testing.

    A senior pentester never runs a tool without a hypothesis behind
    it. SAURON enforces that by asking the orchestrator to record one
    before every action.
    """

    statement: str                             # what the agent believes
    test: str                                  # what the test is
    expected: str                              # what confirmation looks like
    disproof: str                              # what would kill this hypothesis
    status: str = "open"                       # open | confirmed | disproved | abandoned
    iterations_spent: int = 0
    max_iterations: int = 6                    # budget — after this, pivot
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "test": self.test,
            "expected": self.expected,
            "disproof": self.disproof,
            "status": self.status,
            "iterations_spent": self.iterations_spent,
            "max_iterations": self.max_iterations,
        }


@dataclass
class PhaseBudget:
    """Per-phase iteration / wall-clock budget used by the orchestrator
    to avoid infinite rabbit-holes."""

    phase: str
    max_iterations: int = 12
    max_seconds: int = 1800
    iterations_used: int = 0
    started_at: float = field(default_factory=time.time)

    @property
    def exhausted(self) -> bool:
        if self.iterations_used >= self.max_iterations:
            return True
        if (time.time() - self.started_at) >= self.max_seconds:
            return True
        return False

    def consume(self, n: int = 1) -> None:
        self.iterations_used += n


@dataclass
class AgentContext:
    """Everything an agent needs to operate on a live engagement."""

    engagement_id: str
    profile: str                               # web | api | mobile | ...
    scope: dict[str, Any]
    rules_of_engagement: str
    stealth_profile: str = "normal"
    history: list[LLMMessage] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    broadcast: BroadcastFn | None = None       # push events to websocket
    max_iterations: int = 50
    iteration: int = 0
    done: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── senior-mindset additions ─────────────────────
    hypotheses: list[Hypothesis] = field(default_factory=list)
    phase_budgets: dict[str, PhaseBudget] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    rejected_findings: list[dict[str, Any]] = field(default_factory=list)

    async def emit(self, event: dict[str, Any]) -> None:
        if self.broadcast:
            await self.broadcast(event)

    def add_finding(self, finding: dict[str, Any]) -> None:
        self.findings.append(finding)

    def reject_finding(self, finding: dict[str, Any], reason: str) -> None:
        """Track rejected findings so the operator can see what was filtered."""
        self.rejected_findings.append({**finding, "rejected_reason": reason})

    # ── hypothesis journal helpers ───────────────────
    def open_hypothesis(self, h: Hypothesis) -> None:
        self.hypotheses.append(h)

    def current_hypothesis(self) -> Hypothesis | None:
        for h in reversed(self.hypotheses):
            if h.status == "open":
                return h
        return None

    def record_decision(self, decision: str, rationale: str) -> None:
        self.decisions.append({
            "iteration": self.iteration,
            "decision": decision,
            "rationale": rationale,
            "ts": time.time(),
        })

    def budget_for(self, phase: str) -> PhaseBudget:
        if phase not in self.phase_budgets:
            self.phase_budgets[phase] = PhaseBudget(phase=phase)
        return self.phase_budgets[phase]

    def history_text(self, limit: int = 4000) -> str:
        """Flattened recent history used by rabbit-hole detection."""
        out: list[str] = []
        for m in self.history[-20:]:
            out.append(f"[{m.role}] {m.content[:500]}")
        return "\n".join(out)[:limit]


@dataclass
class AgentStep:
    kind: str                                   # thought | action | observation | reflection | error
    content: str
    meta: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    """Minimal shell every specialised agent extends."""

    name: str = "base"
    phase: str = "generic"

    def __init__(self, llm: BaseLLMProvider, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt

    async def think(self, ctx: AgentContext, user_input: str) -> str:
        """One-shot reasoning pass."""
        msgs = [
            LLMMessage(role="system", content=self.system_prompt),
            *ctx.history,
            LLMMessage(role="user", content=user_input),
        ]
        resp = await self.llm.complete(msgs, temperature=0.4, max_tokens=4096)
        ctx.history.append(LLMMessage(role="user", content=user_input))
        ctx.history.append(LLMMessage(role="assistant", content=resp.content))
        return resp.content
