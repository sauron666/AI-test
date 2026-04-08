"""The orchestrator drives a full engagement phase-by-phase.

Core loop (ReAct-style) with senior-mindset guardrails:

    ┌──────────────────────────────────────────────────────────┐
    │  PLAN          →  sub-agent LLM                           │
    │  ACT           →  MCP tool call (budget-gated)            │
    │  OBSERVE       →  tool result (rabbit-hole scanner)       │
    │  VALIDATE      →  FindingValidator (FP firewall)          │
    │  CRITIQUE      →  CriticAgent second-pass (high/critical) │
    │  REFLECT       →  reflection LLM                          │
    │  BUDGET CHECK  →  PhaseBudget consume/exhaust             │
    │  (loop until phase done, budget exhausted, or max iters)  │
    └──────────────────────────────────────────────────────────┘

Every finding must pass the validator BEFORE entering ctx.findings;
every high/critical finding is additionally reviewed by the critic.
"""
from __future__ import annotations

import json
import re
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
from .critic_agent import CriticAgent
from .validator import get_validator

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


# Map the engagement profile to the validator category so FP rules
# are applied with the right lens.
PROFILE_TO_FP_CATEGORY: dict[str, str] = {
    "web_application":  "web",
    "api":              "api",
    "mobile":           "mobile",
    "infrastructure":   "network",
    "network":          "network",
    "active_directory": "active_directory",
    "llm_ai":           "llm_ai",
    "red_team":         "network",
}


# Finding candidates can arrive inline in an agent's thought via a
# fenced JSON block with a leading marker. We accept:
#
#   ```finding
#   { "title": "...", "severity": "high", ... }
#   ```
FINDING_BLOCK_RE = re.compile(
    r"```finding\s*\n(?P<body>\{.*?\})\s*\n```",
    re.DOTALL | re.IGNORECASE,
)


