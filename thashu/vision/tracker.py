import numpy as np


class CentroidTracker:
    """Short-lived object tracks with explicit ambiguity reporting for safe target lock."""

    def __init__(
        self,
        max_disappeared=20,
        max_match_distance=160.0,
        ambiguity_margin=30.0,
        overlap_distance=70.0,
    ):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.max_disappeared = max_disappeared
        self.max_match_distance = float(max_match_distance)
        self.ambiguity_margin = float(ambiguity_margin)
        self.overlap_distance = float(overlap_distance)
        self.last_assignments = {}
        self.last_ambiguous_ids = set()

    def reset(self):
        """Discard tracks so IDs/names from before a vision pause cannot go stale."""
        self.next_object_id = 0
        self.objects.clear()
        self.disappeared.clear()
        self.last_assignments.clear()
        self.last_ambiguous_ids.clear()

    def register(self, centroid):
        object_id = self.next_object_id
        self.objects[object_id] = tuple(map(int, centroid))
        self.disappeared[object_id] = 0
        self.next_object_id += 1
        return object_id

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]

    @staticmethod
    def _centroids(rects):
        return [
            (int((x1 + x2) / 2.0), int((y1 + y2) / 2.0))
            for (x1, y1, x2, y2) in rects
        ]

    def update(self, rects):
        rects = list(rects or [])
        self.last_assignments = {}
        self.last_ambiguous_ids = set()
        centroids = self._centroids(rects)

        if not centroids:
            for object_id in list(self.disappeared):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return dict(self.objects)

        if not self.objects:
            for index, centroid in enumerate(centroids):
                self.last_assignments[index] = self.register(centroid)
            self._mark_close_tracks()
            return dict(self.objects)

        object_ids = list(self.objects)
        old_centroids = [self.objects[object_id] for object_id in object_ids]
        distances = np.linalg.norm(
            np.asarray(old_centroids, dtype=float)[:, None, :]
            - np.asarray(centroids, dtype=float)[None, :, :],
            axis=2,
        )

        # Mark close alternatives as ambiguous before selecting any pair. A
        # caller must stop rather than trust a weak nearest-centroid identity.
        for row, object_id in enumerate(object_ids):
            choices = np.sort(distances[row])
            if len(choices) > 1 and choices[0] <= self.max_match_distance:
                if choices[1] - choices[0] <= self.ambiguity_margin:
                    self.last_ambiguous_ids.add(object_id)
        for col in range(len(centroids)):
            choices = np.sort(distances[:, col])
            if len(choices) > 1 and choices[0] <= self.max_match_distance:
                if choices[1] - choices[0] <= self.ambiguity_margin:
                    for row, distance in enumerate(distances[:, col]):
                        if distance <= choices[1] + self.ambiguity_margin:
                            self.last_ambiguous_ids.add(object_ids[row])

        pairs = sorted(
            (distances[row, col], row, col)
            for row in range(len(object_ids))
            for col in range(len(centroids))
            if distances[row, col] <= self.max_match_distance
        )
        used_rows, used_cols = set(), set()
        matched_old = {}
        for distance, row, col in pairs:
            if row in used_rows or col in used_cols:
                continue
            object_id = object_ids[row]
            self.objects[object_id] = centroids[col]
            self.disappeared[object_id] = 0
            self.last_assignments[col] = object_id
            matched_old[object_id] = old_centroids[row]
            used_rows.add(row)
            used_cols.add(col)

        for row, object_id in enumerate(object_ids):
            if row in used_rows:
                continue
            self.disappeared[object_id] += 1
            if self.disappeared[object_id] > self.max_disappeared:
                self.deregister(object_id)

        for col, centroid in enumerate(centroids):
            if col not in used_cols:
                self.last_assignments[col] = self.register(centroid)

        # If two tracks overlap or cross between frames, centroid-only identity
        # is not reliable. Mark both; the follow controller will stop/reselect.
        assigned = [
            (object_id, old, self.objects[object_id])
            for object_id, old in matched_old.items()
            if object_id in self.objects
        ]
        for left in range(len(assigned)):
            id_a, old_a, new_a = assigned[left]
            for right in range(left + 1, len(assigned)):
                id_b, old_b, new_b = assigned[right]
                close_now = np.linalg.norm(np.asarray(new_a) - np.asarray(new_b)) < self.overlap_distance
                crossed = (old_a[0] - old_b[0]) * (new_a[0] - new_b[0]) < 0
                if close_now or crossed:
                    self.last_ambiguous_ids.update((id_a, id_b))

        self._mark_close_tracks()
        return dict(self.objects)

    def _mark_close_tracks(self):
        ids = list(self.objects)
        for i, id_a in enumerate(ids):
            for id_b in ids[i + 1:]:
                if np.linalg.norm(
                    np.asarray(self.objects[id_a]) - np.asarray(self.objects[id_b])
                ) < self.overlap_distance:
                    self.last_ambiguous_ids.update((id_a, id_b))
