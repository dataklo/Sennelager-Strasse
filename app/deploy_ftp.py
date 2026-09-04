"""Upload a build using explicit FTPS (21) or SFTP over SSH (22)."""

from __future__ import annotations

import argparse
import ftplib
import os
import posixpath
import ssl
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Umgebungsvariable {name} fehlt")
    return value


def selected_protocol() -> str:
    deployment_url = os.environ.get("FTP_URL", "").strip()
    if deployment_url:
        scheme = urlparse(deployment_url).scheme.lower()
        if scheme in {"ftps", "sftp"}:
            return scheme
    configured = os.environ.get("DEPLOY_PROTOCOL", "").strip().lower()
    if not configured:
        configured = "sftp" if os.environ.get("FTP_PORT") == "22" else "ftps"
    if configured not in {"ftps", "sftp"}:
        raise RuntimeError("DEPLOY_PROTOCOL muss 'ftps' oder 'sftp' sein")
    return configured


def connection_settings() -> tuple[str, int, str]:
    deployment_url = os.environ.get("FTP_URL", "").strip()
    protocol = selected_protocol()
    if deployment_url:
        parsed = urlparse(deployment_url)
        if not parsed.hostname:
            raise RuntimeError("FTP_URL enthält keinen Servernamen")
        return parsed.hostname, parsed.port or (22 if protocol == "sftp" else 21), unquote(parsed.path) or "/"
    return (
        required_env("FTP_HOST"),
        int(os.environ.get("FTP_PORT", "22" if protocol == "sftp" else "21")),
        os.environ.get("FTP_REMOTE_DIR", "/"),
    )


def connect_ftps() -> ftplib.FTP:
    host, port, remote_dir = connection_settings()
    ftp = ftplib.FTP_TLS(context=ssl.create_default_context())
    ftp.connect(host, port, timeout=30)
    ftp.login(required_env("FTP_USER"), required_env("FTP_PASSWORD"))
    ftp.prot_p()
    ftp.set_pasv(True)
    ftp.cwd(remote_dir)
    return ftp


def ensure_ftp_directory(ftp: ftplib.FTP, base: str, relative: PurePosixPath) -> None:
    ftp.cwd(base)
    for part in relative.parts:
        if part in {"", "."}:
            continue
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def upload_ftp_tree(ftp: ftplib.FTP, source: Path) -> int:
    base = ftp.pwd()
    count = 0
    for local_file in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = PurePosixPath(local_file.relative_to(source).as_posix())
        ensure_ftp_directory(ftp, base, relative.parent)
        temporary_name = f".{relative.name}.uploading"
        with local_file.open("rb") as handle:
            ftp.storbinary(f"STOR {temporary_name}", handle)
        try:
            ftp.delete(relative.name)
        except ftplib.error_perm:
            pass
        ftp.rename(temporary_name, relative.name)
        count += 1
    ftp.cwd(base)
    return count


def connect_sftp() -> tuple[Any, Any]:
    import paramiko

    host, port, _ = connection_settings()
    known_hosts = Path(os.environ.get("SFTP_KNOWN_HOSTS", "/etc/sennelager-range-known-hosts"))
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    known_hosts.touch(mode=0o600, exist_ok=True)

    client = paramiko.SSHClient()
    client.load_host_keys(str(known_hosts))
    # Trust on first use, then persist and verify that exact key on every later run.
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        host,
        port=port,
        username=required_env("FTP_USER"),
        password=required_env("FTP_PASSWORD"),
        timeout=30,
        banner_timeout=30,
        auth_timeout=30,
        look_for_keys=False,
        allow_agent=False,
    )
    return client, client.open_sftp()


def ensure_sftp_directory(sftp: Any, directory: str) -> None:
    current = "/" if directory.startswith("/") else "."
    for part in PurePosixPath(directory).parts:
        if part in {"", ".", "/"}:
            continue
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


def upload_sftp_tree(sftp: Any, source: Path) -> int:
    _, _, base = connection_settings()
    ensure_sftp_directory(sftp, base)
    count = 0
    for local_file in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = local_file.relative_to(source).as_posix()
        remote_file = posixpath.join(base, relative)
        ensure_sftp_directory(sftp, posixpath.dirname(remote_file))
        temporary = posixpath.join(posixpath.dirname(remote_file), f".{posixpath.basename(remote_file)}.uploading")
        sftp.put(str(local_file), temporary)
        try:
            sftp.remove(remote_file)
        except OSError:
            pass
        sftp.rename(temporary, remote_file)
        count += 1
    return count


def deploy(source: Path) -> int:
    if not source.is_dir():
        raise RuntimeError(f"Build-Verzeichnis fehlt: {source}")
    if selected_protocol() == "sftp":
        client, sftp = connect_sftp()
        try:
            return upload_sftp_tree(sftp, source)
        finally:
            sftp.close()
            client.close()

    ftp = connect_ftps()
    try:
        return upload_ftp_tree(ftp, source)
    finally:
        try:
            ftp.quit()
        except ftplib.all_errors:
            ftp.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Website per FTPS (21) oder SFTP (22) hochladen")
    parser.add_argument("source", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    count = deploy(args.source.resolve())
    print(f"[OK] {count} Dateien per {selected_protocol().upper()} hochgeladen")


if __name__ == "__main__":
    main()
