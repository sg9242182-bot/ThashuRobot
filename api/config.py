"""Shared environment-backed settings for the Pi API."""

import os
from pathlib import Path


def get_api_token() -> str | None:
    """Read the API token from the process environment.

    Read when each request is handled so tests and controlled local
    configuration changes see the current process environment.
    """
    return os.getenv("THASHU_API_TOKEN")


def get_api_state_db_path() -> Path:
    """Choose a writable per-user path for durable API command records."""
    configured = os.getenv("THASHU_API_STATE_DB")
    if configured:
        return Path(configured).expanduser()

    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return root / "ThashuRobot" / "api_state.sqlite3"

    state_home = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_home / "thashu" / "api_state.sqlite3"
