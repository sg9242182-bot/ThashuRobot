import time
import threading
from hardware.gpio_control import GPIOControl
 
 
class ServoTracker:
    def __init__(self):
        self.gpio = GPIOControl()
 
        self.pan  = 90.0
        self.tilt = 90.0
 
        self.pan_min  = 30
        self.pan_max  = 150
        self.tilt_min = 50
        self.tilt_max = 130
 
        self.smooth   = 0.3
        self.max_step = 6
        self.gain     = 18
        self.deadzone = 0.04
 
        self._last_send = 0
        self._last_log  = 0
        print("[SERVO] Initialized")
 
    def update(self, target_x, target_y, frame_w, frame_h):
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
 
    def center(self):
        self.pan  = 90.0
        self.tilt = 90.0
        self.gpio.send("SERVO|PAN_TILT|90|90")
        