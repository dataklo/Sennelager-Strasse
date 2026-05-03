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

install -m 644 systemd/sennelager-web.service /etc/systemd/system/sennelager-web.service
install -m 644 systemd/sennelager-fetch.service /etc/systemd/system/sennelager-fetch.service
install -m 644 systemd/sennelager-fetch.timer /etc/systemd/system/sennelager-fetch.timer

systemctl daemon-reload
systemctl restart sennelager-web.service
systemctl restart sennelager-fetch.timer
systemctl start sennelager-fetch.service || true

echo "[OK] Update abgeschlossen (Branch: $BRANCH)"
