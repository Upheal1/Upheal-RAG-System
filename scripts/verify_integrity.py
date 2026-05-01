"""
scripts/verify_integrity.py
===========================

Integrity checker for the ChromaDB clinical knowledge base.

Scans every document in the configured collection and validates that
metadata contains the mandatory fields required by downstream agents:

  - difficulty     (int 1-5)
  - xp_reward      (int >= 0)
  - clinical_tags  (non-empty string; maps to ClinicalTask.symptom_tags)

Usage
-----
    python scripts/verify_integrity.py

Environment
-----------
    UPHEAL_CHROMA_PATH       default: ./data/vector_db_mini
    UPHEAL_CHROMA_COLLECTION default: clinical_rag_mini

Exit codes
----------
    0  – no violations
    1  – one or more violations found
    2  – checker error (e.g. DB unreachable)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# Add repo root to path so this script can be run standalone.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.shared.logging import get_logger
from services.shared.pathing import repo_root


logger = get_logger(__name__)

MANDATORY_FIELDS: Tuple[str, ...] = ("difficulty", "xp_reward", "clinical_tags")


@dataclass
class Violation:
    """Single metadata violation."""

    task_id: str
    missing_fields: List[str] = field(default_factory=list)
    invalid_fields: List[str] = field(default_factory=list)

    def summary(self) -> str:
        parts: List[str] = []
        if self.missing_fields:
            parts.append(f"missing={self.missing_fields}")
        if self.invalid_fields:
            parts.append(f"invalid={self.invalid_fields}")
        return "; ".join(parts)


@dataclass
class IntegrityReport:
    """Result of scanning a collection."""

    collection_name: str
    vector_db_path: str
    total_documents: int = 0
    violations: List[Violation] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0

    def print_table(self) -> None:
        """Pretty-print violations to stdout; summary to stderr."""
        print(f"\nCollection : {self.collection_name}")
        print(f"DB path    : {self.vector_db_path}")
        print(f"Documents  : {self.total_documents}")
        print(f"Violations : {len(self.violations)}")

        if self.is_clean:
            print("\n✅ All documents have mandatory fields.")
            return

        print(f"\n{'task_id':<40} {'issues'}")
        print("-" * 80)
        for v in self.violations:
            print(f"{v.task_id:<40} {v.summary()}")
        print("-" * 80)


def _validate_field(name: str, value: Any) -> Optional[str]:
    """Return error description if *value* is invalid for *name*, else None."""
    if name == "difficulty":
        try:
            d = int(value)
            if not (1 <= d <= 5):
                return f"difficulty={d} out of range 1-5"
        except (TypeError, ValueError):
            return f"difficulty={value!r} not an int"
    elif name == "xp_reward":
        try:
            x = int(value)
            if x < 0:
                return f"xp_reward={x} negative"
        except (TypeError, ValueError):
            return f"xp_reward={value!r} not an int"
    elif name == "clinical_tags":
        if value is None:
            return "clinical_tags=None"
        s = str(value).strip()
        if not s:
            return "clinical_tags empty"
    return None


def _check_metadata(task_id: str, meta: Optional[Dict[str, Any]]) -> Optional[Violation]:
    """Inspect a single metadata dict and return Violation if any."""
    if meta is None:
        return Violation(task_id=task_id, missing_fields=list(MANDATORY_FIELDS))

    missing: List[str] = []
    invalid: List[str] = []

    for field_name in MANDATORY_FIELDS:
        if field_name not in meta:
            missing.append(field_name)
            continue
        err = _validate_field(field_name, meta[field_name])
        if err:
            invalid.append(err)

    if missing or invalid:
        return Violation(task_id=task_id, missing_fields=missing, invalid_fields=invalid)
    return None


def scan_collection(
    *,
    vector_db_path: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> IntegrityReport:
    """
    Connect to ChromaDB and scan every document's metadata.

    Falls back to environment variables and then repo-root defaults.
    """
    root = repo_root()
    db_path = vector_db_path or os.environ.get(
        "UPHEAL_CHROMA_PATH", str(root / "data" / "vector_db_mini")
    )
    coll_name = collection_name or os.environ.get(
        "UPHEAL_CHROMA_COLLECTION", "clinical_rag_mini"
    )

    report = IntegrityReport(collection_name=coll_name, vector_db_path=db_path)

    try:
        import chromadb
    except Exception as exc:  # pragma: no cover
        logger.error("chromadb_not_available", error=str(exc))
        raise SystemExit(2)

    client = chromadb.PersistentClient(path=str(db_path))

    try:
        collection = client.get_collection(name=coll_name)
    except Exception as exc:
        logger.error("collection_not_found", collection=coll_name, error=str(exc))
        raise SystemExit(2)

    report.total_documents = collection.count()
    logger.info(
        "integrity.scan_start",
        collection=coll_name,
        documents=report.total_documents,
    )

    if report.total_documents == 0:
        return report

    # Pull every document's metadata.  Chroma get() defaults to the first
    # ``limit`` items; we page through the whole collection.
    batch_size = 500
    offset = 0
    while offset < report.total_documents:
        batch = collection.get(
            limit=batch_size,
            offset=offset,
            include=["metadatas"],
        )
        ids: Sequence[str] = batch.get("ids") or []
        metas: Sequence[Optional[Dict[str, Any]]] = batch.get("metadatas") or []

        for task_id, meta in zip(ids, metas):
            violation = _check_metadata(str(task_id), meta)
            if violation:
                report.violations.append(violation)

        offset += len(ids)

    logger.info(
        "integrity.scan_complete",
        collection=coll_name,
        documents=report.total_documents,
        violations=len(report.violations),
    )
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry-point."""
    # Allow optional positional overrides: verify_integrity.py <db_path> <collection>
    args = list(argv) if argv else []
    db_path: Optional[str] = args[0] if len(args) >= 1 else None
    coll_name: Optional[str] = args[1] if len(args) >= 2 else None

    report = scan_collection(vector_db_path=db_path, collection_name=coll_name)
    report.print_table()
    return 0 if report.is_clean else 1


if __name__ == "__main__":
    sys.exit(main())
