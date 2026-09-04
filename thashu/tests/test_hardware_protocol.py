import unittest

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
        self.assertTrue(any("|SERVO|PAN_TILT|90|90\n" in line for line in self._writes()))

    def test_sequence_numbers_increase(self):
        self.transport.send("STOP")
        self.transport.send("HEARTBEAT")
        writes = self._writes()
        sequences = [int(line.split("|")[1]) for line in writes]
        self.assertGreater(sequences[1], sequences[0])


if __name__ == "__main__":
    unittest.main()
