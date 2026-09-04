from hardware.gpio_control import GPIOControl


class Eyes:
    """
    High-level semantic eye controller.

    The ESP32 owns the physical OLEDs and renders the requested expression.
    """

    IDLE = "IDLE"
    HAPPY = "HAPPY"
    THINKING = "THINKING"
    LISTENING = "LISTENING"
    SPEAKING = "SPEAKING"
    ALERT = "ALERT"
    SLEEP = "SLEEP"

    def __init__(self):
        self.gpio = GPIOControl()
        self._current = None
        print("[EYES] Initialized")

    def set(self, expression: str):
        expression = expression.upper()
        if expression == self._current:
            return
        self._current = expression
        self.gpio.send(f"EYES|{expression}")
        print(f"[EYES] {expression}")

    def idle(self):
        self.set(self.IDLE)

    def happy(self):
        self.set(self.HAPPY)

    def thinking(self):
        self.set(self.THINKING)

    def listening(self):
        self.set(self.LISTENING)

    def speaking(self):
        self.set(self.SPEAKING)

    def alert(self):
        self.set(self.ALERT)

    def sleep(self):
        self.set(self.SLEEP)
