"""API-facing aliases for the shared, validated Pi settings."""

from pathlib import Path

from thashu.core.config import api_state_db_path, api_token


def get_api_token() -> str | None:
    """Read the token at request time; never cache the secret in logs."""
    return api_token()


def get_api_state_db_path() -> Path:
    """Choose a writable per-user path for durable API command records."""
    return api_state_db_path()
