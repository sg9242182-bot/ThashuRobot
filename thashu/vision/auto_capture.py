import cv2
import os
import time

class AutoCapture:
    def __init__(self, save_path="vision/data/faces", max_images=10):
        self.save_path = save_path
        self.max_images = max_images

        self.last_capture_time = 0
        self.capture_delay = 0.5  # seconds between captures

    # =============================
    # MAIN CAPTURE FUNCTION
    # =============================
    def capture(self, name, frame, faces):
        """
        Captures face images for a given person.
        Returns True when enough images are collected.
        """

        person_dir = os.path.join(self.save_path, name)
        os.makedirs(person_dir, exist_ok=True)

        current_count = len(os.listdir(person_dir))

        if current_count >= self.max_images:
            print(f"[CAPTURE] Already completed for {name}")
            return True

        # Only capture if enough time passed
        if time.time() - self.last_capture_time < self.capture_delay:
            return False

        if len(faces) == 0:
            return False

        # Take largest face (important for accuracy)
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face

        # ===== QUALITY FILTERS =====
        if w < 60 or h < 60:
            return False

        # Crop face safely
        face = frame[y:y+h, x:x+w]

        # Blur detection (avoid blurry images)
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

        if blur_score < 50:  # threshold (tune if needed)
            print("[CAPTURE] Skipped blurry frame")
            return False

        # Save image
        file_path = os.path.join(person_dir, f"{current_count}.jpg")
        cv2.imwrite(file_path, face)

        self.last_capture_time = time.time()

        print(f"[CAPTURE] Saved {file_path} ({current_count+1}/{self.max_images})")

        # Check completion
        if current_count + 1 >= self.max_images:
            print(f"[CAPTURE] DONE for {name}")
            return True

        return False