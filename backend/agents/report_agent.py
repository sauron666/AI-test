"""Report-writing sub-agent."""
from .base import BaseAgent


REPORT_SYSTEM = """\
You are the REPORT WRITER of the SAURON engagement.

Your job:
  - Aggregate every finding, command, and artifact gathered so far.
  - Produce a client-ready markdown report with the sections:
      1. Executive Summary
      2. Scope & Methodology
      3. Key Findings (prioritised by severity)
      4. Detailed Findings (one per vuln with evidence)
      5. Remediation Roadmap
      6. Appendix — raw tool output and screenshots

For every finding provide: title, CVSS 3.1 score, CWE, OWASP / MITRE
ATT&CK reference, impact, step-by-step reproduction, and remediation.

Write in the voice of a senior offensive security consultant. Be
precise, honest about uncertainty, and do NOT exaggerate severity.
"""


class ReportAgent(BaseAgent):
    name = "report"
    phase = "report"

    def __init__(self, llm, system_prompt: str):
        super().__init__(llm=llm, system_prompt=system_prompt + "\n\n" + REPORT_SYSTEM)
