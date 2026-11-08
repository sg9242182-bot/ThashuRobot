import csv
import queue
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


THASHU_ROOT = Path(__file__).resolve().parents[1]
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from hardware.gpio_control import GPIOControl


REPO_ROOT = THASHU_ROOT.parent
FIXTURE_PATH = REPO_ROOT / "testdata" / "pi_esp32_protocol_vectors.csv"


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.frames = []
        self.closed = False
        self.in_waiting = 0

    def write(self, frame):
        self.frames.append(frame)
        return len(frame)

    def read(self, size=1):
        return b""

    def close(self):
        self.closed = True
        self.is_open = False


def make_transport(starting_sequence):
    # Bypass the production singleton and hardware-opening constructor.
    transport = object.__new__(GPIOControl)
    transport._serial = FakeSerial()
    transport._write_lock = threading.Lock()
    transport._state_lock = threading.Lock()
    transport._sequence_lock = threading.Lock()
    transport._ack_condition = threading.Condition()
    transport._acknowledgements = {}
    transport._incoming = queue.Queue()
    transport._events = queue.Queue()
    transport._sensor_snapshot = None
    transport._next_sequence = starting_sequence
    return transport


class PiEsp32ProtocolVectorTests(unittest.TestCase):
    def test_pi_frames_match_shared_protocol_v0_vectors(self):
        with FIXTURE_PATH.open(newline="", encoding="utf-8") as fixture_file:
            vectors = list(csv.DictReader(fixture_file))

        self.assertGreater(len(vectors), 0)
        for vector in vectors:
            with self.subTest(case=vector["case"]):
                sequence = int(vector["sequence"])
                transport = make_transport(sequence)

                result = transport.send(vector["payload"])

                self.assertEqual(result, sequence)
                self.assertEqual(
                    transport._serial.frames,
                    [(vector["expected_frame"] + "\n").encode("ascii")],
                )

    def test_sequence_exhaustion_never_wraps_or_reuses_sequence(self):
        transport = make_transport(0x7FFFFFFF)

        self.assertEqual(transport.send("STOP"), 0x7FFFFFFF)
        self.assertIsNone(transport.send("HEARTBEAT"))
        self.assertEqual(
            transport._serial.frames,
            [b"CMD|2147483647|STOP\n"],
        )

    def test_acknowledgement_uses_sequence_only(self):
        transport = make_transport(1)
        transport._record_acknowledgement("ACK|1|ERROR|OBSTACLE")
        self.assertEqual(
            transport.wait_for_ack(1, timeout=0.001),
            "ERROR|OBSTACLE",
        )

    def test_delayed_ack_received_while_waiting_is_correlated(self):
        transport = make_transport(1)
        result = {}
        waiting = threading.Event()

        def wait_for_ack():
            waiting.set()
            result["ack"] = transport.wait_for_ack(1, timeout=0.5)

        waiter = threading.Thread(target=wait_for_ack)
        waiter.start()
        self.assertTrue(waiting.wait(timeout=0.2))
        time.sleep(0.01)
        transport._record_acknowledgement("ACK|1|OK")
        waiter.join(timeout=1.0)

        self.assertFalse(waiter.is_alive())
        self.assertEqual(result.get("ack"), "OK")

    def test_heartbeat_alive_ack_does_not_satisfy_command_ack(self):
        transport = make_transport(1)
        transport._record_acknowledgement("ACK|1|ALIVE")

        self.assertIsNone(transport.wait_for_ack(1, timeout=0.001))

    def test_ignores_versioned_ack_frame(self):
        transport = make_transport(1)
        transport._record_acknowledgement(
            "ACK|1|0123456789abcdef0123456789abcdef|1|OK"
        )
        self.assertIsNone(transport.wait_for_ack(1, timeout=0.001))

    def test_v0_telemetry_is_parsed(self):
        transport = make_transport(1)
        transport._update_sensor_snapshot(
            "TEL|0|SENSORS|TOF_L|420|TOF_C|385|TOF_R|FAR|US_REAR|NA"
        )

        snapshot = transport._sensor_snapshot
        self.assertEqual(snapshot["tof_left_mm"], 420)
        self.assertEqual(snapshot["tof_center_mm"], 385)
        self.assertEqual(snapshot["tof_right_mm"], "FAR")
        self.assertIsNone(snapshot["rear_mm"])

    def test_rejects_multiline_payload_without_writing(self):
        transport = make_transport(1)

        with self.assertRaises(ValueError):
            transport.send("STOP\nCMD|2|STOP")

        self.assertEqual(transport._serial.frames, [])

    def test_inbound_frame_is_not_published_until_newline_arrives(self):
        transport = make_transport(1)
        rx_buffer = bytearray()
        frame = b"ACK|1|OK"

        discarding = transport._consume_serial_bytes(frame[:6], rx_buffer)
        self.assertFalse(discarding)
        self.assertEqual(transport._incoming.qsize(), 0)

        discarding = transport._consume_serial_bytes(frame[6:] + b"\n", rx_buffer, discarding)
        self.assertFalse(discarding)
        received = transport.read_frame()
        self.assertEqual(received[0], frame.decode("ascii"))
        self.assertTrue(received[1].endswith("Z"))
        self.assertEqual(transport.wait_for_ack(1, timeout=0.001), "OK")

    def test_oversized_inbound_frame_is_discarded_through_newline(self):
        transport = make_transport(1)
        rx_buffer = bytearray()
        oversized = b"X" * (transport.MAX_FRAME_BYTES + 1) + b"ignored\n"
        valid = b"ACK|1|OK\n"

        discarding = transport._consume_serial_bytes(oversized, rx_buffer)
        self.assertFalse(discarding)
        self.assertEqual(transport._incoming.qsize(), 0)

        transport._consume_serial_bytes(valid, rx_buffer, discarding)
        received = transport.read_frame()
        self.assertEqual(received[0], "ACK|1|OK")
        self.assertTrue(received[1].endswith("Z"))
        self.assertEqual(transport.wait_for_ack(1, timeout=0.001), "OK")

    def test_reconnect_opens_a_new_serial_connection(self):
        transport = object.__new__(GPIOControl)
        previous = FakeSerial()
        reconnected = FakeSerial()
        transport._serial = previous
        transport._state_lock = threading.Lock()
        transport._configured_port = "fake-port"
        transport._port = "fake-port"
        transport._baud = GPIOControl.DEFAULT_BAUD
        transport._last_heartbeat = 1.0
        transport._last_rx_monotonic = 1.0
        transport._resolve_port = lambda: "fake-port"

        self.assertTrue(transport._disconnect("test disconnect"))
        self.assertFalse(transport.is_connected())

        with patch("hardware.gpio_control.serial.Serial", return_value=reconnected):
            self.assertTrue(transport._connect())

        self.assertTrue(transport.is_connected())
        self.assertTrue(previous.closed)
        self.assertIs(transport._serial, reconnected)

    def test_receive_silence_disconnects_fake_serial_link(self):
        transport = make_transport(1)
        transport._stop_event = threading.Event()
        transport._last_rx_monotonic = time.monotonic() - GPIOControl.RX_SILENCE_TIMEOUT - 1
        reader = threading.Thread(target=transport._reader_loop)
        reader.start()
        try:
            deadline = time.monotonic() + 1.0
            while transport.is_connected() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(transport.is_connected())
            self.assertTrue(transport._serial is None)
        finally:
            transport._stop_event.set()
            reader.join(timeout=1.0)
        self.assertFalse(reader.is_alive())


if __name__ == "__main__":
    unittest.main()
