#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  SAURON installer — bootstraps Python venv + system dependencies.
#
#  Supports: Kali / Debian / Ubuntu / any distro with apt or dnf.
#  Works with Python 3.11, 3.12, 3.13. Idempotent and re-runnable.
#
#  Flags:
#    --no-system           Skip all apt/dnf system package steps
#    --no-optional         Skip weasyprint / asciinema (minimal mode)
#    --with-kali-tools     Also install the full Kali offensive stack
#    --with-ollama         Also install ollama + pull WhiteRabbitNeo
#    --venv <path>         Use a custom venv path (default: .venv)
#    --python <bin>        Force a specific python interpreter
#    --recreate-venv       Wipe and recreate .venv
#    -h | --help           Show this help
#
#  Examples:
#    ./scripts/install.sh                         # minimal, safe, automated
#    ./scripts/install.sh --with-kali-tools       # + nmap/nuclei/sqlmap/...
#    ./scripts/install.sh --with-ollama           # + local offline brain
#    ./scripts/install.sh --no-system --no-optional  # already-set-up host
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

# ── colours ──────────────────────────────────────────
if [ -t 1 ]; then
  BOLD=$(tput bold 2>/dev/null || true)
  RED=$(tput setaf 1 2>/dev/null || true)
  GRN=$(tput setaf 2 2>/dev/null || true)
  YEL=$(tput setaf 3 2>/dev/null || true)
  CYN=$(tput setaf 6 2>/dev/null || true)
  RST=$(tput sgr0 2>/dev/null || true)
else
  BOLD=""; RED=""; GRN=""; YEL=""; CYN=""; RST=""
fi

log()  { printf "%s[*]%s %s\n" "$CYN" "$RST" "$*"; }
ok()   { printf "%s[✓]%s %s\n" "$GRN" "$RST" "$*"; }
warn() { printf "%s[!]%s %s\n" "$YEL" "$RST" "$*"; }
err()  { printf "%s[x]%s %s\n" "$RED" "$RST" "$*" >&2; }
die()  { err "$*"; exit 1; }

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

usage() { sed -n '2,25p' "$0"; exit 0; }

# ── defaults ─────────────────────────────────────────
DO_SYSTEM=1
DO_OPTIONAL=1
DO_KALI_TOOLS=0
DO_OLLAMA=0
VENV_DIR=".venv"
PYTHON_BIN=""
RECREATE_VENV=0

while [ $# -gt 0 ]; do
  case "$1" in
    --no-system)        DO_SYSTEM=0 ;;
    --no-optional)      DO_OPTIONAL=0 ;;
    --with-kali-tools)  DO_KALI_TOOLS=1 ;;
    --with-ollama)      DO_OLLAMA=1 ;;
    --venv)             shift; VENV_DIR="$1" ;;
    --python)           shift; PYTHON_BIN="$1" ;;
    --recreate-venv)    RECREATE_VENV=1 ;;
    -h|--help)          usage ;;
    *) die "unknown flag: $1 (use --help)" ;;
  esac
  shift
done

banner
echo "${BOLD}${RED}Installing SAURON…${RST}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ── sudo helper (only if we actually need it) ────────
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi
fi

# ── distro detection ─────────────────────────────────
DISTRO="unknown"
PKG_MGR=""
if [ -r /etc/os-release ]; then
  . /etc/os-release
  DISTRO="${ID:-unknown}"
fi
if command -v apt-get >/dev/null 2>&1; then PKG_MGR="apt"
elif command -v dnf    >/dev/null 2>&1; then PKG_MGR="dnf"
elif command -v pacman >/dev/null 2>&1; then PKG_MGR="pacman"
elif command -v brew   >/dev/null 2>&1; then PKG_MGR="brew"
fi
log "detected distro=${DISTRO} package-manager=${PKG_MGR:-none}"

# ═════════════════════════════════════════════════════
# 1. System packages (python build prereqs + Xvfb + screenshots)
# ═════════════════════════════════════════════════════
install_system_debian() {
  log "installing system packages (apt)…"
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update -y || warn "apt update failed — continuing"
  # Core build prereqs + venv + Xvfb/scrot for screenshots.
  $SUDO apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip python3-dev \
      build-essential pkg-config \
      libssl-dev libffi-dev zlib1g-dev \
      libjpeg-dev libpng-dev \
      xvfb scrot imagemagick \
      curl wget git ca-certificates \
    || warn "some apt packages failed to install — continuing (will retry individually)"

  if [ "$DO_OPTIONAL" -eq 1 ]; then
    log "installing optional system libs for weasyprint (PDF) and asciinema…"
    $SUDO apt-get install -y --no-install-recommends \
        libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 shared-mime-info fonts-dejavu \
        asciinema \
      || warn "optional system libs partially failed — PDF/recording may degrade"
  fi
}

