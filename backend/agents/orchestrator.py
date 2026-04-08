"""The orchestrator drives a full engagement phase-by-phase.

Core loop (ReAct-style):
    ┌───────────────────────────────────────────────┐
    │  PLAN          →  AGENT (planning LLM)        │
    │  ACT           →  MCP tool call               │
    │  OBSERVE       →  tool result                 │
    │  REFLECT       →  AGENT (reflection LLM)      │
    │  (loop until phase done or max_iterations)    │
    └───────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..llm import get_router
from ..llm.base import LLMMessage
from ..mcp.server import SauronMCPServer
from ..settings import get_settings
from ..tools import get_catalog
from ..utils.logger import get_logger
from .base import AgentContext, AgentStep
from .recon_agent import ReconAgent
from .scanner_agent import ScannerAgent
from .exploit_agent import ExploitAgent
from .post_exploit_agent import PostExploitAgent
from .red_team_agent import RedTeamAgent
from .report_agent import ReportAgent

log = get_logger("agents.orchestrator")


PHASE_SEQUENCE: dict[str, list[str]] = {
    "web_application": ["recon", "scan", "exploit", "post_exploit", "report"],
    "api":             ["recon", "scan", "exploit", "report"],
    "mobile":          ["recon", "scan", "exploit", "report"],
    "infrastructure":  ["recon", "scan", "exploit", "post_exploit", "report"],
    "network":         ["recon", "scan", "exploit", "post_exploit", "report"],
    "active_directory":["recon", "scan", "exploit", "post_exploit", "report"],
    "llm_ai":          ["recon", "scan", "exploit", "report"],
    "red_team":        ["recon", "red_team", "post_exploit", "report"],
}


class Orchestrator:
    def __init__(self, mcp: SauronMCPServer | None = None):
        self.settings = get_settings()
        self.router = get_router()
        self.catalog = get_catalog()
        self.mcp = mcp or SauronMCPServer()
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        path = Path(self.settings.root_dir) / "config" / "prompts" / "system.md"
        if path.exists():
            base = path.read_text(encoding="utf-8")
        else:
            base = "You are SAURON, an autonomous pentest operator."
        return base + "\n\n" + self.catalog.summary_for_prompt()

    def _build_agent(self, phase: str):
        llm = self.router.for_role("planning" if phase in {"recon", "red_team"} else "execution")
        mapping = {
            "recon":        ReconAgent,
            "scan":         ScannerAgent,
            "exploit":      ExploitAgent,
            "post_exploit": PostExploitAgent,
            "red_team":     RedTeamAgent,
            "report":       ReportAgent,
        }
        cls = mapping.get(phase, ReconAgent)
        return cls(llm=llm, system_prompt=self._system_prompt)

    async def run_engagement(self, ctx: AgentContext) -> list[AgentStep]:
        phases = PHASE_SEQUENCE.get(ctx.profile, ["recon", "scan", "exploit", "report"])
        steps: list[AgentStep] = []
        await ctx.emit({
            "type": "engagement.start",
            "engagement_id": ctx.engagement_id,
            "phases": phases,
        })

        for phase in phases:
            await ctx.emit({"type": "phase.start", "phase": phase})
            agent = self._build_agent(phase)
            phase_steps = await self._run_phase(agent, ctx, phase)
            steps.extend(phase_steps)
            await ctx.emit({"type": "phase.complete", "phase": phase})
            if ctx.done:
                break

        await ctx.emit({"type": "engagement.complete", "findings": len(ctx.findings)})
        return steps

    async def _run_phase(self, agent, ctx: AgentContext, phase: str) -> list[AgentStep]:
        steps: list[AgentStep] = []
        tools_schema = [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            }
            for t in self.mcp.list_tools()
        ]

        user_kickoff = self._phase_kickoff_prompt(phase, ctx)
        ctx.history.append(LLMMessage(role="user", content=user_kickoff))

        for i in range(ctx.max_iterations):
            ctx.iteration += 1
            msgs = [LLMMessage(role="system", content=self._system_prompt), *ctx.history]
            try:
                resp = await agent.llm.complete(msgs, tools=tools_schema, temperature=0.5, max_tokens=4096)
            except Exception as e:
                log.exception("LLM error")
                await ctx.emit({"type": "agent.error", "error": str(e)})
                steps.append(AgentStep(kind="error", content=str(e)))
                break

            if resp.content:
                steps.append(AgentStep(kind="thought", content=resp.content))
                await ctx.emit({"type": "agent.thought", "phase": phase, "content": resp.content})
                ctx.history.append(LLMMessage(role="assistant", content=resp.content))

            if not resp.tool_calls:
                # Phase finished from the LLM's perspective
                break

            for call in resp.tool_calls:
                tool_name = call.get("name", "")
                tool_args = call.get("arguments", {}) or {}
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {"args": tool_args}
                tool_args.setdefault("engagement_id", ctx.engagement_id)

                await ctx.emit({
                    "type": "agent.action",
                    "phase": phase,
                    "tool": tool_name,
                    "arguments": tool_args,
                })

                if not self.settings.agent_auto_approve_commands:
                    # Hook point — real UI gating lives in the websocket layer.
                    pass

                result = await self.mcp.call_tool(tool_name, tool_args)
                obs = json.dumps(result)[:8000]
                steps.append(AgentStep(kind="observation", content=obs, meta={"tool": tool_name}))
                await ctx.emit({"type": "agent.observation", "phase": phase, "tool": tool_name, "result": result})

                ctx.history.append(LLMMessage(
                    role="tool",
                    content=obs,
                    tool_call_id=call.get("id", ""),
                    name=tool_name,
                ))

            if self.settings.agent_reflection_enabled:
                reflection_llm = self.router.for_role("parsing")
                reflect_msgs = [
                    LLMMessage(
                        role="system",
                        content="You are a senior pentest reviewer. Critique the latest action briefly (<=120 words).",
                    ),
                    *ctx.history[-6:],
                ]
                try:
                    r = await reflection_llm.complete(reflect_msgs, temperature=0.2, max_tokens=400)
                    if r.content:
                        steps.append(AgentStep(kind="reflection", content=r.content))
                        await ctx.emit({"type": "agent.reflection", "phase": phase, "content": r.content})
                except Exception:
                    pass

        return steps

    def _phase_kickoff_prompt(self, phase: str, ctx: AgentContext) -> str:
        return (
            f"[PHASE: {phase.upper()}]\n"
            f"Engagement profile: {ctx.profile}\n"
            f"Scope: {json.dumps(ctx.scope)}\n"
            f"Rules of Engagement: {ctx.rules_of_engagement}\n"
            f"Stealth: {ctx.stealth_profile}\n\n"
            f"Execute the {phase} phase thoroughly. When you believe "
            f"this phase is complete, respond with no tool calls and "
            f"the text 'PHASE_COMPLETE: {phase}'."
        )
