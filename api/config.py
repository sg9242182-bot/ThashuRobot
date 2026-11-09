"""API-facing aliases for the shared, validated Pi settings."""

import ipaddress
from pathlib import Path

from thashu.core.config import (
    api_state_db_path,
    api_token,
    api_tls_certfile,
    api_tls_keyfile,
)


def get_api_token() -> str | None:
    """Read the token at request time; never cache the secret in logs."""
    return api_token()


def get_api_state_db_path() -> Path:
    """Choose a writable per-user path for durable API command records."""
    return api_state_db_path()


def get_api_tls_files() -> tuple[str | None, str | None]:
    """Return the configured TLS certificate/key pair."""
    certfile = api_tls_certfile()
    keyfile = api_tls_keyfile()
    if bool(certfile) != bool(keyfile):
        raise ValueError("Configure both THASHU_API_TLS_CERTFILE and THASHU_API_TLS_KEYFILE")
    return certfile, keyfile


def validate_api_tls_bind(
    host: str,
    certfile: str | None,
    keyfile: str | None,
    android_trust_confirmed: bool = False,
) -> None:
    """Require TLS files and explicit Android trust approval for network binds."""
    try:
        loopback = host.lower() == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback and not (certfile and keyfile):
        raise ValueError(
            "Refusing non-loopback API without TLS; set both certificate and key paths"
        )
    if not loopback and not android_trust_confirmed:
        raise ValueError(
            "Refusing non-loopback API until its hostname and Android certificate trust are confirmed"
        )
