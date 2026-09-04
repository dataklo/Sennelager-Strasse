from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import re

from flask import Flask, Response, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app import fetch_status

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "status_data.json"
app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"), static_folder=str(Path(__file__).resolve().parent.parent / "static"))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
STALE_MAX_AGE_HOURS = 30
REFRESH_LOCK = threading.Lock()

COLOR_MAP = {"open": "green", "closed": "red", "changing": "yellow", "unknown": "gray"}
LABEL_MAP = {"open": "Geöffnet", "closed": "Gesperrt", "changing": "Öffnet/Schließt heute", "unknown": "Unbekannt"}


def header_status_label(today_row: dict) -> str:
    status = today_row.get("status", "unknown")
    if status == "open":
        return "Durchfahrt aktuell möglich"
    if status == "closed":
        return "Durchfahrt aktuell gesperrt"
    if status != "changing":
        return "Unbekannt"

    times_text = str(today_row.get("times", "")).lower()
    if re.search(r"(open\s+from|opens?\s+from|closed\s+until)", times_text):
        return "Durchfahrt öffnet heute"
    if re.search(r"(closed\s+from|closes?\s+from|open\s+until)", times_text):
        return "Durchfahrt schließt heute"
    return "Durchfahrtsstatus ändert sich heute"


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"schedule": {}, "last_fetch_utc": None}
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def parse_last_fetch(last_fetch_utc: str | None) -> datetime | None:
    if not last_fetch_utc:
        return None
    try:
        return datetime.fromisoformat(last_fetch_utc.replace("Z", "+00:00"))
    except ValueError:
        return None


def needs_refresh(last_fetch_utc: str | None) -> bool:
    dt = parse_last_fetch(last_fetch_utc)
    if dt is None:
        return True
    age = datetime.now(dt.tzinfo) - dt
    return age > timedelta(hours=STALE_MAX_AGE_HOURS)


def refresh_if_stale() -> None:
    if app.config.get("STATIC_EXPORT"):
        return
    data = load_data()
    if not needs_refresh(data.get("last_fetch_utc")):
        return
    with REFRESH_LOCK:
        latest = load_data()
        if not needs_refresh(latest.get("last_fetch_utc")):
            return
        try:
            fetch_status.run()
        except Exception:
            app.logger.exception("Automatic stale refresh failed")


def week_days_monday_start(ref: date) -> list[date]:
    monday = ref - timedelta(days=ref.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def format_last_fetch(last_fetch_utc: str | None) -> str:
    if not last_fetch_utc:
        return "noch nie"
    dt = datetime.fromisoformat(last_fetch_utc.replace("Z", "+00:00"))
    return dt.strftime("%d.%m.%Y %H:%M UTC")


def month_blocks(today: date, schedule: dict) -> list[dict]:
    future_dates = []
    for iso in schedule.keys():
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        if d >= today:
            future_dates.append(d)

    end_date = max(future_dates) if future_dates else today
    month_start = today.replace(day=1)

    blocks = []
    cursor = month_start
    while (cursor.year, cursor.month) <= (end_date.year, end_date.month):
        if cursor.month == 12:
            next_month_start = date(cursor.year + 1, 1, 1)
        else:
            next_month_start = date(cursor.year, cursor.month + 1, 1)

        start_week_monday = cursor - timedelta(days=cursor.weekday())
        end_of_month = next_month_start - timedelta(days=1)
        end_week_sunday = end_of_month + timedelta(days=(6 - end_of_month.weekday()))

        weeks = []
        week_cursor = start_week_monday
        while week_cursor <= end_week_sunday:
            week_end = week_cursor + timedelta(days=6)
            if week_end < today:
                week_cursor += timedelta(days=7)
                continue
            week_days = []
            for i in range(7):
                d = week_cursor + timedelta(days=i)
                in_month = d.month == cursor.month and d.year == cursor.year
                row = schedule.get(d.isoformat(), {"status": "unknown"})
                st = row.get("status", "unknown")
                week_days.append({
                    "date_iso": d.isoformat(),
                    "day": d.strftime("%a"),
                    "day_num": d.day,
                    "label": LABEL_MAP.get(st, "Unbekannt"),
                    "color": COLOR_MAP.get(st, "gray"),
                    "is_past": d < today,
                    "is_today": d == today,
                    "is_outside_month": not in_month,
                })
            weeks.append({
                "calendar_week": week_cursor.isocalendar().week,
                "days": week_days,
            })
            week_cursor += timedelta(days=7)

        blocks.append({"title": cursor.strftime("%B %Y"), "month_iso": cursor.strftime("%Y-%m"), "weeks": weeks})
        cursor = next_month_start

    return blocks


def build_absolute_url(path: str) -> str:
    return f"{request.url_root.rstrip('/')}{path}"




@app.after_request
def add_security_headers(resp: Response) -> Response:
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self'; "
        "script-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.is_secure:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


def upcoming_days(today: date, schedule: dict) -> list[dict]:
    future = []
    for iso, row in schedule.items():
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        if d < today:
            continue
        st = row.get("status", "unknown")
        future.append((d, st))

    future.sort(key=lambda item: item[0])
    return [
        {
            "date_display": d.strftime("%a, %d.%m.%Y"),
            "label": LABEL_MAP.get(st, "Unbekannt"),
            "color": COLOR_MAP.get(st, "gray"),
            "is_today": d == today,
        }
        for d, st in future
    ]


def build_ics(schedule: dict) -> str:
    rows = []
    for iso, row in schedule.items():
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        st = row.get("status", "unknown")
        label = LABEL_MAP.get(st, "Unbekannt")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        start = d.strftime("%Y%m%d")
        end = (d + timedelta(days=1)).strftime("%Y%m%d")
        uid = f"senne-{iso}-{st}@range-access"
        rows.append((d, "\n".join([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:Senne – {label}",
            "DESCRIPTION:Privates Projekt ohne Gewähr. Quelle: bfgnet.de/sennelager-range-access",
            "END:VEVENT",
        ])))

    rows.sort(key=lambda item: item[0])
    events = "\n".join(event for _, event in rows)
    return "\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Senne Oeffnungszeiten//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Senne Öffnungszeiten",
        events,
        "END:VCALENDAR",
        "",
    ])