class Orchestrator:
    def __init__(self, mcp: SauronMCPServer | None = None):
        self.settings = get_settings()
        self.router = get_router()
        self.catalog = get_catalog()
        self.mcp = mcp or SauronMCPServer()
        self._system_prompt = self._load_system_prompt()
        self.validator = get_validator()

    # ── system prompt assembly ──────────────────────────────
    def _load_system_prompt(self) -> str:
        root = Path(self.settings.root_dir) / "config" / "prompts"
        base_path = root / "system.md"
        mindset_path = root / "senior_mindset.md"

        if base_path.exists():
            base = base_path.read_text(encoding="utf-8")
        else:
            base = "You are SAURON, an autonomous pentest operator."

        pieces = [base]
        if mindset_path.exists():
            pieces.append("\n\n# Senior Mindset (MANDATORY)\n")
            pieces.append(mindset_path.read_text(encoding="utf-8"))
        pieces.append("\n\n")
        pieces.append(self.catalog.summary_for_prompt())
        return "".join(pieces)

    # ── agent construction ──────────────────────────────────
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

    def _build_critic(self) -> CriticAgent:
        llm = self.router.for_role("parsing")
        return CriticAgent(llm=llm, system_prompt=self._system_prompt)

    # ── main entrypoint ─────────────────────────────────────
    async def run_engagement(self, ctx: AgentContext) -> list[AgentStep]:
        phases = PHASE_SEQUENCE.get(ctx.profile, ["recon", "scan", "exploit", "report"])
        steps: list[AgentStep] = []
        critic = self._build_critic()

        await ctx.emit({
            "type": "engagement.start",
            "engagement_id": ctx.engagement_id,
            "phases": phases,
            "profile": ctx.profile,
            "stealth": ctx.stealth_profile,
        })

        for phase in phases:
            budget = ctx.budget_for(phase)
            await ctx.emit({
                "type": "phase.start",
                "phase": phase,
                "budget": {"max_iters": budget.max_iterations, "max_seconds": budget.max_seconds},
            })
            agent = self._build_agent(phase)
            phase_steps = await self._run_phase(agent, critic, ctx, phase)
            steps.extend(phase_steps)

            # End-of-phase critic review — catches rabbit holes after the fact
            try:
                summary = self._phase_summary(ctx, phase)
                review = await critic.review_phase(ctx, phase, summary)
                steps.append(AgentStep(kind="reflection", content=review, meta={"phase": phase, "source": "critic.phase"}))
                await ctx.emit({"type": "phase.critic", "phase": phase, "content": review})
            except Exception as e:  # noqa: BLE001
                log.warning("critic phase review failed: %s", e)

            await ctx.emit({
                "type": "phase.complete",
                "phase": phase,
                "iters_used": budget.iterations_used,
                "exhausted": budget.exhausted,
            })
            if ctx.done:
                break

        await ctx.emit({
            "type": "engagement.complete",
            "findings": len(ctx.findings),
            "rejected": len(ctx.rejected_findings),
            "hypotheses": len(ctx.hypotheses),
        })
        return steps

    # ── per-phase loop ──────────────────────────────────────
    async def _run_phase(
        self,
        agent,
        critic: CriticAgent,
        ctx: AgentContext,
        phase: str,
    ) -> list[AgentStep]:
        steps: list[AgentStep] = []
        budget = ctx.budget_for(phase)
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
            if budget.exhausted:
                msg = f"Phase budget for '{phase}' exhausted — cutting over to next phase."
                steps.append(AgentStep(kind="reflection", content=msg, meta={"source": "budget"}))
                await ctx.emit({"type": "phase.budget_exhausted", "phase": phase})
                ctx.record_decision(f"cut phase {phase}", "phase budget exhausted")
                break

            ctx.iteration += 1
            budget.consume(1)

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

                # Extract any inline finding candidates and push them
                # through the validator + critic pipeline.
                await self._ingest_inline_findings(ctx, critic, phase, resp.content, steps)

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

            # ── rabbit-hole scanner on recent history ──────
            warnings = self.validator.detect_rabbit_hole(ctx.history_text())
            for w in warnings:
                note = f"RABBIT-HOLE WARNING: {w}"
                steps.append(AgentStep(kind="reflection", content=note, meta={"source": "rabbit_hole"}))
                await ctx.emit({"type": "agent.rabbit_hole", "phase": phase, "advice": w})
                ctx.record_decision("rabbit-hole detected", w)

            # ── light reflection loop ──────────────────────
            if self.settings.agent_reflection_enabled:
                reflection_llm = self.router.for_role("parsing")
                reflect_msgs = [
                    LLMMessage(
                        role="system",
                        content=(
                            "You are a senior pentest reviewer. In <=120 words, critique "
                            "the latest action: is it still on-hypothesis, is evidence "
                            "strong enough, is there a rabbit-hole risk, what should "
                            "happen next."
                        ),
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

    # ── finding pipeline ────────────────────────────────────
    async def _ingest_inline_findings(
        self,
        ctx: AgentContext,
        critic: CriticAgent,
        phase: str,
        text: str,
        steps: list[AgentStep],
    ) -> None:
        """Parse any ```finding blocks from the agent's thought and
        push them through the validator + critic pipeline."""
        category = PROFILE_TO_FP_CATEGORY.get(ctx.profile)
        for match in FINDING_BLOCK_RE.finditer(text or ""):
            body = match.group("body")
            try:
                candidate = json.loads(body)
            except json.JSONDecodeError as e:
                log.warning("invalid inline finding json: %s", e)
                continue
            await self._process_finding_candidate(ctx, critic, phase, candidate, steps, category)

    async def _process_finding_candidate(
        self,
        ctx: AgentContext,
        critic: CriticAgent,
        phase: str,
        candidate: dict[str, Any],
        steps: list[AgentStep],
        category: str | None,
    ) -> None:
        title = str(candidate.get("title", "")).strip() or "untitled"
        severity = str(candidate.get("severity", "info")).lower()
        sources = candidate.get("sources") or candidate.get("tools") or []
        if isinstance(sources, str):
            sources = [sources]
        evidence = candidate.get("evidence", "")
        if isinstance(evidence, (dict, list)):
            evidence_text = json.dumps(evidence)
        else:
            evidence_text = str(evidence)
        confirmed_by_poc = bool(candidate.get("poc") or candidate.get("confirmed_by_poc"))

        verdict = self.validator.validate(
            title=title,
            severity=severity,
            evidence_text=evidence_text,
            sources=list(sources),
            category=category,
            confirmed_by_poc=confirmed_by_poc,
        )

        enriched = {
            **candidate,
            "phase": phase,
            "validation": verdict.to_dict(),
            "severity": verdict.severity,
            "status": verdict.status,
        }

        if not verdict.accepted:
            reason = "; ".join(verdict.reasons) or "dropped by validator"
            ctx.reject_finding(enriched, reason)
            steps.append(AgentStep(
                kind="reflection",
                content=f"Finding REJECTED by validator: {title} — {reason}",
                meta={"source": "validator"},
            ))
            await ctx.emit({"type": "finding.rejected", "phase": phase, "finding": enriched, "reason": reason})
            return

        # Critic review for medium+ findings
        if verdict.severity in {"medium", "high", "critical"}:
            try:
                review = await critic.review_finding(ctx, enriched)
            except Exception as e:  # noqa: BLE001
                log.warning("critic review failed: %s", e)
                review = ""
            enriched["critic_review"] = review
            steps.append(AgentStep(kind="reflection", content=f"Critic review:\n{review}", meta={"source": "critic"}))
            await ctx.emit({"type": "finding.critic", "phase": phase, "review": review})

            # If the critic verdict says REJECT, move it to rejected
            if review and "VERDICT: REJECT" in review.upper():
                ctx.reject_finding(enriched, "rejected by critic")
                await ctx.emit({"type": "finding.rejected", "phase": phase, "finding": enriched, "reason": "critic REJECT"})
                return
            if review and "VERDICT: DEMOTE" in review.upper():
                enriched["status"] = "possible"
                enriched["severity"] = self._demote(enriched.get("severity", "medium"))

        ctx.add_finding(enriched)
        await ctx.emit({"type": "finding.accepted", "phase": phase, "finding": enriched})

    @staticmethod
    def _demote(severity: str) -> str:
        order = ["info", "low", "medium", "high", "critical"]
        if severity not in order:
            return "info"
        idx = max(0, order.index(severity) - 1)
        return order[idx]

    # ── phase summary for critic ────────────────────────────
    def _phase_summary(self, ctx: AgentContext, phase: str) -> str:
        """Compact textual summary used by the critic's end-of-phase
        review. Keeps the most recent history, current hypotheses,
        and any findings attributed to this phase."""
        parts: list[str] = []
        h = ctx.current_hypothesis()
        if h:
            parts.append(f"ACTIVE HYPOTHESIS: {h.statement} (iters_spent={h.iterations_spent})")
        phase_findings = [f for f in ctx.findings if f.get("phase") == phase]
        parts.append(f"Findings filed this phase: {len(phase_findings)}")
        for f in phase_findings[-5:]:
            parts.append(f"- [{f.get('severity')}] {f.get('title')} (status={f.get('status')})")
        rejected = [f for f in ctx.rejected_findings if f.get("phase") == phase]
        if rejected:
            parts.append(f"Rejected this phase: {len(rejected)}")
            for f in rejected[-3:]:
                parts.append(f"- REJECTED [{f.get('severity')}] {f.get('title')} — {f.get('rejected_reason','')}")
        parts.append("Recent history:")
        parts.append(ctx.history_text(limit=2500))
        return "\n".join(parts)

    # ── kickoff prompt ──────────────────────────────────────
    def _phase_kickoff_prompt(self, phase: str, ctx: AgentContext) -> str:
        budget = ctx.budget_for(phase)
        return (
            f"[PHASE: {phase.upper()}]\n"
            f"Engagement profile: {ctx.profile}\n"
            f"Scope: {json.dumps(ctx.scope)}\n"
            f"Rules of Engagement: {ctx.rules_of_engagement}\n"
            f"Stealth: {ctx.stealth_profile}\n"
            f"Phase budget: {budget.max_iterations} iterations / {budget.max_seconds}s\n\n"
            f"Before ANY tool call, emit your hypothesis in the form:\n"
            f"  HYPOTHESIS: ...\n  TEST: ...\n  EXPECTED: ...\n  DISPROOF: ...\n\n"
            f"When you produce a finding, emit it as a fenced JSON block "
            f"with the language tag 'finding' like this:\n\n"
            f"```finding\n"
            f'{{"title": "...", "severity": "medium", "sources": ["nmap","nuclei"], '
            f'"evidence": "...", "poc": false}}\n'
            f"```\n\n"
            f"Findings are run through the SAURON validator (FP filter "
            f"+ dual-source rule) and the CRITIC. Do NOT try to bypass "
            f"them by inflating severity.\n\n"
            f"When you believe the phase is complete, respond with no "
            f"tool calls and the text 'PHASE_COMPLETE: {phase}'."
        )
