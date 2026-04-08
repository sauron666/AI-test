"""Stealth profile helpers — applied transparently to tool invocations.

SAURON does NOT ship evasion payloads. These helpers only tune timing,
jitter, and user-agent rotation — defensive red-team realism, nothing
weaponised.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

from ..settings import get_settings


DEFAULT_UAS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


@dataclass
class StealthProfile:
    name: str
    scan_timing: str = "T3"
    jitter_ms: tuple[int, int] = (200, 1500)
    user_agent_rotation: bool = True
    randomise_source_port: bool = False
    max_parallel: int = 8


def load_profile(name: str | None = None) -> StealthProfile:
    settings = get_settings()
    cfg = settings.load_yaml("default.yaml").get("stealth", {})
    profile_name = name or cfg.get("default_profile", "normal")
    profiles = cfg.get("profiles", {})
    p = profiles.get(profile_name, {})
    jitter = p.get("jitter_ms", [200, 1500])
    return StealthProfile(
        name=profile_name,
        scan_timing=p.get("scan_timing", "T3"),
        jitter_ms=(int(jitter[0]), int(jitter[1])),
        user_agent_rotation=bool(p.get("user_agent_rotation", True)),
        randomise_source_port=bool(p.get("randomise_source_port", False)),
        max_parallel=int(p.get("max_parallel", 8)),
    )


async def apply_jitter(profile: StealthProfile) -> None:
    lo, hi = profile.jitter_ms
    if hi <= 0:
        return
    await asyncio.sleep(random.uniform(lo, hi) / 1000.0)


def pick_user_agent(profile: StealthProfile) -> str:
    if not profile.user_agent_rotation:
        return DEFAULT_UAS[0]
    return random.choice(DEFAULT_UAS)


def decorate_nmap(args: str, profile: StealthProfile) -> str:
    """Inject timing template and idle flags into an nmap command line."""
    extra: list[str] = []
    if f"-{profile.scan_timing}" not in args:
        extra.append(f"-{profile.scan_timing}")
    if profile.randomise_source_port and "--source-port" not in args:
        extra.append("--source-port 53")
    return (" ".join(extra) + " " + args).strip()
