"""Pose-based upper-body detection for Phase 5 person tracking."""

import math
from pathlib import Path

import cv2

from core.model_paths import model_path


class UpperBodyDetector:
    """Detect people from visible shoulders and torso using MediaPipe Pose Lite.

    The public detect(frame) -> list[bbox] interface is kept compatible with
    VisionCore's existing person stabilization and CentroidTracker pipeline.
    This class only produces image detections; it never controls hardware.
    """

    MIN_SHOULDER_VISIBILITY = 0.50
    MIN_HIP_VISIBILITY = 0.35
    MAX_POSES = 4

    def __init__(self, model_file=None, landmarker=None):
        self._mp = None
        self._landmarker = landmarker
        self._error_reported = False

        if self._landmarker is not None:
            try:
                import mediapipe as mp
                self._mp = mp
            except ImportError as exc:
                self._landmarker = None
                print(f"[PERSON DETECT] MediaPipe unavailable: {exc}")
            return

        model_path_value = Path(model_file or model_path("pose_landmarker_lite.task"))
        if not model_path_value.is_file():
            print(
                "[PERSON DETECT] Pose Lite model missing; "
                f"person follow unavailable ({model_path_value})"
            )
            return

        try:
            import mediapipe as mp

            options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(
                    model_asset_path=str(model_path_value)
                ),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_poses=self.MAX_POSES,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_segmentation_masks=False,
            )
            self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(
                options
            )
            self._mp = mp
            print(
                "[PERSON DETECT] MediaPipe Pose Lite loaded "
                f"(up to {self.MAX_POSES} people)"
            )
        except Exception as exc:
            self._landmarker = None
            print(f"[PERSON DETECT] Pose Lite unavailable: {exc}")

    @staticmethod
    def _visible_point(landmarks, index, threshold, width, height):
        point = landmarks[index]
        visibility = float(getattr(point, "visibility", 0.0) or 0.0)
        if visibility < threshold:
            return None

        x = float(point.x)
        y = float(point.y)
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        if x < 0.0 or x > 1.0 or y < 0.0 or y > 1.0:
            return None
        return (x * width, y * height)

    @classmethod
    def _pose_box(cls, landmarks, width, height):
        left_shoulder = cls._visible_point(
            landmarks, 11, cls.MIN_SHOULDER_VISIBILITY, width, height
        )
        right_shoulder = cls._visible_point(
            landmarks, 12, cls.MIN_SHOULDER_VISIBILITY, width, height
        )
        if left_shoulder is None or right_shoulder is None:
            return None

        shoulder_center_x = (left_shoulder[0] + right_shoulder[0]) / 2.0
        shoulder_center_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
        shoulder_width = abs(right_shoulder[0] - left_shoulder[0])
        if shoulder_width < 8.0:
            return None

        hips = [
            cls._visible_point(
                landmarks, index, cls.MIN_HIP_VISIBILITY, width, height
            )
            for index in (23, 24)
        ]
        visible_hips = [point for point in hips if point is not None]

        # Center the box on the shoulder line so arm pose does not drag the
        # pan target sideways. Use hips when visible; otherwise estimate a
        # conservative upper-torso box from the calibrated shoulder scale.
        half_width = max(shoulder_width * 0.85, 20.0)
        top = min(left_shoulder[1], right_shoulder[1]) - shoulder_width * 0.15
        if len(visible_hips) == 2:
            bottom = sum(point[1] for point in visible_hips) / 2.0
        else:
            bottom = shoulder_center_y + shoulder_width * 1.25

        x1 = max(0, min(width - 1, int(round(shoulder_center_x - half_width))))
        x2 = max(0, min(width, int(round(shoulder_center_x + half_width))))
        y1 = max(0, min(height - 1, int(round(top))))
        y2 = max(0, min(height, int(round(bottom))))

        if x2 - x1 < 8 or y2 - y1 < 8:
            return None
        return (x1, y1, x2, y2)

    def detect(self, frame):
        if self._landmarker is None or self._mp is None or frame is None:
            return []

        try:
            height, width = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = self._mp.Image(
                image_format=self._mp.ImageFormat.SRGB,
                data=rgb,
            )
            result = self._landmarker.detect(image)
        except Exception as exc:
            if not self._error_reported:
                print(f"[PERSON DETECT] Pose inference failed: {exc}")
                self._error_reported = True
            return []

        boxes = []
        for landmarks in result.pose_landmarks or []:
            box = self._pose_box(landmarks, width, height)
            if box is not None:
                boxes.append(box)
        self._error_reported = False
        return boxes
