"""dlib face descriptors from detected face crops."""

import cv2
import numpy as np


def _quality_failure_reason(face_img):
    if face_img is None or getattr(face_img, "size", 0) == 0:
        return "empty_face_crop"
    try:
        h, w = face_img.shape[:2]
    except (AttributeError, TypeError, ValueError):
        return "invalid_face_crop"
    if h < 50 or w < 50:
        return f"face_crop_too_small={w}x{h}"
    try:
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except (cv2.error, TypeError, ValueError):
        return "face_quality_measure_failed"
    if sharpness < 50:
        return f"face_crop_blurry={sharpness:.1f}<50"
    return None


class DlibFaceRecognizer:
    """CPU dlib descriptors for detected face crops.

    YuNet remains the face detector. This class deliberately does not run
    dlib's HOG detector, avoiding a second full-frame detection pass.
    Descriptors are raw 128-D dlib vectors; pairwise Euclidean distance is
    handled by DlibFaceDatabase.
    """

    def __init__(self):
        try:
            import dlib
            import face_recognition_models
        except ImportError as exc:
            raise RuntimeError(
                "The dlib backend requires dlib and face_recognition_models; "
                "install thashu/requirements.txt"
            ) from exc

        self._dlib = dlib
        self._shape_predictor = dlib.shape_predictor(
            face_recognition_models.pose_predictor_five_point_model_location()
        )
        self._face_encoder = dlib.face_recognition_model_v1(
            face_recognition_models.face_recognition_model_location()
        )
        self.last_failure_reason = None

    def is_valid_face(self, face_img):
        return _quality_failure_reason(face_img) is None

    def get_embedding(self, face_img, landmarks=None, bbox_origin=(0, 0)):
        """Return one raw dlib 128-D descriptor for an already detected face crop."""
        self.last_failure_reason = None
        quality_failure = _quality_failure_reason(face_img)
        if quality_failure is not None:
            self.last_failure_reason = quality_failure
            return None

        try:
            height, width = face_img.shape[:2]
            if width < 50 or height < 50:
                self.last_failure_reason = f"face_crop_too_small={width}x{height}"
                return None
            rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            rect = self._dlib.rectangle(0, 0, width - 1, height - 1)
            landmarks_dlib = self._shape_predictor(rgb, rect)
            descriptor = self._face_encoder.compute_face_descriptor(
                rgb, landmarks_dlib, 1, 0.25
            )
            embedding = np.asarray(descriptor, dtype=np.float32).reshape(-1)
            if embedding.shape != (128,) or not np.isfinite(embedding).all():
                self.last_failure_reason = "invalid_dlib_descriptor"
                return None
            return embedding
        except Exception as exc:
            self.last_failure_reason = f"dlib_inference_failed={type(exc).__name__}"
            print(f"[RECOGNIZER ERROR] {exc}")
            return None
