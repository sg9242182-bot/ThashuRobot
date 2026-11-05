#!/usr/bin/env python3
"""Isolated live-camera dlib face recognition check.

Uses dlib's CPU HOG detector and 128-D face descriptors via face_recognition.
The camera frames and temporary descriptors stay in memory; this script never
reads or writes Thashu's people_faces.json and never changes production code.

For each identity, enroll a few phone photos, then test with different phone
photos. This is a quick comparison aid, not a calibrated security system.
"""

from __future__ import annotations

import time

import cv2
import face_recognition
import numpy as np

CAMERA_INDEX = 0
SAMPLES_PER_IDENTITY = 3
DEFAULT_TOLERANCE = 0.60


def capture_embedding(camera, prompt):
    input(f"{prompt}\nShow the phone photo to the camera, then press Enter...")
    frame = None
    # Drain buffered frames; process the most recent one.
    for _ in range(12):
        ok, current = camera.read()
        if ok:
            frame = current
        else:
            time.sleep(0.05)

    if frame is None:
        print("CAPTURE_FAILED: camera returned no frame.")
        return None

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    started = time.perf_counter()
    locations = face_recognition.face_locations(rgb, model="hog")
    if len(locations) != 1:
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(f"Retry: dlib HOG found {len(locations)} faces ({elapsed_ms:.0f} ms); show exactly one.")
        return None

    vectors = face_recognition.face_encodings(
        rgb, known_face_locations=locations, num_jitters=1, model="small"
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if len(vectors) != 1:
        print(f"Retry: dlib could not produce one face descriptor ({elapsed_ms:.0f} ms).")
        return None

    print(f"Captured one face; dlib detection + descriptor took {elapsed_ms:.0f} ms.")
    return np.asarray(vectors[0], dtype=np.float32)


def distances_to_gallery(query, gallery):
    # Each identity score is the nearest distance to its temporary samples.
    ranked = []
    for name, samples in gallery.items():
        distance = min(float(np.linalg.norm(query - sample)) for sample in samples)
        ranked.append((distance, name))
    return sorted(ranked)


def main():
    print("DLIB LIVE CAMERA TEST")
    print("This test uses only temporary samples in RAM; no face database is changed.")
    print("Use distinct phone photos for enrollment and testing.")
    print(f"dlib default comparison tolerance for reference: {DEFAULT_TOLERANCE:.2f}")
    print("The threshold is a reference only; this small test does not calibrate it.\n")

    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not camera.isOpened():
        raise SystemExit(f"Could not open camera index {CAMERA_INDEX}.")

    gallery = {}
    try:
        while True:
            name = input(
                "Identity to enroll (for example Tharun / Durai / Madeshwari), "
                "or Enter when done: "
            ).strip()
            if not name:
                break
            if name.casefold() in {key.casefold() for key in gallery}:
                print("That identity is already enrolled in this run.")
                continue

            samples = []
            attempts = 0
            while len(samples) < SAMPLES_PER_IDENTITY and attempts < SAMPLES_PER_IDENTITY * 5:
                attempts += 1
                vector = capture_embedding(
                    camera, f"{name}: enrollment photo {len(samples) + 1}/{SAMPLES_PER_IDENTITY}"
                )
                if vector is not None:
                    samples.append(vector)
            if len(samples) == SAMPLES_PER_IDENTITY:
                gallery[name] = samples
                print(f"Enrolled {name} with {len(samples)} temporary descriptors.\n")
            else:
                print(f"Skipped {name}; only got {len(samples)} usable captures.\n")

        if not gallery:
            raise SystemExit("No identities enrolled.")

        print("\nTest with different phone photos. Enter an expected identity or UNKNOWN.")
        print("Press Enter at the expected-identity prompt to finish.\n")
        totals = {"known": 0, "known_top1_correct": 0, "unknown": 0, "unknown_rejected": 0}

        while True:
            expected = input(
                "Expected identity (" + " / ".join(gallery) + " / UNKNOWN), or Enter to finish: "
            ).strip()
            if not expected:
                break
            is_unknown = expected.casefold() == "unknown"
            if not is_unknown and expected.casefold() not in {key.casefold() for key in gallery}:
                print("That label was not enrolled; try again.")
                continue

            query = capture_embedding(camera, f"Test photo; expected: {expected}")
            if query is None:
                continue
            ranked = distances_to_gallery(query, gallery)
            best_distance, best_name = ranked[0]
            second_distance = ranked[1][0] if len(ranked) > 1 else float("inf")
            accepted = best_distance <= DEFAULT_TOLERANCE

            print("Distances: " + ", ".join(f"{name}={distance:.3f}" for distance, name in ranked))
            print(
                f"Nearest={best_name} ({best_distance:.3f}); "
                f"next gap={second_distance - best_distance:.3f}; "
                f"threshold result={'ACCEPT' if accepted else 'REJECT'}"
            )

            if is_unknown:
                totals["unknown"] += 1
                totals["unknown_rejected"] += int(not accepted)
                print(f"Expected UNKNOWN: {'PASS' if not accepted else 'FALSE ACCEPT'}\n")
            else:
                totals["known"] += 1
                correct = accepted and best_name.casefold() == expected.casefold()
                totals["known_top1_correct"] += int(correct)
                print(f"Expected {expected}: {'PASS' if correct else 'MISMATCH'}\n")

        print("SUMMARY")
        print(
            f"Known identity captures correct: "
            f"{totals['known_top1_correct']}/{totals['known']}"
        )
        print(
            f"Unknown captures rejected: "
            f"{totals['unknown_rejected']}/{totals['unknown']}"
        )
        print("Temporary descriptors discarded; no files or production face data were changed.")
    finally:
        camera.release()


if __name__ == "__main__":
    main()
