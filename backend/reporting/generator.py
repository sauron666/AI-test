"""Markdown → HTML → PDF report generator."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import markdown as md

from ..database.models import CommandRun, Engagement, Finding
from ..database.session import db_session
from ..settings import get_settings
from ..utils.logger import get_logger

log = get_logger("reporting.generator")


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class ReportGenerator:
    def __init__(self):
        self.settings = get_settings()
        self.output_dir = Path(self.settings.report_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, engagement_id: str) -> Path:
        with db_session() as s:
            eng: Engagement | None = s.query(Engagement).filter_by(id=engagement_id).first()
            if not eng:
                raise ValueError(f"engagement not found: {engagement_id}")
            findings: list[Finding] = sorted(
                eng.findings, key=lambda f: SEVERITY_ORDER.get(f.severity.lower(), 99)
            )
            commands: list[CommandRun] = list(eng.commands)

            md_text = self._render_markdown(eng, findings, commands)

        out_dir = self.output_dir / engagement_id
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / "report.md"
        md_path.write_text(md_text, encoding="utf-8")
        log.info("report markdown → %s", md_path)
        return md_path

    def generate_html(self, engagement_id: str) -> Path:
        md_path = self.generate_markdown(engagement_id)
        html_body = md.markdown(
            md_path.read_text(encoding="utf-8"),
            extensions=["fenced_code", "tables", "toc", "attr_list"],
        )
        html_doc = _HTML_TEMPLATE.format(
            title=f"SAURON Report — {engagement_id}",
            company=self.settings.report_company_name,
            body=html_body,
            year=datetime.utcnow().year,
        )
        html_path = md_path.with_suffix(".html")
        html_path.write_text(html_doc, encoding="utf-8")
        log.info("report html → %s", html_path)
        return html_path

    def generate_pdf(self, engagement_id: str) -> Path | None:
        try:
            from weasyprint import HTML
        except Exception as e:
            log.warning("weasyprint unavailable: %s", e)
            return None
        html_path = self.generate_html(engagement_id)
        pdf_path = html_path.with_suffix(".pdf")
        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        log.info("report pdf → %s", pdf_path)
        return pdf_path

    # ── internal rendering ────────────────────────
    def _render_markdown(
        self,
        eng: Engagement,
        findings: list[Finding],
        commands: list[CommandRun],
    ) -> str:
        parts: list[str] = []
        parts.append(f"# SAURON Penetration Test Report")
        parts.append("")
        parts.append(f"**Engagement:** `{eng.name}`  ")
        parts.append(f"**Profile:** `{eng.profile}`  ")
        parts.append(f"**Date:** {datetime.utcnow().strftime('%Y-%m-%d')}  ")
        parts.append(f"**Delivered by:** {self.settings.report_company_name}  ")
        parts.append(f"**Engine:** SAURON v{eng.llm_model or 'multi-LLM'}  ")
        parts.append("")
        parts.append("---")
        parts.append("")

        # Executive Summary
        parts.append("## 1. Executive Summary")
        parts.append("")
        summary = self._severity_summary(findings)
        parts.append(summary)
        parts.append("")

        # Scope
        parts.append("## 2. Scope & Methodology")
        parts.append("")
        parts.append("```json")
        import json as _json
        parts.append(_json.dumps(eng.scope, indent=2))
        parts.append("```")
        parts.append("")
        if eng.rules_of_engagement:
            parts.append(f"**Rules of Engagement:** {eng.rules_of_engagement}")
            parts.append("")

        # Key findings
        parts.append("## 3. Key Findings")
        parts.append("")
        parts.append("| # | Severity | CVSS | Title |")
        parts.append("|---|---|---|---|")
        for i, f in enumerate(findings, 1):
            parts.append(f"| {i} | **{f.severity.upper()}** | {f.cvss:.1f} | {f.title} |")
        parts.append("")

        # Detailed findings
        parts.append("## 4. Detailed Findings")
        parts.append("")
        for i, f in enumerate(findings, 1):
            parts.append(f"### 4.{i} {f.title}")
            parts.append("")
            parts.append(f"- **Severity:** `{f.severity.upper()}`")
            parts.append(f"- **CVSS 3.1:** `{f.cvss:.1f}`")
            if f.cwe:
                parts.append(f"- **CWE:** `{f.cwe}`")
            if f.owasp:
                parts.append(f"- **OWASP:** `{f.owasp}`")
            if f.mitre_attack:
                parts.append(f"- **MITRE ATT&CK:** `{f.mitre_attack}`")
            parts.append(f"- **Confirmed:** {'yes' if f.confirmed else 'suspected'}")
            parts.append("")
            if f.summary:
                parts.append(f"**Summary:** {f.summary}")
                parts.append("")
            if f.description:
                parts.append("**Description**")
                parts.append("")
                parts.append(f.description)
                parts.append("")
            if f.impact:
                parts.append("**Impact**")
                parts.append("")
                parts.append(f.impact)
                parts.append("")
            if f.remediation:
                parts.append("**Remediation**")
                parts.append("")
                parts.append(f.remediation)
                parts.append("")
            if f.evidence:
                parts.append("**Evidence**")
                parts.append("")
                parts.append("```")
                parts.append(_json.dumps(f.evidence, indent=2)[:4000])
                parts.append("```")
                parts.append("")

        # Appendix
        parts.append("## 5. Appendix — Command Log")
        parts.append("")
        for c in commands[:200]:
            parts.append(f"### `{c.tool}` @ {c.started_at}")
            parts.append("")
            parts.append(f"```bash")
            parts.append(c.command)
            parts.append("```")
            parts.append(f"exit={c.exit_code} · {c.duration_ms} ms")
            if c.screenshot_path:
                parts.append("")
                parts.append(f"![screenshot]({c.screenshot_path})")
            parts.append("")

        parts.append("---")
        parts.append("")
        parts.append("_This report was produced by SAURON — the All-Seeing AI for Autonomous Penetration Testing._")
        return "\n".join(parts)

    def _severity_summary(self, findings: list[Finding]) -> str:
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity.lower()] = counts.get(f.severity.lower(), 0) + 1
        lines = ["| Severity | Count |", "|---|---|"]
        for level in ["critical", "high", "medium", "low", "info"]:
            lines.append(f"| {level.title()} | {counts.get(level, 0)} |")
        return "\n".join(lines)


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  @page {{ size: A4; margin: 22mm 18mm; }}
  body {{ font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; color: #111; line-height: 1.5; }}
  h1, h2, h3, h4 {{ color: #0b0d12; font-weight: 700; }}
  h1 {{ border-bottom: 3px solid #ff3b3b; padding-bottom: 8px; }}
  h2 {{ border-bottom: 1px solid #e1e4eb; padding-bottom: 4px; margin-top: 28px; }}
  code, pre {{ font-family: 'JetBrains Mono', 'Menlo', monospace; }}
  pre {{ background: #0d1117; color: #d1d9e1; padding: 14px; border-radius: 8px; overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  th, td {{ border: 1px solid #d6dae3; padding: 6px 10px; text-align: left; font-size: 13px; }}
  th {{ background: #f3f5f9; }}
  .brand {{ color: #ff3b3b; font-weight: 700; letter-spacing: 1px; }}
  footer {{ margin-top: 40px; font-size: 11px; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 8px; }}
</style>
</head>
<body>
  <div><span class="brand">SAURON</span> · {company}</div>
  {body}
  <footer>© {year} {company} · Confidential · Generated by SAURON</footer>
</body>
</html>
"""
