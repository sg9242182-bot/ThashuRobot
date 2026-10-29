import threading
import time

from core.model_paths import data_path, model_path


class VisionCore:
    """Owns camera perception only; hardware actuation belongs to other managers."""

    def __init__(
        self,
        camera=None,
        detector=None,
        recognizer=None,
        database=None,
        tracker=None,
        person_detector=None,
        person_tracker=None,
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
            detector = FaceDetector(model_path("face", "face_detection_yunet_2023mar.onnx"))
            if person_detector is None:
                from vision.person_detection import UpperBodyDetector
                person_detector = UpperBodyDetector()
        if recognizer is None:
            from vision.face_recognition import FaceRecognizer
            recognizer = FaceRecognizer(model_path("face", "w600k_r50.onnx"))
        if database is None:
            from vision.face_database import FaceDatabase
            database = FaceDatabase(data_path("people_faces.json"))
        if tracker is None:
            from vision.tracker import CentroidTracker
            tracker = CentroidTracker(max_disappeared=20)
        if person_detector is not None and person_tracker is None:
            from vision.tracker import CentroidTracker
            person_tracker = CentroidTracker(max_disappeared=8)
        self.camera = camera
        self.detector = detector
        self.person_detector = person_detector
        self.person_tracker = person_tracker
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
        self.current_tracks = []
        self.current_people = []
        self.latest_frame_at = None
        self.frame_size = (640, 480)
        self.person_present = False
        self._reported_face_count = 0
        self._reported_person_count = 0
        self._recognition_votes = {}
        # Haar detections can flicker between frames. Only publish a face after
        # it is spatially consistent across three consecutive camera frames.
        self._detection_candidates = []
        self._next_detection_candidate_id = 0
        self._person_detection_candidates = []
        self._next_person_candidate_id = 0

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
            self.current_tracks = []
            self.current_people = []
            self.latest_frame_at = None
            self.person_present = False
            self._reported_face_count = 0
            self._reported_person_count = 0
            self._tracker_reset_pending = True
            self._recognition_votes.clear()

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
            with self._lock:
                self.current_faces = []
                self.current_names.clear()
                self.current_tracks = []
                self.current_people = []
                self.latest_frame_at = None
                self.person_present = False
                self._reported_person_count = 0
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
        """Return perception and short-lived tracking metadata, never actuators."""
        with self._lock:
            faces = []
            for tracked in self.current_tracks:
                track_id = tracked.get("track_id")
                name = self.current_names.get(track_id, "Unknown")
                faces.append({
                    "bbox": tracked["bbox"],
                    "center": tracked["center"],
                    "track_id": track_id,
                    "ambiguous": tracked.get("ambiguous", True),
                    "name": name,
                    "is_owner": name not in ("Unknown", None),
                })

            return {
                "faces": faces,
                "persons": [dict(person) for person in self.current_people],
                "names": dict(self.current_names),
                "present": self.person_present,
                "observed_at": self.latest_frame_at,
                "frame_size": self.frame_size,
            }

    def begin_enrollment(self, required_samples=5, timeout=45.0):
        """Collect a short-lived batch from one stable, unambiguous face."""
        with self._lock:
            self._enrollment = {
                "status": "collecting",
                "started_at": time.monotonic(),
                "expires_at": time.monotonic() + float(timeout),
                "required_samples": max(5, int(required_samples)),
                "track_id": None,
                "samples": [],
            }

    def enrollment_status(self):
        with self._lock:
            state = getattr(self, "_enrollment", None)
            if not state:
                return {"status": "idle", "sample_count": 0}
            return {
                "status": state["status"],
                "sample_count": len(state["samples"]),
                "required_samples": state["required_samples"],
                "expires_at": state["expires_at"],
            }

    def enrollment_samples(self):
        """Return copies of ready embeddings; caller must clear after commit/cancel."""
        with self._lock:
            state = getattr(self, "_enrollment", None)
            if not state or state["status"] != "ready":
                return None
            return [sample.copy() for sample in state["samples"]]

    def clear_enrollment(self):
        with self._lock:
            self._enrollment = None

    def _stabilize_detections(self, detections):
        """Filter single-frame Haar false positives before tracking or reporting."""
        detections = [tuple(map(int, box)) for box in (detections or [])]
        candidates = self._detection_candidates

        pairs = []
        for candidate_index, candidate in enumerate(candidates):
            x1, y1, x2, y2 = candidate["bbox"]
            old_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            old_size = max(x2 - x1, y2 - y1)
            for detection_index, box in enumerate(detections):
                nx1, ny1, nx2, ny2 = box
                new_center = ((nx1 + nx2) / 2.0, (ny1 + ny2) / 2.0)
                new_size = max(nx2 - nx1, ny2 - ny1)
                dx = old_center[0] - new_center[0]
                dy = old_center[1] - new_center[1]
                distance = (dx * dx + dy * dy) ** 0.5
                gate = max(60.0, 0.65 * max(old_size, new_size))
                if distance <= gate:
                    pairs.append((distance, candidate_index, detection_index))

        used_candidates = set()
        used_detections = set()
        matches = []
        for _distance, candidate_index, detection_index in sorted(pairs):
            if candidate_index in used_candidates or detection_index in used_detections:
                continue
            used_candidates.add(candidate_index)
            used_detections.add(detection_index)
            matches.append((candidate_index, detection_index))

        for candidate_index, candidate in enumerate(candidates):
            if candidate_index not in used_candidates:
                candidate["misses"] += 1
                candidate["hits"] = 0

        for candidate_index, detection_index in matches:
            candidate = candidates[candidate_index]
            was_missing = candidate["misses"] > 0
            candidate["bbox"] = detections[detection_index]
            candidate["misses"] = 0
            candidate["hits"] = 1 if was_missing else candidate["hits"] + 1
            if candidate["hits"] >= 3:
                candidate["confirmed"] = True

        for detection_index, box in enumerate(detections):
            if detection_index not in used_detections:
                candidates.append({
                    "id": self._next_detection_candidate_id,
                    "bbox": box,
                    "hits": 1,
                    "misses": 0,
                    "confirmed": False,
                })
                self._next_detection_candidate_id += 1

        # Hold a confirmed face through brief detector flicker; clear it only
        # after three consecutive misses. This also stabilizes count-change logs.
        self._detection_candidates = [
            candidate for candidate in candidates if candidate["misses"] < 3
        ]
        return [
            candidate["bbox"]
            for candidate in self._detection_candidates
            if candidate["confirmed"]
        ]

    def _stabilize_person_detections(self, detections):
        """Require three spatially consistent frames before publishing a person box."""
        detections = [tuple(map(int, box)) for box in (detections or [])]
        candidates = self._person_detection_candidates
        pairs = []

        for candidate_index, candidate in enumerate(candidates):
            x1, y1, x2, y2 = candidate["bbox"]
            old_center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            old_size = max(x2 - x1, y2 - y1)
            for detection_index, box in enumerate(detections):
                nx1, ny1, nx2, ny2 = box
                new_center = ((nx1 + nx2) / 2.0, (ny1 + ny2) / 2.0)
                new_size = max(nx2 - nx1, ny2 - ny1)
                dx = old_center[0] - new_center[0]
                dy = old_center[1] - new_center[1]
                distance = (dx * dx + dy * dy) ** 0.5
                gate = max(80.0, 0.65 * max(old_size, new_size))
                if distance <= gate:
                    pairs.append((distance, candidate_index, detection_index))

        used_candidates = set()
        used_detections = set()
        for _distance, candidate_index, detection_index in sorted(pairs):
            if candidate_index in used_candidates or detection_index in used_detections:
                continue
            used_candidates.add(candidate_index)
            used_detections.add(detection_index)
            candidate = candidates[candidate_index]
            was_missing = candidate["misses"] > 0
            candidate["bbox"] = detections[detection_index]
            candidate["misses"] = 0
            candidate["hits"] = 1 if was_missing else candidate["hits"] + 1
            if candidate["hits"] >= 3:
                candidate["confirmed"] = True

        for candidate_index, candidate in enumerate(candidates):
            if candidate_index not in used_candidates:
                candidate["misses"] += 1
                candidate["hits"] = 0

        for detection_index, box in enumerate(detections):
            if detection_index not in used_detections:
                candidates.append({
                    "id": self._next_person_candidate_id,
                    "bbox": box,
                    "hits": 1,
                    "misses": 0,
                    "confirmed": False,
                })
                self._next_person_candidate_id += 1

        self._person_detection_candidates = [
            candidate for candidate in candidates if candidate["misses"] < 3
        ]
        return [
            candidate["bbox"]
            for candidate in self._person_detection_candidates
            if candidate["confirmed"]
        ]

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
                    if self.person_tracker is not None:
                        self.person_tracker.reset()
                    self.current_names.clear()
                    self.current_faces = []
                    self.current_people = []
                    self.person_present = False
                    self._detection_candidates = []
                    self._next_detection_candidate_id = 0
                    self._person_detection_candidates = []
                    self._next_person_candidate_id = 0
                    self._tracker_reset_pending = False
                    last_recog = 0.0

            if not self._processing_enabled.is_set():
                continue

            if hasattr(self.camera, "read_with_timestamp"):
                frame, frame_timestamp = self.camera.read_with_timestamp()
            else:
                frame = self.camera.read()
                frame_timestamp = time.monotonic()
            if frame is None:
                time.sleep(0.05)
                continue
            if not self._processing_enabled.is_set():
                continue

            try:
                frame_height, frame_width = frame.shape[:2]
            except (AttributeError, TypeError, ValueError):
                frame_width, frame_height = self.frame_size

            landmark_detections = []
            if getattr(self.detector, "recognition_ready", False):
                landmark_detections = self.detector.detect_with_landmarks(frame)
                detections = [item["bbox"] for item in landmark_detections]
            else:
                landmark_detections = []
            if getattr(self.detector, "recognition_ready", False):
                landmark_detections = self.detector.detect_with_landmarks(frame)
                detections = [item["bbox"] for item in landmark_detections]
            else:
                detections = self.detector.detect(frame)
            if not self._processing_enabled.is_set():
                continue
            faces = self._stabilize_detections(detections)
            person_boxes = []
            if self.person_detector is not None:
                person_detections = self.person_detector.detect(frame)
                if not self._processing_enabled.is_set():
                    continue
                person_boxes = self._stabilize_person_detections(person_detections)

            if self.person_tracker is not None:
                tracked_persons = self.person_tracker.update(person_boxes)
                person_assignments = dict(
                    getattr(self.person_tracker, "last_assignments", {}) or {}
                )
                ambiguous_person_ids = set(
                    getattr(self.person_tracker, "last_ambiguous_ids", set()) or ()
                )
                if not person_assignments and len(person_boxes) == 1 and len(tracked_persons) == 1:
                    person_assignments[0] = next(iter(tracked_persons))
                current_people = []
                for person_index, (x1, y1, x2, y2) in enumerate(person_boxes):
                    track_id = person_assignments.get(person_index)
                    if track_id is None:
                        continue
                    current_people.append({
                        "bbox": (x1, y1, x2, y2),
                        "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                        "track_id": track_id,
                        "ambiguous": track_id in ambiguous_person_ids,
                    })
            else:
                current_people = []

            with self._lock:
                if not self._processing_enabled.is_set():
                    continue
                tracked = self.tracker.update(faces)
                assignments = dict(getattr(self.tracker, "last_assignments", {}) or {})
                ambiguous_ids = set(getattr(self.tracker, "last_ambiguous_ids", set()) or ())
                if not assignments and len(faces) == 1 and len(tracked) == 1:
                    assignments[0] = next(iter(tracked))

            now = time.time()
            with self._lock:
                enrollment = getattr(self, "_enrollment", None)
                if enrollment and enrollment["status"] == "collecting":
                    if time.monotonic() >= enrollment["expires_at"]:
                        enrollment["status"] = "timed_out"
                    elif len(faces) > 1:
                        enrollment["status"] = "ambiguous"
                        enrollment["samples"].clear()
                    elif len(faces) == 1 and (
                        assignments.get(0) is None or assignments.get(0) in ambiguous_ids
                    ):
                        enrollment["samples"].clear()
                        enrollment["track_id"] = None
            if now - last_recog > recog_interval and faces:
                for face_index, (x1, y1, x2, y2) in enumerate(faces):
                    if not self._processing_enabled.is_set():
                        break
                    track_id = assignments.get(face_index)
                    if track_id is None and len(tracked) == 1:
                        track_id = next(iter(tracked))
                    if track_id is None:
                        continue

                    # Match the stabilized box to the closest current YuNet
                    # observation. Haar-only detections have no landmarks and
                    # therefore cannot claim an identity.
                    landmark_item = None
                    best_overlap = 0.0
                    for item in landmark_detections:
                        ax1, ay1, ax2, ay2 = item["bbox"]
                        ix1, iy1 = max(x1, ax1), max(y1, ay1)
                        ix2, iy2 = min(x2, ax2), min(y2, ay2)
                        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                        union = ((x2 - x1) * (y2 - y1)
                                 + (ax2 - ax1) * (ay2 - ay1) - intersection)
                        overlap = intersection / union if union > 0 else 0.0
                        if overlap > best_overlap:
                            best_overlap, landmark_item = overlap, item
                    if landmark_item is None or best_overlap < 0.30:
                        continue

                    face_img = frame[y1:y2, x1:x2]
                    embedding = self.recognizer.get_embedding(
                        face_img,
                        landmark_item["landmarks"],
                        bbox_origin=(x1, y1),
                    )
                    if not self._processing_enabled.is_set():
                        break

                    recognized, _score = (
                        self.database.match(embedding) if embedding is not None
                        else (None, -1.0)
                    )
                    with self._lock:
                        enrollment = getattr(self, "_enrollment", None)
                        if enrollment and enrollment["status"] == "collecting":
                            if (len(faces) != 1 or track_id in ambiguous_ids
                                    or embedding is None):
                                enrollment["samples"].clear()
                                enrollment["track_id"] = None
                            elif enrollment["track_id"] not in (None, track_id):
                                enrollment["status"] = "ambiguous"
                                enrollment["samples"].clear()
                            else:
                                enrollment["track_id"] = track_id
                                enrollment["samples"].append(embedding.copy())
                                if len(enrollment["samples"]) >= enrollment["required_samples"]:
                                    enrollment["status"] = "ready"

                    with self._lock:
                        if not self._processing_enabled.is_set():
                            break
                        previous_name, votes = self._recognition_votes.get(track_id, (None, 0))
                        if recognized is not None and recognized == previous_name:
                            votes += 1
                        elif recognized is not None:
                            previous_name, votes = recognized, 1
                        else:
                            previous_name, votes = None, 0
                        self._recognition_votes[track_id] = (previous_name, votes)
                        self.current_names[track_id] = (
                            recognized if recognized is not None and votes >= 3
                            else "Unknown"
                        )

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
                self.current_tracks = []
                self.current_people = current_people
                for face_index, (x1, y1, x2, y2) in enumerate(faces):
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    track_id = assignments.get(face_index)
                    self.current_tracks.append({
                        "bbox": (x1, y1, x2, y2),
                        "center": (cx, cy),
                        "track_id": track_id,
                        "ambiguous": track_id is None or track_id in ambiguous_ids,
                    })
                self.latest_frame_at = frame_timestamp
                self.frame_size = (frame_width, frame_height)
                self.person_present = bool(faces or current_people)
                previous_person_count = self._reported_person_count
                self._reported_person_count = len(current_people)

            if len(current_people) != previous_person_count:
                if previous_person_count == 0 and current_people:
                    print(
                        "[VISION] Upper body detected "
                        f"(count={len(current_people)}, "
                        f"tracks={[person['track_id'] for person in current_people]})"
                    )
                elif not current_people:
                    print("[VISION] No upper bodies detected")
                else:
                    print(
                        "[VISION] Upper-body count changed: "
                        f"{previous_person_count} -> {len(current_people)}"
                    )

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
