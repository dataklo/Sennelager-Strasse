#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/sennelager-range"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Bitte als root ausführen: sudo /opt/sennelager-range/scripts/update.sh"
  exit 1
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "[ERROR] $APP_DIR ist kein Git-Repository. Bitte erst installieren."
  exit 1
fi

cd "$APP_DIR"

if [[ ! -x "$APP_DIR/.venv/bin/pip" ]]; then
  echo "[ERROR] Python venv fehlt. Bitte Installation neu ausführen."
  exit 1
fi

git fetch --all --prune
DEFAULT_BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
BRANCH="${DEFAULT_BRANCH:-main}"

git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

"$APP_DIR/.venv/bin/pip" install --upgrade -r requirements.txt

install -m 644 systemd/sennelager-fetch.service /etc/systemd/system/sennelager-fetch.service
install -m 644 systemd/sennelager-fetch.timer /etc/systemd/system/sennelager-fetch.timer
install -m 644 config/ftp.env.example /etc/sennelager-range.env.example
chmod +x scripts/publish.sh scripts/deploy_full.sh

systemctl daemon-reload
systemctl disable --now sennelager-web.service 2>/dev/null || true
systemctl restart sennelager-fetch.timer

if [[ -f /etc/sennelager-range.env ]]; then
  "$APP_DIR/scripts/deploy_full.sh"
else
  echo "[WARNUNG] /etc/sennelager-range.env fehlt; Veröffentlichung übersprungen."
fi

echo "[OK] Update abgeschlossen (Branch: $BRANCH)"
