import sys
import threading
import unittest
from pathlib import Path


THASHU_ROOT = Path(__file__).resolve().parents[1]
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from core.robot_manager import (
    ControlMode,
    RobotCommandManager,
    RobotUnavailableError,
    stop_and_wait_for_ack,
)


class FakeTransport:
    def __init__(self, ack="OK"):
        self.ack = ack
        self.waited_for = []

    def wait_for_ack(self, sequence, timeout=0.75):
        self.waited_for.append((sequence, timeout))
        return self.ack


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

    def test_move_switches_manager_into_manual_mode(self):
        self.assertEqual(self.manager.mode, ControlMode.AUTO)
        self.manager.dispatch("forward", 100)
        self.assertEqual(self.manager.mode, ControlMode.MANUAL)

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
        self.assertEqual(motor.commands, [])
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
        self.assertEqual(motor.commands, [("stop", None)])
        self.assertEqual(manager.mode, ControlMode.AUTO)

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
