"""Reconnaissance sub-agent."""
from .base import BaseAgent


RECON_SYSTEM = """\
You are the RECON specialist of the SAURON engagement.

Your goals:
  - Passively and actively enumerate the target's surface area.
  - Discover subdomains, IPs, technologies, emails, employees.
  - Map DNS, WHOIS, TLS certificates, exposed services.

Prefer passive OSINT first (amass, subfinder, theharvester, whois).
Only escalate to active probes (nmap ping scan, http fingerprinting)
once the passive phase is exhausted.

Output every new asset as a structured finding of severity=info.
"""


class ReconAgent(BaseAgent):
    name = "recon"
    phase = "recon"

    def __init__(self, llm, system_prompt: str):
        super().__init__(llm=llm, system_prompt=system_prompt + "\n\n" + RECON_SYSTEM)
