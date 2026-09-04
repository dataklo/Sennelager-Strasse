"""Render the Flask pages as files suitable for ordinary web hosting."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from app.web import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "dist"
EXPORTS = {
    "/": "index.html",
    "/heute-geoeffnet": "heute-geoeffnet/index.html",
    "/impressum": "impressum/index.html",
    "/datenschutz": "datenschutz/index.html",
    "/calendar.ics": "calendar.ics",
    "/robots.txt": "robots.txt",
    "/sitemap.xml": "sitemap.xml",
}


def validate_base_url(value: str) -> str:
    value = value.rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
        raise ValueError("PUBLIC_BASE_URL muss eine vollständige URL ohne Pfad sein")
    return value


def build(output_dir: Path, base_url: str) -> None:
    base_url = validate_base_url(base_url)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Static exports must only use the already fetched JSON and never initiate
    # another network request while Flask renders a route.
    app.config["STATIC_EXPORT"] = True
    with app.test_client() as client:
        for route, relative_target in EXPORTS.items():
            response = client.get(route, base_url=base_url)
            if response.status_code != 200:
                raise RuntimeError(f"Export von {route} fehlgeschlagen: HTTP {response.status_code}")
            target = output_dir / relative_target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.data)

    shutil.copytree(PROJECT_ROOT / "static", output_dir / "static")
    (output_dir / "data").mkdir()
    shutil.copy2(PROJECT_ROOT / "data" / "status_data.json", output_dir / "data" / "status_data.json")
    (output_dir / ".htaccess").write_text(
        "Options -Indexes\nDirectoryIndex index.html\nAddType text/calendar .ics\n",
        encoding="utf-8",
    )
    for legal_directory in ("impressum", "datenschutz"):
        (output_dir / legal_directory / ".htaccess").write_text(
            'Header set X-Robots-Tag "noindex, nofollow, noarchive, nosnippet, noimageindex"\n',
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Statische Website erzeugen")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=os.environ.get("PUBLIC_BASE_URL"))
    args = parser.parse_args()
    if not args.base_url:
        parser.error("--base-url oder PUBLIC_BASE_URL ist erforderlich")
    build(args.output.resolve(), args.base_url)
    print(f"[OK] Statische Website erstellt: {args.output.resolve()}")


if __name__ == "__main__":
    main()
