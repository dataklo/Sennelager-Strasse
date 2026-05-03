# Sennelager Range Access Monitor

Diese App wertet **nur die Tabelle** mit `Day | Date | Times` aus (z. B. "Transit Roads Closed/Open ..."), nicht den Fließtext.

## Installation
```bash
sudo apt update
sudo apt install -y git curl
curl -fsSL https://raw.githubusercontent.com/dataklo/Sennelager-Strasse/main/scripts/install.sh -o /tmp/install.sh
sudo bash /tmp/install.sh
```

## Update
```bash
sudo /opt/sennelager-range/scripts/update.sh
```

## Manuellen Datenabruf starten
```bash
sudo /opt/sennelager-range/scripts/manual-refresh.sh
```

## Anzeige
- Oberer Balken: Status für **heute** (grün/gelb/rot)
- Direkt darunter: **Letzte Aktualisierung** (Datum + Uhrzeit UTC)
- Kalender: 7 Tage (Montag-Sonntag), vergangene Tage grau
