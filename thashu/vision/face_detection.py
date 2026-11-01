"""Face detection with five landmarks for ArcFace alignment.

YuNet is loaded from the machine-local model directory when present. Haar
remains a detection-only fallback for existing vision behavior; fallback boxes
are never treated as recognition-ready observations.
"""

import cv2


class FaceDetector:
    def __init__(self, model_path=None, config_path=None, conf_threshold=0.65):
        self.conf_threshold = float(conf_threshold)
        self._yunet = None
        if model_path:
            try:
                self._yunet = cv2.FaceDetectorYN_create(
                    model_path, "", (320, 320), self.conf_threshold, 0.3, 5000
                )
                print("[FACE DETECT] YuNet loaded with five-point landmarks")
            except (AttributeError, cv2.error, TypeError) as exc:
                print(f"[FACE DETECT] YuNet unavailable; using Haar detection only: {exc}")

        self.detector = None
        if self._yunet is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.detector = cv2.CascadeClassifier(cascade_path)
            if self.detector.empty():
                raise RuntimeError("[VISION] Haar cascade failed to load")
            print("[FACE DETECT] Haar cascade loaded (recognition requires YuNet landmarks)")

    @property
    def recognition_ready(self):
        return self._yunet is not None

    def detect_with_landmarks(self, frame):
        """Return detections as {bbox, landmarks, score}; landmarks are frame absolute."""
        if self._yunet is None:
            return []
        height, width = frame.shape[:2]
        self._yunet.setInputSize((width, height))
        _status, rows = self._yunet.detect(frame)
        if rows is None:
            return []
        results = []
        for row in rows:
            x, y, w, h = [int(round(float(v))) for v in row[:4]]
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(width, x + w), min(height, y + h)
            if x2 <= x1 or y2 <= y1:
                continue
            # YuNet order: right eye, left eye, nose, right mouth, left mouth.
            points = row[4:14].reshape(5, 2)
            landmarks = [points[1], points[0], points[2], points[4], points[3]]
            results.append({
                "bbox": (x1, y1, x2, y2),
                "landmarks": [[float(px), float(py)] for px, py in landmarks],
                "score": float(row[14]),
            })
        return results

    def detect(self, frame):
        """Return face boxes; preserves existing consumers' box-only interface."""
        landmark_detections = self.detect_with_landmarks(frame)
        if self._yunet is not None:
            return [item["bbox"] for item in landmark_detections]

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections = self.detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        return [(x, y, x + w, y + h) for (x, y, w, h) in detections]
