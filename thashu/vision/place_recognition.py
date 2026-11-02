"""Best-effort visual place matching using existing OpenCV ORB features.

This is view recognition only: it does not estimate robot position, map space, or
authorize movement. Confidence thresholds remain provisional until Raspberry Pi
trials with known and unknown places are recorded.
"""

import base64
from collections import deque
import time

import cv2
import numpy as np


class PlaceRecognizer:
    MIN_FEATURES = 80
    MAX_FEATURES = 500
    MIN_GOOD_MATCHES = 18
    MATCH_DISTANCE = 48
    DUPLICATE_VIEW_SCORE = 0.84
    RECOGNITION_SCORE = 0.58
    MIN_LABEL_MARGIN = 0.12
    CAPTURE_INTERVAL_SECONDS = 1.2
    DEFAULT_REQUIRED_VIEWS = 5
    DEFAULT_CAPTURE_TIMEOUT = 180.0
    TEMPORAL_WINDOW = 5
    TEMPORAL_VOTES = 3
    MAX_FRAME_AGE_SECONDS = 1.0

    def __init__(self, place_memory, cv2_module=None):
        self.cv2 = cv2_module or cv2
        self.place_memory = place_memory
        self.orb = self.cv2.ORB_create(
            nfeatures=self.MAX_FEATURES,
            scaleFactor=1.2,
            nlevels=8,
            edgeThreshold=15,
            fastThreshold=12,
        )
        self._capture = None
        self._last_frame_at = None
        self._votes = deque(maxlen=self.TEMPORAL_WINDOW)
        self._last_output = {"label": None, "confidence": 0.0, "observed_at": None}

    def begin_capture(self, label, required_views=DEFAULT_REQUIRED_VIEWS,
                      timeout=DEFAULT_CAPTURE_TIMEOUT):
        self._capture = {
            "label": label,
            "required_views": max(3, int(required_views)),
            "expires_at": time.monotonic() + max(10.0, float(timeout)),
            "started_at": 0.0,
            "views": [],
            "status": "capturing",
            "error": None,
        }
        self.reset_temporal()

    def cancel_capture(self):
        if self._capture and self._capture["status"] == "capturing":
            self._capture["status"] = "cancelled"
            self._capture["views"].clear()

    def clear_capture(self):
        self._capture = None

    def capture_status(self):
        state = self._capture
        if not state:
            return {"status": "idle", "captured": 0, "required": 0}
        return {
            "status": state["status"],
            "label": state["label"],
            "captured": len(state["views"]),
            "required": state["required_views"],
            "expires_at": state["expires_at"],
            "error": state["error"],
        }

    @staticmethod
    def _encode(descriptors):
        return base64.b64encode(descriptors.tobytes()).decode("ascii")

    @staticmethod
    def _decode(encoded):
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return None
        if not raw or len(raw) % 32:
            return None
        return np.frombuffer(raw, dtype=np.uint8).reshape((-1, 32))

    def _extract(self, frame):
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        _keypoints, descriptors = self.orb.detectAndCompute(gray, None)
        if descriptors is None or len(descriptors) < self.MIN_FEATURES:
            return None
        return descriptors[:self.MAX_FEATURES].copy()

    def _match_score(self, query, reference):
        stored = self._decode(reference)
        if stored is None or len(stored) < self.MIN_FEATURES:
            return 0.0, 0
        matcher = self.cv2.BFMatcher(self.cv2.NORM_HAMMING, crossCheck=True)
        matches = matcher.match(query, stored)
        good_count = sum(1 for match in matches if match.distance <= self.MATCH_DISTANCE)
        if good_count < self.MIN_GOOD_MATCHES:
            return 0.0, good_count
        coverage = good_count / max(1, min(len(query), len(stored)))
        # Feature count and relative coverage both contribute; the score is
        # deliberately conservative and will be calibrated with Pi trials.
        score = 0.55 * min(1.0, good_count / 55.0)
        score += 0.45 * min(1.0, coverage / 0.28)
        return score, good_count

    def _capture_frame(self, descriptors, now):
        state = self._capture
        if not state or state["status"] != "capturing":
            return
        if now >= state["expires_at"]:
            state["status"] = "timed_out"
            state["error"] = "capture timed out before enough distinct views were collected"
            return
        if descriptors is None:
            return
        if now - state["started_at"] < self.CAPTURE_INTERVAL_SECONDS:
            return
        if len(descriptors) < self.MIN_FEATURES:
            return

        encoded = self._encode(descriptors)
        for previous in state["views"]:
            score, _matches = self._match_score(descriptors, previous)
            if score >= self.DUPLICATE_VIEW_SCORE:
                return

        state["views"].append(encoded)
        state["started_at"] = now
        print(
            f"[PLACE] Captured distinct view {len(state['views'])}/"
            f"{state['required_views']} for {state['label']}"
        )
        if len(state["views"]) >= state["required_views"]:
            try:
                total = self.place_memory.save_views(state["label"], state["views"])
                state["status"] = "complete"
                print(
                    f"[PLACE] Learned {len(state['views'])} views for "
                    f"{state['label']} ({total} stored)"
                )
            except (OSError, TypeError, ValueError) as exc:
                state["status"] = "error"
                state["error"] = str(exc)
                print(f"[PLACE] Could not persist views: {exc}")

    def _classify(self, descriptors):
        labels = []
        for label in self.place_memory.labels():
            record = self.place_memory.get(label) or {}
            views = record.get("views", [])
            scores = [
                self._match_score(descriptors, reference)[0]
                for reference in views
            ]
            scores = sorted((score for score in scores if score > 0), reverse=True)
            if scores:
                # Several views may support a label; cap the contribution from
                # any single lucky match and prefer repeated reference support.
                score = 0.70 * scores[0] + 0.30 * (sum(scores[:3]) / min(3, len(scores)))
                labels.append((score, label))
        labels.sort(reverse=True)
        if not labels:
            return None, 0.0
        best_score, best_label = labels[0]
        runner_up = labels[1][0] if len(labels) > 1 else 0.0
        if best_score < self.RECOGNITION_SCORE or best_score - runner_up < self.MIN_LABEL_MARGIN:
            return None, best_score
        return best_label, best_score

    def update(self, frame, observed_at=None):
        """Capture diverse views or publish a temporally stable place candidate."""
        now = time.monotonic() if observed_at is None else observed_at
        if observed_at is not None:
            if observed_at == self._last_frame_at:
                return dict(self._last_output)
            self._last_frame_at = observed_at
            if time.monotonic() - observed_at > self.MAX_FRAME_AGE_SECONDS:
                self.reset_temporal()
                self._last_output = {
                    "label": None, "confidence": 0.0, "observed_at": observed_at
                }
                return dict(self._last_output)

        descriptors = self._extract(frame)
        if self._capture and self._capture["status"] == "capturing":
            self._capture_frame(descriptors, now)
            self.reset_temporal()
            return self._last_output

        if descriptors is None:
            candidate, confidence = None, 0.0
        else:
            candidate, confidence = self._classify(descriptors)
        self._votes.append(candidate)
        stable = None
        if candidate and sum(vote == candidate for vote in self._votes) >= self.TEMPORAL_VOTES:
            stable = candidate
        self._last_output = {
            "label": stable,
            "confidence": confidence if stable else 0.0,
            "observed_at": now,
        }
        return dict(self._last_output)

    def reset_temporal(self):
        self._votes.clear()
        self._last_output = {"label": None, "confidence": 0.0, "observed_at": None}
