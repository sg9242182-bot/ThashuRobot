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
        self.read_calls = 0
        self._lock = threading.Lock()

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1

    def read(self):
        with self._lock:
            self.read_calls += 1
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


class FakeFollow:
    def select_target(self, faces):
        return (80, 50) if faces else None

    def should_move_motors(self, _cx, _cy):
        return "RIGHT"


class FakeServo:
    def __init__(self):
        self.update_calls = 0
        self.center_calls = 0

    def update(self, *_args):
        self.update_calls += 1

    def center(self):
        self.center_calls += 1


class FakeMotors:
    def __init__(self):
        self.right_calls = 0
        self.left_calls = 0
        self.stop_calls = 0
        self._lock = threading.Lock()

    def right(self, **_kwargs):
        with self._lock:
            self.right_calls += 1

    def left(self, **_kwargs):
        with self._lock:
            self.left_calls += 1

    def stop(self):
        with self._lock:
            self.stop_calls += 1

    def move_count(self):
        with self._lock:
            return self.right_calls + self.left_calls


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
    follow = FakeFollow()
    servo = FakeServo()
    motors = FakeMotors()
    vision = VisionCore(
        camera=camera,
        detector=detector,
        recognizer=recognizer,
        database=FakeDatabase(),
        tracker=tracker,
        follow=follow,
        servo=servo,
        motors=motors,
    )
    return vision, camera, detector, recognizer, tracker, servo, motors


class VisionLifecycleTests(unittest.TestCase):
    def test_pause_stops_inference_and_follow_then_resume_reuses_models(self):
        vision, camera, detector, recognizer, tracker, servo, motors = make_vision()
        try:
            vision.start()
            self.assertTrue(wait_for(lambda: motors.move_count() > 0))
            vision.on_runtime_state_changed({"to": "THINKING"})
            move_count = motors.move_count()
            calls_at_pause = detector.call_count()
            self.assertGreater(motors.stop_calls, 0)
            self.assertGreater(servo.center_calls, 0)

            time.sleep(0.2)
            self.assertEqual(detector.call_count(), calls_at_pause)
            self.assertEqual(motors.move_count(), move_count)
            self.assertFalse(vision.get_state()["present"])

            vision.on_runtime_state_changed({"to": "IDLE"})
            self.assertTrue(wait_for(lambda: detector.call_count() > calls_at_pause))
            self.assertGreater(tracker.reset_calls, 0)
            self.assertIs(vision.recognizer, recognizer)
            self.assertIs(vision.detector, detector)
            self.assertEqual(camera.start_calls, 1)
        finally:
            vision.stop()

    def test_state_change_during_inference_prevents_later_motor_command(self):
        detector = FakeDetector(block_first=True)
        vision, _camera, _detector, _recognizer, _tracker, _servo, motors = make_vision(detector)
        try:
            vision.start()
            self.assertTrue(detector.entered.wait(timeout=1.0))
            vision.on_runtime_state_changed({"to": "SPEAKING"})
            detector.release.set()
            time.sleep(0.15)
            self.assertEqual(motors.move_count(), 0)
        finally:
            detector.release.set()
            vision.stop()

    def test_start_is_idempotent_and_stop_joins_vision_worker(self):
        vision, camera, _detector, _recognizer, _tracker, _servo, _motors = make_vision()
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
