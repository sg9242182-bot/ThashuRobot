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

    def remember(self, name: str, kind: str, text: str, *, confirmed_identity=False):
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

        people = self.data.setdefault(self.MEMORY_KEY, {})
        person = people.setdefault(name, {"facts": [], "events": []})
        records = person.setdefault("facts" if kind == "fact" else "events", [])
        if any(record.get("text", "").casefold() == text.casefold() for record in records):
            return False

        records.append({
            "text": text,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        del records[:-self.MAX_MEMORIES_PER_KIND]
        save_data(self.data)
        return True

    def recall(self, name: str, limit=DEFAULT_RECALL_LIMIT):
        """Return a small, newest-first set of saved facts and events."""
        if not self._confirmed_name(name):
            return []
        limit = max(1, min(self.DEFAULT_RECALL_LIMIT, int(limit)))
        person = self.data.get(self.MEMORY_KEY, {}).get(name, {})
        records = []
        for kind, key in (("fact", "facts"), ("event", "events")):
            for record in person.get(key, []):
                if isinstance(record, dict) and isinstance(record.get("text"), str):
                    records.append({
                        "kind": kind,
                        "text": record["text"],
                        "saved_at": record.get("saved_at"),
                    })
        records.sort(key=lambda record: record.get("saved_at") or "", reverse=True)
        return records[:limit]

    def forget(self, name: str, kind=None, text=None):
        """Delete one person's memories; callers must require explicit confirmation."""
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
