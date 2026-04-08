#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  SAURON installer — bootstraps Python venv + system dependencies.
#  Run on Kali / Debian / Ubuntu. For Docker, use `docker compose up`.
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

BOLD=$(tput bold 2>/dev/null || true); RED=$(tput setaf 1 2>/dev/null || true); RESET=$(tput sgr0 2>/dev/null || true)

banner() {
  cat <<'EOF'
  ███████╗ █████╗ ██╗   ██╗██████╗  ██████╗ ███╗   ██╗
  ██╔════╝██╔══██╗██║   ██║██╔══██╗██╔═══██╗████╗  ██║
  ███████╗███████║██║   ██║██████╔╝██║   ██║██╔██╗ ██║
  ╚════██║██╔══██║██║   ██║██╔══██╗██║   ██║██║╚██╗██║
  ███████║██║  ██║╚██████╔╝██║  ██║╚██████╔╝██║ ╚████║
  ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
EOF
}

banner
echo "${BOLD}${RED}Installing SAURON…${RESET}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 1. OS packages --------------------------------------------------
if command -v apt-get >/dev/null 2>&1; then
  echo "[*] installing system packages (python, xvfb, scrot, imagemagick)…"
  sudo apt-get update -y
  sudo apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip \
      xvfb scrot imagemagick \
      build-essential libssl-dev libffi-dev \
      curl wget git
fi

# 2. Python venv --------------------------------------------------
if [ ! -d .venv ]; then
  echo "[*] creating python venv…"
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt

# 3. .env ---------------------------------------------------------
if [ ! -f .env ]; then
  echo "[*] copying .env.example → .env (remember to fill in API keys!)"
  cp .env.example .env
fi

# 4. runtime dirs -------------------------------------------------
mkdir -p data logs reports/output screenshots artifacts sessions

# 5. success ------------------------------------------------------
cat <<EOF

${BOLD}${RED}SAURON installed.${RESET}

Next steps:
  1. edit ${BOLD}.env${RESET} and add at least one LLM provider key
  2. (optional) ./scripts/setup_ollama.sh    # for WhiteRabbitNeo
  3. ./scripts/start.sh                      # launch the platform

The Eye is ready.
EOF
