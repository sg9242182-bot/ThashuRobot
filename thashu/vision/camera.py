 # vision/camera.py

import cv2  
import threading
import time


class Camera:
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.width = width
        self.height = height

        self.cap = None
        self._init_camera()

        self.frame = None
        self.running = False
        self.lock = threading.Lock()

        # reconnect control
        self.last_fail_time = 0
        self.reconnect_delay = 2  # seconds

    def _init_camera(self):
        """Initialize camera with stable settings"""
        self.cap = cv2.VideoCapture(self.src, cv2.CAP_V4L2)

        # ⚡ Performance tuning
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def start(self):
        if self.running:
            return self

        self.running = True
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        while self.running:
            ret, frame = self.cap.read()

            if not ret:
                current_time = time.time()

                # avoid spam + controlled reconnect
                if current_time - self.last_fail_time > self.reconnect_delay:
                    print("[CAMERA] Frame failed → reconnecting...")

                    try:
                        self.cap.release()
                    except:
                        pass

                    time.sleep(0.5)
                    self._init_camera()

                    self.last_fail_time = current_time

                time.sleep(0.05)
                continue

            with self.lock:
                self.frame = frame

    def read(self):
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()

    def stop(self):
        self.running = False
        try:
            self.cap.release()
        except:
            pass