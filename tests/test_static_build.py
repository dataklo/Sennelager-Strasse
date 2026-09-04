from pathlib import Path

import pytest

from app.build_static import EXPORTS, build, validate_base_url
from app.build_data import build as build_data
from app.deploy_ftp import connection_settings, selected_protocol


def test_build_writes_every_route_and_static_assets(tmp_path: Path) -> None:
    output = tmp_path / "site"

    build(output, "https://senne.example")

    for target in EXPORTS.values():
        assert (output / target).is_file()
    assert (output / "static/style.css").is_file()
    assert (output / "static/app.js").is_file()
    assert (output / "data/status_data.json").is_file()
    assert "https://senne.example/" in (output / "index.html").read_text(encoding="utf-8")
    assert "https://senne.example/sitemap.xml" in (output / "robots.txt").read_text(encoding="utf-8")
    assert "noindex, nofollow" in (output / "impressum/index.html").read_text(encoding="utf-8")
    assert "X-Robots-Tag" in (output / "impressum/.htaccess").read_text(encoding="utf-8")


@pytest.mark.parametrize("value", ["example.de", "ftp://example.de", "https://example.de/path"])
def test_validate_base_url_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_base_url(value)


def test_data_build_contains_only_runtime_files(tmp_path: Path) -> None:
    output = tmp_path / "runtime"

    build_data(output)

    assert sorted(str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()) == [
        "calendar.ics",
        "data/status_data.json",
    ]


def test_port_22_selects_sftp_when_protocol_is_not_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEPLOY_PROTOCOL", raising=False)
    monkeypatch.setenv("FTP_PORT", "22")
    assert selected_protocol() == "sftp"


def test_port_21_selects_ftps_when_protocol_is_not_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEPLOY_PROTOCOL", raising=False)
    monkeypatch.setenv("FTP_PORT", "21")
    assert selected_protocol() == "ftps"


def test_upload_url_contains_protocol_server_port_and_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FTP_URL", "sftp://upload.example:22/public_html/site")
    assert selected_protocol() == "sftp"
    assert connection_settings() == ("upload.example", 22, "/public_html/site")
