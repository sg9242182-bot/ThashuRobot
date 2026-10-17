import cv2
import threading
import time


class Camera:
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.width = width
        self.height = height

        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._thread = None

        self.last_fail_time = 0
        self.reconnect_delay = 2
        self._init_camera()

    def _init_camera(self):
        """Open the configured camera and apply the existing capture settings."""
        self.cap = cv2.VideoCapture(self.src, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def start(self):
        """Start exactly one capture thread; reopen a camera released by stop()."""
        with self._lifecycle_lock:
            if self.running and self._thread is not None and self._thread.is_alive():
                return self
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Previous camera capture thread is still stopping")

            if self.cap is None or not self.cap.isOpened():
                self._init_camera()

            self.running = True
            self._thread = threading.Thread(
                target=self.update,
                name="thashu-camera",
                daemon=True,
            )
            self._thread.start()
        return self

    def update(self):
        while self.running:
            cap = self.cap
            if cap is None:
                ret, frame = False, None
            else:
                ret, frame = cap.read()

            if not ret:
                if not self.running:
                    break

                current_time = time.time()
                if current_time - self.last_fail_time > self.reconnect_delay:
                    print("[CAMERA] Frame failed; reconnecting")
                    try:
                        if cap is not None:
                            cap.release()
                    except Exception:
                        pass

                    time.sleep(0.5)
                    with self._lifecycle_lock:
                        if not self.running:
                            break
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
        """Release the device and join its capture thread before another start."""
        with self._lifecycle_lock:
            self.running = False
            thread = self._thread
            cap = self.cap
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

        with self._lifecycle_lock:
            if thread is self._thread and (thread is None or not thread.is_alive()):
                self._thread = None
            elif thread is not None and thread.is_alive():
                print("[CAMERA] Capture thread is still stopping")
