import ftplib
from pathlib import Path

import pytest

from app.build_static import EXPORTS, build, validate_base_url
from app.build_data import build as build_data
from app.deploy_ftp import (
    connection_settings,
    replace_ftp_file,
    replace_sftp_file,
    selected_protocol,
)


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


def test_ftps_replacement_restores_live_file_when_promotion_fails() -> None:
    class FakeFtp:
        def __init__(self) -> None:
            self.files = {"status.json": "old", ".status.json.uploading": "new"}
            self.promotions = 0

        def rename(self, source: str, destination: str) -> None:
            if source == ".status.json.uploading":
                self.promotions += 1
                if self.promotions == 1 or any("backup-" in name for name in self.files):
                    raise ftplib.error_perm("promotion rejected")
            if source not in self.files or destination in self.files:
                raise ftplib.error_perm("rename rejected")
            self.files[destination] = self.files.pop(source)

        def delete(self, name: str) -> None:
            del self.files[name]

    ftp = FakeFtp()
    with pytest.raises(ftplib.error_perm, match="promotion rejected"):
        replace_ftp_file(ftp, ".status.json.uploading", "status.json")

    assert ftp.files["status.json"] == "old"


def test_sftp_replacement_uses_atomic_posix_rename() -> None:
    class FakeSftp:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def posix_rename(self, source: str, destination: str) -> None:
            self.calls.append((source, destination))

        def remove(self, name: str) -> None:
            raise AssertionError(f"live file was removed: {name}")

    sftp = FakeSftp()
    replace_sftp_file(sftp, "/data/.status.json.uploading", "/data/status.json")

    assert sftp.calls == [("/data/.status.json.uploading", "/data/status.json")]
