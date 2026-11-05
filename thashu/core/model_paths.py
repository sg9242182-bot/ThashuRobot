"""Stable source and machine-local model paths for Thashu."""

from pathlib import Path

from core.config import data_dir, models_dir


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = models_dir()


def project_path(*parts):
    """Return an absolute path within the Thashu Python project directory."""
    return str(PROJECT_ROOT.joinpath(*parts))


def model_path(*parts):
    """Return an absolute path in the persistent, machine-local model directory."""
    return str(MODELS_DIR.joinpath(*parts))


DATA_DIR = data_dir()


def data_path(*parts):
    """Return a path in persistent machine-local data, outside the Git checkout."""
    return str(DATA_DIR.joinpath(*parts))
