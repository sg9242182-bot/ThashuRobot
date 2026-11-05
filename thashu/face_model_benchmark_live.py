#!/usr/bin/env python3
"""Temporary live-camera comparison: current ArcFace vs AdaFace IR-18.

This tool is isolated from Thashu runtime and production face data. It opens the
same Pi camera, captures frames while the operator displays phone photos, and
keeps comparison embeddings in RAM only. It does not save camera frames,
embeddings, or change people_faces.json.

Enrollment and test must use different photos for each labeled identity.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.model_paths import model_path  # noqa: E402
from vision.face_detection import FaceDetector  # noqa: E402
from vision.face_recognition import FaceRecognizer  # noqa: E402


def normalize(vector):
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1e-12:
        return None
    return vector / norm


def capture_frame(camera):
    input("Show the requested phone photo centered in the camera, then press Enter...")
    frame = None
    # Discard buffered frames and use the newest camera view.
    for _ in range(5):
        ok, current = camera.read()
        if ok:
            frame = current
        else:
            time.sleep(0.1)
    if frame is None:
        print("CAPTURE_FAILED: no camera frame")
    return frame


def extract_arcface(frame, detector, recognizer):
    detections = detector.detect_with_landmarks(frame)
    if len(detections) != 1:
        return None, f"YuNet found {len(detections)} faces; show exactly one"
    item = detections[0]
    x1, y1, x2, y2 = item["bbox"]
    if min(x2 - x1, y2 - y1) < 50:
        return None, "YuNet face crop is under 50 px"
    embedding = recognizer.get_embedding(
        frame[y1:y2, x1:x2],
        item["landmarks"],
        bbox_origin=(x1, y1),
    )
    if embedding is None:
        reason = getattr(recognizer, "last_failure_reason", None) or "embedding failed"
        return None, reason
    return normalize(embedding), None


def extract_adaface(frame, recognizer):
    detections, landmarks = recognizer.detector.detect(frame)
    if len(detections) != 1 or landmarks is None:
        return None, f"SCRFD found {len(detections)} faces; show exactly one"
    x1, y1, x2, y2 = [int(round(float(value))) for value in detections[0, :4]]
    if min(x2 - x1, y2 - y1) < 50:
        return None, "SCRFD face crop is under 50 px"
    embedding = recognizer.recognizer.get_normalized_embedding(frame, landmarks[0])
    return normalize(embedding), None


def rank(query, gallery):
    scores = []
    for name, embeddings in gallery.items():
        if embeddings:
            score = max(float(np.dot(query, item)) for item in embeddings)
            scores.append((score, name))
    return sorted(scores, reverse=True)


def report(model_name, query, gallery, expected):
    if query is None:
        print(f"  {model_name}: no usable embedding")
        return False
    scores = rank(query, gallery)
    if not scores:
        print(f"  {model_name}: gallery is empty")
        return False
    winner_score, winner_name = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else -1.0
    correct = winner_name.casefold() == expected.casefold()
    print(
        f"  {model_name}: top={winner_name} {winner_score:.3f}; "
        f"runner_up={second_score:.3f}; gap={winner_score - second_score:.3f}; "
        f"expected={expected}; {'TOP1' if correct else 'WRONG'}"
    )
    return correct


def main():
    ada_root = Path(os.environ.get(
        "THASHU_ADAFACE_REPO",
        Path.home() / ".local/share/thashu/benchmarks/adaface-onnx",
    )).expanduser().resolve()
    detector_path = ada_root / "weights/det_10g.onnx"
    adaface_path = ada_root / "weights/adaface_ir_18.onnx"
    if not (ada_root / "model").is_dir():
        raise SystemExit(
            f"AdaFace source is missing: {ada_root}\n"
            "Clone yakhyo/adaface-onnx there and download det_10g.onnx "
            "and adaface_ir_18.onnx into its weights/ folder."
        )
    if not detector_path.is_file() or not adaface_path.is_file():
        raise SystemExit(
            f"AdaFace weights missing. Expected:\n  {detector_path}\n  {adaface_path}"
        )

    # Import the experimental ONNX implementation only after locating its source.
    sys.path.insert(0, str(ada_root))
    try:
        from model import FaceRecognition as AdaFaceRecognition
    except Exception as exc:
        raise SystemExit(
            "Could not import AdaFace ONNX dependencies. Install the benchmark "
            f"requirements in the active venv first. Details: {exc}"
        ) from exc

    print("[BENCH] Loading current ArcFace/YuNet and experimental AdaFace/SCRFD...")
    arc_detector = FaceDetector(model_path("face", "face_detection_yunet_2023mar.onnx"))
    if not arc_detector.recognition_ready:
        raise SystemExit("YuNet landmarks are required for the current ArcFace pipeline.")
    arc_recognizer = FaceRecognizer(model_path("face", "w600k_r50.onnx"))
    ada_recognizer = AdaFaceRecognition(
        detector_path=str(detector_path),
        recognition_path=str(adaface_path),
    )

    camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not camera.isOpened():
        raise SystemExit("Could not open Pi camera at index 0.")

    galleries = {"ArcFace": {}, "AdaFace IR-18": {}}
    samples_per_identity = 3
    try:
        print(
            "\nThis is a preliminary comparison, not a production change. "
            "Use different phone photos for enrollment and testing.\n"
            "Type each identity label exactly as saved, or press Enter when done."
        )
        while True:
            name = input("\nIdentity to enroll (Tharun / Durai / Madeshwari): ").strip()
            if not name:
                break
            if name in galleries["ArcFace"]:
                print("That label is already enrolled in this temporary run.")
                continue

            arc_samples = []
            ada_samples = []
            attempts = 0
            while min(len(arc_samples), len(ada_samples)) < samples_per_identity:
                attempts += 1
                if attempts > samples_per_identity * 5:
                    print(f"Could not collect enough paired samples for {name}; skipping.")
                    break
                print(
                    f"\n{name}: sample {min(len(arc_samples), len(ada_samples)) + 1}/"
                    f"{samples_per_identity}"
                )
                frame = capture_frame(camera)
                if frame is None:
                    continue
                arc_embedding, arc_error = extract_arcface(
                    frame, arc_detector, arc_recognizer
                )
                ada_embedding, ada_error = extract_adaface(frame, ada_recognizer)
                if arc_embedding is None or ada_embedding is None:
                    print(
                        "  Retry; "
                        f"ArcFace={arc_error or 'OK'}; AdaFace={ada_error or 'OK'}"
                    )
                    continue
                arc_samples.append(arc_embedding)
                ada_samples.append(ada_embedding)
                print("  Paired embeddings captured; camera frames were not saved.")

            if len(arc_samples) == samples_per_identity:
                galleries["ArcFace"][name] = arc_samples
                galleries["AdaFace IR-18"][name] = ada_samples
                print(f"[BENCH] Enrolled {name}: {samples_per_identity} paired samples.")

        if not galleries["ArcFace"]:
            raise SystemExit("No identities enrolled; nothing to compare.")

        print(
            "\nNow test each identity with different phone photos than the enrollment "
            "photos. Enter the expected identity for each test; blank ends the run."
        )
        counts = {
            model_name: {"tests": 0, "top1": 0}
            for model_name in galleries
        }
        while True:
            expected = input("\nExpected identity for next phone photo (or Enter to finish): ").strip()
            if not expected:
                break
            if expected not in galleries["ArcFace"]:
                print("That identity was not enrolled in this run; try again.")
                continue
            frame = capture_frame(camera)
            if frame is None:
                continue

            started = time.perf_counter()
            arc_embedding, arc_error = extract_arcface(
                frame, arc_detector, arc_recognizer
            )
            arc_ms = (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            ada_embedding, ada_error = extract_adaface(frame, ada_recognizer)
            ada_ms = (time.perf_counter() - started) * 1000.0

            print(f"[TEST] ArcFace inference {arc_ms:.0f} ms; AdaFace IR-18 {ada_ms:.0f} ms")
            if arc_error:
                print(f"  ArcFace capture note: {arc_error}")
            if ada_error:
                print(f"  AdaFace capture note: {ada_error}")
            for model_name, embedding in (
                ("ArcFace", arc_embedding),
                ("AdaFace IR-18", ada_embedding),
            ):
                ok = report(model_name, embedding, galleries[model_name], expected)
                if embedding is not None:
                    counts[model_name]["tests"] += 1
                    counts[model_name]["top1"] += int(ok)

        print("\n[BENCH] Preliminary top-1 results (small sample; not calibrated):")
        for model_name, result in counts.items():
            print(
                f"  {model_name}: {result['top1']}/{result['tests']} "
                "usable test captures"
            )
        print("[BENCH] Temporary embeddings were held in RAM and discarded.")
    finally:
        camera.release()


if __name__ == "__main__":
    main()
