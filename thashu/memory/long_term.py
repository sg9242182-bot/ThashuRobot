# memory/long_term.py

from memory.storage import load_data, save_data


class LongTermMemory:
    def __init__(self):
        self.data = load_data()

    # ===== GET =====
    def get(self, key, default=None):
        return self.data.get(key, default)

    # ===== SET =====
    def set(self, key, value):
        self.data[key] = value
        save_data(self.data)

    # ===== DELETE =====
    def delete(self, key):
        if key in self.data:
            del self.data[key]
            save_data(self.data)

    # ===== DEBUG =====
    def show_all(self):
        return self.data