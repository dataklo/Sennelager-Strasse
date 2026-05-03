from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

URL = "https://bfgnet.de/sennelager-range-access"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "status_data.json"


def detect_status_from_times(times_text: str) -> tuple[str, str]:
    t = times_text.lower()
    has_open = "open" in t
    has_closed = "closed" in t
    has_transition = any(k in t for k in ["until", "from", "today", "hrs"])

    if has_open and has_closed:
        return "changing", "Open/Closed im selben Eintrag"
    if has_transition and (has_open or has_closed):
        return "changing", "Wechselzeit im Eintrag"
    if has_open:
        return "open", "Transit Roads Open"
    if has_closed:
        return "closed", "Transit Roads Closed"
    return "unknown", "Unbekannter Tabelleninhalt"


def fetch_remote_html() -> str:
    r = requests.get(URL, timeout=30, headers={"User-Agent": "SennelagerRangeMonitor/1.0"})
    r.raise_for_status()
    return r.text


def parse_schedule_table(html: str) -> dict[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    schedule: dict[str, dict] = {}

    for row in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue

        day_txt, date_txt, times_txt = cells[0], cells[1], cells[2]
        if date_txt.lower() == "date" or day_txt.lower() == "day":
            continue

        try:
            dt = dateparser.parse(date_txt, dayfirst=True, fuzzy=True)
        except Exception:
            continue
        if not dt:
            continue

        iso = dt.date().isoformat()
        status, note = detect_status_from_times(times_txt)
        schedule[iso] = {
            "day": day_txt,
            "date_text": date_txt,
            "times": times_txt,
            "status": status,
            "note": note,
        }

    return schedule


def load_existing() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run() -> None:
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    html = fetch_remote_html()
    schedule = parse_schedule_table(html)

    payload = load_existing()
    payload["schedule"] = schedule
    payload["last_fetch_utc"] = now
    payload["source_url"] = URL
    payload["entry_count"] = len(schedule)

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
