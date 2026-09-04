"""Create the small set of files refreshed by the Proxmox updater."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from app.web import DATA_FILE, build_ics

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True)
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    # Copy through JSON serialization so a partially written source can never
    # be published and browsers always receive valid UTF-8 JSON.
    (data_dir / "status_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "calendar.ics").write_text(
        build_ics(data.get("schedule", {})), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Dynamische Statusdateien erzeugen")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "publish-data")
    args = parser.parse_args()
    build(args.output.resolve())
    print(f"[OK] Statusdateien erstellt: {args.output.resolve()}")


if __name__ == "__main__":
    main()
