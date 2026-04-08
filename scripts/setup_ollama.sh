#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  Install Ollama + pull a local offline brain for SAURON.
#
#  Default target is WhiteRabbitNeo if the tag resolves; otherwise
#  we fall back through a list of known-good offensive-security
#  fine-tunes and, as a last resort, llama3.1:8b.
#
#  Env overrides:
#    OLLAMA_MODEL      primary model tag  (default tries a list)
#    OLLAMA_TRIAGE     fast triage model  (default: llama3.1:8b)
#    SKIP_TRIAGE=1     don't pull the triage model
#
#  WhiteRabbitNeo note:
#    The upstream WhiteRabbitNeo project publishes on HuggingFace,
#    not always on ollama.com/library. If none of the ollama tags
#    resolve, pull it from HF directly:
#
#       ollama pull hf.co/WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-8B-GGUF
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

# Candidates tried in order. First one that resolves wins.
CANDIDATES=(
  "${OLLAMA_MODEL:-}"
  "hf.co/WhiteRabbitNeo/Llama-3.1-WhiteRabbitNeo-2-8B-GGUF"
  "hf.co/WhiteRabbitNeo/Llama-3-WhiteRabbitNeo-8B-v2.0-GGUF"
  "llama3.1:8b"
)
TRIAGE="${OLLAMA_TRIAGE:-llama3.1:8b}"

log()  { printf "[*] %s\n" "$*"; }
ok()   { printf "[✓] %s\n" "$*"; }
warn() { printf "[!] %s\n" "$*" >&2; }

# 1. Install ollama if missing -----------------------
if ! command -v ollama >/dev/null 2>&1; then
  log "installing ollama…"
  if ! curl -fsSL https://ollama.com/install.sh | sh; then
    warn "ollama install script failed — install manually from https://ollama.com/download"
    exit 1
  fi
else
  log "ollama already installed: $(ollama --version 2>/dev/null || echo unknown)"
fi

# 2. Start the daemon --------------------------------
if ! pgrep -x ollama >/dev/null 2>&1; then
  log "starting ollama daemon in background…"
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  warn "ollama daemon is not reachable on 127.0.0.1:11434 — check /tmp/ollama.log"
  exit 1
fi

# 3. Pull the first candidate that resolves ----------
PRIMARY=""
for m in "${CANDIDATES[@]}"; do
  [ -z "$m" ] && continue
  log "trying to pull: ${m}"
  if ollama pull "$m"; then
    PRIMARY="$m"
    ok "pulled ${m}"
    break
  else
    warn "  ${m} not available (continuing)"
  fi
done

if [ -z "$PRIMARY" ]; then
  warn "no model could be pulled — check network and ollama.com / huggingface availability"
  exit 1
fi

# 4. Triage model ------------------------------------
if [ "${SKIP_TRIAGE:-0}" != "1" ] && [ "$PRIMARY" != "$TRIAGE" ]; then
  log "pulling triage model: ${TRIAGE}…"
  ollama pull "${TRIAGE}" || warn "triage model pull failed — continuing"
fi

# 5. Summary -----------------------------------------
cat <<EOF

Ollama is ready.
  Primary : ${PRIMARY}
  Triage  : $( [ "${SKIP_TRIAGE:-0}" = "1" ] && echo "(skipped)" || echo "${TRIAGE}" )

To use the local brain for SAURON, set in .env:

  DEFAULT_LLM_PROVIDER=ollama
  OLLAMA_MODEL=${PRIMARY}

Note: raw local models have NO guardrails. SAURON applies its
senior-mindset / validator / critic layers only when you drive
the model through the SAURON agent — not when you run
'ollama run' directly.
EOF
