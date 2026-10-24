# core/decision.py

import re


_STOP_PHRASES = {
    "stop",
    "stop now",
    "stop robot",
    "stop the robot",
    "stop moving",
    "stop the robot now",
    "stop moving now",
    "stop all motors",
    "stop the motors",
    "emergency stop",
    "emergency stop now",
    "halt",
    "halt now",
    "halt robot",
    "please stop",
    "please stop now",
    "please stop robot",
    "can you stop",
    "can you stop now",
    "could you stop",
    "could you stop now",
}


def is_stop_command(user_input: str) -> bool:
    """Recognize only explicit stop phrases; avoid matching incidental mentions."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (user_input or "").lower()).strip()
    return normalized in _STOP_PHRASES


_FORWARD_MEDIUM_PHRASES = {
    "forward",
    "go forward",
    "move forward",
    "drive forward",
    "move ahead",
    "drive ahead",
    "please go forward",
    "please move forward",
    "please drive forward",
    "forward medium",
    "medium forward",
    "move forward medium",
    "move forward at medium speed",
    "move forward at normal speed",
    "go forward at medium speed",
    "drive forward at medium speed",
}
_FORWARD_SLOW_PHRASES = {
    "slow forward",
    "forward slow",
    "forward slowly",
    "move forward slow",
    "move forward slowly",
    "move slowly forward",
    "move forward at slow speed",
    "move forward at a slow speed",
    "go forward slowly",
    "go forward at slow speed",
    "drive forward slowly",
    "drive forward at slow speed",
}
_FORWARD_FAST_PHRASES = {
    "fast forward",
    "forward fast",
    "move forward fast",
    "move forward quickly",
    "move quickly forward",
    "move forward at fast speed",
    "move forward at a fast speed",
    "go forward fast",
    "go forward quickly",
    "go forward at fast speed",
    "drive forward fast",
    "drive forward quickly",
    "drive forward at fast speed",
}
_FORWARD_SPEEDS = {
    "slow": 150,
    "medium": 200,
    "fast": 255,
}


def get_forward_speed(user_input: str):
    """Return (speed name, PWM) for a strictly matched forward command, else None."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (user_input or "").lower()).strip()
    if normalized in _FORWARD_SLOW_PHRASES:
        level = "slow"
    elif normalized in _FORWARD_FAST_PHRASES:
        level = "fast"
    elif normalized in _FORWARD_MEDIUM_PHRASES:
        level = "medium"
    else:
        return None
    return level, _FORWARD_SPEEDS[level]


_DIRECTION_COMMANDS = {
    "backward": "BACKWARD",
    "go backward": "BACKWARD",
    "move backward": "BACKWARD",
    "drive backward": "BACKWARD",
    "back up": "BACKWARD",
    "go back": "BACKWARD",
    "move back": "BACKWARD",
    "reverse": "BACKWARD",
    "turn left": "LEFT",
    "turn to the left": "LEFT",
    "rotate left": "LEFT",
    "spin left": "LEFT",
    "left turn": "LEFT",
    "turn right": "RIGHT",
    "turn to the right": "RIGHT",
    "rotate right": "RIGHT",
    "spin right": "RIGHT",
    "right turn": "RIGHT",
}


def get_direction_command(user_input: str):
    """Return a deterministic reverse/turn action for an exact spoken phrase."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (user_input or "").lower()).strip()
    return _DIRECTION_COMMANDS.get(normalized)


def is_forward_command(user_input: str) -> bool:
    """Accept only explicit forward phrases with an optional recognized speed."""
    return get_forward_speed(user_input) is not None


def decide(user_input: str, context=None) -> str:
    """
    Decision logic for Thashu

    Returns:
        str: response OR control signal
    """

    if not user_input:
        return ""

    text = user_input.lower()

    # ===== CONTEXT FOLLOW-UP =====
    if context:
        last = context[-1] if len(context) > 0 else None

        if last:
            last_input = last["input"].lower()

            if "your name" in last_input and "what about yours" in text:
                return "My name is Thashu."

    # ===== SIMPLE COMMAND RULES =====
    if is_stop_command(user_input):
        return "STOP"

    if "move" in text:
        return "MOVE"

    # ===== DEFAULT =====
    return "AI_FALLBACK"