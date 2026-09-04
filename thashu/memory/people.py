from memory.storage import load_data, save_data
import time


class PeopleMemory:
    """
    Tracks who Thashu has seen, when, and how many times.
    Stored in long_term memory DB.
    """
    KEY = "people_seen"

    def __init__(self):
        self.data = load_data()
        if self.KEY not in self.data:
            self.data[self.KEY] = {}

    def seen(self, name: str):
        """Call when a known face is detected."""
        if not name or name == "Unknown":
            return
        entry = self.data[self.KEY].get(name, {"count": 0})
        self.data[self.KEY][name] = {
            "last_seen": time.strftime("%Y-%m-%d %H:%M"),
            "count":     entry["count"] + 1
        }
        save_data(self.data)

    def get_last_seen(self, name: str) -> str:
        return self.data[self.KEY].get(name, {}).get("last_seen", None)

    def get_count(self, name: str) -> int:
        return self.data[self.KEY].get(name, {}).get("count", 0)

    def is_known(self, name: str) -> bool:
        return name in self.data[self.KEY]

    def all_known(self) -> list:
        return list(self.data[self.KEY].keys())