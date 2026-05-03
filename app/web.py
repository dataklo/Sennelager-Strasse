from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, render_template

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "status_data.json"
app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"), static_folder=str(Path(__file__).resolve().parent.parent / "static"))

COLOR_MAP = {"open": "green", "closed": "red", "changing": "yellow", "unknown": "gray"}
LABEL_MAP = {"open": "Geöffnet", "closed": "Geschlossen", "changing": "Öffnet/Schließt heute", "unknown": "Unbekannt"}


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"schedule": {}, "last_fetch_utc": None}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def week_days_monday_start(ref: date) -> list[date]:
    monday = ref - timedelta(days=ref.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def format_last_fetch(last_fetch_utc: str | None) -> str:
    if not last_fetch_utc:
        return "noch nie"
    dt = datetime.fromisoformat(last_fetch_utc.replace("Z", "+00:00"))
    return dt.strftime("%d.%m.%Y %H:%M UTC")


@app.route("/")
def index():
    data = load_data()
    schedule = data.get("schedule", {})
    today = date.today()
    week = week_days_monday_start(today)

    week_view = []
    for d in week:
        iso = d.isoformat()
        row = schedule.get(iso, {"status": "unknown"})
        st = row.get("status", "unknown")
        week_view.append({
            "day": d.strftime("%a"),
            "day_num": d.day,
            "label": LABEL_MAP.get(st, "Unbekannt"),
            "color": COLOR_MAP.get(st, "gray"),
            "is_past": d < today,
            "is_today": d == today,
        })

    today_status = schedule.get(today.isoformat(), {"status": "unknown"}).get("status", "unknown")
    return render_template("index.html", header_color=COLOR_MAP.get(today_status, "gray"), header_label=LABEL_MAP.get(today_status, "Unbekannt"), week=week_view, last_fetch_display=format_last_fetch(data.get("last_fetch_utc")))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
