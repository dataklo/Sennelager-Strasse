import ftplib
from pathlib import Path

import pytest

from app.build_static import EXPORTS, build, validate_base_url
from app.build_data import build as build_data
from app.deploy_ftp import connection_settings, selected_protocol, upload_ftp_tree, upload_sftp_tree
from app.web import build_ics


def test_build_writes_every_route_and_static_assets(tmp_path: Path) -> None:
    output = tmp_path / "site"

    build(output, "https://senne.example")

    for target in EXPORTS.values():
        assert (output / target).is_file()
    assert (output / "static/style.css").is_file()
    assert (output / "static/app.js").is_file()
    assert (output / "data/status_data.json").is_file()
    assert "https://senne.example/" in (output / "index.html").read_text(encoding="utf-8")
    index_html = (output / "index.html").read_text(encoding="utf-8")
    assert 'src="/static/ads/left.png"' in index_html
    assert 'src="/static/ads/right.png"' in index_html
    assert 'class="ad-placeholder" hidden' not in index_html
    assert "Hier könnte Ihre Werbung stehen" in index_html
    assert "Werbeplatz verfügbar" in index_html
    assert "https://senne.example/sitemap.xml" in (output / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /datenschutz" in (output / "robots.txt").read_text(encoding="utf-8")
    assert "noindex, nofollow" in (output / "impressum/index.html").read_text(encoding="utf-8")
    assert "X-Robots-Tag" in (output / "impressum/.htaccess").read_text(encoding="utf-8")
    assert "X-Robots-Tag" in (output / "datenschutz/.htaccess").read_text(encoding="utf-8")


def test_calendar_uses_short_event_titles() -> None:
    calendar = build_ics({"2026-09-04": {"status": "closed"}})
    assert "SUMMARY:Senne – " in calendar
    assert "SUMMARY:Senne Öffnungszeiten" not in calendar


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


def test_ftps_failed_replacement_never_moves_live_file(tmp_path: Path) -> None:
    (tmp_path / "status_data.json").write_text("new", encoding="utf-8")

    class FakeFtp:
        files = {"status_data.json": b"old"}
        operations = []

        def pwd(self): return "/"
        def cwd(self, _path): return None
        def storbinary(self, command, handle): self.files[command.removeprefix("STOR ")] = handle.read()
        def delete(self, name):
            self.operations.append(("delete", name))
            if name not in self.files:
                raise ftplib.error_perm("missing")
            del self.files[name]
        def rename(self, source, destination):
            self.operations.append(("rename", source, destination))
            if source == ".status_data.json.uploading" and destination == "status_data.json":
                raise ftplib.error_perm("commit rejected")
            if source not in self.files:
                raise ftplib.error_perm("missing")
            self.files[destination] = self.files.pop(source)

    ftp = FakeFtp()
    with pytest.raises(Exception, match="commit rejected"):
        upload_ftp_tree(ftp, tmp_path)
    assert ftp.files["status_data.json"] == b"old"
    assert ("rename", "status_data.json", ".status_data.json.previous") not in ftp.operations
    assert ("delete", "status_data.json") not in ftp.operations


def test_sftp_failed_replacement_never_moves_live_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "calendar.ics"
    local.write_text("new", encoding="utf-8")
    monkeypatch.setenv("FTP_URL", "sftp://upload.example/site")

    class FakeSftp:
        files = {"/site/calendar.ics": b"old"}
        operations = []
        def stat(self, _path): return object()
        def mkdir(self, _path): return None
        def put(self, source, destination): self.files[destination] = Path(source).read_bytes()
        def posix_rename(self, _source, _destination): raise OSError("unsupported")
        def remove(self, path):
            self.operations.append(("remove", path))
            if path not in self.files:
                raise OSError("missing")
            del self.files[path]
        def rename(self, source, destination):
            self.operations.append(("rename", source, destination))
            if source.endswith(".uploading") and destination == "/site/calendar.ics":
                raise OSError("commit rejected")
            if source not in self.files:
                raise OSError("missing")
            self.files[destination] = self.files.pop(source)

    sftp = FakeSftp()
    with pytest.raises(OSError, match="commit rejected"):
        upload_sftp_tree(sftp, tmp_path)
    assert sftp.files["/site/calendar.ics"] == b"old"
    assert ("rename", "/site/calendar.ics", "/site/.calendar.ics.previous") not in sftp.operations
    assert ("remove", "/site/calendar.ics") not in sftp.operations
