# core/decision.py

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
    if "stop" in text:
        return "STOP"

    if "move" in text:
        return "MOVE"

    # ===== DEFAULT =====
    return "AI_FALLBACK"