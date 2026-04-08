#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  SAURON start — boots the stack.
#
#  Single process by default (FastAPI + MCP + static UI on :8000).
#  If the venv is missing or dependencies are broken, we abort with
#  a clear hint instead of crashing on `import uvicorn`.
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ── colours ──────────────────────────────────────────
if [ -t 1 ]; then
  RED=$(tput setaf 1 2>/dev/null || true)
  GRN=$(tput setaf 2 2>/dev/null || true)
  YEL=$(tput setaf 3 2>/dev/null || true)
  CYN=$(tput setaf 6 2>/dev/null || true)
  RST=$(tput sgr0 2>/dev/null || true)
else
  RED=""; GRN=""; YEL=""; CYN=""; RST=""
fi
log()  { printf "%s[*]%s %s\n" "$CYN" "$RST" "$*"; }
ok()   { printf "%s[✓]%s %s\n" "$GRN" "$RST" "$*"; }
warn() { printf "%s[!]%s %s\n" "$YEL" "$RST" "$*"; }
err()  { printf "%s[x]%s %s\n" "$RED" "$RST" "$*" >&2; }
die()  { err "$*"; exit 1; }

# ── .env ─────────────────────────────────────────────
if [ -f .env ]; then
  set -a; source .env; set +a
fi

# ── venv ─────────────────────────────────────────────
if [ ! -d .venv ]; then
  err "no virtualenv found at .venv"
  cat <<EOT
This host has not been installed yet. Run:

    ./scripts/install.sh

(or pass --with-kali-tools / --with-ollama if needed)
EOT
  exit 1
fi

if [ -z "${VIRTUAL_ENV:-}" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# ── dependency health check ──────────────────────────
if ! python -c "import uvicorn, fastapi, pydantic" 2>/dev/null; then
  err "core Python dependencies are missing in the venv"
  cat <<EOT
The venv exists but 'uvicorn', 'fastapi', or 'pydantic' cannot be
imported. The previous install almost certainly failed.

Try:

    ./scripts/install.sh --recreate-venv

If you see a Pillow / PyYAML / psutil build error, your Python
interpreter is newer than the pinned wheels. The fresh
requirements.txt uses version floors (>=) so re-running the
installer should fix it automatically.
EOT
  exit 1
fi
ok "venv healthy: $(python -V)"

# ── Xvfb for GUI Kali tools / screenshots ────────────
if ! pgrep -x Xvfb >/dev/null 2>&1; then
  if command -v Xvfb >/dev/null 2>&1; then
    log "starting Xvfb on :99…"
    Xvfb :99 -screen 0 1920x1080x24 +extension RANDR >/tmp/xvfb.log 2>&1 &
    export DISPLAY=:99
    sleep 0.4
  else
    warn "Xvfb not installed — screenshot capture will be disabled"
  fi
fi

# ── Ollama daemon (optional) ─────────────────────────
if command -v ollama >/dev/null 2>&1; then
  if ! pgrep -x ollama >/dev/null 2>&1; then
    log "starting ollama daemon in background…"
    nohup ollama serve >/tmp/ollama.log 2>&1 &
    sleep 1
  fi
fi

# ── runtime dirs (idempotent) ────────────────────────
mkdir -p data logs reports/output screenshots artifacts sessions \
         runtime/workdir runtime/screenshots runtime/recordings runtime/reports

# ── launch ───────────────────────────────────────────
PORT="${SAURON_PORT:-8000}"
HOST="${SAURON_HOST:-0.0.0.0}"
echo "👁  SAURON is opening its eye on ${HOST}:${PORT} …"

exec python -m backend.main
