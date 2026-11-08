"""Persistent dlib face descriptors for explicitly confirmed identities."""

import difflib
import json
import os
import tempfile

import numpy as np


class DlibFaceDatabase:
    """Stores raw 128-D dlib descriptors separately from legacy ArcFace data."""

    VERSION = 1
    MAX_EMBEDDINGS_PER_PERSON = 15
    DEFAULT_THRESHOLD = 0.60
    DEFAULT_MARGIN = 0.12
    DESCRIPTOR_SIZE = 128

    def __init__(self, db_path="~/.local/share/thashu/data/people_faces_dlib.json", threshold=None, margin=None):
        self.db_path = os.path.abspath(os.path.expanduser(db_path))
        self.threshold = float(self.DEFAULT_THRESHOLD if threshold is None else threshold)
        self.margin = float(self.DEFAULT_MARGIN if margin is None else margin)
        if not np.isfinite(self.threshold) or self.threshold <= 0 or self.threshold > 2:
            raise ValueError("Invalid dlib distance threshold")
        if not np.isfinite(self.margin) or self.margin < 0 or self.margin > 2:
            raise ValueError("Invalid dlib distance margin")
        self.load_error = None
        self.data = self.load()

    @staticmethod
    def _normalize(vector):
        """Validate a finite raw 128-D dlib descriptor without rescaling it."""
        value = np.asarray(vector, dtype=np.float32).reshape(-1)
        if value.size != DlibFaceDatabase.DESCRIPTOR_SIZE or not np.isfinite(value).all():
            raise ValueError("Expected a finite 128-D dlib descriptor")
        return value.copy()

    def is_overlap(self, distance):
        return float(distance) <= self.threshold

    @staticmethod
    def _clean_name(name):
        if not isinstance(name, str):
            raise ValueError("Person name must be text")
        name = " ".join(name.strip().split())
        if not name or len(name) > 64 or not all(ch.isalnum() or ch in " _.-'" for ch in name):
            raise ValueError("Person name is empty or contains unsupported characters")
        return name

    def load(self):
        if not os.path.exists(self.db_path):
            return {}
        try:
            with open(self.db_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            people = raw.get("people", {}) if isinstance(raw, dict) and "people" in raw else raw
            if not isinstance(people, dict):
                raise ValueError("Expected a people mapping")
            clean = {}
            for name, embeddings in people.items():
                name = self._clean_name(name)
                if not isinstance(embeddings, list):
                    raise ValueError(f"Invalid embedding list for {name}")
                vectors = []
                for embedding in embeddings[-self.MAX_EMBEDDINGS_PER_PERSON:]:
                    vectors.append(self._normalize(embedding).tolist())
                if vectors:
                    clean[name] = vectors
            return clean
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            # Fail closed: do not overwrite a corrupt store with an empty one.
            self.load_error = str(exc)
            print(f"[DB ERROR] Face database unavailable; refusing to reset it: {exc}")
            return {}

    def save(self):
        directory = os.path.dirname(self.db_path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".people-faces-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": self.VERSION, "people": self.data}, handle,
                          ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.db_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def resolve_name(self, spoken_name):
        """Resolve a spoken name to one saved label; callers must confirm fuzzy matches."""
        query = " ".join(str(spoken_name or "").strip().split())
        if not query:
            return None

        exact = [
            name for name in self.data
            if name.casefold() == query.casefold()
        ]
        if len(exact) == 1:
            return exact[0]

        def normalized(value):
            return "".join(ch.casefold() for ch in value if ch.isalnum())

        query_key = normalized(query)
        if len(query_key) < 3:
            return None
        scored = sorted(
            (
                difflib.SequenceMatcher(None, query_key, normalized(name)).ratio(),
                name,
            )
            for name in self.data
        )
        scored.reverse()
        if not scored or scored[0][0] < 0.65:
            return None
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        if scored[0][0] - second_score < 0.10:
            return None
        return scored[0][1]

    def remove_person(self, name, *, confirmed=False):
        """Delete a stored identity only after an explicit user confirmation."""
        if confirmed is not True:
            raise PermissionError("Identity deletion requires explicit confirmation")
        if self.load_error is not None:
            raise OSError("Face database could not be loaded; refusing to overwrite it")
        name = self._clean_name(name)
        if name not in self.data:
            return False
        previous = self.data.pop(name)
        try:
            self.save()
        except OSError:
            self.data[name] = previous
            raise
        return True

    def best_other_match(self, embedding, exclude_name=None):
        query = self._normalize(embedding)
        excluded = str(exclude_name or "").strip().casefold()
        best_name, best_distance = None, float("inf")
        for name, embeddings in self.data.items():
            if name.casefold() == excluded:
                continue
            distances = [
                float(np.linalg.norm(query - self._normalize(stored)))
                for stored in embeddings
            ]
            if distances and min(distances) < best_distance:
                best_name, best_distance = name, min(distances)
        return best_name, best_distance

    def filter_enrollment_samples(self, name, embeddings):
        if self.load_error is not None:
            raise OSError("Face database could not be loaded; refusing enrollment")
        name = self._clean_name(name)
        accepted, rejected = [], []
        for index, embedding in enumerate(embeddings):
            vector = self._normalize(embedding)
            other_name, distance = self.best_other_match(vector, exclude_name=name)
            if other_name is not None and self.is_overlap(distance):
                rejected.append((index, other_name, distance))
            else:
                accepted.append(vector)
        return accepted, rejected

    def add_person(self, name, embedding, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError("Face enrollment requires explicit identity confirmation")
        if self.load_error is not None:
            raise OSError("Face database could not be loaded; refusing to overwrite it")
        name = self._clean_name(name)
        vector = self._normalize(embedding)
        existing = self.data.get(name, [])
        if any(
            float(np.linalg.norm(vector - self._normalize(stored))) <= 0.20
            for stored in existing
        ):
            return False
        previous = self.data.get(name)
        self.data[name] = list(previous or []) + [vector.tolist()]
        self.data[name] = self.data[name][-self.MAX_EMBEDDINGS_PER_PERSON:]
        try:
            self.save()
        except OSError:
            if previous is None:
                self.data.pop(name, None)
            else:
                self.data[name] = previous
            raise
        return True

    def add_person_samples(self, name, embeddings, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError("Face enrollment requires explicit identity confirmation")
        if self.load_error is not None:
            raise OSError("Face database could not be loaded; refusing to overwrite it")
        name = self._clean_name(name)
        vectors = [self._normalize(item) for item in embeddings]
        if len(vectors) < 5:
            raise ValueError("At least five quality-approved observations are required")

        distances = [
            float(np.linalg.norm(vectors[left] - vectors[right]))
            for left in range(len(vectors))
            for right in range(left + 1, len(vectors))
        ]
        if distances and float(np.median(distances)) > self.threshold:
            raise ValueError("Enrollment observations are inconsistent; no identity was saved")

        accepted, rejected = self.filter_enrollment_samples(name, vectors)
        if rejected:
            summary = ", ".join(
                f"sample {index + 1} overlaps {other_name} distance={distance:.3f}"
                for index, other_name, distance in rejected
            )
            raise ValueError(
                "Enrollment still contains overlapping samples; capture replacements: "
                + summary
            )

        previous = self.data.get(name)
        self.data[name] = list(previous or []) + [item.tolist() for item in accepted]
        self.data[name] = self.data[name][-self.MAX_EMBEDDINGS_PER_PERSON:]
        try:
            self.save()
        except OSError:
            if previous is None:
                self.data.pop(name, None)
            else:
                self.data[name] = previous
            raise
        return True

    def match_details(self, embedding):
        if not self.data:
            return None, float("inf"), 0.0
        try:
            query = self._normalize(embedding)
        except (TypeError, ValueError):
            return None, float("inf"), 0.0

        distances = []
        for name, embeddings in self.data.items():
            if embeddings:
                best = min(
                    float(np.linalg.norm(query - self._normalize(stored)))
                    for stored in embeddings
                )
                distances.append((best, name))
        if not distances:
            return None, float("inf"), 0.0
        distances.sort()
        best_distance, best_name = distances[0]
        second_distance = distances[1][0] if len(distances) > 1 else float("inf")
        return best_name, best_distance, second_distance - best_distance

    def match(self, embedding, threshold=None, margin=None, *, diagnostics=False):
        best_name, best_distance, separation = self.match_details(embedding)
        if best_name is None:
            if diagnostics:
                print("[FACE MATCH TEST] rejected: dlib identity database is empty or invalid")
            return None, float("inf")

        maximum_distance = self.threshold if threshold is None else float(threshold)
        minimum_margin = self.margin if margin is None else float(margin)
        distance_pass = best_distance <= maximum_distance
        margin_pass = separation >= minimum_margin
        if diagnostics:
            verdict = "candidate" if distance_pass and margin_pass else "rejected"
            print(
                f"[FACE MATCH TEST] {verdict}: best_distance={best_distance:.3f} "
                f"({best_name}), separation={separation:.3f}, "
                f"maximum_distance={maximum_distance:.3f}, "
                f"required_margin={minimum_margin:.3f}, identities={len(self.data)}"
            )
        if distance_pass and margin_pass:
            return best_name, best_distance
        return None, best_distance

    def compare_sample_and_prototype_scores(self, embedding):
        # ArcFace cosine diagnostics are not meaningful for raw dlib descriptors.
        return []

    def add_high_confidence_sample(self, name, embedding):
        # Unattended dlib enrollment remains disabled until its distance gates
        # have been validated on the robot's actual camera.
        return False


# Compatibility name; this database always stores dlib descriptors.
FaceDatabase = DlibFaceDatabase
