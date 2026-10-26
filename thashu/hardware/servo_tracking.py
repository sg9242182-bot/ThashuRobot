import time
import threading
from hardware.gpio_control import GPIOControl
 
 
class ServoTracker:
    FOLLOW_FIXED_TILT_DEG = 60.0

    def __init__(self):
        self.gpio = GPIOControl()
 
        self.pan  = 90.0
        self.tilt = 90.0
 
        self.pan_min  = 45
        self.pan_max  = 135
        self.tilt_min = 30
        self.tilt_max = 135
 
        self.smooth   = 0.3
        self.max_step = 6
        self.gain     = 18
        self.deadzone = 0.04
 
        self._last_send = 0
        self._last_log  = 0
        self._search_active = False
        self._search_direction = 1
        self._search_tilt_direction = 1
        self._search_last_step = 0.0
        print("[SERVO] Initialized")
 
    def update(self, target_x, target_y, frame_w, frame_h):
        self._search_active = False
        cx = frame_w // 2
        cy = frame_h // 2
 
        error_x = (target_x - cx) / cx
        error_y = (target_y - cy) / cy
 
        if abs(error_x) < self.deadzone: error_x = 0
        if abs(error_y) < self.deadzone: error_y = 0
        if error_x == 0 and error_y == 0: return
 
        # ── Edge damping ──────────────────────────────────────────────────────
        ef = 1.0
        if self.pan  <= self.pan_min  + 5 or self.pan  >= self.pan_max  - 5: ef *= 0.4
        if self.tilt <= self.tilt_min + 5 or self.tilt >= self.tilt_max - 5: ef *= 0.4
 
        target_pan  = self.pan  - error_x * self.gain * ef
        target_tilt = self.tilt + error_y * self.gain * ef
 
        target_pan  = max(self.pan_min,  min(self.pan_max,  target_pan))
        target_tilt = max(self.tilt_min, min(self.tilt_max, target_tilt))
 
        # ── Step limit ────────────────────────────────────────────────────────
        pan_diff  = max(-self.max_step, min(self.max_step, target_pan  - self.pan))
        tilt_diff = max(-self.max_step, min(self.max_step, target_tilt - self.tilt))
 
        # ── Smoothing ─────────────────────────────────────────────────────────
        self.pan  += pan_diff  * self.smooth
        self.tilt += tilt_diff * self.smooth
 
        # ── Rate limit: send max 10 times/sec to avoid Arduino overflow ───────
        now = time.time()
        if now - self._last_send < 0.1:
            return
        self._last_send = now
 
        self.gpio.send(f"SERVO|PAN_TILT|{int(self.pan)}|{int(self.tilt)}")
 
        # ── Debug log (once per second) ───────────────────────────────────────
        if now - self._last_log > 1.0:
            print(f"[SERVO] Pan:{int(self.pan)} Tilt:{int(self.tilt)}")
            self._last_log = now
 
    def set_follow_tilt(self, angle=None):
        """Set the calibrated fixed tilt used while tracking an upper body."""
        self._search_active = False
        angle = self.FOLLOW_FIXED_TILT_DEG if angle is None else float(angle)
        self.tilt = max(self.tilt_min, min(self.tilt_max, angle))
        self._last_send = time.time()
        return self.gpio.send(
            f"SERVO|PAN_TILT|{int(self.pan)}|{int(self.tilt)}"
        )

    def update_pan_only(self, target_x, frame_w):
        """Pan toward a follow target while holding the calibrated tilt fixed."""
        if frame_w <= 0:
            return
        self._search_active = False
        center_x = frame_w / 2.0
        error_x = (target_x - center_x) / center_x
        if abs(error_x) < self.deadzone:
            return

        edge_factor = 0.4 if (
            self.pan <= self.pan_min + 5 or self.pan >= self.pan_max - 5
        ) else 1.0
        target_pan = self.pan - error_x * self.gain * edge_factor
        target_pan = max(self.pan_min, min(self.pan_max, target_pan))
        pan_diff = max(
            -self.max_step,
            min(self.max_step, target_pan - self.pan),
        )
        self.pan += pan_diff * self.smooth

        now = time.time()
        if now - self._last_send < 0.1:
            return
        self._last_send = now
        self.gpio.send(
            f"SERVO|PAN_TILT|{int(self.pan)}|{int(self.tilt)}"
        )

    def search_step(self):
        """Sweep the head slowly while follow mode searches for a person."""
        now = time.monotonic()
        if not self._search_active:
            self._search_active = True
            self._search_direction = -1 if self.pan >= 125 else 1
            self._search_tilt_direction = -1 if self.tilt >= 105 else 1
            self.pan = max(50.0, min(130.0, self.pan))
            self._search_last_step = 0.0
        if now - self._search_last_step < 0.35:
            return
        self._search_last_step = now

        next_pan = self.pan + self._search_direction * 8.0
        if next_pan >= 125.0:
            next_pan = 125.0
            self._search_direction = -1
        elif next_pan <= 55.0:
            next_pan = 55.0
            self._search_direction = 1


        self.pan = next_pan
        self.gpio.send(f"SERVO|PAN_TILT|{int(self.pan)}|{int(self.tilt)}")

    def stop_search(self):
        self._search_active = False

    def look(self, direction):
        """Move the head by one bounded step and return the serial command sequence."""
        self._search_active = False
        step = 15.0
        if direction == "UP":
            self.tilt -= step
        elif direction == "DOWN":
            self.tilt += step
        elif direction == "LEFT":
            self.pan += step
        elif direction == "RIGHT":
            self.pan -= step
        elif direction == "CENTER":
            self.pan = 90.0
            self.tilt = 90.0
        else:
            return None

        self.pan = max(self.pan_min, min(self.pan_max, self.pan))
        self.tilt = max(self.tilt_min, min(self.tilt_max, self.tilt))
        self._last_send = time.time()
        return self.gpio.send(
            f"SERVO|PAN_TILT|{int(self.pan)}|{int(self.tilt)}"
        )

    def center(self):
        self._search_active = False
        self.pan  = 90.0
        self.tilt = 90.0
        return self.gpio.send("SERVO|PAN_TILT|90|90")
        