#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  Install Ollama + pull the WhiteRabbitNeo offensive-sec model.
#  This gives SAURON a fully offline, air-gapped brain.
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

MODEL="${OLLAMA_MODEL:-whiterabbitneo:13b}"

echo "[*] installing ollama…"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! pgrep -x ollama >/dev/null 2>&1; then
  echo "[*] starting ollama daemon in background…"
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  sleep 2
fi

echo "[*] pulling ${MODEL} (this can take a while)…"
ollama pull "${MODEL}"

echo "[*] also pulling a fast generalist for triage tasks…"
ollama pull llama3.1:8b || true

cat <<EOF

Ollama is ready. SAURON will use ${MODEL} as the local brain.
Set DEFAULT_LLM_PROVIDER=ollama in .env to run fully offline.
EOF
