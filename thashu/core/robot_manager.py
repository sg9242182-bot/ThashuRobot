"""Serialized command dispatch for the Raspberry Pi motor service.

This is the single Pi-side entry point for manual motor commands. It validates
and serializes requests before passing them to the existing MotorController.
Manual/automatic mode arbitration is intentionally not exposed until its safe
transition policy is agreed with the hardware owner.
"""

from enum import Enum
from math import isfinite
from threading import Lock


class RobotUnavailableError(RuntimeError):
    """Raised when the Pi cannot write a motor command to the ESP32 transport."""


class ModeSwitchError(RuntimeError):
    """Raised when STOP cannot be confirmed during a control-mode switch."""

    def __init__(self, error_code):
        super().__init__(error_code)
        self.error_code = error_code


class ControlModeError(RuntimeError):
    """Raised when a caller tries to move outside its selected control mode."""

    def __init__(self, error_code):
        super().__init__(error_code)
        self.error_code = error_code


class RobotSafetyError(RuntimeError):
    """Raised when fresh sensor data does not permit the requested movement."""

    def __init__(self, error_code):
        super().__init__(error_code)
        self.error_code = error_code


class ControlMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


def stop_and_wait_for_ack(motor, timeout=0.75):
    """Send dedicated STOP and require its protocol-v0 OK ACK before continuing."""
    sequence = motor.stop()
    if sequence is None:
        return False
    transport = getattr(motor, "gpio", None)
    wait_for_ack = getattr(transport, "wait_for_ack", None)
    if not callable(wait_for_ack):
        return False
    try:
        return wait_for_ack(sequence, timeout=timeout) == "OK"
    except Exception:
        return False


