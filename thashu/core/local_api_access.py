"""Provisioning material and addressing for the local HTTPS API.

The robot API stays on loopback for the existing Caddy/Tailscale path. This
module prepares a second, TLS-only listener on the current Wi-Fi address for
app-only local hotspot use. Secrets are stored outside the repository.
"""
from __future__ import annotations

import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import tempfile


def enabled() -> bool:
    value = os.environ.get("THASHU_API_LOCAL_ACCESS", "0").strip()
    if value not in {"0", "1"}:
        raise ValueError("THASHU_API_LOCAL_ACCESS must be 0 or 1")
    return value == "1"


def wifi_interface() -> str:
    value = os.environ.get("THASHU_API_WIFI_INTERFACE", "wlan0").strip()
    if not value or any(ch.isspace() for ch in value) or "/" in value:
        raise ValueError("THASHU_API_WIFI_INTERFACE must be an interface name")
    return value


def local_api_port() -> int:
    try:
        port = int(os.environ.get("THASHU_API_LOCAL_PORT", "8443"))
    except ValueError as exc:
        raise ValueError("THASHU_API_LOCAL_PORT must be an integer from 1 to 65535") from exc
    if not 1 <= port <= 65535:
        raise ValueError("THASHU_API_LOCAL_PORT must be an integer from 1 to 65535")
    return port


def state_dir() -> Path:
    configured = os.environ.get("THASHU_LOCAL_API_STATE_DIR")
    path = Path(configured).expanduser() if configured else (
        Path.home() / ".local/share/thashu/local_api"
    )
    return path


def token_path() -> Path:
    return state_dir() / "api.token"


def ipv4_for_interface(interface: str | None = None) -> str | None:
    """Return one global IPv4 address assigned to the configured Wi-Fi device."""
    name = interface or wifi_interface()
    request = struct_ifreq(name)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        import fcntl
        response = fcntl.ioctl(sock.fileno(), 0x8915, request)
    except OSError:
        return None
    finally:
        sock.close()
    address = socket.inet_ntoa(response[20:24])
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return None
    if parsed.is_loopback or parsed.is_unspecified or parsed.is_link_local:
        return None
    return address


def struct_ifreq(name: str) -> bytes:
    encoded = name.encode("ascii", errors="strict")
    if len(encoded) >= 16:
        raise ValueError("network interface name is too long")
    return encoded + (b"\0" * (16 - len(encoded))) + (b"\0" * 24)


def _owner() -> tuple[int, int] | None:
    username = os.environ.get("THASHU_LOCAL_API_OWNER")
    if not username:
        return None
    import pwd
    account = pwd.getpwnam(username)
    return account.pw_uid, account.pw_gid


def _apply_owner(path: Path) -> None:
    if os.geteuid() != 0:
        return
    owner = _owner()
    if owner is not None:
        os.chown(path, owner[0], owner[1])


def _ensure_dir() -> Path:
    directory = state_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    _apply_owner(directory)
    return directory


def _atomic_secret(path: Path, value: str) -> None:
    temp_name = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
        _apply_owner(path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def ensure_api_token() -> str:
    """Return a stable per-Pi token, syncing an explicitly configured token."""
    _ensure_dir()
    path = token_path()
    configured = os.environ.get("THASHU_API_TOKEN")
    if configured:
        if not path.exists() or path.read_text(encoding="utf-8").strip() != configured:
            _atomic_secret(path, configured)
        return configured
    try:
        token = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        token = ""
    if not token:
        token = secrets.token_urlsafe(32)
        _atomic_secret(path, token)
    if len(token) < 32 or any(ch.isspace() for ch in token):
        raise ValueError("The persisted local API token is invalid")
    return token


def api_token_from_file() -> str | None:
    try:
        value = token_path().read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def _certificate_paths() -> tuple[Path, Path, Path]:
    directory = _ensure_dir()
    return (
        directory / "server.crt",
        directory / "server.key",
        directory / "server-ip.txt",
    )


def ensure_local_api_material(ip_address: str) -> dict[str, str]:
    """Generate/retain a pinned TLS cert and token for the current Wi-Fi IP."""
    address = str(ipaddress.ip_address(ip_address))
    if ":" in address:
        raise ValueError("Local API currently supports IPv4 Wi-Fi addresses only")
    directory = _ensure_dir()
    lock_path = directory / ".material.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        _apply_owner(lock_path)
        fcntl.flock(fd, fcntl.LOCK_EX)
        cert_path, key_path, ip_path = _certificate_paths()
        token = ensure_api_token()
        current_ip = ip_path.read_text(encoding="ascii").strip() if ip_path.exists() else ""
        if not cert_path.exists() or not key_path.exists() or current_ip != address:
            with tempfile.TemporaryDirectory(prefix=".tls-", dir=directory) as tmp:
                temp = Path(tmp)
                temp_cert = temp / "server.crt"
                temp_key = temp / "server.key"
                completed = subprocess.run(
                    [
                        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-sha256", "-days", "3650",
                        "-subj", f"/CN={address}",
                        "-addext", f"subjectAltName=IP:{address}",
                        "-keyout", str(temp_key), "-out", str(temp_cert),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                    check=False,
                )
                if completed.returncode != 0:
                    raise RuntimeError("Could not create the local HTTPS certificate")
                os.chmod(temp_key, 0o600)
                os.chmod(temp_cert, 0o644)
                _apply_owner(temp_key)
                _apply_owner(temp_cert)
                os.replace(temp_cert, cert_path)
                os.replace(temp_key, key_path)
                _atomic_secret(ip_path, address)
        pem = ssl.PEM_cert_to_DER_cert(cert_path.read_text(encoding="ascii"))
        fingerprint = hashlib.sha256(pem).hexdigest()
        _apply_owner(cert_path)
        _apply_owner(key_path)
        os.chmod(cert_path, 0o644)
        os.chmod(key_path, 0o600)
        return {
            "api_base_url": f"https://{address}:{local_api_port()}",
            "server_cert_sha256": fingerprint,
            "api_token": token,
            "certfile": str(cert_path),
            "keyfile": str(key_path),
        }
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

def connection_info() -> bytes:
    """Return the BLE handoff only after Wi-Fi has a local address."""
    address = ipv4_for_interface()
    if address is None:
        raise RuntimeError("Wi-Fi address is not ready")
    material = ensure_local_api_material(address)
    public = {
        "api_base_url": material["api_base_url"],
        "server_cert_sha256": material["server_cert_sha256"],
        "api_token": material["api_token"],
    }
    payload = json.dumps(public, separators=(",", ":")).encode("utf-8")
    if len(payload) > 500:
        raise RuntimeError("Local API handoff exceeds BLE payload limit")
    return payload
