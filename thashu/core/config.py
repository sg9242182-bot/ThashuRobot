"""Validated environment-backed settings shared by Pi services."""

import os
from pathlib import Path


def _configured_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if value is not None and not value.strip():
        raise ValueError(f"{name} must not be empty")
    return Path(value).expanduser() if value is not None else default.expanduser()


def api_host() -> str:
    host = os.environ.get("THASHU_API_HOST", "127.0.0.1").strip()
    if not host or any(character.isspace() for character in host):
        raise ValueError("THASHU_API_HOST must be a non-empty host name or IP address")
    return host


def api_port() -> int:
    value = os.environ.get("THASHU_API_PORT", "8000")
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("THASHU_API_PORT must be an integer from 1 to 65535") from exc
    if not 1 <= port <= 65535:
        raise ValueError("THASHU_API_PORT must be an integer from 1 to 65535")
    return port


def api_token() -> str | None:
    return os.getenv("THASHU_API_TOKEN")


def api_state_db_path() -> Path:
    configured = os.getenv("THASHU_API_STATE_DB")
    if configured is not None:
        if not configured.strip():
            raise ValueError("THASHU_API_STATE_DB must not be empty")
        return Path(configured).expanduser()

    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return root / "ThashuRobot" / "api_state.sqlite3"

    state_home = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_home / "thashu" / "api_state.sqlite3"


def models_dir() -> Path:
    return _configured_path(
        "THASHU_MODELS_DIR", Path.home() / ".local/share/thashu/models"
    ).resolve()


def data_dir() -> Path:
    return _configured_path("THASHU_DATA_DIR", Path.home() / ".local/share/thashu/data").resolve()


def piper_binary() -> str:
    value = os.environ.get("THASHU_PIPER_BIN", "~/piper/piper/piper").strip()
    if not value:
        raise ValueError("THASHU_PIPER_BIN must not be empty")
    return str(Path(value).expanduser())


def voice_cache_dir() -> Path:
    data_home = Path(os.getenv("XDG_DATA_HOME", "~/.local/share")).expanduser()
    default = data_home / "thashu" / "voice_responses"
    return _configured_path("THASHU_VOICE_CACHE_DIR", default)


def face_match_debug_enabled() -> bool:
    value = os.environ.get("THASHU_FACE_MATCH_DEBUG", "0").strip()
    if value not in {"0", "1"}:
        raise ValueError("THASHU_FACE_MATCH_DEBUG must be 0 or 1")
    return value == "1"


def api_tls_certfile() -> str | None:
    value = os.environ.get("THASHU_API_TLS_CERTFILE")
    if value is not None and not value.strip():
        raise ValueError("THASHU_API_TLS_CERTFILE must not be empty")
    return str(Path(value).expanduser()) if value else None


def api_tls_keyfile() -> str | None:
    value = os.environ.get("THASHU_API_TLS_KEYFILE")
    if value is not None and not value.strip():
        raise ValueError("THASHU_API_TLS_KEYFILE must not be empty")
    return str(Path(value).expanduser()) if value else None


def api_tls_android_trust_confirmed() -> bool:
    """Require explicit operator approval before exposing TLS to the network."""
    value = os.environ.get("THASHU_API_TLS_ANDROID_TRUST_CONFIRMED", "0").strip()
    if value not in {"0", "1"}:
        raise ValueError("THASHU_API_TLS_ANDROID_TRUST_CONFIRMED must be 0 or 1")
    return value == "1"
