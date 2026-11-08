"""API-facing aliases for the shared, validated Pi settings."""

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
