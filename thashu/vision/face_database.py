# vision/face_database.py

import numpy as np
import json
import os

class FaceDatabase:
    def __init__(self, db_path="data/faces.json"):
        self.db_path = db_path
        self.data = self.load()

    def load(self):
        if not os.path.exists(self.db_path):
            return {}
        
        try:
            with open(self.db_path, "r") as f:
                data = f.read().strip()
                if not data:
                    return {}
                return json.loads(data)
        except Exception as e:
            print(f"[DB WARNING] Corrupted database, resetting: {e}")
            return {}

    def save(self):
        with open(self.db_path, "w") as f:
            json.dump(self.data, f)

    def add_person(self, name, embedding):
        if name not in self.data:
            self.data[name] = []
        
        # avoid duplicate embeddings
        for stored in self.data[name]:
            stored = np.array(stored)
            score = np.dot(embedding, stored)

            if score > 0.85:  # stricter duplicate check
                return
            
        self.data[name].append(embedding.tolist())
        self.save()

    def match(self, embedding, threshold=0.55):
        best_match = None
        best_score = -1
        
        for name, embeddings in self.data.items():

            for stored in embeddings:
                stored = np.array(stored)
                score = np.dot(embedding, stored)

                # ✅ FIX: compare correct score
                if score > best_score:
                    best_score = score
                    best_match = name

        if best_score > threshold:
            return best_match, best_score

        return None, best_score