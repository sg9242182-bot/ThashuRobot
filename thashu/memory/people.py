"""Persistent memories associated only with confirmed face identities."""

import time

from memory.storage import load_data, save_data


class PeopleMemory:
    """Stores sparse person facts and deliberately saved events."""

    SEEN_KEY = "people_seen"
    MEMORY_KEY = "person_memories"
    MEMORY_KINDS = {"fact", "event"}
    MAX_TEXT_LENGTH = 240
    MAX_MEMORIES_PER_KIND = 50
    DEFAULT_RECALL_LIMIT = 5

    def __init__(self):
        self.data = load_data()
        self.data.setdefault(self.SEEN_KEY, {})
        self.data.setdefault(self.MEMORY_KEY, {})

    @staticmethod
    def _confirmed_name(name):
        return (
            isinstance(name, str)
            and bool(name.strip())
            and name.strip().casefold() != "unknown"
        )

    def seen(self, name: str):
        """Record a sighting only for a known, confirmed identity."""
        if not self._confirmed_name(name):
            return
        people_seen = self.data.setdefault(self.SEEN_KEY, {})
        entry = people_seen.get(name, {"count": 0})
        people_seen[name] = {
            "last_seen": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
            "count": int(entry.get("count", 0)) + 1,
        }
        save_data(self.data)

    def remember(self, name: str, kind: str, text: str, *, confirmed_identity=False, location=None):
        """Persist an explicit fact/event for one confirmed person."""
        if confirmed_identity is not True or not self._confirmed_name(name):
            raise PermissionError("Memory writes require a confirmed face identity")
        if kind not in self.MEMORY_KINDS:
            raise ValueError("Memory kind must be 'fact' or 'event'")
        if not isinstance(text, str):
            raise ValueError("Memory text must be plain text")
        text = " ".join(text.strip().split())
        if not text or len(text) > self.MAX_TEXT_LENGTH:
            raise ValueError(
                f"Memory text must contain 1 to {self.MAX_TEXT_LENGTH} characters"
            )

        if location is not None:
            if kind != "event" or not isinstance(location, str):
                raise ValueError("A location is allowed only as event text context")
            location = " ".join(location.strip().split())
            if not location or len(location) > 80:
                raise ValueError("Event location must contain 1 to 80 characters")
        if kind != "event" and location is not None:
            raise ValueError("Facts cannot carry an event location")

        people = self.data.setdefault(self.MEMORY_KEY, {})
        if not isinstance(people, dict):
            raise ValueError("Person memory records are malformed")
        person_existed = name in people
        person = people.setdefault(name, {"facts": [], "events": []})
        if not isinstance(person, dict):
            raise ValueError("Person memory record is malformed")
        key = "facts" if kind == "fact" else "events"
        records = person.setdefault(key, [])
        if not isinstance(records, list):
            raise ValueError("Person memory list is malformed")

        def same_record(record):
            if not isinstance(record, dict):
                return False
            existing_text = record.get("text")
            if not isinstance(existing_text, str) or existing_text.casefold() != text.casefold():
                return False
            if kind == "event":
                existing_location = record.get("location")
                if not isinstance(existing_location, str):
                    existing_location = ""
                return existing_location.casefold() == (location or "").casefold()
            return True
        if any(same_record(record) for record in records):
            return False

        original_records = list(records)
        record = {
            "text": text,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if kind == "event" and location is not None:
            record["location"] = location
        records.append(record)
        del records[:-self.MAX_MEMORIES_PER_KIND]
        try:
            save_data(self.data)
        except Exception:
            person[key] = original_records
            if not person_existed and not person.get("facts") and not person.get("events"):
                people.pop(name, None)
            raise
        return True

    def recall(self, name: str, limit=DEFAULT_RECALL_LIMIT, *, kind=None, contains=None):
        """Return a bounded newest-first set, optionally filtered by kind or text."""
        if not self._confirmed_name(name):
            return []
        if kind is not None and kind not in self.MEMORY_KINDS:
            raise ValueError("Memory kind must be 'fact' or 'event'")
        if contains is not None and not isinstance(contains, str):
            raise ValueError("Memory search text must be plain text")
        needle = " ".join((contains or "").casefold().split())
        limit = max(1, min(self.DEFAULT_RECALL_LIMIT, int(limit)))
        people = self.data.get(self.MEMORY_KEY, {})
        if not isinstance(people, dict):
            return []
        person = people.get(name, {})
        if not isinstance(person, dict):
            return []
        records = []
        for item_kind, key in (("fact", "facts"), ("event", "events")):
            if kind is not None and item_kind != kind:
                continue
            entries = person.get(key, [])
            if not isinstance(entries, list):
                continue
            for record in entries:
                if not isinstance(record, dict) or not isinstance(record.get("text"), str):
                    continue
                location = record.get("location")
                if not isinstance(location, str):
                    location = None
                searchable = record["text"].casefold()
                if location:
                    searchable += " " + location.casefold()
                if needle and needle not in searchable:
                    continue
                recalled = {
                    "kind": item_kind,
                    "text": record["text"],
                    "saved_at": record.get("saved_at"),
                }
                if item_kind == "event" and location and location.strip():
                    recalled["location"] = location.strip()
                records.append(recalled)
        records.sort(key=lambda record: record.get("saved_at") or "", reverse=True)
        return records[:limit]

    def forget(self, name: str, kind=None, text=None, *, confirmed=False):
        """Delete one person's memories; callers must require explicit confirmation."""
        if confirmed is not True:
            raise PermissionError("Memory deletion requires explicit confirmation")
        if not self._confirmed_name(name):
            return 0
        if kind is not None and kind not in self.MEMORY_KINDS:
            raise ValueError("Memory kind must be 'fact' or 'event'")
        person = self.data.get(self.MEMORY_KEY, {}).get(name)
        if not isinstance(person, dict):
            return 0

        removed = 0
        keys = (
            [("fact", "facts"), ("event", "events")]
            if kind is None
            else [(kind, "facts" if kind == "fact" else "events")]
        )
        for _, key in keys:
            records = person.get(key, [])
            if text is None:
                removed += len(records)
                person[key] = []
            else:
                kept = [
                    record for record in records
                    if not isinstance(record, dict)
                    or record.get("text", "").casefold() != text.casefold()
                ]
                removed += len(records) - len(kept)
                person[key] = kept
        if removed:
            save_data(self.data)
        return removed

    def get_last_seen(self, name: str):
        return self.data.get(self.SEEN_KEY, {}).get(name, {}).get("last_seen")

    def get_count(self, name: str) -> int:
        return self.data.get(self.SEEN_KEY, {}).get(name, {}).get("count", 0)

    def is_known(self, name: str) -> bool:
        return name in self.data.get(self.SEEN_KEY, {})

    def all_known(self) -> list:
        return list(self.data.get(self.SEEN_KEY, {}).keys())
