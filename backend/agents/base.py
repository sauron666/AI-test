"""Base agent scaffolding."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..llm.base import BaseLLMProvider, LLMMessage


BroadcastFn = Callable[[dict[str, Any]], Awaitable[None]]


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

    async def emit(self, event: dict[str, Any]) -> None:
        if self.broadcast:
            await self.broadcast(event)

    def add_finding(self, finding: dict[str, Any]) -> None:
        self.findings.append(finding)


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
