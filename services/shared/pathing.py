from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


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


def resolve_chroma_path(env_var_name: str = "UPHEAL_CHROMA_PATH", subdir: str = "data/vector_db_mini") -> str:
    """
    Resolve the ChromaDB data path in a deployment-agnostic way.

    Tries multiple strategies in order:
      1. Explicit env var (UPHEAL_CHROMA_PATH).
      2. Relative to cwd: ./data/vector_db_mini.
      3. Common Render path: /opt/render/project/src/data/vector_db_mini.
      4. Hardcoded /app/data/vector_db_mini (Docker default).
      5. repo_root() fallback (local dev).

    Returns the *first* path that exists as a directory.
    If none exist, returns the env var or the cwd-relative path as a last resort.
    """
    candidates: list[str] = []

    # 1. Environment variable (highest priority)
    env_path = os.environ.get(env_var_name)
    if env_path:
        candidates.append(env_path)

    # 2. Relative to current working directory
    candidates.append(f"./{subdir}")

    # 3. Common Render project root
    candidates.append(f"/opt/render/project/src/{subdir}")

    # 4. Docker /app default
    candidates.append(f"/app/{subdir}")

    # 5. repo_root fallback (local development)
    try:
        candidates.append(str(repo_root() / subdir.replace("/", os.sep)))
    except Exception:
        pass

    for p in candidates:
        normalized = os.path.normpath(os.path.expanduser(p))
        if os.path.isdir(normalized):
            return normalized

    # Nothing found — return the first candidate so callers still have *some* path
    # (health checks will report it as missing).
    return candidates[0] if candidates else f"./{subdir}"

