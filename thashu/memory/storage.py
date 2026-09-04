# memory/storage.py

import json
import os

DB_PATH = "data/memory_db/long_term.json"


def load_data():
    if not os.path.exists(DB_PATH):
        return {}

    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=4)