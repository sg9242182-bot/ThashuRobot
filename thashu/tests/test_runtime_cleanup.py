import sys
import threading
import unittest
from types import ModuleType
from unittest.mock import patch

from hardware.gpio_control import GPIOControl

# Runtime cleanup tests exercise AudioManager.stop() without audio hardware.
# Stub its optional DSP/audio backend imports so CI need not install or load
# NumPy, PortAudio, or device drivers just to test resource cleanup.
_numpy_stub = ModuleType("numpy")
_numpy_stub.ndarray = object
_sounddevice_stub = ModuleType("sounddevice")
_sounddevice_stub.InputStream = object
with patch.dict(
    sys.modules,
    {"numpy": _numpy_stub, "sounddevice": _sounddevice_stub},
):
    from voice.audio_manager import AudioManager  # noqa: E402


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
        serial_connection = FakeSerial()
        gpio._serial = serial_connection
        gpio._reader_thread = FakeThread("reader")
        gpio._transport_thread = FakeThread("transport")

        gpio.close()

        self.assertTrue(gpio._stop_event.is_set())
        self.assertIsNone(gpio._serial)
        self.assertTrue(serial_connection.closed)
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
        watchdog = FakeThread("audio-watchdog")
        audio._watchdog_thread = watchdog

        audio.stop()

        self.assertFalse(audio._running)
        self.assertTrue(audio._stop_event.is_set())
        self.assertTrue(audio._stream is None)
        self.assertTrue(watchdog.joined)


if __name__ == "__main__":
    unittest.main()
