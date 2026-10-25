import time


class FollowLogic:
    """Pure target-selection and follow-mode state logic; never actuates hardware."""

    OFF = "OFF"
    WAITING_FOR_TARGET = "WAITING_FOR_TARGET"
    SELECTING_TARGET = "SELECTING_TARGET"
    TRACKING = "TRACKING"
    TARGET_LOST = "TARGET_LOST"
    NEEDS_RESELECTION = "NEEDS_RESELECTION"

    MAX_FRAME_AGE_SECONDS = 0.35
    TARGET_LOSS_GRACE_SECONDS = 1.5
    REACQUIRE_STABLE_FRAMES = 3

    def __init__(self, frame_w=640, frame_h=480):
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.enabled = False
        self.state = self.OFF
        self.target_id = None
        self.pending_region = None
        self._lost_since = None
        self._reacquire_frames = 0
        self._notice_latched = set()

    def start(self):
        """Enable follow mode, but defer target choice until fresh perception arrives."""
        self.enabled = True
        self.state = self.WAITING_FOR_TARGET
        self.target_id = None
        self.pending_region = None
        self._lost_since = None
        self._reacquire_frames = 0
        self._notice_latched.clear()

    def stop(self):
        """Disable follow mode and discard the session target."""
        was_enabled = self.enabled
        self.enabled = False
        self.state = self.OFF
        self.target_id = None
        self.pending_region = None
        self._lost_since = None
        self._reacquire_frames = 0
        self._notice_latched.clear()
        return was_enabled

    def request_region(self, region):
        """Queue a left/center/right choice for the next fresh camera snapshot."""
        region = str(region).upper()
        if not self.enabled or region not in ("LEFT", "CENTER", "RIGHT"):
            return False
        self.pending_region = region
        self.state = self.SELECTING_TARGET
        self._notice_latched.discard("selection_required")
        return True

    def _notice_once(self, key):
        if key in self._notice_latched:
            return None
        self._notice_latched.add(key)
        return key

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
        faces = snapshot.get("faces") or []
        return faces, width

    def _choose(self, faces, width, region=None):
        candidates = [
            face for face in faces
            if self._valid_face(face)
            and (region is None or self._region_for(face, width) == region)
        ]
        if len(candidates) != 1:
            return None
        return candidates[0]

    def update(self, snapshot, runtime_idle=True, now=None):
        """Return a target/stop/notice decision from one perception snapshot.

        The caller owns servo and motor interfaces. A missing, ambiguous, or stale
        target never gets replaced silently by another face.
        """
        now = time.monotonic() if now is None else now
        result = {
            "state": self.state,
            "target": None,
            "stop_motion": False,
            "notice": None,
        }
        if not self.enabled:
            return result
        if not runtime_idle:
            self.stop()
            result.update(state=self.OFF, stop_motion=True, notice="paused_for_interaction")
            return result

        faces, width = self._fresh_faces(snapshot or {}, now)
        if faces is None:
            result.update(stop_motion=self.state in (self.TRACKING, self.TARGET_LOST))
            result["notice"] = self._notice_once("stale_frame")
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
                result.update(state=self.state, target=selected)
                return result
            self.state = self.SELECTING_TARGET
            result.update(
                state=self.state,
                notice=self._notice_once("selection_required"),
            )
            return result

        if self.state == self.SELECTING_TARGET:
            if self.pending_region is None:
                result.update(
                    notice=self._notice_once("selection_required"),
                )
                return result
            selected = self._choose(faces, width, self.pending_region)
            self.pending_region = None
            if selected is None:
                result.update(
                    notice=self._notice_once("selection_not_unique"),
                )
                return result
            self.target_id = selected["track_id"]
            self.state = self.TRACKING
            self._lost_since = None
            self._reacquire_frames = 0
            self._notice_latched.clear()
            result.update(state=self.state, target=selected)
            return result

        if self.state == self.NEEDS_RESELECTION:
            result["notice"] = self._notice_once("reselect_target")
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
                stop_motion=True,
                notice=self._notice_once("target_ambiguous"),
            )
            return result

        if self.state == self.TRACKING:
            if matching is None:
                self.state = self.TARGET_LOST
                self._lost_since = now
                self._reacquire_frames = 0
                result.update(
                    state=self.state,
                    stop_motion=True,
                    notice=self._notice_once("target_lost"),
                )
                return result
            self._notice_latched.discard("target_lost")
            result.update(state=self.state, target=matching)
            return result

        if self.state == self.TARGET_LOST:
            if matching is not None:
                self._reacquire_frames += 1
                if self._reacquire_frames >= self.REACQUIRE_STABLE_FRAMES:
                    self.state = self.TRACKING
                    self._lost_since = None
                    self._reacquire_frames = 0
                    self._notice_latched.clear()
                    result.update(state=self.state, target=matching)
                    return result
            elif self._lost_since is not None and now - self._lost_since >= self.TARGET_LOSS_GRACE_SECONDS:
                self.target_id = None
                self.state = self.NEEDS_RESELECTION
                result.update(
                    state=self.state,
                    notice=self._notice_once("reselect_target"),
                )
                return result
            result.update(state=self.state, stop_motion=True)
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
