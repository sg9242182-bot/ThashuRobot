import threading
import time

from core.model_paths import model_path, project_path


class VisionCore:
    """Owns camera perception only; hardware actuation belongs to other managers."""

    def __init__(
        self,
        camera=None,
        detector=None,
        recognizer=None,
        database=None,
        tracker=None,
    ):
        # Lazy imports let lifecycle behavior be tested without opening hardware
        # or loading vision models. Production still uses the existing modules.
        if camera is None:
            from vision.camera import Camera
            camera = Camera(src=0, width=640, height=480)
        if detector is None:
            from vision.face_detection import FaceDetector
            # FaceDetector uses OpenCV's packaged Haar cascade; it has no local
            # MobileNet model files to load.
            detector = FaceDetector()
        if recognizer is None:
            from vision.face_recognition import FaceRecognizer
            recognizer = FaceRecognizer(model_path("face", "w600k_r50.onnx"))
        if database is None:
            from vision.face_database import FaceDatabase
            database = FaceDatabase(project_path("data", "faces.json"))
        if tracker is None:
            from vision.tracker import CentroidTracker
            tracker = CentroidTracker(max_disappeared=20)
        self.camera = camera
        self.detector = detector
        self.recognizer = recognizer
        self.database = database
        self.tracker = tracker
        self._thread = None
        self._running = False
        self._lifecycle_lock = threading.Lock()
        self._lock = threading.Lock()
        self._processing_enabled = threading.Event()
        self._processing_enabled.set()  # Runtime starts in IDLE.

        self._tracker_reset_pending = False
        self.current_faces = []
        self.current_names = {}
        self.person_present = False
        self._reported_face_count = 0

        print("[VISION] Initialized")

    def on_runtime_state_changed(self, payload):
        """Run perception only in IDLE, pausing inference during voice/AI work."""
        if not isinstance(payload, dict) or "to" not in payload:
            return

        target_state = payload["to"]
        enable_processing = target_state == "IDLE"
        was_enabled = self._processing_enabled.is_set()
        if enable_processing:
            if not was_enabled:
                with self._lock:
                    self._tracker_reset_pending = True
                print("[VISION] Processing resumed in IDLE; camera and models retained")
            self._processing_enabled.set()
            return

        if was_enabled:
            print(f"[VISION] Processing paused at {target_state}")
        else:
            print(f"[VISION] Processing remains paused during {target_state}")
        self._processing_enabled.clear()
        with self._lock:
            self.current_faces = []
            self.current_names.clear()
            self.person_present = False
            self._reported_face_count = 0
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
        print("[VISION] Started (camera worker active)")
        return self

    def stop(self):
        """Stop camera perception and join the worker without duplicating threads."""
        with self._lifecycle_lock:
            if not self._running and self._thread is None:
                return

            self._running = False
            self._processing_enabled.clear()
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

            face_count = len(faces)
            with self._lock:
                if not self._processing_enabled.is_set():
                    continue
                previous_count = self._reported_face_count
                self._reported_face_count = face_count
                self.current_faces = faces
                self.person_present = bool(faces)

            if face_count != previous_count:
                if previous_count == 0 and face_count > 0:
                    centers = [
                        ((x1 + x2) // 2, (y1 + y2) // 2)
                        for x1, y1, x2, y2 in faces
                    ]
                    print(f"[VISION] Face detected (count={face_count}, centers={centers})")
                elif face_count == 0:
                    print("[VISION] No faces detected")
                else:
                    print(f"[VISION] Face count changed: {previous_count} -> {face_count}")

            time.sleep(0.08)
