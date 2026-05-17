"""
services/shared/state.py
========================

State Manager for Upheal RAG pipeline.

Three responsibilities:
1. **Pathing helpers** — resolve and validate paths for clinical PDF directories,
   chunk output, vector DB, and config artifacts.
2. **Supabase sync hooks** — optimistic-locking sync primitives that push local
   state to Supabase tables (clinical_tasks, interaction_logs, roadmaps, …).
3. **Offline retry backoff** — exponential backoff (1 s → 2 s → 4 s … cap 60 s)
   for sync operations when Supabase is unreachable.

Environment overrides
---------------------
    UPHEAL_DATA_DIR        base data directory (default: <repo_root>/data)
    UPHEAL_CHROMA_PATH     ChromaDB persistence directory
    UPHEAL_CHROMA_COLLECTION ChromaDB collection name
    UPHEAL_EMBEDDING_MODEL embedding model name
    UPHEAL_SUPABASE_URL    Supabase project URL
    UPHEAL_SUPABASE_KEY    Supabase anon/service key
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from services.shared.logging import get_logger
from services.shared.pathing import repo_root

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pathing helpers
# ---------------------------------------------------------------------------

_DEFAULT_DIRS = {
    "books": "books",
    "rag_chunks": "rag_chunks",
    "vector_db_mini": "vector_db_mini",
    "vector_db_enriched": "vector_db_mini_enriched",
}

_DEFAULT_FILES = {
    "semantic_chunks": ("rag_chunks", "semantic_chunks.json"),
    "config": ("", "config.json"),
}


def data_root() -> Path:
    """Return the base data directory (``<repo>/data`` by default)."""
    env_dir = os.getenv("UPHEAL_DATA_DIR", "")
    if env_dir:
        return Path(env_dir).resolve()
    return repo_root() / "data"


def resolve_path(*parts: str) -> Path:
    """_join path components under :pyfunc:`data_root`."""
    return data_root().joinpath(*parts)


def books_dir() -> Path:
    """Return the clinical PDF source directory."""
    return resolve_path(_DEFAULT_DIRS["books"])


def rag_chunks_dir() -> Path:
    """Return the directory holding ``semantic_chunks.json``."""
    return resolve_path(_DEFAULT_DIRS["rag_chunks"])


def vector_db_path() -> Path:
    """Return the ChromaDB persistence directory (env-aware)."""
    env = os.getenv("UPHEAL_CHROMA_PATH")
    if env:
        return Path(env).resolve()
    return resolve_path(_DEFAULT_DIRS["vector_db_enriched"])


def chroma_collection_name() -> str:
    """Return the configured ChromaDB collection name."""
    return os.getenv("UPHEAL_CHROMA_COLLECTION", "clinical_rag_mini")


def embedding_model_name() -> str:
    """Return the configured embedding model name."""
    return os.getenv("UPHEAL_EMBEDDING_MODEL", "all-mpnet-base-v2")


def semantic_chunks_path() -> Path:
    """Return the path to ``semantic_chunks.json``."""
    subdir, fname = _DEFAULT_FILES["semantic_chunks"]
    return resolve_path(subdir, fname)


def config_path() -> Path:
    """Return the path to the ingestion ``config.json``."""
    subdir, fname = _DEFAULT_FILES["config"]
    return resolve_path(subdir, fname)


def list_pdf_books() -> List[str]:
    """Return a sorted list of PDF filenames (stems) in :pyfunc:`books_dir`."""
    bdir = books_dir()
    if not bdir.is_dir():
        return []
    return sorted(p.stem for p in bdir.glob("*.pdf"))


def ensure_data_dirs() -> None:
    """Create all standard data sub-directories if they don't exist."""
    for name in _DEFAULT_DIRS.values():
        (data_root() / name).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Supabase sync hooks (optimistic locking)
# ---------------------------------------------------------------------------

_SUPABASE_URL_ENV = "UPHEAL_SUPABASE_URL"
_SUPABASE_KEY_ENV = "UPHEAL_SUPABASE_KEY"

_LOCK_VERSION_COLUMN = "version"


class SyncConflictError(Exception):
    """Raised when an optimistic-lock update fails (row was modified by another writer)."""


