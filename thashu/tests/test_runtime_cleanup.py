import threading
import unittest
from unittest.mock import patch

from hardware.gpio_control import GPIOControl
from voice.audio_manager import AudioManager


class FakeThread:
    def __init__(self, name):
        self.name = name
        self.alive = True
        self.joined = False

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.joined = True
        self.alive = False


class FakeSerial:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeStream:
    def __init__(self):
        self.stopped = False
        self.closed = False

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class RuntimeCleanupTests(unittest.TestCase):
    def test_gpio_close_stops_and_joins_transport_threads(self):
        gpio = GPIOControl.__new__(GPIOControl)
        gpio._stop_event = threading.Event()
        gpio._state_lock = threading.Lock()
        gpio._serial = FakeSerial()
        gpio._reader_thread = FakeThread("reader")
        gpio._transport_thread = FakeThread("transport")

        gpio.close()

        self.assertTrue(gpio._stop_event.is_set())
        self.assertTrue(gpio._serial is None)
        self.assertTrue(gpio._reader_thread.joined)
        self.assertTrue(gpio._transport_thread.joined)

    def test_gpio_cannot_reconnect_after_close(self):
        gpio = GPIOControl.__new__(GPIOControl)
        gpio._stop_event = threading.Event()
        gpio._stop_event.set()
        with patch("hardware.gpio_control.serial.Serial") as serial_open:
            self.assertFalse(gpio._connect())
        serial_open.assert_not_called()

    def test_audio_stop_closes_stream_and_joins_watchdog(self):
        audio = AudioManager.__new__(AudioManager)
        audio._running = True
        audio._paused = False
        audio._stop_event = threading.Event()
        audio._stream = FakeStream()
        audio._watchdog_thread = FakeThread("audio-watchdog")

        audio.stop()

        self.assertFalse(audio._running)
        self.assertTrue(audio._stop_event.is_set())
        self.assertTrue(audio._stream is None)
        self.assertTrue(audio._watchdog_thread.joined)


if __name__ == "__main__":
    unittest.main()
