# Sennelager Range Access Monitor

Eine kleine Flask-App, die die **Tabelle `Day | Date | Times`** von `https://bfgnet.de/sennelager-range-access` ausliest und den Tagesstatus als Webansicht + iCal-Feed bereitstellt.

> Wichtig: Es wird **nur** die Tabelle ausgewertet, **nicht** der Fließtext der Quellseite.

## Funktionsumfang

- Täglicher Abruf der Quelldaten per Systemd-Timer.
- Status-Erkennung pro Datum:
  - `open` → Grün
  - `closed` → Rot
  - `changing` (z. B. Open/Closed mit Uhrzeiten) → Gelb
  - `unknown` → Grau
- Weboberfläche mit:
  - Tagesstatus im Kopfbereich
  - Monatskalender (inkl. vergangene Tage/Grenztage)
  - Liste kommender Tage
  - Letzter Aktualisierungszeitpunkt (UTC)
- Zusätzliche Routen:
  - `/calendar.ics` (iCal-Export)
  - `/robots.txt`
  - `/sitemap.xml`
  - `/impressum`
  - `/datenschutz`

## Architektur & Dateien

- `app/fetch_status.py`: Lädt HTML, parst Tabelle und speichert JSON.
- `app/web.py`: Flask-Webserver für UI, SEO-Routen und iCal.
- `data/status_data.json`: Persistente, zuletzt geladene Daten.
- `systemd/*.service` + `systemd/*.timer`: Betriebsdienste.
- `scripts/install.sh`: Komplett-Installation unter `/opt/sennelager-range`.
- `scripts/update.sh`: Update (Git Pull + Dependencies + Service-Restart).

## Voraussetzungen

- Debian/Ubuntu-ähnliches Linux mit `systemd`
- Root-Rechte für Installation/Service-Setup
- Ausgehender HTTPS-Zugriff auf:
  - `github.com` (Repo-Download)
  - `bfgnet.de` (Quelldaten)

## Installation

```bash
sudo apt update
sudo apt install -y git
curl -fsSL https://raw.githubusercontent.com/dataklo/Sennelager-Strasse/main/scripts/install.sh -o /tmp/install.sh
sudo bash /tmp/install.sh
```

Die Installation:

1. klont das Repo nach `/opt/sennelager-range`
2. erstellt eine Python-Virtualenv in `/opt/sennelager-range/.venv`
3. installiert Python-Abhängigkeiten aus `requirements.txt`
4. installiert und aktiviert die Systemd-Units
5. startet Webservice + Timer und triggert initialen Fetch

Danach erreichbar unter: `http://<host>:8080`

## Update

```bash
sudo /opt/sennelager-range/scripts/update.sh
```

Das Update-Skript führt aus:

- `git fetch --all --prune`
- Checkout auf den Default-Branch von `origin`
- `git pull --ff-only`
- erneute Installation der Python-Abhängigkeiten
- Neuinstallation/Reload der Systemd-Units
- Neustart von Webservice und Timer + einmaliger Fetch

## Betrieb mit systemd

### Enthaltene Units

- `sennelager-web.service`
  - startet Flask-App via `.venv/bin/python /opt/sennelager-range/app/web.py`
  - Restart-Policy: `always`
- `sennelager-fetch.service`
  - One-shot Job zum Abruf/Parsing
- `sennelager-fetch.timer`
  - Zeitplan-Basis: täglich um `00:01:00` (Server-Lokalzeit)
  - Zufällige Verzögerung: `RandomizedDelaySec=5h 58m`
    - Effektiv läuft der Abruf pro Tag zufällig zwischen **00:01 und 05:59 Uhr**
  - `Persistent=true` (nachholen nach Reboot)

### Nützliche Befehle

```bash
# Status prüfen
systemctl status sennelager-web.service
systemctl status sennelager-fetch.timer

# Logs live verfolgen
journalctl -u sennelager-web.service -f
journalctl -u sennelager-fetch.service -f

# Fetch manuell anstoßen
sudo systemctl start sennelager-fetch.service

# Optional: sofort prüfen, wann der nächste automatische Lauf geplant ist
systemctl list-timers sennelager-fetch.timer
```

## Wichtiger Betriebs-Hinweis (Proxy)

Der Container läuft **hinter einem Proxy**.

- Der Webserver muss immer auf **`0.0.0.0:8080`** gebunden bleiben.
- Änderungen auf `127.0.0.1`, einen anderen Port oder abweichende Bind-Adressen brechen die Erreichbarkeit hinter dem Proxy.
- Bei Änderungen an `app/web.py`, Service-Dateien oder Startskripten diesen Punkt immer zuerst prüfen.

## Konfiguration

### Umgebungsvariable `SITE_DOMAIN` (optional)

`app/web.py` nutzt optional `SITE_DOMAIN`, um absolute URLs für Canonical/Sitemap/Robots zu erzeugen.

Beispiel:

```bash
SITE_DOMAIN=https://example.org
```

Wenn nicht gesetzt, wird die URL dynamisch aus dem Request (`request.url_root`) erzeugt.

### Umgebungsvariable `ALLOWED_HOSTS` (optional)

Komma-separierte Liste erlaubter Hostnamen für den Host-Header-Check (z. B. `example.org,www.example.org,.example.net`).

- Ist `ALLOWED_HOSTS` leer, werden alle Hosts akzeptiert.
- Subdomain-Wildcard über führenden Punkt ist möglich (z. B. `.example.org`).
- IP-basierte Aufrufe (z. B. `http://<server-ip>:8080`) bleiben standardmäßig erlaubt.

### Umgebungsvariable `ALLOW_IP_HOSTS` (optional, Standard: `true`)

Steuert, ob direkte Zugriffe über IP-Literale trotz gesetzter `ALLOWED_HOSTS` akzeptiert werden.

- `true` (Standard): Hostnamen **und** IP-Aufrufe sind erlaubt.
- `false`: Es gelten ausschließlich Einträge aus `ALLOWED_HOSTS`.

## Datenformat (`data/status_data.json`)

Typische Felder:

- `schedule`: Objekt mit ISO-Datum als Schlüssel (z. B. `2026-05-03`)
- `last_fetch_utc`: letzter erfolgreicher Abruf in UTC (ISO-Format)
- `source_url`: aktuell `https://bfgnet.de/sennelager-range-access`
- `entry_count`: Anzahl erkannter Tabelleneinträge

## Entwicklung lokal

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python app/fetch_status.py
python app/web.py
```

Danach lokal öffnen: `http://127.0.0.1:8080`

## Haftungsausschluss

Privates Projekt ohne Gewähr. Maßgeblich ist immer die Originalquelle auf `bfgnet.de`.
