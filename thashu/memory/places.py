"""Persistent, user-labeled place records, stored separately from person memory.

Visual references are added by the vision pipeline in a later Phase 8 step. A
label with no references is never sufficient to recognize a place.
"""

import copy
import json
import os
import tempfile
import time

from core.model_paths import data_path


PLACES_PATH = data_path("places.json")
MAX_LABEL_LENGTH = 48


def normalize_place_label(label):
    """Validate a user-supplied label while retaining its readable spelling."""
    if not isinstance(label, str):
        raise ValueError("Place label must be text")
    label = " ".join(label.strip().strip(" .!?").split())
    if not label or len(label) > MAX_LABEL_LENGTH:
        raise ValueError(f"Place label must contain 1 to {MAX_LABEL_LENGTH} characters")
    if any(ord(character) < 32 for character in label):
        raise ValueError("Place label contains a control character")
    return label


class PlaceMemory:
    """Machine-local place labels and compact visual references."""

    def __init__(self, path=None):
        self.path = os.fspath(path or PLACES_PATH)
        self._load_error = None
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict) or not isinstance(data.get("places"), dict):
                raise ValueError("place memory root must contain a places object")
            data.setdefault("schema_version", 1)
            return data
        except FileNotFoundError:
            return {"schema_version": 1, "places": {}}
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._load_error = f"{self.path}: {exc}"
            print(f"[PLACE] Store could not be read; preserving it: {self._load_error}")
            return {"schema_version": 1, "places": {}}

    def _save(self):
        if self._load_error is not None:
            raise OSError(f"Refusing to overwrite an unreadable place store: {self._load_error}")
        directory = os.path.dirname(self.path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".places-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
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

    @staticmethod
    def _key(label):
        return normalize_place_label(label).casefold()

    def labels(self):
        return [
            record["label"]
            for record in self.data["places"].values()
            if isinstance(record, dict) and isinstance(record.get("label"), str)
        ]

    def get(self, label):
        record = self.data["places"].get(self._key(label))
        return record if isinstance(record, dict) else None

    def save_views(self, label, views):
        """Persist confirmed multi-view descriptors for a user-labeled place."""
        label = normalize_place_label(label)
        if not isinstance(views, list) or not views:
            raise ValueError("At least one captured visual view is required")
        if any(not isinstance(view, str) or not view for view in views):
            raise ValueError("Visual views must be nonempty encoded descriptors")

        original = self.data
        self.data = copy.deepcopy(self.data)
        key = label.casefold()
        record = self.data["places"].get(key)
        if record is None:
            record = {
                "label": label,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "views": [],
            }
            self.data["places"][key] = record
        record.setdefault("views", []).extend(views)
        # Bound persistent storage while retaining a spread of recent views.
        record["views"] = record["views"][-12:]
        try:
            self._save()
        except Exception:
            self.data = original
            raise
        return len(record["views"])

    def rename(self, old_label, new_label):
        """Relabel one existing place without disturbing any captured views."""
        old_key = self._key(old_label)
        new_label = normalize_place_label(new_label)
        new_key = new_label.casefold()
        if old_key not in self.data["places"]:
            raise KeyError(old_label)
        if new_key != old_key and new_key in self.data["places"]:
            raise FileExistsError(new_label)
        original = self.data
        self.data = copy.deepcopy(self.data)
        record = self.data["places"].pop(old_key)
        record["label"] = new_label
        self.data["places"][new_key] = record
        try:
            self._save()
        except Exception:
            self.data = original
            raise
        return new_label