class SupabaseSyncHook:
    """
    Optimistic-locking sync primitive for a Supabase table.

    On every :pyfunc:`upsert_row` the current ``version`` column is checked
    against the expected value. If the row has been_modified by another process,
    :pyclass:`SyncConflictError` is raised instead of overwriting.

    Parameters
    ----------
    table:
        Target table name (e.g. ``"clinical_tasks"``).
    client:
        An optional pre-built ``supabase.Client``. If *None*, a new client is
        constructed from :envvar:`UPHEAL_SUPABASE_URL` and
        :envvar:`UPHEAL_SUPABASE_KEY`.
    version_column:
        The column used for optimistic locking (default ``"version"``).
    """

    def __init__(
        self,
        table: str,
        client: Optional[Any] = None,
        version_column: str = _LOCK_VERSION_COLUMN,
    ) -> None:
        self.table = table
        self._client = client
        self._version_col = version_column
        self._lock = threading.Lock()

    # ---- lazy client construction ----

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    @staticmethod
    def _build_client() -> Any:
        url = os.getenv(_SUPABASE_URL_ENV)
        key = os.getenv(_SUPABASE_KEY_ENV)
        if not url or not key:
            raise EnvironmentError(
                f"Set {_SUPABASE_URL_ENV} and {_SUPABASE_KEY_ENV} "
                "to enable Supabase sync."
            )

        try:
            from supabase import create_client
        except ImportError as exc:
            raise ImportError(
                "supabase package is required for sync hooks. "
                "Install it with: pip install supabase"
            ) from exc

        return create_client(url, key)

    # ---- read ----

    def fetch_one(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Fetch a single row matching *filters* (equality)."""
        query = self.client.table(self.table).select("*")
        for col, val in filters.items():
            query = query.eq(col, val)
        resp = query.limit(1).execute()
        rows = resp.data or []
        return rows[0] if rows else None

    # ---- write ----

    def insert_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a new row. The ``version`` column is initialised to **1** if
        not already set.
        """
        row.setdefault(self._version_col, 1)
        resp = self.client.table(self.table).insert(row).execute()
        log.info(
            "state.supabase.insert",
            table=self.table,
            row_count=len(resp.data or []),
        )
        return resp.data[0] if resp.data else {}

    def upsert_row(
        self,
        row: Dict[str, Any],
        expected_version: int,
        conflict_cols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Upsert a row with **optimistic locking**.

        The row must include a ``version`` value that matches
        *expected_version*. On conflict (stale version) a
        :pyclass:`SyncConflictError` is raised.

        Parameters
        ----------
        row:
            Full row dict (must include primary-key columns).
        expected_version:
            The version the caller believes is current. If the row in the DB
            has a different version the write is rejected.
        conflict_cols:
            Column names that define uniqueness for the upsert (used as
            ``on_conflict`` in Supabase). If *None*, the primary key is
            inferred from the first column.
        """
        with self._lock:
            pk_cols = conflict_cols or [next(iter(row))]
            filters = {col: row[col] for col in pk_cols}
            existing = self.fetch_one(filters)

            if existing is not None:
                current_ver = existing.get(self._version_col, 0)
                if current_ver != expected_version:
                    raise SyncConflictError(
                        f"Optimistic lock conflict on {self.table}: "
                        f"expected version {expected_version}, "
                        f"but found {current_ver}"
                    )
                row[self._version_col] = expected_version + 1
                resp = (
                    self.client.table(self.table)
                    .update(row)
                    .eq(pk_cols[0], row[pk_cols[0]])
                    .execute()
                )

                log.info(
                    "state.supabase.update",
                    table=self.table,
                    expected_version=expected_version,
                )
            else:
                row.setdefault(self._version_col, 1)
                resp = self.client.table(self.table).insert(row).execute()
                log.info("state.supabase.insert", table=self.table)

            return resp.data[0] if resp.data else {}

    def delete_row(self, filters: Dict[str, Any]) -> None:
        """Delete rows matching *filters*."""
        query = self.client.table(self.table).delete()
        for col, val in filters.items():
            query = query.eq(col, val)
        query.execute()
        log.info("state.supabase.delete", table=self.table, filters=filters)


# ---------------------------------------------------------------------------
# Offline retry backoff
# ---------------------------------------------------------------------------

_INITIAL_BACKOFF = 1.0
_MAX_BACKOFF = 60.0
_BACKOFF_MULTIPLIER = 2.0


class OfflineRetryExhausted(Exception):
    """Raised when all retry attempts fail."""


def _default_is_retryable(exc: BaseException) -> bool:
    """Heuristic: retry on connection / timeout errors, not on auth errors."""
    name = type(exc).__name__.lower()
    return any(k in name for k in ("connection", "timeout", "network", "http"))


def retry_with_backoff(
    fn: Callable[[], Any],
    max_retries: int = 5,
    initial_backoff: float = _INITIAL_BACKOFF,
    max_backoff: float = _MAX_BACKOFF,
    multiplier: float = _BACKOFF_MULTIPLIER,
    is_retryable: Optional[Callable[[BaseException], bool]] = None,
) -> Any:
    """
    Call *fn* with exponential backoff on failure.

    The delay sequence is: *initial_backoff*, *initial_backoff* × 2, …,
    capped at *max_backoff* seconds.

    Parameters
    ----------
    fn:
        Callable that may raise on network / Supabase errors.
    max_retries:
        Maximum number of retry attempts **after** the first call.
    initial_backoff:
        First wait duration in seconds (default 1).
    max_backoff:
        Ceiling for backoff duration (default 60).
    multiplier:
        Factor by which backoff grows each iteration (default 2).
    is_retryable:
        Predicate that decides whether an exception is worth retrying.
        Defaults to retrying on connection / timeout / network errors.

    Returns
    -------
    The return value of *fn*.

    Raises
    ------
    OfflineRetryExhausted
        If all attempts fail or the last error is not retryable.
    """
    if is_retryable is None:
        is_retryable = _default_is_retryable

    backoff = initial_backoff
    last_exc: Optional[BaseException] = None

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries or not is_retryable(exc):
                break
            log.warning(
                "state.retry.backoff",
                attempt=attempt + 1,
                backoff_seconds=backoff,
                error=str(exc),
            )
            time.sleep(backoff)
            backoff = min(backoff * multiplier, max_backoff)

    raise OfflineRetryExhausted(
        f"All {max_retries + 1} attempts failed"
    ) from last_exc


# ---------------------------------------------------------------------------
# Convenience: file-hash helper (used by migration & integrity scripts)
# ---------------------------------------------------------------------------


def file_sha256(path: Path, block_size: int = 1 << 16) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(block_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Convenience: load / save config.json
# ---------------------------------------------------------------------------


def load_config() -> Dict[str, Any]:
    """Load ``config.json`` from the data root; return empty dict if missing."""
    p = config_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_config(cfg: Dict[str, Any]) -> None:
    """Write ``config.json`` to the data root (atomic-ish)."""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("state.config.saved", path=str(p))