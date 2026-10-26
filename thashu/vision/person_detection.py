import cv2


class UpperBodyDetector:
    """Detect visible upper-body regions using OpenCV's packaged Haar cascade."""

    def __init__(self, cascade_path=None):
        cascade_path = cascade_path or (
            cv2.data.haarcascades + "haarcascade_upperbody.xml"
        )
        self.detector = cv2.CascadeClassifier(cascade_path)
        if self.detector.empty():
            raise RuntimeError(
                f"[VISION] Upper-body Haar cascade failed to load: {cascade_path}"
            )
        print("[PERSON DETECT] Upper-body Haar cascade loaded")

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(64, 96),
        )
        return [
            (int(x), int(y), int(x + w), int(y + h))
            for x, y, w, h in detections
        ]
