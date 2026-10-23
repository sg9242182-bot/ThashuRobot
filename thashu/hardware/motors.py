from hardware.gpio_control import GPIOControl


class MotorController:
    """High-level motor interface; ESP32 owns the actual motor hardware."""

    def __init__(self):
        self.gpio = GPIOControl()
        self.speed = 200   # default speed, 0-255
        print("[MOTORS] Initialized")

    def _speed(self, speed):
        s = self.speed if speed is None else int(speed)
        if not 0 <= s <= 255:
            raise ValueError("motor speed must be between 0 and 255")
        return s

    def forward(self, speed=None):
        self.gpio.send(f"MOTOR|FORWARD|{self._speed(speed)}")

    def backward(self, speed=None):
        self.gpio.send(f"MOTOR|BACKWARD|{self._speed(speed)}")

    def left(self, speed=None):
        self.gpio.send(f"MOTOR|LEFT|{self._speed(speed)}")

    def right(self, speed=None):
        self.gpio.send(f"MOTOR|RIGHT|{self._speed(speed)}")

    def stop(self):
        # STOP is deliberately a dedicated high-priority protocol command.
        self.gpio.send("STOP")
