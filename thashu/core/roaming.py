"""Fail-closed direction selection for Thashu's opt-in roaming mode."""

from math import isfinite
from random import choice

OBSTACLE_CLEARANCE_MM = 300
MAX_REVERSE_ATTEMPTS = 2
FORWARD_PULSES_BEFORE_TURN = 4


def is_clear(value, clearance_mm=OBSTACLE_CLEARANCE_MM):
    if value == "FAR":
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return isfinite(value) and value > clearance_mm


def select_roaming_action(sensors, *, forward_pulses=0, reverse_attempts=0, choose=choice):
    """Return (direction, updated forward count, updated reverse count, reason).

    A missing, invalid, stale or blocked sensor snapshot must be filtered by the
    caller and results in no direction here; this policy never guesses a route.
    """
    if not isinstance(sensors, dict):
        return None, forward_pulses, reverse_attempts, "sensor_unavailable"
    left, center, right, rear = (
        sensors.get("tof_left_mm"),
        sensors.get("tof_center_mm"),
        sensors.get("tof_right_mm"),
        sensors.get("rear_mm"),
    )
    if all(is_clear(value) for value in (left, center, right)):
        next_forward = forward_pulses + 1
        if next_forward >= FORWARD_PULSES_BEFORE_TURN:
            turn = choose(("LEFT", "RIGHT"))
            if turn not in ("LEFT", "RIGHT"):
                raise ValueError("turn selector must choose LEFT or RIGHT")
            return turn, 0, 0, "periodic_turn"
        return "FORWARD", next_forward, 0, "front_clear"
    if is_clear(rear):
        if reverse_attempts < MAX_REVERSE_ATTEMPTS:
            return "BACKWARD", 0, reverse_attempts + 1, "front_blocked_reverse"
        left_clear, right_clear = is_clear(left), is_clear(right)
        if left_clear or right_clear:
            if left_clear and not right_clear:
                turn = "LEFT"
            elif right_clear and not left_clear:
                turn = "RIGHT"
            else:
                lm = float("inf") if left == "FAR" else float(left)
                rm = float("inf") if right == "FAR" else float(right)
                turn = "LEFT" if lm >= rm else "RIGHT"
            return turn, 0, reverse_attempts, "clearer_side"
    return None, 0, reverse_attempts, "no_clear_route"
