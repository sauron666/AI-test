"""Shell executor with sandboxing, logging, screenshots & PTY recording.

The executor is the ONLY place where commands actually run on the host.
It is designed to be audited: every invocation produces
  - stdout file
  - stderr file
  - exit code
  - duration
  - optional asciinema PTY recording
  - optional terminal screenshot (via scrot/imagemagick under Xvfb)
All artifacts live under ./artifacts/<engagement_id>/<command_id>/.
"""
from __future__ import annotations

import asyncio
import os
import shlex
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..settings import get_settings
from ..utils.logger import get_logger
from ..utils.security import is_command_banned

log = get_logger("tools.executor")


@dataclass
class CommandResult:
    id: str
    command: str
    tool: str
    exit_code: int
    stdout: str
    stderr: str
    stdout_path: str
    stderr_path: str
    screenshot_path: str = ""
    pty_record_path: str = ""
    duration_ms: int = 0
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "tool": self.tool,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:20000],
            "stderr": self.stderr[:5000],
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "screenshot_path": self.screenshot_path,
            "pty_record_path": self.pty_record_path,
            "duration_ms": self.duration_ms,
        }


class ShellExecutor:
    """Async command runner with artifact capture."""

    def __init__(self):
        self.settings = get_settings()
        self._base = Path(self.settings.root_dir) / "artifacts"
        self._base.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        command: str,
        *,
        tool: str = "shell",
        engagement_id: str = "adhoc",
        timeout: int | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_screenshot: bool | None = None,
        record_pty: bool | None = None,
    ) -> CommandResult:
        if is_command_banned(command):
            log.warning("Refusing banned command: %s", command)
            return CommandResult(
                id=str(uuid.uuid4()),
                command=command,
                tool=tool,
                exit_code=126,
                stdout="",
                stderr="SAURON executor refused a destructive/banned command pattern.",
                stdout_path="",
                stderr_path="",
            )

        cmd_id = str(uuid.uuid4())
        artifact_dir = self._base / engagement_id / cmd_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = artifact_dir / "stdout.log"
        stderr_path = artifact_dir / "stderr.log"
        screenshot_path = artifact_dir / "screenshot.png"
        pty_path = artifact_dir / "session.cast"

        effective_timeout = timeout or self.settings.executor_timeout_seconds
        take_shot = (
            capture_screenshot
            if capture_screenshot is not None
            else self.settings.executor_screenshots
        )
        do_record = record_pty if record_pty is not None else self.settings.executor_record_pty

        log.info("exec[%s] %s", tool, command)
        started = time.time()

        # Build the effective command. If PTY recording is enabled and
        # asciinema is installed we wrap the command in `asciinema rec`.
        if do_record and _which("asciinema"):
            recorded_cmd = (
                f"asciinema rec -q --overwrite -c {shlex.quote(command)} "
                f"{shlex.quote(str(pty_path))}"
            )
            run_cmd = recorded_cmd
        else:
            run_cmd = command
            pty_path = Path()

        proc = await asyncio.create_subprocess_shell(
            run_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or self.settings.executor_workdir,
            env={**os.environ, **(env or {})},
        )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=effective_timeout)
            exit_code = proc.returncode or 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            stdout_b, stderr_b = b"", f"TIMEOUT after {effective_timeout}s".encode()
            exit_code = 124

        duration_ms = int((time.time() - started) * 1000)
        stdout_path.write_bytes(stdout_b)
        stderr_path.write_bytes(stderr_b)

        if take_shot and _which("scrot"):
            await self._take_screenshot(screenshot_path)

        return CommandResult(
            id=cmd_id,
            command=command,
            tool=tool,
            exit_code=exit_code,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            screenshot_path=str(screenshot_path) if screenshot_path.exists() else "",
            pty_record_path=str(pty_path) if pty_path and pty_path.exists() else "",
            duration_ms=duration_ms,
            started_at=started,
        )

    async def _take_screenshot(self, path: Path) -> None:
        """Capture the virtual display (Xvfb) using scrot."""
        try:
            proc = await asyncio.create_subprocess_shell(
                f"scrot -o {shlex.quote(str(path))}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
        except Exception as e:
            log.debug("screenshot failed: %s", e)


def _which(binary: str) -> bool:
    from shutil import which
    return which(binary) is not None


_executor: ShellExecutor | None = None


def get_executor() -> ShellExecutor:
    global _executor
    if _executor is None:
        _executor = ShellExecutor()
    return _executor
