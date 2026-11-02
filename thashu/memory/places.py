"""Persistent, user-labeled place records, stored separately from person memory.

Visual references are added by the vision pipeline in a later Phase 8 step. A
label with no references is never sufficient to recognize a place.
"""

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
        self.path = path or PLACES_PATH
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {"schema_version": 1, "places": {}}
        if not isinstance(data, dict) or not isinstance(data.get("places"), dict):
            raise ValueError("Place memory file has an invalid structure")
        data.setdefault("schema_version", 1)
        return data

    def _save(self):
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
        return [record["label"] for record in self.data["places"].values()]

    def get(self, label):
        return self.data["places"].get(self._key(label))

    def add_label(self, label):
        """Save a confirmed label, initially with no recognition references."""
        label = normalize_place_label(label)
        key = label.casefold()
        if key in self.data["places"]:
            return False
        self.data["places"][key] = {
            "label": label,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "views": [],
        }
        self._save()
        return True

    def rename(self, old_label, new_label):
        """Relabel one existing place without disturbing any captured views."""
        old_key = self._key(old_label)
        new_label = normalize_place_label(new_label)
        new_key = new_label.casefold()
        if old_key not in self.data["places"]:
            raise KeyError(old_label)
        if new_key != old_key and new_key in self.data["places"]:
            raise FileExistsError(new_label)
        record = self.data["places"].pop(old_key)
        record["label"] = new_label
        self.data["places"][new_key] = record
        self._save()
        return new_label
