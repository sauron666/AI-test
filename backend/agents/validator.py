"""Finding validator — the false-positive firewall.

Every finding the agent proposes to persist goes through this module
first. It does three things:

  1. Applies the YAML false-positive knowledge base — pattern match
     against the evidence, cap severity or downgrade.
  2. Enforces dual-source confirmation for HIGH/CRITICAL findings
     — at least two independent tools (or one tool + a manual PoC)
     must agree before the finding can reach `confirmed` status.
  3. Produces an "evidence quality" score so the report can show
     which findings the operator should double-check by hand.

This module is intentionally conservative. A senior pentester would
rather under-report than fabricate, and so does SAURON.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from ..settings import get_settings
from ..utils.logger import get_logger

log = get_logger("agents.validator")

SEV_ORDER = ["info", "low", "medium", "high", "critical"]


@dataclass
class FPRule:
    id: str
    category: str
    pattern: re.Pattern
    reason: str
    severity_cap: str | None = None
    downgrade_to: str | None = None


@dataclass
class ValidationResult:
    accepted: bool
    severity: str
    status: str                        # suspected | possible | confirmed | exploited
    quality_score: float               # 0.0 .. 1.0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fp_rules_hit: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "severity": self.severity,
            "status": self.status,
            "quality_score": round(self.quality_score, 2),
            "reasons": self.reasons,
            "warnings": self.warnings,
            "fp_rules_hit": self.fp_rules_hit,
        }


@lru_cache
def _load_rules() -> list[FPRule]:
    settings = get_settings()
    data = settings.load_yaml("knowledge/false_positives.yaml") or {}
    rules: list[FPRule] = []
    for category, items in data.items():
        if category == "rabbit_holes":
            continue
        for r in items or []:
            try:
                rules.append(
                    FPRule(
                        id=r["id"],
                        category=category,
                        pattern=re.compile(r["pattern"], re.IGNORECASE),
                        reason=r.get("reason", ""),
                        severity_cap=r.get("severity_cap"),
                        downgrade_to=r.get("downgrade_to"),
                    )
                )
            except re.error as e:
                log.warning("invalid FP regex %s: %s", r.get("id"), e)
    return rules


@lru_cache
def _load_rabbit_holes() -> list[dict[str, Any]]:
    data = get_settings().load_yaml("knowledge/false_positives.yaml") or {}
    return data.get("rabbit_holes", []) or []


def _cap_severity(current: str, cap: str) -> str:
    if SEV_ORDER.index(current) > SEV_ORDER.index(cap):
        return cap
    return current


class FindingValidator:
    """Single-shot validation of one finding candidate."""

    def __init__(self):
        self.rules = _load_rules()

    def validate(
        self,
        *,
        title: str,
        severity: str,
        evidence_text: str,
        sources: list[str],
        category: str | None = None,
        confirmed_by_poc: bool = False,
    ) -> ValidationResult:
        """Run the finding through every rule and gate.

        Parameters
        ----------
        title
            Short finding title.
        severity
            Proposed severity (info/low/medium/high/critical).
        evidence_text
            Concatenated stdout/stderr/body that the agent cites as proof.
        sources
            Names of the tools that produced this finding.
        category
            Optional category filter (web, network, api, ...).
        confirmed_by_poc
            Set True if the agent claims a successful, visible PoC.
        """
        severity = (severity or "info").lower()
        if severity not in SEV_ORDER:
            severity = "info"

        result = ValidationResult(
            accepted=True,
            severity=severity,
            status="suspected",
            quality_score=0.0,
            reasons=[],
        )

        # ── 1. pattern-based FP filter ──────────────────────
        for rule in self.rules:
            if category and rule.category != category:
                continue
            if rule.pattern.search(evidence_text or ""):
                result.fp_rules_hit.append(rule.id)
                result.warnings.append(f"FP rule hit: {rule.id} — {rule.reason}")
                if rule.downgrade_to:
                    result.severity = rule.downgrade_to
                elif rule.severity_cap:
                    result.severity = _cap_severity(result.severity, rule.severity_cap)

        # ── 2. dual-source confirmation gate ────────────────
        distinct_sources = {s for s in sources if s}
        if result.severity in {"high", "critical"}:
            if len(distinct_sources) >= 2 or confirmed_by_poc:
                result.status = "exploited" if confirmed_by_poc else "confirmed"
            else:
                result.reasons.append(
                    "single-source high/critical finding — demoted to 'possible' "
                    "until independently verified"
                )
                result.status = "possible"
                result.severity = _cap_severity(result.severity, "medium")
        elif result.severity == "medium":
            result.status = "confirmed" if len(distinct_sources) >= 2 or confirmed_by_poc else "possible"
        else:
            result.status = "suspected"

        # ── 3. evidence quality scoring ─────────────────────
        quality = 0.0
        if len(distinct_sources) >= 1:
            quality += 0.3
        if len(distinct_sources) >= 2:
            quality += 0.2
        if confirmed_by_poc:
            quality += 0.3
        if evidence_text and len(evidence_text) >= 200:
            quality += 0.1
        if not result.fp_rules_hit:
            quality += 0.1
        result.quality_score = min(1.0, quality)

        # ── 4. final accept decision ────────────────────────
        # Reject obviously low-quality info findings unless they're
        # tagged as confirmed via PoC — they just bloat the report.
        if result.severity == "info" and result.quality_score < 0.2 and not confirmed_by_poc:
            result.accepted = False
            result.reasons.append("dropped: info-level noise without evidence")

        return result

    # ── rabbit-hole detection ───────────────────────────────
    @staticmethod
    def detect_rabbit_hole(history_text: str) -> list[str]:
        """Scan recent agent history for known rabbit-hole signatures."""
        warnings: list[str] = []
        for rh in _load_rabbit_holes():
            trig = rh.get("trigger", "").lower()
            if "waf block" in trig and history_text.lower().count("waf") >= 5:
                warnings.append(rh.get("advice", ""))
            if "429" in trig and history_text.count("429") >= 3:
                warnings.append(rh.get("advice", ""))
            if "example.com" in trig and "example.com" in history_text.lower():
                warnings.append(rh.get("advice", ""))
        return warnings


_validator: FindingValidator | None = None


def get_validator() -> FindingValidator:
    global _validator
    if _validator is None:
        _validator = FindingValidator()
    return _validator
