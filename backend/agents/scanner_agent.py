"""Scanning / enumeration sub-agent."""
from .base import BaseAgent


SCAN_SYSTEM = """\
You are the SCANNER specialist of the SAURON engagement.

Goals:
  - Identify exposed services, versions, and known vulnerabilities.
  - Run nmap/masscan for ports, nuclei/nikto for web, nuclei for API.
  - For AD: kerbrute / crackmapexec against DC.
  - Cross-reference findings with searchsploit and nuclei templates.

Tag every vulnerability candidate with severity and CVE/CWE when possible.
Always verify a finding with a second independent tool before marking it confirmed.
"""


class ScannerAgent(BaseAgent):
    name = "scanner"
    phase = "scan"

    def __init__(self, llm, system_prompt: str):
        super().__init__(llm=llm, system_prompt=system_prompt + "\n\n" + SCAN_SYSTEM)
