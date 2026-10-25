import time


class FollowLogic:
    """Pure target-selection and follow-mode state logic; never actuates hardware."""

    OFF = "OFF"
    WAITING_FOR_TARGET = "WAITING_FOR_TARGET"
    SELECTING_TARGET = "SELECTING_TARGET"
    TRACKING = "TRACKING"
    NEEDS_RESELECTION = "NEEDS_RESELECTION"

    MAX_FRAME_AGE_SECONDS = 0.35

    def __init__(self, frame_w=640, frame_h=480):
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.enabled = False
        self.state = self.OFF
        self.target_id = None
        self.pending_region = None
        self._notice_latched = set()
        self._stop_latched = False

    def start(self):
        """Enable follow mode, but defer target choice until fresh perception arrives."""
        self.enabled = True
        self.state = self.WAITING_FOR_TARGET
        self.target_id = None
        self.pending_region = None
        self._notice_latched.clear()
        self._stop_latched = False

    def stop(self):
        """Disable follow mode and discard the session target."""
        was_enabled = self.enabled
        self.enabled = False
        self.state = self.OFF
        self.target_id = None
        self.pending_region = None
        self._notice_latched.clear()
        self._stop_latched = False
        return was_enabled

    def request_region(self, region):
        """Queue a left/center/right choice for the next fresh camera snapshot."""
        region = str(region).upper()
        if not self.enabled or region not in ("LEFT", "CENTER", "RIGHT"):
            return False
        self.pending_region = region
        self.state = self.SELECTING_TARGET
        self._notice_latched.discard("selection_required")
        self._notice_latched.discard("selection_not_unique")
        return True

    def _notice_once(self, key):
        if key in self._notice_latched:
            return None
        self._notice_latched.add(key)
        return key

    def _request_stop_once(self, result):
        if not self._stop_latched:
            result["stop_motion"] = True
            self._stop_latched = True

    @staticmethod
    def _region_for(face, frame_width):
        x = face.get("center", (None, None))[0]
        if x is None:
            return None
        if x < frame_width / 3:
            return "LEFT"
        if x > 2 * frame_width / 3:
            return "RIGHT"
        return "CENTER"

    @staticmethod
    def _valid_face(face):
        return (
            isinstance(face, dict)
            and face.get("track_id") is not None
            and not face.get("ambiguous", True)
        )

    def _fresh_faces(self, snapshot, now):
        observed_at = snapshot.get("observed_at")
        if not isinstance(observed_at, (int, float)):
            return None, None
        age = now - observed_at
        if age < 0 or age > self.MAX_FRAME_AGE_SECONDS:
            return None, None
        size = snapshot.get("frame_size") or (self.frame_w, self.frame_h)
        width = int(size[0]) if size and size[0] else self.frame_w
        return snapshot.get("faces") or [], width

    def _choose(self, faces, width, region=None):
        candidates = [
            face for face in faces
            if self._valid_face(face)
            and (region is None or self._region_for(face, width) == region)
        ]
        return candidates[0] if len(candidates) == 1 else None

    def update(self, snapshot, runtime_idle=True, now=None):
        """Return a target/stop/notice decision from one perception snapshot.

        The caller owns servo and motor interfaces. A missing, ambiguous, or stale
        target never gets replaced silently by another face.
        """
        now = time.monotonic() if now is None else now
        result = {"state": self.state, "target": None, "stop_motion": False, "notice": None}
        if not self.enabled:
            return result
        if not runtime_idle:
            self.stop()
            result.update(state=self.OFF, stop_motion=True, notice="paused_for_interaction")
            return result

        faces, width = self._fresh_faces(snapshot or {}, now)
        if faces is None:
            if self.state == self.TRACKING:
                # Tracker IDs are not identity proof across a camera gap.
                self.target_id = None
                self.state = self.NEEDS_RESELECTION
                self._notice_latched.add("reselect_target")
                self._request_stop_once(result)
                result.update(
                    state=self.state,
                    notice=self._notice_once("stale_frame"),
                )
            return result

        if self.state == self.WAITING_FOR_TARGET:
            if not faces:
                result["notice"] = self._notice_once("no_target")
                return result
            selected = self._choose(faces, width)
            if selected is not None:
                self.target_id = selected["track_id"]
                self.state = self.TRACKING
                self._notice_latched.clear()
                self._stop_latched = False
                result.update(state=self.state, target=selected)
                return result
            self.state = self.SELECTING_TARGET
            result.update(state=self.state, notice=self._notice_once("selection_required"))
            return result

        if self.state == self.SELECTING_TARGET:
            if self.pending_region is None:
                result.update(notice=self._notice_once("selection_required"))
                return result
            selected = self._choose(faces, width, self.pending_region)
            self.pending_region = None
            if selected is None:
                result.update(notice=self._notice_once("selection_not_unique"))
                return result
            self.target_id = selected["track_id"]
            self.state = self.TRACKING
            self._notice_latched.clear()
            self._stop_latched = False
            result.update(state=self.state, target=selected)
            return result

        if self.state == self.NEEDS_RESELECTION:
            return result

        matching = next(
            (face for face in faces if face.get("track_id") == self.target_id),
            None,
        )
        if matching is not None and matching.get("ambiguous", False):
            self.target_id = None
            self.pending_region = None
            self.state = self.NEEDS_RESELECTION
            result.update(
                state=self.state,
                notice=self._notice_once("target_ambiguous"),
            )
            self._request_stop_once(result)
            return result

        if self.state == self.TRACKING:
            if matching is None:
                # No appearance identity is retained for follow mode, so do not
                # trust centroid reacquisition after even a short occlusion.
                self.target_id = None
                self.state = self.NEEDS_RESELECTION
                self._notice_latched.add("reselect_target")
                result.update(state=self.state, notice=self._notice_once("target_lost"))
                self._request_stop_once(result)
                return result
            self._stop_latched = False
            result.update(state=self.state, target=matching)
            return result


        return result

    # Compatibility helpers for older callers. Target choice is deliberately
    # restricted to exactly one face; a largest-face heuristic is unsafe.
    def select_target(self, faces):
        if len(faces or []) != 1:
            return None
        face = faces[0]
        return face.get("center") if isinstance(face, dict) else (
            (face[0] + face[2]) // 2,
            (face[1] + face[3]) // 2,
        )

    def should_move_motors(self, cx, cy, threshold=0.25):
        """Legacy advisory only; this method does not issue hardware commands."""
        return "NONE"

    def should_stop_motors(self, faces):
        """Legacy helper reports no-face; callers must issue STOP themselves."""
        return not bool(faces)
