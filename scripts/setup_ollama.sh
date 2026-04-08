#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  Install Ollama + pull the WhiteRabbitNeo offensive-sec model.
#  This gives SAURON a fully offline, air-gapped brain.
#
#  Env overrides:
#    OLLAMA_MODEL      primary model to pull (default: whiterabbitneo:13b)
#    OLLAMA_TRIAGE     fast triage model    (default: llama3.1:8b)
#    SKIP_TRIAGE=1     don't pull the triage model
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

MODEL="${OLLAMA_MODEL:-whiterabbitneo:13b}"
TRIAGE="${OLLAMA_TRIAGE:-llama3.1:8b}"

log() { printf "[*] %s\n" "$*"; }
warn(){ printf "[!] %s\n" "$*" >&2; }

# 1. Install ollama if missing
if ! command -v ollama >/dev/null 2>&1; then
  log "installing ollama…"
  if ! curl -fsSL https://ollama.com/install.sh | sh; then
    warn "ollama install script failed — install manually from https://ollama.com/download"
    exit 1
  fi
else
  log "ollama already installed: $(ollama --version 2>/dev/null || echo unknown)"
fi

# 2. Start the daemon
if ! pgrep -x ollama >/dev/null 2>&1; then
  log "starting ollama daemon in background…"
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  # Wait for the socket to come up
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  warn "ollama daemon is not reachable on 127.0.0.1:11434 — check /tmp/ollama.log"
  exit 1
fi

# 3. Pull models
log "pulling primary model: ${MODEL} (this can take a while)…"
if ! ollama pull "${MODEL}"; then
  warn "failed to pull ${MODEL} — you may need to try a smaller tag or check disk space"
fi

if [ "${SKIP_TRIAGE:-0}" != "1" ]; then
  log "pulling triage model: ${TRIAGE}…"
  ollama pull "${TRIAGE}" || warn "triage model pull failed — continuing"
fi

cat <<EOF

Ollama is ready.
  Primary : ${MODEL}
  Triage  : $( [ "${SKIP_TRIAGE:-0}" = "1" ] && echo "(skipped)" || echo "${TRIAGE}" )

Set DEFAULT_LLM_PROVIDER=ollama in .env to run fully offline.
EOF
