from collections import defaultdict
from threading import RLock


class EventBus:
    """Small in-process publish/subscribe bus for runtime coordination."""

    def __init__(self):
        self._subscribers = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name, callback):
        if not event_name or not callable(callback):
            raise ValueError("event_name and callable callback are required")

        with self._lock:
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name, callback):
        with self._lock:
            callbacks = self._subscribers.get(event_name, [])
            if callback in callbacks:
                callbacks.remove(callback)
            if not callbacks and event_name in self._subscribers:
                del self._subscribers[event_name]

    def publish(self, event_name, payload=None):
        with self._lock:
            callbacks = tuple(self._subscribers.get(event_name, ()))

        for callback in callbacks:
            callback(payload)

    def clear(self):
        with self._lock:
            self._subscribers.clear()
