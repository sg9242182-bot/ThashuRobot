# vision/face_recognition.py

import cv2
import numpy as np
import onnxruntime as ort

class FaceRecognizer:
    def __init__(self, model_path):
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    # =============================
    # QUALITY CHECK (IMPORTANT)
    # =============================
    def is_valid_face(self, face_img):
        if face_img is None:
            return False

        h, w = face_img.shape[:2]

        # Too small → bad embedding
        if h < 50 or w < 50:
            return False

        # Blur detection (variance of Laplacian)
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

        if blur_score < 50:  # tune later
            return False

        return True

    # =============================
    # PREPROCESS
    # =============================
    def preprocess(self, face_img):
        face = cv2.resize(face_img, (112, 112))

        # Convert BGR → RGB
        face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)

        # Normalize to [-1, 1]
        face = face.astype(np.float32) / 255.0
        face = (face - 0.5) / 0.5

        # HWC → CHW
        face = np.transpose(face, (2, 0, 1))

        # Add batch dimension
        face = np.expand_dims(face, axis=0)

        return face

    # =============================
    # EMBEDDING
    # =============================
    def get_embedding(self, face_img):
        # Validate face quality
        if not self.is_valid_face(face_img):
            return None

        try:
            input_tensor = self.preprocess(face_img)

            embedding = self.session.run(
                None,
                {self.input_name: input_tensor}
            )[0]

            embedding = embedding.flatten()

            # Normalize (VERY IMPORTANT)
            norm = np.linalg.norm(embedding)

            if norm == 0:
                return None

            embedding = embedding / norm

            return embedding

        except Exception as e:
            print(f"[RECOGNIZER ERROR] {e}")
            return None