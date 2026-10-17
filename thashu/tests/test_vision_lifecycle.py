Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import threading
import time
import unittest

from vision.vision_core import VisionCore


class FakeFrame:
    def __getitem__(self, _key):
        return self


class FakeCamera:
    def __init__(self):
        self.start_calls = 0
        self.stop_calls = 0
        self._lock = threading.Lock()

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1

    def read(self):
        return FakeFrame()


class FakeDetector:
    def __init__(self, block_first=False):
        self.calls = 0
        self._lock = threading.Lock()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block_first = block_first

    def detect(self, _frame):
        with self._lock:
            self.calls += 1
            call = self.calls
        self.entered.set()
        if self.block_first and call == 1:
            self.release.wait(timeout=2.0)
        return [(0, 0, 100, 100)]

    def call_count(self):
        with self._lock:
            return self.calls


class FakeRecognizer:
    def get_embedding(self, _face):
        return None


class FakeDatabase:
    def match(self, _embedding):
        return None, 0.0


class FakeTracker:
    def __init__(self):
        self.objects = {}
        self.reset_calls = 0

    def reset(self):
        self.objects.clear()
        self.reset_calls += 1

    def update(self, faces):
        self.objects = {1: (50, 50)} if faces else {}
        return dict(self.objects)


def wait_for(predicate, timeout=1.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def make_vision(detector=None):
    camera = FakeCamera()
    detector = detector or FakeDetector()
    recognizer = FakeRecognizer()
    tracker = FakeTracker()
    vision = VisionCore(
        camera=camera,
        detector=detector,
        recognizer=recognizer,
        database=FakeDatabase(),
        tracker=tracker,
    )
    return vision, camera, detector, recognizer, tracker


class VisionLifecycleTests(unittest.TestCase):
    def test_pause_stops_inference_then_resume_reuses_models(self):
        vision, camera, detector, recognizer, tracker = make_vision()
        try:
            vision.start()
            self.assertTrue(wait_for(lambda: detector.call_count() > 0))
            vision.on_runtime_state_changed({"to": "THINKING"})
            calls_at_pause = detector.call_count()
            self.assertFalse(vision.get_state()["present"])

            time.sleep(0.2)
            self.assertEqual(detector.call_count(), calls_at_pause)

            vision.on_runtime_state_changed({"to": "IDLE"})
            self.assertTrue(wait_for(lambda: detector.call_count() > calls_at_pause))
            self.assertGreater(tracker.reset_calls, 0)
            self.assertIs(vision.recognizer, recognizer)
            self.assertIs(vision.detector, detector)
            self.assertEqual(camera.start_calls, 1)
        finally:
            vision.stop()

    def test_state_change_during_inference_prevents_stale_face_publish(self):
        detector = FakeDetector(block_first=True)
        vision, _camera, _detector, _recognizer, _tracker = make_vision(detector)
        try:
            vision.start()
            self.assertTrue(detector.entered.wait(timeout=1.0))
            vision.on_runtime_state_changed({"to": "SPEAKING"})
            detector.release.set()
            time.sleep(0.15)
            self.assertFalse(vision.get_state()["present"])
            self.assertEqual(detector.call_count(), 1)
        finally:
            detector.release.set()
            vision.stop()

    def test_vision_has_no_motor_or_servo_controller(self):
        vision, *_ = make_vision()
        self.assertFalse(hasattr(vision, "motors"))
        self.assertFalse(hasattr(vision, "servo"))
        self.assertFalse(hasattr(vision, "follow"))

    def test_start_is_idempotent_and_stop_joins_vision_worker(self):
        vision, camera, *_ = make_vision()
        vision.start()
        worker = vision._thread
        vision.start()
        self.assertIs(vision._thread, worker)
        self.assertEqual(camera.start_calls, 1)
        vision.stop()
        self.assertFalse(worker.is_alive())
        self.assertEqual(camera.stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
