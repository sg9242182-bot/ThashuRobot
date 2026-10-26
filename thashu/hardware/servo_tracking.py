import time
import threading
from hardware.gpio_control import GPIOControl
 
 
class ServoTracker:
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
 
    def search_step(self):
        """Sweep the head slowly while follow mode searches for a face."""
        now = time.monotonic()
        if not self._search_active:
            self._search_active = True
            self._search_direction = -1 if self.pan >= 125 else 1
            self._search_tilt_direction = -1 if self.tilt >= 105 else 1
            self.pan = max(50.0, min(130.0, self.pan))
            self.tilt = max(75.0, min(105.0, self.tilt))
            self._search_last_step = 0.0
        if now - self._search_last_step < 0.35:
            return
        self._search_last_step = now

        next_pan = self.pan + self._search_direction * 8.0
        if next_pan >= 125.0:
            next_pan = 125.0
            self._search_direction = -1
            self.tilt += self._search_tilt_direction * 10.0
        elif next_pan <= 55.0:
            next_pan = 55.0
            self._search_direction = 1
            self.tilt += self._search_tilt_direction * 10.0

        if self.tilt >= 105.0:
            self.tilt = 105.0
            self._search_tilt_direction = -1
        elif self.tilt <= 75.0:
            self.tilt = 75.0
            self._search_tilt_direction = 1

        self.pan = next_pan
        self.gpio.send(f"SERVO|PAN_TILT|{int(self.pan)}|{int(self.tilt)}")

    def stop_search(self):
        self._search_active = False

    def center(self):
        self._search_active = False
        self.pan  = 90.0
        self.tilt = 90.0
        self.gpio.send("SERVO|PAN_TILT|90|90")
        