install_system_rhel() {
  log "installing system packages (dnf)…"
  $SUDO dnf install -y \
      python3 python3-virtualenv python3-pip python3-devel \
      gcc gcc-c++ make pkgconfig \
      openssl-devel libffi-devel zlib-devel \
      libjpeg-turbo-devel libpng-devel \
      xorg-x11-server-Xvfb scrot ImageMagick \
      curl wget git ca-certificates \
    || warn "some dnf packages failed — continuing"
  if [ "$DO_OPTIONAL" -eq 1 ]; then
    $SUDO dnf install -y cairo pango gdk-pixbuf2 shared-mime-info dejavu-fonts-common asciinema || warn "optional rhel libs partially failed"
  fi
}

if [ "$DO_SYSTEM" -eq 1 ]; then
  case "$PKG_MGR" in
    apt)    install_system_debian ;;
    dnf)    install_system_rhel ;;
    pacman) warn "Arch/Manjaro detected — install python, xvfb, scrot, cairo, pango manually" ;;
    brew)   warn "macOS detected — run 'brew install python xquartz cairo pango gdk-pixbuf libffi'" ;;
    *)      warn "no known package manager — skipping system package step" ;;
  esac
else
  log "skipping system packages (--no-system)"
fi

# ═════════════════════════════════════════════════════
# 2. Python interpreter discovery
# ═════════════════════════════════════════════════════
find_python() {
  if [ -n "$PYTHON_BIN" ] && command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "$PYTHON_BIN"; return 0
  fi
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
        echo "$candidate"; return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(find_python || true)"
[ -n "$PYTHON_BIN" ] || die "Python 3.11+ is required. Install python3 and re-run."
PY_VER="$("$PYTHON_BIN" -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"
ok "using python: $PYTHON_BIN (${PY_VER})"

# ═════════════════════════════════════════════════════
# 3. Virtualenv
# ═════════════════════════════════════════════════════
if [ "$RECREATE_VENV" -eq 1 ] && [ -d "$VENV_DIR" ]; then
  warn "removing existing venv at $VENV_DIR (--recreate-venv)"
  rm -rf "$VENV_DIR"
fi

if [ ! -d "$VENV_DIR" ]; then
  log "creating virtualenv at $VENV_DIR…"
  "$PYTHON_BIN" -m venv "$VENV_DIR" \
    || die "failed to create venv (make sure python3-venv is installed)"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
ok "venv activated: $(which python)"

# ═════════════════════════════════════════════════════
# 4. Python dependencies
#    Strategy: (a) upgrade pip/setuptools/wheel first,
#              (b) prefer binary wheels (avoid source builds),
#              (c) on failure, retry each failed package individually,
#              (d) optional extras are best-effort (never fatal).
# ═════════════════════════════════════════════════════
log "upgrading pip / setuptools / wheel…"
python -m pip install --upgrade --quiet pip setuptools wheel

PIP_INSTALL=(python -m pip install --prefer-binary --disable-pip-version-check)

install_requirements() {
  local req_file="$1"
  local label="$2"
  local fatal="$3"   # 1 = fail the installer on error, 0 = best-effort

  log "installing ${label} from ${req_file}…"
  if "${PIP_INSTALL[@]}" -r "$req_file"; then
    ok "${label} installed"
    return 0
  fi

  warn "${label}: bulk install hit an error — retrying packages one by one"
  local failed=()
  # shellcheck disable=SC2013
  while IFS= read -r line; do
    # strip comments and blanks
    local pkg
    pkg="$(echo "$line" | sed 's/#.*$//' | xargs || true)"
    [ -z "$pkg" ] && continue
    if ! "${PIP_INSTALL[@]}" "$pkg"; then
      failed+=("$pkg")
      warn "   ✗ $pkg"
    fi
  done < "$req_file"

  if [ "${#failed[@]}" -gt 0 ]; then
    if [ "$fatal" -eq 1 ]; then
      err "${label}: the following required packages failed: ${failed[*]}"
      err "   re-run with: pip install ${failed[*]}"
      return 1
    else
      warn "${label}: optional packages skipped: ${failed[*]}"
      warn "   features depending on them will degrade gracefully"
      return 0
    fi
  fi
  ok "${label} installed (one-by-one fallback)"
}

install_requirements "requirements.txt" "core dependencies" 1 \
  || die "core dependencies failed — see messages above"

if [ "$DO_OPTIONAL" -eq 1 ] && [ -f requirements-optional.txt ]; then
  install_requirements "requirements-optional.txt" "optional extras" 0
else
  warn "skipping optional extras (PDF export / asciinema will be disabled)"
fi

# ═════════════════════════════════════════════════════
# 5. Verification — import the real modules
# ═════════════════════════════════════════════════════
log "verifying the install…"
python - <<'PY'
import importlib, sys
required = [
    "fastapi", "uvicorn", "pydantic", "pydantic_settings",
    "yaml", "httpx", "aiofiles", "websockets", "jinja2",
    "sqlalchemy", "aiosqlite", "alembic",
    "anthropic", "openai", "google.generativeai", "ollama",
    "mcp", "ptyprocess", "psutil",
    "PIL", "markdown", "rich",
    "dns", "requests", "bs4",
    "structlog", "loguru",
]
optional = ["weasyprint"]

missing = []
for m in required:
    try:
        importlib.import_module(m)
    except Exception as e:
        missing.append((m, repr(e)))

opt_missing = []
for m in optional:
    try:
        importlib.import_module(m)
    except Exception as e:
        opt_missing.append((m, repr(e)))

if missing:
    print("REQUIRED_IMPORT_FAILURES:")
    for name, err in missing:
        print(f"  - {name}: {err}")
    sys.exit(2)

if opt_missing:
    print("OPTIONAL_IMPORT_FAILURES (ok, degraded):")
    for name, err in opt_missing:
        print(f"  - {name}: {err}")

print("VERIFY_OK")
PY

# ═════════════════════════════════════════════════════
# 6. Runtime dirs + .env
# ═════════════════════════════════════════════════════
log "ensuring runtime directories exist…"
mkdir -p data logs reports/output screenshots artifacts sessions runtime/workdir runtime/screenshots runtime/recordings runtime/reports

if [ ! -f .env ]; then
  log "copying .env.example → .env"
  cp .env.example .env
else
  ok ".env already present (left untouched)"
fi

# ═════════════════════════════════════════════════════
# 7. (optional) Kali tool chain
# ═════════════════════════════════════════════════════
if [ "$DO_KALI_TOOLS" -eq 1 ]; then
  if [ "$PKG_MGR" = "apt" ]; then
    log "installing Kali offensive tool chain (--with-kali-tools)…"
    $SUDO apt-get install -y --no-install-recommends \
      nmap masscan \
      amass subfinder theharvester whatweb wafw00f \
      nuclei nikto wpscan \
      sqlmap wfuzz ffuf gobuster feroxbuster \
      hydra john hashcat medusa \
      metasploit-framework \
      impacket-scripts responder \
      smbmap enum4linux-ng \
      sslscan \
      dnsrecon dnsenum \
      || warn "some Kali tools are not available on this repo — skipped"
    ok "Kali tool chain step finished"
  else
    warn "--with-kali-tools requested but this is not an apt-based host"
  fi
fi

# ═════════════════════════════════════════════════════
# 8. (optional) Ollama + offline brain
# ═════════════════════════════════════════════════════
if [ "$DO_OLLAMA" -eq 1 ]; then
  log "running setup_ollama.sh…"
  "$ROOT_DIR/scripts/setup_ollama.sh" || warn "ollama setup had issues — see above"
fi

# ═════════════════════════════════════════════════════
# 9. Success
# ═════════════════════════════════════════════════════
cat <<EOF

${BOLD}${GRN}SAURON installed successfully.${RST}

  Python:       ${PY_VER}
  Venv:         ${ROOT_DIR}/${VENV_DIR}
  Core deps:    OK
  Optional:     $( [ "$DO_OPTIONAL" -eq 1 ] && echo "installed (best-effort)" || echo "skipped" )
  Kali tools:   $( [ "$DO_KALI_TOOLS" -eq 1 ] && echo "attempted" || echo "skipped (use --with-kali-tools)" )
  Ollama:       $( [ "$DO_OLLAMA" -eq 1 ] && echo "attempted" || echo "skipped (use --with-ollama)" )

${BOLD}Next steps:${RST}
  1. edit ${BOLD}.env${RST} and add at least one LLM provider key
  2. (optional) ./scripts/setup_ollama.sh    # for WhiteRabbitNeo
  3. ./scripts/start.sh                      # launch the platform

${BOLD}The Eye is ready.${RST}
EOF
