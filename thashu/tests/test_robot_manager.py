import sys
import threading
import unittest
from pathlib import Path


THASHU_ROOT = Path(__file__).resolve().parents[1]
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from core.robot_manager import (
    ControlMode,
    ControlModeError,
    ModeSwitchError,
    RobotCommandManager,
    RobotSafetyError,
    RobotUnavailableError,
    stop_and_wait_for_ack,
)


class FakeTransport:
    def __init__(self, ack="OK", snapshot=None):
        self.ack = ack
        self.connected = True
        self.waited_for = []
        self.snapshot = snapshot or {
            "tof_left_mm": 500,
            "tof_center_mm": 500,
            "tof_right_mm": 500,
            "rear_mm": 500,
        }

    def wait_for_ack(self, sequence, timeout=0.75):
        self.waited_for.append((sequence, timeout))
        return self.ack

    def is_connected(self):
        return self.connected

    def get_sensor_snapshot(self, max_age=0.75):
        return self.snapshot


class FakeMotor:
    speed = 200

    def __init__(self, sequence=1):
        self.sequence = sequence
        self.commands = []
        self.gpio = FakeTransport()

    def forward(self, speed):
        self.commands.append(("forward", speed))
        return self.sequence

    def backward(self, speed):
        self.commands.append(("backward", speed))
        return self.sequence

    def left(self, speed):
        self.commands.append(("left", speed))
        return self.sequence

    def right(self, speed):
        self.commands.append(("right", speed))
        return self.sequence

    def stop(self):
        self.commands.append(("stop", None))
        return self.sequence


