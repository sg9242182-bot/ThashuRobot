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

    @staticmethod
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

    def is_valid_face(self, face_img):
        return self._quality_failure_reason(face_img) is None

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
        On failure, last_failure_reason provides a non-image diagnostic for the
        optional Pi face-match debug log.
        """
        self.last_failure_reason = None
        quality_failure = self._quality_failure_reason(face_img)
        if quality_failure is not None:
            self.last_failure_reason = quality_failure
            return None
        if landmarks is None:
            self.last_failure_reason = "missing_yunet_landmarks"
            return None
        try:
            points = np.asarray(landmarks, dtype=np.float32).reshape(-1, 2)
        except (TypeError, ValueError):
            self.last_failure_reason = "invalid_yunet_landmarks"
            return None
        if points.shape != (5, 2) or not np.isfinite(points).all():
            self.last_failure_reason = "invalid_yunet_landmarks"
            return None
        ox, oy = bbox_origin
        points = points - np.asarray([ox, oy], dtype=np.float32)
        aligned = self.align(face_img, points)
        if aligned is None:
            self.last_failure_reason = "face_alignment_failed"
            return None
        try:
            output = self.session.run(None, {self.input_name: self.preprocess(aligned)})[0]
            embedding = np.asarray(output, dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(embedding))
            if not np.isfinite(norm) or norm <= 1e-12 or not np.isfinite(embedding).all():
                self.last_failure_reason = "invalid_model_embedding"
                return None
            return embedding / norm
        except Exception as exc:
            self.last_failure_reason = f"onnx_inference_failed={type(exc).__name__}"
            print(f"[RECOGNIZER ERROR] {exc}")
            return None



class DlibFaceRecognizer:
    """CPU dlib descriptors for YuNet-detected faces.

    YuNet remains the face detector. This class deliberately does not run
    dlib's HOG detector, avoiding a second full-frame detection pass.
    Descriptors are raw 128-D dlib vectors; pairwise distance is handled by
    DlibFaceDatabase, never by the ArcFace cosine-score database.
    """

    def __init__(self):
        try:
            import dlib
            import face_recognition_models
        except ImportError as exc:
            raise RuntimeError(
                "The dlib backend requires dlib and face_recognition_models; "
                "install thashu/requirements-dlib.txt"
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
        return FaceRecognizer._quality_failure_reason(face_img) is None

    def get_embedding(self, face_img, landmarks=None, bbox_origin=(0, 0)):
        """Return one raw dlib 128-D descriptor for an already detected face crop."""
        self.last_failure_reason = None
        quality_failure = FaceRecognizer._quality_failure_reason(face_img)
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
