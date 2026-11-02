import csv
import sys
import threading
import unittest
from pathlib import Path


THASHU_ROOT = Path(__file__).resolve().parents[1]
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from hardware.gpio_control import GPIOControl


REPO_ROOT = THASHU_ROOT.parent
FIXTURE_PATH = REPO_ROOT / "testdata" / "pi_esp32_protocol_vectors.csv"
TEST_SESSION = "0123456789abcdef0123456789abcdef"


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.frames = []

    def write(self, frame):
        self.frames.append(frame)
        return len(frame)


def make_transport(starting_sequence, session_id=TEST_SESSION):
    # Bypass the production singleton and hardware-opening constructor.
    transport = object.__new__(GPIOControl)
    transport._serial = FakeSerial()
    transport._write_lock = threading.Lock()
    transport._state_lock = threading.Lock()
    transport._sequence_lock = threading.Lock()
    transport._ack_condition = threading.Condition()
    transport._acknowledgements = {}
    transport._sensor_snapshot = None
    transport._session_id = session_id
    transport._next_sequence = starting_sequence
    return transport


class PiEsp32ProtocolVectorTests(unittest.TestCase):
    def test_pi_frames_match_shared_protocol_vectors(self):
        with FIXTURE_PATH.open(newline="", encoding="utf-8") as fixture_file:
            vectors = list(csv.DictReader(fixture_file))

        self.assertGreater(len(vectors), 0)
        for vector in vectors:
            with self.subTest(case=vector["case"]):
                sequence = int(vector["sequence"])
                transport = make_transport(sequence, vector["session_id"])

                result = transport.send(vector["payload"])

                self.assertEqual(result, sequence)
                self.assertEqual(
                    transport._serial.frames,
                    [(vector["expected_frame"] + "\n").encode("ascii")],
                )

    def test_sequence_exhaustion_never_reuses_identity(self):
        transport = make_transport(0x7FFFFFFF)

        self.assertEqual(transport.send("STOP"), 0x7FFFFFFF)
        self.assertIsNone(transport.send("HEARTBEAT"))
        self.assertEqual(
            transport._serial.frames,
            [f"CMD|1|{TEST_SESSION}|2147483647|STOP\n".encode("ascii")],
        )

    def test_ack_from_previous_session_cannot_match_current_sequence(self):
        transport = make_transport(1)

        transport._record_acknowledgement(
            "ACK|1|ffffffffffffffffffffffffffffffff|1|OK"
        )
        self.assertIsNone(transport.wait_for_ack(1, timeout=0.001))

        transport._record_acknowledgement(
            f"ACK|1|{TEST_SESSION}|1|ERROR|OBSTACLE"
        )
        self.assertEqual(
            transport.wait_for_ack(1, timeout=0.001),
            "ERROR|OBSTACLE",
        )

    def test_ignores_ack_with_unsupported_version(self):
        transport = make_transport(1)

        transport._record_acknowledgement(
            f"ACK|2|{TEST_SESSION}|1|OK"
        )
        self.assertIsNone(transport.wait_for_ack(1, timeout=0.001))

    def test_versioned_telemetry_is_parsed(self):
        transport = make_transport(1)
        transport._update_sensor_snapshot(
            "TEL|1|0|SENSORS|TOF_L|420|TOF_C|385|TOF_R|FAR|US_REAR|NA"
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


if __name__ == "__main__":
    unittest.main()
