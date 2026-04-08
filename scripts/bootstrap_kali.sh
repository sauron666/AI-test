#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  Optional — install the full Kali toolchain on a Debian/Ubuntu host
#  that is NOT Kali. Skip if you are already running Kali.
# ══════════════════════════════════════════════════════════════════
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root / with sudo"
  exit 1
fi

echo "[*] adding Kali rolling repository…"
apt-get update -y
apt-get install -y curl gnupg ca-certificates lsb-release

install -d -m 0755 /usr/share/keyrings
curl -fsSL https://archive.kali.org/archive-key.asc | gpg --dearmor -o /usr/share/keyrings/kali-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/kali-archive-keyring.gpg] http://http.kali.org/kali kali-rolling main contrib non-free non-free-firmware" \
    > /etc/apt/sources.list.d/kali.list

# Lower Kali priority so system packages still come from the base distro
cat >/etc/apt/preferences.d/kali.pref <<'PREF'
Package: *
Pin: release o=Kali
Pin-Priority: 50
PREF

apt-get update -y

echo "[*] installing Kali metapackages…"
apt-get install -y --no-install-recommends \
    kali-tools-top10 kali-tools-web kali-tools-information-gathering \
    kali-tools-vulnerability kali-tools-passwords kali-tools-wireless \
    kali-tools-reverse-engineering kali-tools-exploitation kali-tools-post-exploitation

echo "Kali toolchain installed."
