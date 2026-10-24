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


_FORWARD_PHRASES = {
    "forward",
    "go forward",
    "move forward",
    "drive forward",
    "move ahead",
    "drive ahead",
    "please go forward",
    "please move forward",
    "please drive forward",
}


def is_forward_command(user_input: str) -> bool:
    """Accept only explicit forward commands; never infer motion from a question."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (user_input or "").lower()).strip()
    return normalized in _FORWARD_PHRASES


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