import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

from core.model_paths import data_path, model_path


_vision_logger = logging.getLogger("thashu.vision")
_vision_logger.setLevel(logging.INFO)
_vision_logger.propagate = False
if not _vision_logger.handlers:
    _vision_handler = logging.StreamHandler()
    _vision_handler.setFormatter(logging.Formatter("%(message)s"))
    _vision_logger.addHandler(_vision_handler)


def _log_vision_event(event: str, **fields) -> None:
    """Emit one JSON log record containing only explicitly selected metadata."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "severity": "INFO",
        "component": "pi_vision",
        "event": event,
        **fields,
    }
    _vision_logger.info("%s", json.dumps(record, separators=(",", ":"), sort_keys=True))


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
            from vision.face_recognition import DlibFaceRecognizer
            recognizer = DlibFaceRecognizer()
        if database is None:
            from vision.face_database import DlibFaceDatabase
            database = DlibFaceDatabase(data_path("people_faces_dlib.json"))
        face_backend = "dlib"
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
        self.face_backend = face_backend
        _log_vision_event("recognizer_initialized", backend="dlib", descriptor_dimensions=128)
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
        self._recognition_events = []
        self.current_tracks = []
        self.current_people = []
        self.latest_frame_at = None
        self.frame_size = (640, 480)
        self.person_present = False
        self._reported_face_count = 0
        self._reported_person_count = 0
        self._recognition_votes = {}
        self._last_adaptive_sample_at = {}
        self._auto_face_adapt = os.environ.get("THASHU_FACE_AUTO_ADAPT", "").strip() == "1"
        # Haar detections can flicker between frames. Only publish a face after
        # it is spatially consistent across three consecutive camera frames.
        self._detection_candidates = []
        self._next_detection_candidate_id = 0
        self._person_detection_candidates = []
        self._next_person_candidate_id = 0

        _log_vision_event("initialized")

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
                _log_vision_event("processing_resumed")
            self._processing_enabled.set()
            return

        if was_enabled:
            _log_vision_event("processing_paused")
        else:
            _log_vision_event("processing_remains_paused")
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
        _log_vision_event("started")
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
                _log_vision_event("worker_still_stopping")

        _log_vision_event("stopped")

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

    def drain_recognition_events(self):
        """Return confirmed, unambiguous recognition transitions since last drain."""
        with self._lock:
            events = self._recognition_events
            self._recognition_events = []
            return events

    def begin_enrollment(
        self, required_samples=5, timeout=180.0, *,
        initial_samples=None, target_name=None,
    ):
        """Collect quality-approved samples, optionally replacing overlaps."""
        required_samples = max(5, int(required_samples))
        seed_samples = [sample.copy() for sample in (initial_samples or [])]
        if len(seed_samples) > required_samples:
            raise ValueError("Initial enrollment samples exceed the required count")
        with self._lock:
            self._enrollment = {
                "status": "ready" if len(seed_samples) >= required_samples else "collecting",
                "started_at": time.monotonic(),
                "expires_at": time.monotonic() + float(timeout),
                "required_samples": required_samples,
                "track_id": None,
                "samples": [sample.copy() for sample in seed_samples],
                "seed_samples": seed_samples,
                "target_name": target_name,
                "overlap_rejections": 0,
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
                "overlap_rejections": state.get("overlap_rejections", 0),
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
        recog_interval = 0.75
        debug_match = os.environ.get("THASHU_FACE_MATCH_DEBUG", "").strip() == "1"
        if debug_match:
            _log_vision_event("face_match_diagnostics_enabled")
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

            # Dlib computes its own five-point landmarks inside each detected crop.
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
            # Dlib descriptors are more CPU intensive. Run them at a lower
            # cadence inside the dedicated vision worker; camera capture,
            # audio, motor control, and safety loops remain independent.
            recog_interval = 0.75
            if now - last_recog > recog_interval and faces:
                for face_index, (x1, y1, x2, y2) in enumerate(faces):
                    if not self._processing_enabled.is_set():
                        break
                    track_id = assignments.get(face_index)
                    if track_id is None and len(tracked) == 1:
                        track_id = next(iter(tracked))
                    if track_id is None:
                        if debug_match:
                            _log_vision_event("face_match_skipped_unstable_track")
                        continue

                    face_img = frame[y1:y2, x1:x2]
                    embedding = self.recognizer.get_embedding(face_img)
                    if not self._processing_enabled.is_set():
                        break

                    if embedding is None:
                        recognized, _score = None, -1.0
                        if debug_match:
                            _log_vision_event("face_match_skipped_embedding_unavailable")
                    elif debug_match:
                        recognized, _score = self.database.match(
                            embedding, diagnostics=True
                        )
                        compare_scores = getattr(
                            self.database, "compare_sample_and_prototype_scores", None
                        )
                        if callable(compare_scores):
                            comparisons = compare_scores(embedding)
                            if comparisons:
                                _log_vision_event("face_match_comparison_completed")
                    else:
                        recognized, _score = self.database.match(embedding)
                    with self._lock:
                        enrollment = getattr(self, "_enrollment", None)
                        if enrollment and enrollment["status"] == "collecting":
                            if (len(faces) != 1 or track_id in ambiguous_ids
                                    or embedding is None):
                                enrollment["samples"] = [
                                    sample.copy() for sample in enrollment.get("seed_samples", [])
                                ]
                                enrollment["track_id"] = None
                            elif enrollment["track_id"] not in (None, track_id):
                                enrollment["status"] = "ambiguous"
                                enrollment["samples"] = [
                                    sample.copy() for sample in enrollment.get("seed_samples", [])
                                ]
                            else:
                                enrollment["track_id"] = track_id
                                target_name = enrollment.get("target_name")
                                overlap = (
                                    self.database.best_other_match(
                                        embedding, exclude_name=target_name
                                    )
                                    if target_name
                                    else (None, -1.0)
                                )
                                other_name, overlap_score = overlap
                                overlap_check = getattr(
                                    self.database, "is_overlap", None
                                )
                                overlaps = (
                                    overlap_check(overlap_score)
                                    if callable(overlap_check)
                                    else overlap_score >= self.database.threshold
                                )
                                if other_name is not None and overlaps:
                                    enrollment["overlap_rejections"] = (
                                        enrollment.get("overlap_rejections", 0) + 1
                                    )
                                    needed = max(
                                        0,
                                        enrollment["required_samples"]
                                        - len(enrollment["samples"]),
                                    )
                                    _log_vision_event(
                                        "enrollment_view_rejected_overlap",
                                        accepted_samples=len(enrollment["samples"]),
                                        required_samples=enrollment["required_samples"],
                                        replacement_samples_needed=needed,
                                    )
                                else:
                                    enrollment["samples"].append(embedding.copy())
                                    sample_count = len(enrollment["samples"])
                                    _log_vision_event(
                                        "enrollment_sample_accepted",
                                        accepted_samples=sample_count,
                                        required_samples=enrollment["required_samples"],
                                    )
                                    if sample_count >= enrollment["required_samples"]:
                                        enrollment["status"] = "ready"
                                        _log_vision_event("enrollment_capture_ready")

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
                        published_name = (
                            recognized if recognized is not None and votes >= 3
                            else "Unknown"
                        )
                        if debug_match and recognized is not None and votes < 3:
                            gate_label = (
                                "distance gates passed"
                                if self.face_backend == "dlib"
                                else "similarity gates passed"
                            )
                            _log_vision_event(
                                "face_match_temporal_confirmation",
                                gate=gate_label,
                                votes=votes,
                                required_votes=3,
                            )
                        old_published_name = self.current_names.get(track_id, "Unknown")
                        self.current_names[track_id] = published_name
                        if (
                            published_name != "Unknown"
                            and published_name != old_published_name
                            and len(faces) == 1
                            and track_id not in ambiguous_ids
                            and getattr(self, "_enrollment", None) is None
                        ):
                            self._recognition_events.append({
                                "name": published_name,
                                "observed_at": time.monotonic(),
                            })
                        adapt_identity = None
                        if (
                            published_name != old_published_name
                            and published_name != "Unknown"
                        ):
                            _log_vision_event("identity_recognized")
                        elif old_published_name != "Unknown" and published_name == "Unknown":
                            _log_vision_event("identity_confidence_lost")

                        enrollment_active = getattr(self, "_enrollment", None) is not None
                        if (
                            published_name != "Unknown"
                            and votes >= 3
                            and len(faces) == 1
                            and track_id not in ambiguous_ids
                            and not enrollment_active
                            and self._auto_face_adapt
                            and time.monotonic()
                                - self._last_adaptive_sample_at.get(published_name, 0.0)
                                >= 60.0
                            and callable(
                                getattr(self.database, "add_high_confidence_sample", None)
                            )
                        ):
                            adapt_identity = published_name

                    if adapt_identity is not None and embedding is not None:
                        try:
                            if self.database.add_high_confidence_sample(
                                adapt_identity, embedding
                            ):
                                self._last_adaptive_sample_at[adapt_identity] = time.monotonic()
                                _log_vision_event("high_confidence_adaptation_sample_added")
                        except Exception as exc:
                            _log_vision_event(
                                "high_confidence_adaptation_sample_skipped",
                                error_type=type(exc).__name__,
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
                    _log_vision_event(
                        "upper_body_detection_started", count=len(current_people)
                    )
                elif not current_people:
                    _log_vision_event("upper_body_detection_cleared")
                else:
                    _log_vision_event(
                        "upper_body_count_changed",
                        previous_count=previous_person_count,
                        count=len(current_people),
                    )

            if face_count != previous_count:
                if previous_count == 0 and face_count > 0:
                    _log_vision_event("face_detection_started", count=face_count)
                elif face_count == 0:
                    _log_vision_event("face_detection_cleared")
                else:
                    _log_vision_event(
                        "face_count_changed", previous_count=previous_count, count=face_count
                    )

            time.sleep(0.08)
