"""Serialized command dispatch for the Raspberry Pi motor service.

This is the single Pi-side entry point for manual motor commands. It validates
and serializes requests before passing them to the existing MotorController.
Manual/automatic mode arbitration is intentionally not exposed until its safe
transition policy is agreed with the hardware owner.
"""

from enum import Enum
from threading import Lock


class RobotUnavailableError(RuntimeError):
    """Raised when the Pi cannot write a motor command to the ESP32 transport."""


class ControlMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class RobotCommandManager:
    """Validate and serialize manual motor commands through MotorController."""

    _MOVES = frozenset({"forward", "backward", "left", "right"})

    def __init__(self, motor=None):
        if motor is None:
            from hardware.motors import MotorController

            motor = MotorController()
        self.motor = motor
        self._command_lock = Lock()
        self._mode = ControlMode.AUTO

    @property
    def mode(self):
        with self._command_lock:
            return self._mode

    @staticmethod
    def _validate_speed(speed):
        if isinstance(speed, bool) or not isinstance(speed, int):
            raise ValueError("motor speed must be an integer between 0 and 255")
        if not 0 <= speed <= 255:
            raise ValueError("motor speed must be between 0 and 255")

    def dispatch(self, command, speed=None):
        """Write one allowed command; return its Pi-ESP32 sequence number.

        A returned sequence means the Pi transport wrote the frame. It is not
        an ESP32 acknowledgement or proof that the robot completed the action.
        """
        if command == "stop":
            if speed is not None:
                raise ValueError("stop does not accept a speed")
            action = self.motor.stop
            args = ()
        elif command in self._MOVES:
            if speed is None:
                speed = self.motor.speed
            self._validate_speed(speed)
            action = getattr(self.motor, command)
            args = (speed,)
        else:
            raise ValueError(f"unsupported motor command: {command!r}")

        with self._command_lock:
            sequence = action(*args)
            if sequence is None:
                raise RobotUnavailableError("motor transport is unavailable")
            self._mode = ControlMode.AUTO if command == "stop" else ControlMode.MANUAL
        return sequence
