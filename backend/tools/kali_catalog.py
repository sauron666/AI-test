"""Kali tool catalog — loaded from config/kali_tools.yaml.

The catalog is the single source of truth for every wrapper SAURON can
execute.  It is consumed by:
  - the MCP server (exposes each tool as an MCP tool)
  - the agent orchestrator (injects descriptions into the system prompt)
  - the frontend (renders a searchable tool browser)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from ..settings import get_settings


@dataclass
class ToolSpec:
    name: str
    cmd: str
    category: str
    domain: str
    desc: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cmd": self.cmd,
            "category": self.category,
            "domain": self.domain,
            "desc": self.desc,
            "notes": self.notes,
        }

    def to_mcp_schema(self) -> dict[str, Any]:
        """Return a JSON schema describing this tool as an MCP function."""
        return {
            "name": f"kali_{self.name}",
            "description": (
                f"{self.desc or self.name} "
                f"(category={self.category}, domain={self.domain})"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "string",
                        "description": f"Arguments passed to `{self.cmd}`.",
                    },
                    "target": {
                        "type": "string",
                        "description": "Primary target (URL, IP, CIDR, domain…).",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 900).",
                    },
                },
                "required": ["args"],
            },
        }


class KaliToolCatalog:
    def __init__(self):
        self.settings = get_settings()
        self._tools: dict[str, ToolSpec] = {}
        self._load()

    def _load(self) -> None:
        data = self.settings.load_yaml("kali_tools.yaml")
        for domain, tools in data.items():
            for entry in tools or []:
                spec = ToolSpec(
                    name=entry["name"],
                    cmd=entry.get("cmd", entry["name"]),
                    category=entry.get("category", "misc"),
                    domain=domain,
                    desc=entry.get("desc", ""),
                    notes=entry.get("notes", ""),
                )
                self._tools[spec.name] = spec

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def by_domain(self, domain: str) -> list[ToolSpec]:
        return [t for t in self._tools.values() if t.domain == domain]

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def as_mcp_tools(self) -> list[dict[str, Any]]:
        return [t.to_mcp_schema() for t in self._tools.values()]

    def summary_for_prompt(self) -> str:
        """Human-readable summary injected into the agent's system prompt."""
        lines = ["# Available Kali Tools"]
        by_domain: dict[str, list[ToolSpec]] = {}
        for t in self._tools.values():
            by_domain.setdefault(t.domain, []).append(t)
        for domain, tools in sorted(by_domain.items()):
            lines.append(f"\n## {domain}")
            for t in tools:
                lines.append(f"- **{t.name}** (`{t.cmd}`) — {t.desc or t.category}")
        return "\n".join(lines)


@lru_cache
def get_catalog() -> KaliToolCatalog:
    return KaliToolCatalog()
