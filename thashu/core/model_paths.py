"""Stable paths for Thashu's source tree and machine-local model assets."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"


def project_path(*parts):
    """Return an absolute path within the Thashu Python project directory."""
    return str(PROJECT_ROOT.joinpath(*parts))


def model_path(*parts):
    """Return an absolute path within the ignored, machine-local models folder."""
    return str(MODELS_DIR.joinpath(*parts))
