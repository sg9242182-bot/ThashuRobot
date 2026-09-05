from enum import Enum
from threading import Lock


class RuntimeState(str, Enum):
    IDLE = "IDLE"
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    RETURN_TO_IDLE = "RETURN_TO_IDLE"


class StateTransitionError(ValueError):
    """Raised when an invalid runtime state transition is requested."""


class RuntimeStateMachine:
    """Owns Thashu's approved runtime states and valid transitions."""

    _TRANSITIONS = {
        RuntimeState.IDLE: {RuntimeState.WAKE_DETECTED},
        RuntimeState.WAKE_DETECTED: {RuntimeState.LISTENING},
        RuntimeState.LISTENING: {
            RuntimeState.THINKING,
            RuntimeState.RETURN_TO_IDLE,
        },
        RuntimeState.THINKING: {
            RuntimeState.SPEAKING,
            RuntimeState.RETURN_TO_IDLE,
        },
        RuntimeState.SPEAKING: {RuntimeState.RETURN_TO_IDLE},
        RuntimeState.RETURN_TO_IDLE: {RuntimeState.IDLE},
    }

    def __init__(self, initial_state=RuntimeState.IDLE):
        self._lock = Lock()
        self._state = self._coerce_state(initial_state)

    @staticmethod
    def _coerce_state(state):
        if isinstance(state, RuntimeState):
            return state
        try:
            return RuntimeState(state)
        except ValueError as exc:
            raise ValueError(f"Unknown runtime state: {state!r}") from exc

    @property
    def current(self):
        with self._lock:
            return self._state

    def can_transition_to(self, target_state):
        target = self._coerce_state(target_state)
        with self._lock:
            return target in self._TRANSITIONS[self._state]

    def transition_to(self, target_state):
        target = self._coerce_state(target_state)
        with self._lock:
            if target not in self._TRANSITIONS[self._state]:
                raise StateTransitionError(
                    f"Invalid transition: {self._state.value} -> {target.value}"
                )
            previous = self._state
            self._state = target
            return previous, target

    def valid_transitions(self):
        with self._lock:
            return frozenset(self._TRANSITIONS[self._state])
