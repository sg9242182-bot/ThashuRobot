import sys
import unittest
from pathlib import Path


THASHU_ROOT = Path(__file__).resolve().parents[1]
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from core.robot_manager import ControlMode, RobotCommandManager, RobotUnavailableError


class FakeMotor:
    speed = 200

    def __init__(self, sequence=1):
        self.sequence = sequence
        self.commands = []

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

    def test_stop_returns_manager_to_auto_mode(self):
        self.manager.dispatch("forward", 100)
        self.manager.dispatch("stop")
        self.assertEqual(self.manager.mode, ControlMode.AUTO)

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
