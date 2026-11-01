"""ArcFace ONNX embeddings with five-point landmark alignment."""

import cv2
import numpy as np
import onnxruntime as ort


# ArcFace 112x112 canonical landmark template (left eye, right eye, nose,
# left mouth corner, right mouth corner), also used by InsightFace.
_ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


class FaceRecognizer:
    """Extract unit-length embeddings only from quality-gated, aligned faces."""

    def __init__(self, model_path):
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
        )
        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        self.input_shape = model_input.shape

    def is_valid_face(self, face_img):
        if face_img is None or getattr(face_img, "size", 0) == 0:
            return False
        h, w = face_img.shape[:2]
        if h < 50 or w < 50:
            return False
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var() >= 50

    @staticmethod
    def align(face_img, landmarks):
        """Warp a face crop into ArcFace's canonical five-point coordinate frame."""
        points = np.asarray(landmarks, dtype=np.float32)
        if points.shape != (5, 2) or not np.isfinite(points).all():
            return None
        # Landmark coordinates are frame-absolute; translate to crop coordinates.
        # Caller passes the original box origin in landmarks when needed.
        transform, inliers = cv2.estimateAffinePartial2D(
            points, _ARCFACE_TEMPLATE, method=cv2.LMEDS
        )
        if transform is None or not np.isfinite(transform).all():
            return None
        aligned = cv2.warpAffine(
            face_img, transform, (112, 112), borderMode=cv2.BORDER_REPLICATE
        )
        return aligned

    def preprocess(self, face_img):
        face = cv2.resize(face_img, (112, 112), interpolation=cv2.INTER_LINEAR)
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
        face = (face.astype(np.float32) - 127.5) / 127.5
        return np.transpose(face, (2, 0, 1))[None, ...]

    def get_embedding(self, face_img, landmarks=None, bbox_origin=(0, 0)):
        """Return a normalized embedding; missing landmarks fail closed.

        landmarks must be YuNet's five points in the full camera-frame
        coordinates. An unaligned Haar crop is deliberately not embedded.
        """
        if not self.is_valid_face(face_img) or landmarks is None:
            return None
        points = np.asarray(landmarks, dtype=np.float32).reshape(-1, 2)
        if points.shape != (5, 2):
            return None
        ox, oy = bbox_origin
        points = points - np.asarray([ox, oy], dtype=np.float32)
        aligned = self.align(face_img, points)
        if aligned is None:
            return None
        try:
            output = self.session.run(None, {self.input_name: self.preprocess(aligned)})[0]
            embedding = np.asarray(output, dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(embedding))
            if not np.isfinite(norm) or norm <= 1e-12 or not np.isfinite(embedding).all():
                return None
            return embedding / norm
        except Exception as exc:
            print(f"[RECOGNIZER ERROR] {exc}")
            return None
