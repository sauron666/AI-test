# ══════════════════════════════════════════════════════════════════
#  SAURON — Kali-based container with full toolchain + Python stack
# ══════════════════════════════════════════════════════════════════
FROM kalilinux/kali-rolling:latest

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SAURON_HOME=/opt/sauron

# ── System deps ───────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        git curl wget ca-certificates gnupg lsb-release \
        xvfb scrot imagemagick \
        chromium \
        build-essential libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Kali pentest metapackages (comment out what you don't need) ──
RUN apt-get update && apt-get install -y --no-install-recommends \
        kali-tools-top10 \
        kali-tools-web \
        kali-tools-information-gathering \
        kali-tools-vulnerability \
        kali-tools-passwords \
        kali-tools-wireless \
        kali-tools-reverse-engineering \
        kali-tools-exploitation \
        kali-tools-post-exploitation \
    && rm -rf /var/lib/apt/lists/*

# ── Python venv ───────────────────────────────────────────────────
WORKDIR ${SAURON_HOME}
COPY requirements.txt ./
RUN python3 -m venv .venv \
    && .venv/bin/pip install --upgrade pip wheel \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

# ── App source ────────────────────────────────────────────────────
COPY backend ./backend
COPY frontend ./frontend
COPY config ./config
COPY scripts ./scripts
COPY docs ./docs
COPY .env.example ./

RUN mkdir -p data logs reports/output screenshots artifacts sessions \
    && chmod +x scripts/*.sh

ENV PATH="${SAURON_HOME}/.venv/bin:${PATH}"

EXPOSE 8000 8080 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["./scripts/start.sh"]
