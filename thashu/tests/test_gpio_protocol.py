import csv
import sys
import threading
import unittest
from pathlib import Path


THASHU_ROOT = Path(__file__).resolve().parents[1]
if str(THASHU_ROOT) not in sys.path:
    sys.path.insert(0, str(THASHU_ROOT))

from hardware.gpio_control import GPIOControl


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pi_esp32_protocol_vectors.csv"


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.frames = []

    def write(self, frame):
        self.frames.append(frame)
        return len(frame)


def make_transport(starting_sequence):
    # Bypass the production singleton and hardware-opening constructor.
    transport = object.__new__(GPIOControl)
    transport._serial = FakeSerial()
    transport._write_lock = threading.Lock()
    transport._state_lock = threading.Lock()
    transport._sequence_lock = threading.Lock()
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
                transport = make_transport(sequence)

                result = transport.send(vector["payload"])

                self.assertEqual(result, sequence)
                self.assertEqual(
                    transport._serial.frames,
                    [(vector["expected_frame"] + "\n").encode("ascii")],
                )

    def test_sequence_wraps_to_one_after_maximum(self):
        transport = make_transport(0x7FFFFFFF)

        self.assertEqual(transport.send("STOP"), 0x7FFFFFFF)
        self.assertEqual(transport.send("HEARTBEAT"), 1)
        self.assertEqual(
            transport._serial.frames,
            [b"CMD|2147483647|STOP\n", b"CMD|1|HEARTBEAT\n"],
        )

    def test_rejects_multiline_payload_without_writing(self):
        transport = make_transport(1)

        with self.assertRaises(ValueError):
            transport.send("STOP\nCMD|2|STOP")

        self.assertEqual(transport._serial.frames, [])


if __name__ == "__main__":
    unittest.main()
