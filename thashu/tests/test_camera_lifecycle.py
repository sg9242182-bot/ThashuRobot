import importlib
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch


class FakeCapture:
    def __init__(self):
        self.opened = True

    def set(self, *_args):
        return True

    def isOpened(self):
        return self.opened

    def read(self):
        time.sleep(0.003)
        return (self.opened, object() if self.opened else None)

    def release(self):
        self.opened = False


class CameraLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_cv2 = types.ModuleType("cv2")
        fake_cv2.CAP_V4L2 = 0
        fake_cv2.CAP_PROP_BUFFERSIZE = 1
        fake_cv2.CAP_PROP_FOURCC = 2
        fake_cv2.CAP_PROP_FRAME_WIDTH = 3
        fake_cv2.CAP_PROP_FRAME_HEIGHT = 4
        fake_cv2.CAP_PROP_FPS = 5
        fake_cv2.VideoWriter_fourcc = lambda *_args: 0
        cls.captures = []

        def create_capture(*_args):
            cap = FakeCapture()
            cls.captures.append(cap)
            return cap

        fake_cv2.VideoCapture = create_capture
        with patch.dict(sys.modules, {"cv2": fake_cv2}):
            sys.modules.pop("vision.camera", None)
            cls.camera_module = importlib.import_module("vision.camera")
        cls.Camera = cls.camera_module.Camera

    def test_start_is_idempotent_and_restart_waits_for_old_capture_thread(self):
        self.captures.clear()
        camera = self.Camera()
        camera.start()
        first_thread = camera._thread
        camera.start()
        self.assertIs(camera._thread, first_thread)
        self.assertEqual(len(self.captures), 1)

        camera.stop()
        self.assertFalse(first_thread.is_alive())

        camera.start()
        second_thread = camera._thread
        self.assertIsNot(second_thread, first_thread)
        self.assertEqual(len(self.captures), 2)
        camera.stop()
        self.assertFalse(second_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
