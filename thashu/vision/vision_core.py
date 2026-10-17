import threading
import time


class VisionCore:
    """Coordinates the single camera/vision worker and gates follow behavior by runtime state."""

    def __init__(
        self,
        camera=None,
        detector=None,
        recognizer=None,
        database=None,
        tracker=None,
        follow=None,
        servo=None,
        motors=None,
    ):
        # Lazy imports let lifecycle behavior be tested without opening hardware
        # or loading vision models. Production still uses the existing modules.
        if camera is None:
            from vision.camera import Camera
            camera = Camera(src=0, width=640, height=480)
        if detector is None:
            from vision.face_detection import FaceDetector
            detector = FaceDetector(
                model_path="models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
                config_path="models/mobilenet_ssd/MobileNetSSD_deploy.prototxt",
            )
        if recognizer is None:
            from vision.face_recognition import FaceRecognizer
            recognizer = FaceRecognizer("models/face/w600k_r50.onnx")
        if database is None:
            from vision.face_database import FaceDatabase
            database = FaceDatabase("data/faces.json")
        if tracker is None:
            from vision.tracker import CentroidTracker
            tracker = CentroidTracker(max_disappeared=20)
        if follow is None:
            from vision.follow_logic import FollowLogic
            follow = FollowLogic(frame_w=640, frame_h=480)
        if servo is None:
            from hardware.servo_tracking import ServoTracker
            servo = ServoTracker()
        if motors is None:
            from hardware.motors import MotorController
            motors = MotorController()

        self.camera = camera
        self.detector = detector
        self.recognizer = recognizer
        self.database = database
        self.tracker = tracker
        self.follow = follow
        self.servo = servo
        self.motors = motors

        self._thread = None
        self._running = False
        self._lifecycle_lock = threading.Lock()
        self._actuation_lock = threading.Lock()
        self._lock = threading.Lock()
        self._processing_enabled = threading.Event()
        self._processing_enabled.set()  # Runtime starts in IDLE.

        self._tracker_reset_pending = False
        self.current_faces = []
        self.current_names = {}
        self.person_present = False

        print("[VISION] Initialized")

    def on_runtime_state_changed(self, payload):
        """Run inference and autonomous following only in IDLE."""
        if not isinstance(payload, dict) or "to" not in payload:
            return

        enable_processing = payload["to"] == "IDLE"
        with self._actuation_lock:
            was_enabled = self._processing_enabled.is_set()
            if enable_processing:
                if not was_enabled:
                    with self._lock:
                        self._tracker_reset_pending = True
                self._processing_enabled.set()
                return

            self._processing_enabled.clear()
            if was_enabled:
                # Serialize the stop with the vision worker's actuator writes.
                self.motors.stop()
                self.servo.center()

            with self._lock:
                self.current_faces = []
                self.current_names.clear()
                self.person_present = False
                self._tracker_reset_pending = True

    def start(self):
        """Start the camera and one vision worker; repeated starts are harmless."""
        with self._lifecycle_lock:
            if self._running and self._thread is not None and self._thread.is_alive():
                return self
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Previous vision worker is still stopping")

            self.camera.start()
            self._running = True
            self._thread = threading.Thread(
                target=self._loop,
                name="thashu-vision",
                daemon=True,
            )
            self._thread.start()
        print("[VISION] Started")
        return self

    def stop(self):
        """Stop outputs and join the vision worker without leaving a duplicate thread."""
        with self._lifecycle_lock:
            if not self._running and self._thread is None:
                return

            self._running = False
            with self._actuation_lock:
                self._processing_enabled.clear()
                self.motors.stop()
                self.servo.center()
            self.camera.stop()
            thread = self._thread

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

        with self._lifecycle_lock:
            if thread is self._thread and (thread is None or not thread.is_alive()):
                self._thread = None
            elif thread is not None and thread.is_alive():
                print("[VISION] Worker is still stopping; refusing duplicate start")

        print("[VISION] Stopped")

    def get_state(self) -> dict:
        """Thread-safe state read for main/brain."""
        with self._lock:
            persons = []
            for (x1, y1, x2, y2) in self.current_faces:
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                closest_id = None
                if self.current_names:
                    closest_id = min(
                        self.current_names.keys(),
                        key=lambda i: abs(self.tracker.objects.get(i, (cx, cy))[0] - cx)
                                    + abs(self.tracker.objects.get(i, (cx, cy))[1] - cy)
                    )
                name = self.current_names.get(closest_id, "Unknown") if closest_id else "Unknown"

                persons.append({
                    "bbox": (x1, y1, x2, y2),
                    "center": (cx, cy),
                    "name": name,
                    "is_owner": name not in ("Unknown", None),
                })

            return {
                "faces": persons,
                "names": dict(self.current_names),
                "present": self.person_present,
            }

    def _loop(self):
        recog_interval = 2.0
        last_recog = 0.0

        while self._running:
            if not self._processing_enabled.wait(timeout=0.1):
                continue
            if not self._running:
                break

            with self._lock:
                if self._tracker_reset_pending:
                    self.tracker.reset()
                    self.current_names.clear()
                    self.current_faces = []
                    self.person_present = False
                    self._tracker_reset_pending = False
                    last_recog = 0.0

            if not self._processing_enabled.is_set():
                continue

            frame = self.camera.read()
            if frame is None:
                time.sleep(0.05)
                continue
            if not self._processing_enabled.is_set():
                continue

            faces = self.detector.detect(frame)
            if not self._processing_enabled.is_set():
                continue

            with self._lock:
                if not self._processing_enabled.is_set():
                    continue
                tracked = self.tracker.update(faces)

            now = time.time()
            if now - last_recog > recog_interval and faces:
                for (x1, y1, x2, y2) in faces:
                    if not self._processing_enabled.is_set():
                        break
                    face_img = frame[y1:y2, x1:x2]
                    embedding = self.recognizer.get_embedding(face_img)
                    if not self._processing_enabled.is_set():
                        break

                    if embedding is not None and tracked:
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        closest_id = min(
                            tracked.keys(),
                            key=lambda i: abs(tracked[i][0] - cx) + abs(tracked[i][1] - cy),
                        )
                        name, _score = self.database.match(embedding)
                        with self._lock:
                            if self._processing_enabled.is_set():
                                self.current_names[closest_id] = name or "Unknown"

                last_recog = now

            if not self._processing_enabled.is_set():
                continue

            with self._lock:
                if not self._processing_enabled.is_set():
                    continue
                self.current_faces = faces
                self.person_present = bool(faces)

            target = self.follow.select_target(faces)
            if target:
                cx, cy = target
                direction = self.follow.should_move_motors(cx, cy)
                with self._actuation_lock:
                    if not self._processing_enabled.is_set():
                        continue
                    self.servo.update(cx, cy, 640, 480)
                    if direction == "LEFT":
                        self.motors.left(speed=150)
                    elif direction == "RIGHT":
                        self.motors.right(speed=150)
                    else:
                        self.motors.stop()
            else:
                with self._actuation_lock:
                    if not self._processing_enabled.is_set():
                        continue
                    self.motors.stop()

            time.sleep(0.08)
