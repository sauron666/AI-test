#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  SAURON start — boots the stack.
#  Single process by default (FastAPI + MCP + static UI on :8000).
#  Pass --split to run the MCP server in its own process.
# ══════════════════════════════════════════════════════════════════
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a; source .env; set +a
fi

# Activate venv if present
if [ -d .venv ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Start a virtual display so GUI Kali tools work inside Docker/headless hosts
if ! pgrep -x Xvfb >/dev/null 2>&1; then
  if command -v Xvfb >/dev/null 2>&1; then
    Xvfb :99 -screen 0 1920x1080x24 +extension RANDR &
    export DISPLAY=:99
    sleep 0.4
  fi
fi

# Optionally start ollama daemon
if command -v ollama >/dev/null 2>&1; then
  if ! pgrep -x ollama >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama.log 2>&1 &
    sleep 1
  fi
fi

echo "👁  SAURON is opening its eye on :${SAURON_PORT:-8000} …"

exec python -m backend.main