class RobotCommandManager:
    """Validate and serialize robot commands through MotorController."""

    _MOVES = frozenset({"forward", "backward", "left", "right"})
    _FRONT_SENSORS = ("tof_left_mm", "tof_center_mm", "tof_right_mm")

    def __init__(
        self,
        motor=None,
        command_lock=None,
        before_manual_command=None,
        before_mode_switch=None,
        before_external_stop=None,
        sensor_max_age=0.75,
        obstacle_clearance_mm=300,
    ):
        if motor is None:
            from hardware.motors import MotorController

            motor = MotorController()
        self.motor = motor
        self._command_lock = command_lock or Lock()
        self._before_manual_command = before_manual_command
        self._before_mode_switch = before_mode_switch
        self._before_external_stop = before_external_stop
        self._sensor_max_age = sensor_max_age
        self._obstacle_clearance_mm = obstacle_clearance_mm
        self._mode = ControlMode.AUTO
        self._auto_active = False
        self._motion_inhibited = False
        self._state_version = 0

    @property
    def mode(self):
        with self._command_lock:
            return self._mode

    @property
    def auto_active(self):
        with self._command_lock:
            return self._auto_active

    @property
    def motion_inhibited(self):
        with self._command_lock:
            return self._motion_inhibited

    @property
    def state_version(self):
        with self._command_lock:
            return self._state_version

    def start_auto(self):
        """Enable the existing autonomous behavior after an explicit start."""
        with self._command_lock:
            if self._motion_inhibited:
                raise ControlModeError("STOP_CONFIRMATION_REQUIRED")
            if self._mode != ControlMode.AUTO:
                raise ControlModeError("AUTO_MODE_REQUIRED")
            self._auto_active = True
            self._state_version += 1

    @staticmethod
    def _validate_speed(speed):
        if isinstance(speed, bool) or not isinstance(speed, int):
            raise ValueError("motor speed must be an integer between 0 and 255")
        if not 0 <= speed <= 255:
            raise ValueError("motor speed must be between 0 and 255")

    @staticmethod
    def _normalize_mode(mode):
        try:
            return ControlMode(mode)
        except ValueError as exc:
            raise ValueError("mode must be AUTO or MANUAL") from exc

    def _require_clear_sensors(self, command):
        transport = getattr(self.motor, "gpio", None)
        get_snapshot = getattr(transport, "get_sensor_snapshot", None)
        try:
            snapshot = (
                get_snapshot(max_age=self._sensor_max_age)
                if callable(get_snapshot)
                else None
            )
        except Exception:
            snapshot = None
        if snapshot is None:
            self._stop_for_sensor_failure()
            raise RobotSafetyError("SENSOR_NOT_READY")

        relevant = ("rear_mm",) if command == "backward" else self._FRONT_SENSORS
        for name in relevant:
            value = snapshot.get(name)
            if value == "FAR":
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                self._stop_for_sensor_failure()
                raise RobotSafetyError("SENSOR_NOT_READY")
            if not isfinite(value) or value <= self._obstacle_clearance_mm:
                self._stop_for_sensor_failure()
                raise RobotSafetyError("OBSTACLE_BLOCKED")

    def _stop_for_sensor_failure(self):
        """Cancel active motion when a Pi-side movement safety check fails."""
        if self._before_external_stop is not None:
            self._before_external_stop()
        sequence = self.motor.stop()
        self._auto_active = False
        self._state_version += 1
        if sequence is None:
            self._motion_inhibited = True

    def switch_mode(self, mode, stop_timeout=0.75):
        """Cancel motion, then change mode only after the ESP32 ACKs STOP.

        Selecting AUTO only selects that source; it does not start follow.
        """
        next_mode = self._normalize_mode(mode)
        with self._command_lock:
            if self._before_mode_switch is not None:
                self._before_mode_switch()

            sequence = self.motor.stop()
            if sequence is None:
                self._auto_active = False
                self._motion_inhibited = True
                self._state_version += 1
                raise ModeSwitchError("STOP_DISPATCH_FAILED")

            transport = getattr(self.motor, "gpio", None)
            wait_for_ack = getattr(transport, "wait_for_ack", None)
            try:
                acknowledgement = (
                    wait_for_ack(sequence, timeout=stop_timeout)
                    if callable(wait_for_ack)
                    else None
                )
            except Exception:
                acknowledgement = None

            if acknowledgement != "OK":
                # Best effort: a lost/rejected ACK leaves dispatch uncertain.
                # Re-send STOP, keep the old mode, and report the failed switch.
                try:
                    self.motor.stop()
                except Exception:
                    pass
                self._auto_active = False
                self._motion_inhibited = True
                self._state_version += 1
                error_code = (
                    "STOP_ACK_TIMEOUT"
                    if acknowledgement is None
                    else "STOP_REJECTED"
                )
                raise ModeSwitchError(error_code)

            self._mode = next_mode
            self._auto_active = False
            self._motion_inhibited = False
            self._state_version += 1
            return sequence

    def stop_all(self):
        """Cancel Pi-side motion sources, then send STOP and select Auto paused."""
        with self._command_lock:
            if self._before_external_stop is not None:
                self._before_external_stop()
            self._auto_active = False
            sequence = self.motor.stop()
            if sequence is None:
                self._motion_inhibited = True
                self._state_version += 1
                raise RobotUnavailableError("motor transport is unavailable")
            self._mode = ControlMode.AUTO
            self._state_version += 1
            return sequence

    def stop_pulse(self):
        """End one bounded autonomous/manual pulse without cancelling its mode."""
        with self._command_lock:
            sequence = self.motor.stop()
            if sequence is None:
                raise RobotUnavailableError("motor transport is unavailable")
            return sequence

    def dispatch(
        self,
        command,
        speed=None,
        control_mode=ControlMode.MANUAL,
        require_current_mode=False,
        expected_state_version=None,
    ):
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
            next_mode = self._normalize_mode(control_mode)
            action = getattr(self.motor, command)
            args = (speed,)
        else:
            raise ValueError(f"unsupported motor command: {command!r}")

        with self._command_lock:
            if command == "stop":
                if self._before_external_stop is not None:
                    self._before_external_stop()
                self._auto_active = False
                sequence = action(*args)
                if sequence is None:
                    self._motion_inhibited = True
                    self._state_version += 1
                    raise RobotUnavailableError("motor transport is unavailable")
                self._mode = ControlMode.AUTO
                self._state_version += 1
                return sequence

            if (
                expected_state_version is not None
                and expected_state_version != self._state_version
            ):
                raise ControlModeError("CONTROL_STATE_CHANGED")

            if self._motion_inhibited:
                raise ControlModeError("STOP_CONFIRMATION_REQUIRED")

            if (
                command != "stop"
                and next_mode == ControlMode.MANUAL
                and self._mode != ControlMode.MANUAL
                and require_current_mode
            ):
                raise ControlModeError("MANUAL_MODE_REQUIRED")
            if (
                command != "stop"
                and next_mode == ControlMode.AUTO
            ):
                if self._mode != ControlMode.AUTO:
                    raise ControlModeError("AUTO_MODE_REQUIRED")
                if not self._auto_active:
                    raise ControlModeError("AUTO_NOT_STARTED")
            if (
                command != "stop"
                and next_mode == ControlMode.MANUAL
                and self._mode != ControlMode.MANUAL
                and self._before_manual_command is not None
                and not self._before_manual_command()
            ):
                self._auto_active = False
                self._motion_inhibited = True
                self._state_version += 1
                try:
                    self.motor.stop()
                except Exception:
                    pass
                return None
            if command != "stop":
                self._require_clear_sensors(command)
            sequence = action(*args)
            if sequence is None:
                raise RobotUnavailableError("motor transport is unavailable")
            if next_mode == ControlMode.MANUAL:
                self._mode = ControlMode.MANUAL
        return sequence

    def safety_stop(self):
        """Send a fail-safe STOP without selecting or changing the control mode."""
        with self._command_lock:
            if self._before_external_stop is not None:
                self._before_external_stop()
            self._auto_active = False
            self._motion_inhibited = True
            self._state_version += 1
            sequence = self.motor.stop()
            if sequence is None:
                raise RobotUnavailableError("motor transport is unavailable")
            return sequence
