#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/dataklo/Sennelager-Strasse.git"
APP_DIR="/opt/sennelager-range"
ENV_FILE="/etc/sennelager-range.env"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "[ERROR] Bitte als root ausführen: sudo bash install.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y curl git python3 python3-venv python3-pip ca-certificates openssh-client

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  echo "[INFO] Repo existiert bereits in $APP_DIR"
  git -C "$APP_DIR" pull --ff-only
fi

cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install --upgrade -r requirements.txt

install -m 644 systemd/sennelager-fetch.service /etc/systemd/system/sennelager-fetch.service
install -m 644 systemd/sennelager-fetch.timer /etc/systemd/system/sennelager-fetch.timer
install -m 644 config/ftp.env.example /etc/sennelager-range.env.example
chmod +x scripts/publish.sh scripts/deploy_full.sh

read_config() {
  local name="$1" prompt="$2" default="${3:-}" secret="${4:-false}" current input=""
  current="${!name:-$default}"
  if [[ -t 0 ]]; then
    if [[ "$secret" == true ]]; then
      read -r -s -p "$prompt: " current; echo
    else
      read -r -p "$prompt${default:+ [$default]}: " input
      current="${input:-$current}"
    fi
  fi
  if [[ -z "$current" ]]; then
    echo "[ERROR] $name fehlt. Alternativ vorab als Umgebungsvariable setzen."
    exit 1
  fi
  printf -v "$name" '%s' "$current"
}

if [[ -f "$ENV_FILE" ]]; then
  echo "[INFO] Vorhandene FTP-Konfiguration wird weiterverwendet: $ENV_FILE"
else
  echo "[INFO] FTP-/Domain-Konfiguration (Hetzner-Zugangsdaten aus konsoleH):"
  read_config PUBLIC_BASE_URL "Öffentliche URL (https://domain.de)"
  read_config FTP_URL "Upload-URL (ftps://server:21/pfad oder sftp://server:22/pfad)"
  if [[ "$FTP_URL" != ftps://* && "$FTP_URL" != sftp://* ]]; then
    echo "[ERROR] FTP_URL muss mit ftps:// oder sftp:// beginnen."
    exit 1
  fi
  read_config FTP_USER "FTP-Benutzer"
  read_config FTP_PASSWORD "FTP-Passwort" "" true
  umask 077
  {
    printf 'PUBLIC_BASE_URL=%q\n' "$PUBLIC_BASE_URL"
    printf 'FTP_URL=%q\n' "$FTP_URL"
    printf 'FTP_USER=%q\n' "$FTP_USER"
    printf 'FTP_PASSWORD=%q\n' "$FTP_PASSWORD"
    printf 'SFTP_KNOWN_HOSTS=%q\n' "/etc/sennelager-range-known-hosts"
  } > "$ENV_FILE"
fi

systemctl daemon-reload
systemctl disable --now sennelager-web.service 2>/dev/null || true
systemctl enable --now sennelager-fetch.timer
"$APP_DIR/scripts/deploy_full.sh"

echo "[OK] CT eingerichtet und Website erstmals veröffentlicht."
echo "[INFO] Update: sudo /opt/sennelager-range/scripts/update.sh"
