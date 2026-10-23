"""Stable source and machine-local model paths for Thashu."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS_DIR = Path.home() / ".local" / "share" / "thashu" / "models"
MODELS_DIR = Path(
    os.environ.get("THASHU_MODELS_DIR", str(DEFAULT_MODELS_DIR))
).expanduser().resolve()


def project_path(*parts):
    """Return an absolute path within the Thashu Python project directory."""
    return str(PROJECT_ROOT.joinpath(*parts))


def model_path(*parts):
    """Return an absolute path in the persistent, machine-local model directory."""
    return str(MODELS_DIR.joinpath(*parts))
