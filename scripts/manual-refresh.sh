#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Bitte als root ausführen: sudo /opt/sennelager-range/scripts/manual-refresh.sh"
  exit 1
fi

systemctl start sennelager-fetch.service
systemctl --no-pager --full status sennelager-fetch.service || true

echo "[OK] Manueller Abruf gestartet."
