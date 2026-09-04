import cv2


class FaceDetector:
    def __init__(self, model_path=None, config_path=None, conf_threshold=0.5):
        self.conf_threshold = conf_threshold
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.detector = cv2.CascadeClassifier(cascade_path)
        if self.detector.empty():
            raise RuntimeError("[VISION] Haar cascade failed to load")
        print("[FACE DETECT] Haar cascade loaded")

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        detections = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60)
        )

        faces = []
        for (x, y, w, h) in detections:
            faces.append((x, y, x + w, y + h))

        return faces