class RobotCommandManagerTests(unittest.TestCase):
    def setUp(self):
        self.motor = FakeMotor(sequence=17)
        self.manager = RobotCommandManager(self.motor)

    def test_dispatch_blocks_when_esp32_transport_is_disconnected(self):
        self.motor.gpio.connected = False
        with self.assertRaises(RobotSafetyError) as failure:
            self.manager.dispatch("forward", 100)
        self.assertEqual(failure.exception.error_code, "ESP32_UNAVAILABLE")
        self.assertEqual(self.motor.commands, [("stop", None)])

    def test_dispatches_allowed_move_with_requested_speed(self):
        self.assertEqual(self.manager.dispatch("forward", 100), 17)
        self.assertEqual(self.motor.commands, [("forward", 100)])

    def test_uses_motor_default_speed_when_speed_is_omitted(self):
        self.manager.dispatch("left")
        self.assertEqual(self.motor.commands, [("left", 200)])

    def test_dispatches_dedicated_stop(self):
        self.manager.dispatch("stop")
        self.assertEqual(self.motor.commands, [("stop", None)])
        self.assertEqual(self.manager.mode, ControlMode.AUTO)

    def test_normal_stop_preserves_manual_mode(self):
        self.manager.switch_mode(ControlMode.MANUAL)
        self.manager.stop_preserving_mode()
        self.assertEqual(self.manager.mode, ControlMode.MANUAL)
        self.assertFalse(self.manager.auto_active)
        self.assertEqual(self.motor.commands, [
            ("stop", None),
            ("stop", None),
        ])

    def test_move_switches_manager_into_manual_mode(self):
        self.assertEqual(self.manager.mode, ControlMode.AUTO)
        self.manager.dispatch("forward", 100)
        self.assertEqual(self.manager.mode, ControlMode.MANUAL)

    def test_explicit_mode_switch_waits_for_stop_ack_and_only_selects_mode(self):
        self.manager.switch_mode(ControlMode.MANUAL)
        self.assertEqual(self.motor.commands, [("stop", None)])
        self.assertEqual(self.motor.gpio.waited_for, [(17, 0.75)])
        self.assertEqual(self.manager.mode, ControlMode.MANUAL)

    def test_mode_switch_invalidates_a_move_waiting_on_an_older_state(self):
        pending_version = self.manager.state_version
        self.manager.switch_mode(ControlMode.MANUAL)
        with self.assertRaises(ControlModeError) as failure:
            self.manager.dispatch(
                "forward",
                100,
                require_current_mode=True,
                expected_state_version=pending_version,
            )
        self.assertEqual(failure.exception.error_code, "CONTROL_STATE_CHANGED")
        self.assertEqual(self.motor.commands, [("stop", None)])

    def test_mode_switch_failure_keeps_old_mode_and_retries_stop(self):
        self.motor.gpio.ack = "ERROR|SAFETY_STOP"
        with self.assertRaises(ModeSwitchError) as failure:
            self.manager.switch_mode(ControlMode.MANUAL)
        self.assertEqual(failure.exception.error_code, "STOP_REJECTED")
        self.assertEqual(self.manager.mode, ControlMode.AUTO)
        self.assertEqual(self.motor.commands, [
            ("stop", None),
            ("stop", None),
        ])
        self.assertTrue(self.manager.motion_inhibited)
        with self.assertRaises(ControlModeError) as blocked:
            self.manager.dispatch("forward", 100)
        self.assertEqual(blocked.exception.error_code, "STOP_CONFIRMATION_REQUIRED")

    def test_switching_to_auto_does_not_send_a_movement(self):
        self.manager.switch_mode(ControlMode.AUTO)
        self.assertEqual(self.manager.mode, ControlMode.AUTO)
        self.assertEqual(self.motor.commands, [("stop", None)])
        self.assertFalse(self.manager.auto_active)

    def test_auto_movement_is_blocked_while_manual_is_selected(self):
        self.manager.switch_mode(ControlMode.MANUAL)
        with self.assertRaises(ControlModeError) as failure:
            self.manager.dispatch("forward", 100, control_mode=ControlMode.AUTO)
        self.assertEqual(failure.exception.error_code, "AUTO_MODE_REQUIRED")
        self.assertEqual(self.motor.commands, [("stop", None)])

    def test_auto_movement_requires_explicit_auto_start(self):
        with self.assertRaises(ControlModeError) as failure:
            self.manager.dispatch("forward", 100, control_mode=ControlMode.AUTO)
        self.assertEqual(failure.exception.error_code, "AUTO_NOT_STARTED")
        self.assertEqual(self.motor.commands, [])

        self.manager.start_auto()
        self.assertEqual(
            self.manager.dispatch("forward", 100, control_mode=ControlMode.AUTO),
            17,
        )
        self.assertEqual(self.motor.commands, [("forward", 100)])

    def test_bounded_auto_pulse_stop_preserves_explicitly_started_auto(self):
        self.manager.start_auto()
        self.manager.dispatch("forward", 100, control_mode=ControlMode.AUTO)
        self.manager.stop_pulse()
        self.assertEqual(self.manager.mode, ControlMode.AUTO)
        self.assertTrue(self.manager.auto_active)
        self.assertEqual(self.motor.commands, [
            ("forward", 100),
            ("stop", None),
        ])

    def test_manual_move_requires_successful_pre_move_stop(self):
        motor = FakeMotor(sequence=17)
        stop_results = []

        def stop_automatic_motion():
            stop_results.append("stop")
            return False

        manager = RobotCommandManager(
            motor,
            before_manual_command=stop_automatic_motion,
        )

        self.assertIsNone(manager.dispatch("forward", 100))
        self.assertEqual(stop_results, ["stop"])
        self.assertEqual(motor.commands, [("stop", None)])
        self.assertEqual(manager.mode, ControlMode.AUTO)

    def test_successful_pre_move_stop_runs_only_when_entering_manual(self):
        motor = FakeMotor(sequence=17)
        stop_results = []
        manager = RobotCommandManager(
            motor,
            before_manual_command=lambda: stop_results.append("stop") or True,
        )

        manager.dispatch("forward", 100)
        manager.dispatch("right", 80)

        self.assertEqual(stop_results, ["stop"])
        self.assertEqual(
            motor.commands,
            [("forward", 100), ("right", 80)],
        )
        self.assertEqual(manager.mode, ControlMode.MANUAL)

    def test_manual_transition_requires_stop_ok_ack(self):
        motor = FakeMotor(sequence=17)
        manager = RobotCommandManager(
            motor,
            before_manual_command=lambda: stop_and_wait_for_ack(motor),
        )

        self.assertEqual(manager.dispatch("forward", 100), 17)
        self.assertEqual(motor.commands, [
            ("stop", None),
            ("forward", 100),
        ])
        self.assertEqual(motor.gpio.waited_for, [(17, 0.75)])
        self.assertEqual(manager.mode, ControlMode.MANUAL)

    def test_manual_transition_is_blocked_when_stop_ack_is_not_ok(self):
        motor = FakeMotor(sequence=17)
        motor.gpio.ack = "ERROR|SAFETY_STOP"
        manager = RobotCommandManager(
            motor,
            before_manual_command=lambda: stop_and_wait_for_ack(motor),
        )

        self.assertIsNone(manager.dispatch("forward", 100))
        self.assertEqual(motor.commands, [
            ("stop", None),
            ("stop", None),
        ])
        self.assertEqual(manager.mode, ControlMode.AUTO)

    def test_move_rejects_missing_or_stale_sensor_snapshot(self):
        motor = FakeMotor(sequence=17)
        motor.gpio.snapshot = None
        manager = RobotCommandManager(motor)
        with self.assertRaises(RobotSafetyError) as failure:
            manager.dispatch("forward", 100)
        self.assertEqual(failure.exception.error_code, "SENSOR_NOT_READY")
        self.assertEqual(motor.commands, [("stop", None)])

    def test_move_rejects_sensor_reading_at_or_below_clearance(self):
        motor = FakeMotor(sequence=17)
        motor.gpio.snapshot["tof_center_mm"] = 300
        manager = RobotCommandManager(motor)
        with self.assertRaises(RobotSafetyError) as failure:
            manager.dispatch("forward", 100)
        self.assertEqual(failure.exception.error_code, "OBSTACLE_BLOCKED")
        self.assertEqual(motor.commands, [("stop", None)])

    def test_unavailable_sensor_reader_sends_stop_and_blocks_move(self):
        motor = FakeMotor(sequence=17)
        motor.gpio.get_sensor_snapshot = lambda **_kwargs: (_ for _ in ()).throw(OSError())
        manager = RobotCommandManager(motor)
        with self.assertRaises(RobotSafetyError) as failure:
            manager.dispatch("forward", 100)
        self.assertEqual(failure.exception.error_code, "SENSOR_NOT_READY")
        self.assertEqual(motor.commands, [("stop", None)])

    def test_far_sensor_value_counts_as_clear(self):
        motor = FakeMotor(sequence=17)
        motor.gpio.snapshot["tof_left_mm"] = "FAR"
        manager = RobotCommandManager(motor)
        self.assertEqual(manager.dispatch("forward", 100), 17)

    def test_stop_returns_manager_to_auto_mode(self):
        self.manager.dispatch("forward", 100)
        self.manager.dispatch("stop")
        self.assertEqual(self.manager.mode, ControlMode.AUTO)

    def test_safety_stop_does_not_change_selected_mode(self):
        self.manager.dispatch("forward", 100)
        self.manager.safety_stop()
        self.assertEqual(self.motor.commands, [
            ("forward", 100),
            ("stop", None),
        ])
        self.assertEqual(self.manager.mode, ControlMode.MANUAL)

    def test_concurrent_move_and_stop_are_serialized(self):
        move_entered = threading.Event()
        release_move = threading.Event()
        stop_called = threading.Event()
        order = []

        class BlockingMotor(FakeMotor):
            def forward(self, speed):
                order.append("move-start")
                move_entered.set()
                if not release_move.wait(timeout=2):
                    raise AssertionError("test did not release blocked move")
                order.append("move-end")
                return self.sequence

            def stop(self):
                order.append("stop")
                stop_called.set()
                return self.sequence

        motor = BlockingMotor(sequence=17)
        manager = RobotCommandManager(motor)
        move_thread = threading.Thread(target=manager.dispatch, args=("forward", 100))
        stop_thread = threading.Thread(target=manager.dispatch, args=("stop",))

        move_thread.start()
        self.assertTrue(move_entered.wait(timeout=1))
        stop_thread.start()
        try:
            self.assertFalse(stop_called.wait(timeout=0.05))
        finally:
            release_move.set()
            move_thread.join(timeout=1)
            stop_thread.join(timeout=1)

        self.assertFalse(move_thread.is_alive())
        self.assertFalse(stop_thread.is_alive())
        self.assertEqual(order, ["move-start", "move-end", "stop"])

    def test_rejects_unknown_command(self):
        with self.assertRaises(ValueError):
            self.manager.dispatch("spin", 100)

    def test_rejects_non_integer_or_out_of_range_speed(self):
        for speed in (True, 1.5, -1, 256):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    self.manager.dispatch("forward", speed)
        self.assertEqual(self.motor.commands, [])

    def test_raises_when_motor_transport_cannot_write(self):
        motor = FakeMotor(sequence=None)
        manager = RobotCommandManager(motor)
        with self.assertRaises(RobotUnavailableError):
            manager.dispatch("forward", 100)
        self.assertEqual(manager.mode, ControlMode.AUTO)


if __name__ == "__main__":
    unittest.main()
