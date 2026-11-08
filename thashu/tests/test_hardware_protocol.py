import json
import time
import unittest
from pathlib import Path

from hardware import gpio_control
from hardware.motors import MotorController
from hardware.eyes import Eyes
from hardware.servo_tracking import ServoTracker


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.writes = []

    def write(self, data):
        self.writes.append(data.decode("ascii"))
        return len(data)

    def readline(self):
        return b""

    def close(self):
        self.is_open = False


class HardwareProtocolTests(unittest.TestCase):
    def setUp(self):
        gpio_control.GPIOControl.reset_singleton_for_tests()
        self.fake = FakeSerial()
        self.original_serial = gpio_control.serial.Serial
        gpio_control.serial.Serial = lambda *args, **kwargs: self.fake
        self.transport = gpio_control.GPIOControl(port="/dev/fake-esp32")
        # Stop the background transport for deterministic command assertions.
        self.transport._stop_event.set()

    def tearDown(self):
        self.transport.close()
        gpio_control.serial.Serial = self.original_serial
        gpio_control.GPIOControl.reset_singleton_for_tests()

    def _writes(self):
        return [line for line in self.fake.writes if line.startswith("CMD|")]

    def test_motor_protocol(self):
        motors = MotorController()
        motors.forward(180)
        motors.stop()
        writes = self._writes()
        self.assertTrue(any("|MOTOR|FORWARD|180\n" in line for line in writes))
        self.assertTrue(any("|STOP\n" in line for line in writes))

    def test_speed_zero_is_valid(self):
        motors = MotorController()
        motors.forward(0)
        self.assertTrue(any("|MOTOR|FORWARD|0\n" in line for line in self._writes()))

    def test_eye_protocol(self):
        eyes = Eyes()
        eyes.happy()
        self.assertTrue(any("|EYES|HAPPY\n" in line for line in self._writes()))

    def test_servo_protocol(self):
        servo = ServoTracker()
        servo.center()
        self.assertTrue(any("|SERVO|MOVE|90|90|220\n" in line for line in self._writes()))

    def test_shared_protocol_v0_vectors(self):
        vector_path = Path(__file__).with_name("protocol_vectors.json")
        vectors = json.loads(vector_path.read_text(encoding="utf-8"))

        for vector in vectors["commands"]:
            with self.subTest(vector=vector["name"]):
                sequence = self.transport.send(vector["payload"])
                self.assertIsNotNone(sequence)
                expected = vector["request_frame"].format(sequence=sequence) + chr(10)
                self.assertEqual(self.fake.writes[-1], expected)

    def test_controller_readiness_requires_ready_event(self):
        self.assertFalse(self.transport.has_ready_event())
        self.transport._observe_controller_event("EVENT|0|OTHER")
        self.assertFalse(self.transport.has_ready_event())
        self.transport._observe_controller_event("EVENT|0|READY")
        self.assertTrue(self.transport.has_ready_event())

    def test_sensor_freshness_is_unknown_until_complete_frame(self):
        result = self.transport.get_sensor_freshness()
        self.assertEqual(
            result, {"observed": False, "fresh": None, "age_ms": None}
        )

    def test_complete_sensor_frame_with_far_and_na_is_fresh(self):
        self.transport._update_sensor_snapshot(
            "TEL|0|SENSORS|TOF_L|420|TOF_C|FAR|TOF_R|NA|US_REAR|730"
        )
        result = self.transport.get_sensor_freshness()
        self.assertTrue(result["observed"])
        self.assertTrue(result["fresh"])
        self.assertIsInstance(result["age_ms"], int)
        snapshot = self.transport.get_sensor_snapshot(max_age=1.0)
        self.assertEqual(snapshot["tof_center_mm"], "FAR")
        self.assertIsNone(snapshot["tof_right_mm"])

    def test_stale_diagnostic_age_does_not_relax_safety_snapshot_age(self):
        self.transport._update_sensor_snapshot(
            "TEL|0|SENSORS|TOF_L|420|TOF_C|400|TOF_R|390|US_REAR|730"
        )
        with self.transport._state_lock:
            self.transport._sensor_snapshot["received_at"] = time.monotonic() - 1.2

        result = self.transport.get_sensor_freshness(max_age=1.0)
        self.assertTrue(result["observed"])
        self.assertFalse(result["fresh"])
        self.assertGreaterEqual(result["age_ms"], 1200)
        self.assertIsNone(self.transport.get_sensor_snapshot())

    def test_incomplete_sensor_frame_does_not_create_freshness(self):
        self.transport._update_sensor_snapshot(
            "TEL|0|SENSORS|TOF_L|420|TOF_C|400|TOF_R|390"
        )
        self.assertEqual(
            self.transport.get_sensor_freshness(),
            {"observed": False, "fresh": None, "age_ms": None},
        )

    def test_sequence_numbers_increase(self):
        self.transport.send("STOP")
        self.transport.send("HEARTBEAT")
        writes = self._writes()
        sequences = [int(line.split("|")[1]) for line in writes]
        self.assertGreater(sequences[1], sequences[0])


if __name__ == "__main__":
    unittest.main()
