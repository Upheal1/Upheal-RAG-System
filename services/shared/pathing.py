from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """
    Resolve the repository root directory.

    File layout: services/shared/pathing.py -> shared -> services -> repo root.
    """
    return Path(__file__).resolve().parents[2]


def ensure_dir(path: Path) -> Path:
    """Create the directory (and parents) if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path

