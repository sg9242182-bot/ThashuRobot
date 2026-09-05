import threading
import time

from vision.camera           import Camera
from vision.face_detection   import FaceDetector
from vision.face_recognition import FaceRecognizer
from vision.face_database    import FaceDatabase
from vision.tracker          import CentroidTracker
from vision.follow_logic     import FollowLogic
from hardware.servo_tracking import ServoTracker
from hardware.motors         import MotorController



class VisionCore:
    def __init__(self):
        self.camera     = Camera(src=0, width=640, height=480)
        self.detector   = FaceDetector(
            model_path  ="models/mobilenet_ssd/MobileNetSSD_deploy.caffemodel",
            config_path ="models/mobilenet_ssd/MobileNetSSD_deploy.prototxt"
        )
        self.recognizer = FaceRecognizer("models/face/w600k_r50.onnx")
        self.database   = FaceDatabase("data/faces.json")
        self.tracker    = CentroidTracker(max_disappeared=20)
        self.follow     = FollowLogic(frame_w=640, frame_h=480)
        self.servo      = ServoTracker()
        self.motors     = MotorController()


        self._thread  = None
        self._running = False
        self._lock    = threading.Lock()

        self.current_faces  = []
        self.current_names  = {}
        self.person_present = False
        self._following_enabled = True

        print("[VISION] Initialized")

    def on_runtime_state_changed(self, payload):
        """Enable autonomous following only when runtime is IDLE."""
        if not payload or "to" not in payload:
            return

        self._following_enabled = payload["to"] == "IDLE"

        if not self._following_enabled:
            self.motors.stop()
            self.servo.center()

    def start(self):
        self.camera.start()
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[VISION] Started")

    def stop(self):
        self._running = False
        self.motors.stop()
        self.servo.center()
        self.camera.stop()
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
                    "bbox":     (x1, y1, x2, y2),
                    "center":   (cx, cy),
                    "name":     name,
                    "is_owner": name not in ("Unknown", None)
                })

            return {
                "faces":   persons,
                "names":   dict(self.current_names),
                "present": self.person_present
            }

    def _loop(self):
        RECOG_INTERVAL = 2
        last_recog     = 0

        while self._running:
            frame = self.camera.read()
            if frame is None:
                time.sleep(0.05)
                continue

            faces = self.detector.detect(frame)
            tracked = self.tracker.update(faces)

            now = time.time()
            if now - last_recog > RECOG_INTERVAL and faces:
                for (x1, y1, x2, y2) in faces:
                    face_img  = frame[y1:y2, x1:x2]
                    embedding = self.recognizer.get_embedding(face_img)

                    if embedding is not None:
                        name, score = self.database.match(embedding)

                        if tracked:
                            cx = (x1 + x2) // 2
                            cy = (y1 + y2) // 2
                            closest_id = min(
                                tracked.keys(),
                                key=lambda i: abs(tracked[i][0] - cx) + abs(tracked[i][1] - cy)
                            )
                            with self._lock:
                                self.current_names[closest_id] = name or "Unknown"

                last_recog = now

            with self._lock:
                self.current_faces  = faces
                self.person_present = len(faces) > 0

            if self._following_enabled:
                target = self.follow.select_target(faces)

                if target:
                    cx, cy = target
                    self.servo.update(cx, cy, 640, 480)

                    direction = self.follow.should_move_motors(cx, cy)
                    if direction == "LEFT":
                        self.motors.left(speed=150)
                    elif direction == "RIGHT":
                        self.motors.right(speed=150)
                    else:
                        self.motors.stop()
                else:
                    self.motors.stop()
            else:
                if self.follow.should_stop_motors(faces):
                    self.motors.stop()
                    self.servo.center()

            time.sleep(0.08)