"""Machine-local JSON storage for persistent Thashu memories."""

import json
import os
import tempfile

from core.model_paths import data_path, project_path


DB_PATH = data_path("memory_db", "long_term.json")
LEGACY_DB_PATHS = tuple(dict.fromkeys((
    os.path.abspath("data/memory_db/long_term.json"),
    project_path("data", "memory_db", "long_term.json"),
)))
_load_error = None


def load_data():
    """Load the canonical store, falling back to existing checkout-local data."""
    global _load_error
    _load_error = None
    candidates = (DB_PATH,) + LEGACY_DB_PATHS
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("memory database root must be a JSON object")
            return data
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            _load_error = f"{path}: {exc}"
            print(f"[MEMORY] Store could not be read; preserving it: {_load_error}")
            return {}
    return {}


def save_data(data):
    """Atomically write persistent memory outside the Git checkout."""
    if _load_error is not None:
        raise OSError(f"Refusing to overwrite an unreadable memory store: {_load_error}")
    if not isinstance(data, dict):
        raise TypeError("memory data must be a dictionary")

    directory = os.path.dirname(DB_PATH)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".long-term-", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, DB_PATH)
        try:
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
