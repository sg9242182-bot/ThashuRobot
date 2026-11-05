import tempfile
import unittest
from pathlib import Path

import numpy as np

from vision.face_database import DlibFaceDatabase


class DlibFaceDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = DlibFaceDatabase(Path(self.temp.name) / "people_faces_dlib.json")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def vector(value):
        result = np.zeros(128, dtype=np.float32)
        result[0] = value
        return result

    def test_raw_descriptor_scale_is_preserved(self):
        sample = self.vector(0.25)
        np.testing.assert_array_equal(self.db._normalize(sample), sample)

    def test_matching_uses_distance_and_runner_up_margin(self):
        alice = self.vector(0.20)
        bob = self.vector(1.20)
        self.db.data = {"Alice": [alice.tolist()], "Bob": [bob.tolist()]}
        self.assertEqual(self.db.match(alice)[0], "Alice")
        self.assertIsNone(self.db.match(self.vector(0.70))[0])

    def test_confirmed_enrollment_roundtrips(self):
        samples = [self.vector(0.20 + i / 1000) for i in range(6)]
        with self.assertRaises(PermissionError):
            self.db.add_person_samples("Alice", samples)
        self.db.add_person_samples("Alice", samples, confirmed=True)
        reloaded = DlibFaceDatabase(self.db.db_path)
        self.assertEqual(len(reloaded.data["Alice"]), 6)

    def test_duplicate_sample_is_not_added(self):
        self.assertTrue(self.db.add_person("Alice", self.vector(0.2), confirmed=True))
        self.assertFalse(self.db.add_person("Alice", self.vector(0.2), confirmed=True))
        self.assertEqual(len(self.db.data["Alice"]), 1)

    def test_invalid_descriptor_size_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db._normalize(np.zeros(127, dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
