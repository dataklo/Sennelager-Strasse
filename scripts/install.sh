#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/dataklo/Sennelager-Strasse.git"
APP_DIR="/opt/sennelager-range"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Bitte als root ausführen: sudo bash install.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y git python3 python3-venv python3-pip ca-certificates

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  echo "[INFO] Repo existiert bereits in $APP_DIR"
fi

cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install --upgrade -r requirements.txt

install -m 644 systemd/sennelager-web.service /etc/systemd/system/sennelager-web.service
install -m 644 systemd/sennelager-fetch.service /etc/systemd/system/sennelager-fetch.service
install -m 644 systemd/sennelager-fetch.timer /etc/systemd/system/sennelager-fetch.timer

systemctl daemon-reload
systemctl enable --now sennelager-web.service
systemctl enable --now sennelager-fetch.timer
systemctl start sennelager-fetch.service || true

echo "[OK] Installation abgeschlossen: http://<host>:8080"
echo "[INFO] Update: sudo /opt/sennelager-range/scripts/update.sh"
