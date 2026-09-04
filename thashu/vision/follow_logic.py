import time
 
 
class FollowLogic:
    """
    Decides whether Thashu should follow a face
    and which face to prioritize.
    Includes direction debounce and no-face sustain
    to prevent motor jitter and stuttering.
    """
 
    def __init__(self, frame_w=640, frame_h=480):
        self.frame_w  = frame_w
        self.frame_h  = frame_h
        self.center_x = frame_w // 2
        self.center_y = frame_h // 2
 
        # Motor debounce
        self._last_direction  = "NONE"
        self._direction_since = 0
        self._no_face_since   = 0
 
        self.DIRECTION_HOLD = 0.3   # direction must be stable 300ms before acting
        self.NO_FACE_STOP   = 1.0   # stop motors after 1s sustained no face
 
    def select_target(self, faces: list) -> tuple:
        """
        Returns (cx, cy) of the best face to follow.
        Priority: largest face (most likely closest).
        Returns None if no faces.
        """
        if not faces:
            return None
 
        best = max(faces, key=lambda f: (f[2] - f[0]) * (f[3] - f[1]))
        x1, y1, x2, y2 = best
        return (x1 + x2) // 2, (y1 + y2) // 2
 
    def should_move_motors(self, cx: int, cy: int, threshold=0.25) -> str:
        """
        Returns motor direction only after direction is
        held stable for DIRECTION_HOLD seconds.
        Prevents jitter from brief face movements.
        """
        error_x = (cx - self.center_x) / self.center_x
        now = time.time()
 
        if error_x > threshold:
            direction = "RIGHT"
        elif error_x < -threshold:
            direction = "LEFT"
        else:
            direction = "NONE"
 
        # Reset timer if direction changed
        if direction != self._last_direction:
            self._last_direction  = direction
            self._direction_since = now
            return "NONE"  # don't act yet — wait for stable hold
 
        # Act only after stable hold period
        if now - self._direction_since >= self.DIRECTION_HOLD:
            return direction
 
        return "NONE"
 
    def should_stop_motors(self, faces: list) -> bool:
        """
        Returns True only after sustained no-face period.
        Prevents motors stopping on brief detection gaps.
        """
        now = time.time()
        if not faces:
            if self._no_face_since == 0:
                self._no_face_since = now
            return (now - self._no_face_since) > self.NO_FACE_STOP
        else:
            self._no_face_since = 0
            return False