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



_FOLLOW_START_PHRASES = {
    "follow me",
    "start following",
    "start follow mode",
    "follow that person",
}
_FOLLOW_STOP_PHRASES = {
    "stop following",
    "stop follow mode",
    "cancel following",
}
_FOLLOW_SELECTION_PHRASES = {
    "follow left": "LEFT",
    "follow the person on the left": "LEFT",
    "follow person on the left": "LEFT",
    "select the person on the left": "LEFT",
    "follow center": "CENTER",
    "follow the person in the center": "CENTER",
    "follow person in the center": "CENTER",
    "select the person in the center": "CENTER",
    "follow right": "RIGHT",
    "follow the person on the right": "RIGHT",
    "follow person on the right": "RIGHT",
    "select the person on the right": "RIGHT",
}


def get_follow_command(user_input: str):
    """Return an exact, deterministic follow-mode command or None."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (user_input or "").lower()).strip()
    if normalized in _FOLLOW_START_PHRASES:
        return "START"
    if normalized in _FOLLOW_STOP_PHRASES:
        return "STOP"
    return _FOLLOW_SELECTION_PHRASES.get(normalized)


_RECOGNITION_ENROLL_PHRASES = {
    "remember me",
    "remember this person",
    "remember this face",
    "enroll me",
    "register my face",
}
_RECOGNITION_CANCEL_PHRASES = {
    "cancel enrollment",
    "cancel registration",
    "forget it",
    "never mind",
}
_RECOGNITION_YES_PHRASES = {"yes", "yes confirm", "confirm", "save it"}
_RECOGNITION_NO_PHRASES = {"no", "no cancel", "cancel", "do not save"}


def _normalize_phrase(user_input):
    return re.sub(r"[^a-z0-9']+", " ", (user_input or "").lower()).strip()


def get_recognition_command(user_input):
    """Return only exact, deterministic person-enrollment control phrases."""
    normalized = _normalize_phrase(user_input)
    if normalized in _RECOGNITION_ENROLL_PHRASES:
        return "ENROLL"
    if normalized in _RECOGNITION_CANCEL_PHRASES:
        return "CANCEL"
    if normalized in _RECOGNITION_YES_PHRASES:
        return "CONFIRM"
    if normalized in _RECOGNITION_NO_PHRASES:
        return "REJECT"
    return None


def get_remove_identity_name(user_input):
    """Return a name only for an explicit request to remove its stored face identity."""
    normalized = _normalize_phrase(user_input)
    if normalized in _RECOGNITION_CANCEL_PHRASES:
        return None
    match = re.fullmatch(r"(?:forget|remove|delete) ([a-z][a-z .'-]{0,62})", normalized)
    if not match:
        return None
    name = " ".join(match.group(1).split()).strip(" .'-")
    if not name or len(name.split()) > 4:
        return None
    return name.title()


def get_registration_name(user_input):
    """Extract a short user-provided name only from explicit self-identification."""
    normalized = _normalize_phrase(user_input)
    match = re.fullmatch(r"(?:my name is|i am|i'm|call me) ([a-z][a-z .'-]{0,62})", normalized)
    if not match:
        return None
    name = " ".join(match.group(1).split()).strip(" .'-")
    if not name or len(name.split()) > 4:
        return None
    return name.title()


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
    # Common Whisper mis-transcriptions observed during turn-command tests.
    "on left": "LEFT",
    "done left": "LEFT",
    "turn right": "RIGHT",
    "turn to the right": "RIGHT",
    "rotate right": "RIGHT",
    "spin right": "RIGHT",
    "right turn": "RIGHT",
    "on right": "RIGHT",
    "done right": "RIGHT",
}


def get_direction_command(user_input: str):
    """Return a deterministic reverse/turn action for an exact spoken phrase."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (user_input or "").lower()).strip()
    return _DIRECTION_COMMANDS.get(normalized)


_LOOK_COMMANDS = {
    "look up": "UP",
    "look upward": "UP",
    "look to the left": "LEFT",
    "look left": "LEFT",
    "look left side": "LEFT",
    "look to the left side": "LEFT",
    "look on the left": "LEFT",
    "look right": "RIGHT",
    "look to the right": "RIGHT",
    "look right side": "RIGHT",
    "look to the right side": "RIGHT",
    "look on the right": "RIGHT",
    "look down": "DOWN",
    "look downward": "DOWN",
    "look straight": "CENTER",
    "look straight ahead": "CENTER",
    "look center": "CENTER",
    "look at the center": "CENTER",
}


def get_look_command(user_input: str):
    """Return a strictly matched head-servo look direction or None."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (user_input or "").lower()).strip()
    return _LOOK_COMMANDS.get(normalized)


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