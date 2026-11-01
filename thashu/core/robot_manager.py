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

    def __init__(self, motor=None, command_lock=None, before_manual_command=None):
        if motor is None:
            from hardware.motors import MotorController

            motor = MotorController()
        self.motor = motor
        self._command_lock = command_lock or Lock()
        self._before_manual_command = before_manual_command
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

    def dispatch(self, command, speed=None, control_mode=ControlMode.MANUAL):
        """Write one allowed command and update the selected control mode.

        A returned sequence means the Pi transport wrote the frame. It is not
        an ESP32 acknowledgement or proof that the robot completed the action.
        A failed pre-move STOP returns None without sending the requested move.
        """
        if command == "stop":
            if speed is not None:
                raise ValueError("stop does not accept a speed")
            action = self.motor.stop
            args = ()
            next_mode = ControlMode.AUTO
        elif command in self._MOVES:
            if speed is None:
                speed = self.motor.speed
            self._validate_speed(speed)
            try:
                next_mode = ControlMode(control_mode)
            except ValueError as exc:
                raise ValueError("control_mode must be AUTO or MANUAL") from exc
            action = getattr(self.motor, command)
            args = (speed,)
        else:
            raise ValueError(f"unsupported motor command: {command!r}")

        with self._command_lock:
            if (
                command != "stop"
                and next_mode == ControlMode.MANUAL
                and self._mode != ControlMode.MANUAL
                and self._before_manual_command is not None
                and not self._before_manual_command()
            ):
                return None
            sequence = action(*args)
            if sequence is None:
                raise RobotUnavailableError("motor transport is unavailable")
            self._mode = next_mode
        return sequence
