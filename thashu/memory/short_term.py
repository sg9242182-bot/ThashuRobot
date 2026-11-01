import time


class ShortTermMemory:
    """Recent conversation context with a bounded size and inactivity expiry."""

    DEFAULT_MAX_SIZE = 5
    DEFAULT_EXPIRATION_SECONDS = 10 * 60

    def __init__(self, max_size=DEFAULT_MAX_SIZE,
                 expiration_seconds=DEFAULT_EXPIRATION_SECONDS):
        self.max_size = max(1, int(max_size))
        self.expiration_seconds = max(1.0, float(expiration_seconds))
        self.memory = []
        self._added_at = []

    def _expire(self, now=None):
        """Drop oldest conversation pairs after the configured idle window."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.expiration_seconds
        while self._added_at and self._added_at[0] <= cutoff:
            self._added_at.pop(0)
            self.memory.pop(0)

    def add(self, user_input: str, response: str):
        """Store a conversation pair, retaining only recent, unexpired context."""
        now = time.monotonic()
        self._expire(now)
        self.memory.append({
            "input": user_input,
            "response": response
        })
        self._added_at.append(now)

        while len(self.memory) > self.max_size:
            self.memory.pop(0)
            self._added_at.pop(0)

    def get_context(self):
        """Return unexpired recent conversation pairs without internal timestamps."""
        self._expire()
        return list(self.memory)
