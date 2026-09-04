# Sennelager Range Access Monitor auf Hetzner Webhosting

Die eigentliche Website liegt auf einem **Hetzner-Webhosting-S-Paket**. Ein separater
**Ubuntu-Proxmox-CT** aktualisiert im Hintergrund die Öffnungsdaten per FTPS.

## Wie die Lösung funktioniert

Das Webhosting-S-Paket kann keine dauerhaft laufende Python-Anwendung bereitstellen. Deshalb
werden Darstellung und Daten getrennt:

```text
Besucher -> index.html + app.js auf Hetzner
                         |
                         +-> lädt /data/status_data.json

bfgnet.de -> Ubuntu-CT -> erzeugt status_data.json + calendar.ics -> FTPS -> Hetzner
```

- HTML, CSS und JavaScript werden nur bei Installation oder Projektupdates hochgeladen.
- Der Browser lädt bei jedem Seitenaufruf die eigenständige Datei
  `/data/status_data.json` mit deaktiviertem Cache und baut Status, Tagesliste und Kalender daraus.
- Der CT aktualisiert täglich ausschließlich `data/status_data.json` und `calendar.ics`.
- Flask dient auf dem CT nur zum einmaligen Erzeugen des HTML-Grundgerüsts; auf dem
  Webhosting läuft kein Python-Prozess.

Damit ist nicht die ganze Website täglich neu zu bauen. Nur die kleine Datendatei und der
Kalender-Feed werden übertragen.

## Komplettinstallation in einem neuen Ubuntu-Proxmox-CT

Empfehlung: Ubuntu 24.04, mindestens 512 MB RAM, Internetzugriff und aktiviertes `systemd`.
Im frischen CT als `root` ausführen:

```bash
apt update && apt install -y curl
curl -fsSL https://raw.githubusercontent.com/dataklo/Sennelager-Strasse/main/scripts/install.sh -o /tmp/install-sennelager.sh
bash /tmp/install-sennelager.sh
```

Das Installationsskript erledigt vollständig:

1. Installation von Git, Python, Virtualenv und Zertifikaten.
2. Klonen nach `/opt/sennelager-range`.
3. Installation aller Python-Abhängigkeiten.
4. Auswahl von **FTPS auf Port 21** oder **SFTP auf Port 22** und Abfrage der Zugangsdaten.
5. Geschützte Speicherung in `/etc/sennelager-range.env`.
6. Abruf der Quelldaten, vollständigen Erst-Build und verschlüsselten FTPS-/SFTP-Upload.
7. Installation und Aktivierung des täglichen Systemd-Timers.

Benötigt werden die Werte aus dem Hetzner-/konsoleH-Webhostingbereich:

- öffentliche URL, z. B. `https://senne.example.de`
- vollständige Upload-URL, z. B. `ftps://server:21/public_html` oder `sftp://server:22/public_html`
- Benutzer und Passwort

### Installation ohne Rückfragen

Für automatisches Provisioning können alle Werte vorgegeben werden:

```bash
PUBLIC_BASE_URL=https://senne.example.de \
FTP_URL=sftp://wwwXXX.your-server.de:22/public_html \
FTP_USER=usr_webXXX_1 \
FTP_PASSWORD='GEHEIM' \
bash /tmp/install-sennelager.sh
```

Eine `FTP_URL` mit `ftps://` verwendet explizites, TLS-verschlüsseltes FTP auf Port 21 und prüft
das Serverzertifikat. Eine URL mit `sftp://` verwendet SSH/SFTP auf Port 22. Beim ersten SFTP-Lauf
wird der SSH-Hostschlüssel nach `/etc/sennelager-range-known-hosts` geschrieben und bei allen
weiteren Verbindungen geprüft. Unverschlüsseltes FTP wird nicht unterstützt.

## Betrieb

```bash
# Nur Daten und Kalender jetzt aktualisieren
systemctl start sennelager-fetch.service

# Ergebnis/Fehler ansehen
systemctl status sennelager-fetch.service
journalctl -u sennelager-fetch.service -n 100 --no-pager

# Nächsten geplanten Lauf anzeigen
systemctl list-timers sennelager-fetch.timer

# Gesamte Website einschließlich HTML/CSS/JavaScript erneut hochladen
/opt/sennelager-range/scripts/deploy_full.sh

# Git-Projekt aktualisieren und vollständige Website veröffentlichen
/opt/sennelager-range/scripts/update.sh
```

Der Timer läuft täglich ab 00:01 Uhr mit einer zufälligen Verzögerung von höchstens 5 Stunden
und 58 Minuten. Bei einem ausgeschalteten CT wird der Lauf dank `Persistent=true` nachgeholt.

## Werbeflächen

Die beiden bisherigen Seitenflächen sind für PNG-Dateien vorbereitet:

```text
static/ads/left.png
static/ads/right.png
```

Auf großen Desktop-Bildschirmen bleiben die Flächen dezent mit **160 Pixel Breite** seitlich
angeordnet. Auf kleineren Desktop- und Tablet-Bildschirmen wandern sie unter den Hauptinhalt; auf
Smartphones stehen sie dort untereinander. Die Höhe ergibt sich automatisch und unverzerrt aus
dem Seitenverhältnis der PNG-Datei. Fehlt eine Datei, erscheint ein neutraler Werbeplatzhalter.

Nach dem Hinzufügen oder Austauschen der PNG-Dateien ins Git-Repository muss einmal die
vollständige Veröffentlichung laufen:

```bash
/opt/sennelager-range/scripts/update.sh
```

## Dateien und Veröffentlichung

- `static/app.js`: lädt JSON und rendert Status/Kalender im Browser.
- `app/fetch_status.py`: liest ausschließlich die Tabelle der BFG-Quellseite.
- `app/build_data.py`: erzeugt nur JSON und ICS für den täglichen Upload.
- `app/build_static.py`: erzeugt bei Installation/Update die gesamte Website.
- `app/deploy_ftp.py`: FTPS- oder SFTP-Upload über temporäre Dateien.
- `scripts/publish.sh`: täglicher Datenlauf.
- `scripts/deploy_full.sh`: vollständige Veröffentlichung.
- `config/ftp.env.example`: Beispiel der CT-Konfiguration.

Projektfremde Dateien auf dem Webspace werden vom Uploader nicht gelöscht.

## Fehlerdiagnose

- `530 Login incorrect`: FTP-Benutzer oder Passwort kontrollieren.
- `550 ...`: `FTP_REMOTE_DIR` und Schreibrechte kontrollieren.
- TLS-Fehler: den Hetzner-Hostnamen statt einer IP-Adresse verwenden.
- Seite lädt, bleibt aber grau: Im Browser prüfen, ob `/data/status_data.json` erreichbar ist.
- Änderungen an CSS/JS/PNG fehlen: `deploy_full.sh` statt nur des täglichen Dienstes ausführen.

## Haftungsausschluss

Privates Projekt ohne Gewähr. Maßgeblich ist immer die Originalquelle auf `bfgnet.de`.
