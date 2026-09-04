#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sennelager-range}"
ENV_FILE="${ENV_FILE:-/etc/sennelager-range.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] Konfiguration fehlt: $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

cd "$APP_DIR"
"$APP_DIR/.venv/bin/python" -m app.fetch_status
"$APP_DIR/.venv/bin/python" -m app.build_data --output "$APP_DIR/publish-data"
"$APP_DIR/.venv/bin/python" -m app.deploy_ftp "$APP_DIR/publish-data"
