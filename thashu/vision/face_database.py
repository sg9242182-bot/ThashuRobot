"""Persistent face embeddings; unknown people are never enrolled automatically."""

import json
import os
import tempfile

import numpy as np


class FaceDatabase:
    """Stores only confirmed names and normalized embeddings, never face photos."""

    VERSION = 1
    MAX_EMBEDDINGS_PER_PERSON = 8
    # Conservative initial gates; the Pi validation must tune/confirm them with
    # labeled same-person and different-person samples before Phase 6 completes.
    DEFAULT_THRESHOLD = 0.50
    DEFAULT_MARGIN = 0.08

    def __init__(self, db_path="data/people_faces.json",
                 threshold=DEFAULT_THRESHOLD, margin=DEFAULT_MARGIN):
        self.db_path = os.path.abspath(os.path.expanduser(db_path))
        self.threshold = float(threshold)
        self.margin = float(margin)
        if not -1.0 <= self.threshold <= 1.0 or not 0.0 <= self.margin <= 2.0:
            raise ValueError("Invalid face recognition thresholds")
        self.load_error = None
        self.data = self.load()

    @staticmethod
    def _clean_name(name):
        if not isinstance(name, str):
            raise ValueError("Person name must be text")
        name = " ".join(name.strip().split())
        if not name or len(name) > 64 or not all(ch.isalnum() or ch in " _.-'" for ch in name):
            raise ValueError("Person name is empty or contains unsupported characters")
        return name

    @staticmethod
    def _normalize(vector):
        value = np.asarray(vector, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(value))
        if value.size == 0 or not np.isfinite(value).all() or not np.isfinite(norm) or norm <= 1e-12:
            raise ValueError("Embedding must be a finite, non-zero vector")
        return value / norm

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

    def add_person(self, name, embedding, *, confirmed=False):
        """Persist one enrollment sample only after the explicit confirmation flow."""
        if confirmed is not True:
            raise PermissionError("Face enrollment requires explicit identity confirmation")
        if self.load_error is not None:
            raise OSError("Face database could not be loaded; refusing to overwrite it")
        name = self._clean_name(name)
        vector = self._normalize(embedding)
        existing = self.data.get(name, [])
        for stored in existing:
            if float(np.dot(vector, np.asarray(stored, dtype=np.float32))) >= 0.90:
                return False
        self.data.setdefault(name, []).append(vector.tolist())
        self.data[name] = self.data[name][-self.MAX_EMBEDDINGS_PER_PERSON:]
        self.save()
        return True

    def remove_person(self, name, *, confirmed=False):
        """Delete a stored identity only after an explicit user confirmation."""
        if confirmed is not True:
            raise PermissionError("Identity deletion requires explicit confirmation")
        if self.load_error is not None:
            raise OSError("Face database could not be loaded; refusing to overwrite it")
        name = self._clean_name(name)
        if name not in self.data:
            return False
        del self.data[name]
        self.save()
        return True

    def add_person_samples(self, name, embeddings, *, confirmed=False):
        """Persist a batch collected from one stable face after spoken confirmation."""
        if confirmed is not True:
            raise PermissionError("Face enrollment requires explicit identity confirmation")
        if self.load_error is not None:
            raise OSError("Face database could not be loaded; refusing to overwrite it")
        name = self._clean_name(name)
        vectors = [self._normalize(item) for item in embeddings]
        if len(vectors) < 5:
            raise ValueError("At least five quality-approved observations are required")
        if name in self.data:
            raise ValueError("That confirmed name already exists; refusing to merge identities")

        matrix = np.stack(vectors)
        similarities = matrix @ matrix.T
        pair_scores = similarities[np.triu_indices(len(vectors), k=1)]
        if pair_scores.size and float(np.median(pair_scores)) < 0.45:
            raise ValueError("Enrollment observations are inconsistent; no identity was saved")

        # Refuse an enrollment that looks like an existing identity, instead of
        # silently creating a duplicate label for a face already in the store.
        for existing_name, stored_embeddings in self.data.items():
            score = max(
                float(np.dot(vector, self._normalize(stored)))
                for vector in vectors
                for stored in stored_embeddings
            )
            if score >= self.threshold:
                raise ValueError(f"Enrollment resembles the existing identity {existing_name}")

        self.data[name] = [vector.tolist() for vector in vectors[-self.MAX_EMBEDDINGS_PER_PERSON:]]
        self.save()
        return True

    def match(self, embedding, threshold=None, margin=None):
        """Return (name, score) only when best score and separation both pass."""
        if not self.data:
            return None, -1.0
        try:
            query = self._normalize(embedding)
        except (TypeError, ValueError):
            return None, -1.0

        best_by_person = []
        for name, embeddings in self.data.items():
            scores = [
                float(np.dot(query, self._normalize(stored)))
                for stored in embeddings
            ]
            if scores:
                best_by_person.append((max(scores), name))
        if not best_by_person:
            return None, -1.0

        best_by_person.sort(reverse=True)
        best_score, best_name = best_by_person[0]
        second_score = best_by_person[1][0] if len(best_by_person) > 1 else -1.0
        required_score = self.threshold if threshold is None else float(threshold)
        required_margin = self.margin if margin is None else float(margin)
        if best_score >= required_score and best_score - second_score >= required_margin:
            return best_name, best_score
        return None, best_score