@app.route("/calendar.ics")
def calendar_ics():
    refresh_if_stale()
    data = load_data()
    schedule = data.get("schedule", {})
    return Response(build_ics(schedule), mimetype="text/calendar")


@app.route("/robots.txt")
def robots_txt():
    sitemap_url = build_absolute_url("/sitemap.xml")
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /impressum\n"
        "Disallow: /datenschutz\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    page_url = build_absolute_url("/")
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        f"<url><loc>{page_url}</loc><lastmod>{now}</lastmod><changefreq>hourly</changefreq><priority>0.9</priority></url>"
        "</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@app.route("/impressum")
def impressum():
    return render_template("impressum.html")


@app.route("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")


@app.route("/heute-geoeffnet")
def heute_geoeffnet():
    refresh_if_stale()
    data = load_data()
    schedule = data.get("schedule", {})
    today = date.today()
    today_row = schedule.get(today.isoformat(), {"status": "unknown"})
    today_status = today_row.get("status", "unknown")
    seo_status_label = header_status_label(today_row)
    return render_template(
        "heute-geoeffnet.html",
        header_color=COLOR_MAP.get(today_status, "gray"),
        header_label=seo_status_label,
        canonical_url=build_absolute_url("/heute-geoeffnet"),
        page_title=f"Heute geöffnet? Senne Status am {today.strftime('%d.%m.%Y')}",
        meta_description="Ist die Senne heute geöffnet oder geschlossen? Hier siehst du den aktuellen Tagesstatus plus Öffnungs-Kalender.",
        og_image_url=build_absolute_url("/static/og-image.svg"),
        seo_status_label=seo_status_label,
        seo_today_iso=today.isoformat(),
        seo_last_fetch=data.get("last_fetch_utc"),
        last_fetch_display=format_last_fetch(data.get("last_fetch_utc")),
    )


@app.route("/")
def index():
    refresh_if_stale()
    data = load_data()
    schedule = data.get("schedule", {})
    today = date.today()

    today_row = schedule.get(today.isoformat(), {"status": "unknown"})
    today_status = today_row.get("status", "unknown")
    seo_status_label = header_status_label(today_row)
    seo_date = today.strftime("%d.%m.%Y")
    page_title = f"Senne Öffnungszeiten heute ({seo_date}): {seo_status_label}"
    meta_description = (
        f"Aktueller Status vom Truppenübungsplatz Senne am {seo_date}: {seo_status_label}. "
        "Mit Kalender, kommenden Öffnungs-/Schließtagen und iCal-Abo."
    )
    return render_template(
        "index.html",
        header_color=COLOR_MAP.get(today_status, "gray"),
        header_label=seo_status_label,
        month_blocks=month_blocks(today, schedule),
        last_fetch_display=format_last_fetch(data.get("last_fetch_utc")),
        canonical_url=build_absolute_url("/"),
        page_title=page_title,
        meta_description=meta_description,
        og_image_url=build_absolute_url("/static/og-image.svg"),
        upcoming_days=upcoming_days(today, schedule),
        seo_status_label=seo_status_label,
        seo_today_iso=today.isoformat(),
        seo_last_fetch=data.get("last_fetch_utc"),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
