"""Screenshot service.

Two modes:
  1. Xvfb + scrot: captures the virtual display used by GUI Kali tools.
  2. Synthetic: renders a terminal-style PNG of the command's stdout
     using Pillow — guarantees a visual even when no display is active.
"""
from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..settings import get_settings
from ..utils.logger import get_logger

log = get_logger("reporting.screenshot")


class ScreenshotService:
    def __init__(self):
        self.settings = get_settings()
        self.root = Path(self.settings.root_dir) / "screenshots"
        self.root.mkdir(parents=True, exist_ok=True)

    def synthetic_terminal(
        self,
        *,
        command: str,
        stdout: str,
        exit_code: int,
        engagement_id: str,
        tool: str = "shell",
    ) -> Path:
        """Render a cyberpunk terminal-style screenshot of a command run."""
        lines = [f"┌─[sauron@{tool}]─[{datetime.utcnow().strftime('%H:%M:%S')}]",
                 f"└─$ {command}",
                 ""]
        for raw_line in stdout.splitlines()[:60]:
            lines.extend(textwrap.wrap(raw_line, width=110) or [""])
        lines.append("")
        lines.append(f"[exit {exit_code}]")

        width = 1280
        line_h = 18
        height = max(720, line_h * (len(lines) + 4))
        img = Image.new("RGB", (width, height), (5, 8, 16))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
            bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 14)
        except Exception:
            font = ImageFont.load_default()
            bold = font

        # Title bar
        draw.rectangle([(0, 0), (width, 26)], fill=(18, 24, 38))
        draw.text((14, 6), "SAURON // terminal", fill=(255, 77, 77), font=bold)
        draw.text((width - 220, 6), datetime.utcnow().isoformat(timespec="seconds") + "Z", fill=(120, 180, 255), font=font)

        # Body
        y = 40
        for line in lines:
            color = (180, 255, 200) if line.startswith("└─$") else (200, 210, 230)
            if line.startswith("┌─"):
                color = (255, 170, 80)
            if line.startswith("[exit"):
                color = (255, 120, 120) if exit_code else (120, 255, 160)
            draw.text((18, y), line, fill=color, font=font)
            y += line_h
            if y > height - 40:
                break

        # Eye-of-Sauron watermark
        draw.text((width - 240, height - 28), "👁 saw this", fill=(120, 60, 60), font=font)

        out_dir = self.root / engagement_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}_{tool}.png"
        img.save(path, format="PNG")
        log.debug("synthetic screenshot → %s", path)
        return path
