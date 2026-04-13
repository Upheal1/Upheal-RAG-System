"""
services/shared/logging.py
==========================

UpHeal structured JSON logger.

Every log entry is a valid JSON object with these required fields:
- ``timestamp``: ISO-8601 UTC timestamp
- ``service``: package name of the emitting module (e.g. ``"ingestion.formatter_agent"``)
- ``event``: dot-separated event name (e.g. ``"ingestion.pdf.start"``)
- ``payload``: arbitrary key-value object with event-specific data

Usage
-----
    from services.shared.logging import get_logger

    log = get_logger(__name__)  # service = "ingestion.formatter_agent"
    log.info("ingestion.pdf.start", extra={"source_path": "/data/clinical_pdfs/inbox/dsm5.pdf", "sha256": "abc123..."})

Correlation
-----------
Trace a single PDF through the pipeline using ``payload["source_path"]`` or
``payload["task_id"]`` / Chroma ``id`` across stages.

Example trace::

    {"timestamp": "2026-04-13T10:00:00Z", "service": "ingestion.pdf_utils", "event": "ingestion.pdf.start", "payload": {"source_path": "...", "sha256": "..."}}
    {"timestamp": "2026-04-13T10:00:01Z", "service": "ingestion.pdf_utils", "event": "ingestion.chunk.created", "payload": {"chunk_index": 0, "source_path": "...", "byte_span": [0, 500]}}
    {"timestamp": "2026-04-13T10:00:02Z", "service": "ingestion.formatter_agent", "event": "ingestion.formatter.done", "payload": {"task_id": "...", "difficulty": 2, "xp_reward": 50}}
    {"timestamp": "2026-04-13T10:00:03Z", "service": "knowledge_base.chroma_adapter", "event": "kb.chroma.upsert", "payload": {"collection": "clinical_rag", "ids": ["..."]}}
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_global_configured = False
_config_lock = threading.Lock()


class JSONFormatter(logging.Formatter):
    """
    Format log records as structured JSON with timestamp, service, event, payload.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = getattr(record, "payload", {})

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": getattr(record, "service", record.name),
            "event": getattr(record, "event", "log"),
            "payload": payload,
        }

        if record.levelno >= logging.ERROR:
            log_entry["error"] = {
                "message": record.getMessage(),
                "exc_info": self.formatException(record.exc_info)
                if record.exc_info
                else None,
            }

        return json.dumps(log_entry, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """
    Per-thread and per-handler context injection.
    """

    _local = threading.local()

    @staticmethod
    def set_context(**kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(ContextFilter._local, k, v)

    @staticmethod
    def clear_context() -> None:
        attrs = [a for a in dir(ContextFilter._local) if not a.startswith("_")]
        for attr in attrs:
            delattr(ContextFilter._local, attr)

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = getattr(ContextFilter._local, "service", record.name)
        if not hasattr(record, "event"):
            record.event = getattr(ContextFilter._local, "event", "log")
        if not hasattr(record, "payload"):
            record.payload = getattr(ContextFilter._local, "payload", {})
        return True


_context_filter = ContextFilter()


def configure_logging(
    level: int = logging.INFO,
    output_path: Optional[Path] = None,
    json_format: bool = True,
) -> None:
    """
    Configure the root logger with structured JSON output.

    Args:
        level: Logging level (default INFO).
        output_path: Optional file path for JSON log output. If None, logs to stderr.
        json_format: If True (default), output structured JSON. If False, use plain text.
    """
    global _global_configured

    with _config_lock:
        if _global_configured:
            return

        root = logging.getLogger()
        root.setLevel(level)
        root.handlers.clear()

        if json_format:
            handler: logging.Handler
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(output_path, encoding="utf-8")
            else:
                handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(JSONFormatter())
        else:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                )
            )

        handler.addFilter(_context_filter)
        root.addHandler(handler)
        _global_configured = True


def get_logger(
    name: str,
    level: Optional[int] = None,
    service: Optional[str] = None,
) -> _StructuredLogger:
    """
    Return a structured logger for the given module.

    Args:
        name: Module name (use ``__name__``). The ``service`` field will be
              derived from the package path (e.g. ``"ingestion.pdf_utils"``)
              unless explicitly overridden.
        level: Optional logging level override.
        service: Override the service name in log entries.

    Returns:
        A ``_StructuredLogger`` instance with structured event methods.

    Example::
        log = get_logger(__name__)
        log.info("ingestion.pdf.start", source_path="/data/clinical_pdfs/inbox/dsm5.pdf", sha256="abc123")

        # or with explicit service name:
        log = get_logger(__name__, service="ingestion.formatter_agent")
    """
    if not _global_configured:
        configure_logging()

    logger_name = service or _derive_service_name(name)
    base_logger = logging.getLogger(logger_name)

    if level is not None:
        base_logger.setLevel(level)

    return _StructuredLogger(base_logger, service=logger_name)


def _derive_service_name(name: str) -> str:
    """
    Derive a dot-separated service name from a Python module path.

    Examples::
        "services.ingestion.pdf_utils" -> "ingestion.pdf_utils"
        "services.knowledge_base.chroma_adapter" -> "knowledge_base.chroma_adapter"
        "services.gateway.main" -> "gateway.main"
    """
    parts = name.split(".")
    if "services" in parts:
        idx = parts.index("services")
        return ".".join(parts[idx + 1 :])
    return name


class _StructuredLogger:
    """
    Wrapper around ``logging.Logger`` that adds structured event methods.

    Each method accepts an event name as the first positional argument,
    followed by key-value pairs that populate the ``payload`` in the JSON log entry.
    """

    def __init__(self, logger: logging.Logger, service: str):
        self._logger = logger
        self._service = service

    def _log(
        self,
        level: int,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra = {
            "service": self._service,
            "event": event,
            "payload": payload or {},
        }
        self._logger.log(level, event, extra=extra)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, event, kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, event, kwargs)


# -----------------------------------------------------------------------------
# Convenience helpers for ingestion pipeline events
# -----------------------------------------------------------------------------


def log_pdf_start(
    source_path: str, sha256: str, logger: Optional[_StructuredLogger] = None
) -> None:
    """
    Log the start of PDF ingestion.

    Event: ``ingestion.pdf.start``

    Args:
        source_path: Path to the PDF being ingested.
        sha256: SHA-256 hash of the PDF file.
        logger: Optional logger instance. If None, a new logger for this module is created.
    """
    _log_helper(
        "ingestion.pdf.start",
        {"source_path": source_path, "sha256": sha256},
        logger,
    )


def log_chunk_created(
    chunk_index: int,
    source_path: str,
    byte_span: list[int],
    task_id: Optional[str] = None,
    logger: Optional[_StructuredLogger] = None,
) -> None:
    """
    Log the creation of a semantic chunk.

    Event: ``ingestion.chunk.created``

    Args:
        chunk_index: Zero-based index of this chunk within the document.
        source_path: Path to the source PDF.
        byte_span: [start, end] byte offsets of this chunk in the original PDF.
        task_id: Optional assigned task ID after formatter processing.
        logger: Optional logger instance.
    """
    payload = {
        "chunk_index": chunk_index,
        "source_path": source_path,
        "byte_span": byte_span,
    }
    if task_id:
        payload["task_id"] = task_id
    _log_helper("ingestion.chunk.created", payload, logger)


def log_formatter_done(
    task_id: str,
    difficulty: int,
    xp_reward: int,
    symptom_tags: Optional[list[str]] = None,
    safety_risk: bool = False,
    logger: Optional[_StructuredLogger] = None,
) -> None:
    """
    Log successful formatter agent processing of a chunk.

    Event: ``ingestion.formatter.done``

    Args:
        task_id: Unique identifier for the formatted task.
        difficulty: Assigned difficulty level (1-5).
        xp_reward: Calculated XP reward for completing this task.
        symptom_tags: List of clinical symptom tags assigned to this task.
        safety_risk: Whether the chunk contained crisis/safety-risk keywords.
        logger: Optional logger instance.
    """
    payload = {
        "task_id": task_id,
        "difficulty": difficulty,
        "xp_reward": xp_reward,
        "safety_risk": safety_risk,
    }
    if symptom_tags:
        payload["symptom_tags"] = symptom_tags
    _log_helper("ingestion.formatter.done", payload, logger)


def log_chroma_upsert(
    collection: str,
    ids: list[str],
    count: Optional[int] = None,
    logger: Optional[_StructuredLogger] = None,
) -> None:
    """
    Log a ChromaDB upsert operation.

    Event: ``kb.chroma.upsert``

    Args:
        collection: Name of the Chroma collection that was written to.
        ids: List of document IDs that were upserted.
        count: Optional count of documents written (if known).
        logger: Optional logger instance.
    """
    payload: Dict[str, Any] = {
        "collection": collection,
        "ids": ids,
    }
    if count is not None:
        payload["count"] = count
    _log_helper("kb.chroma.upsert", payload, logger)


def _log_helper(
    event: str,
    payload: Dict[str, Any],
    logger: Optional[_StructuredLogger] = None,
) -> None:
    """Internal helper to log with a default logger if none provided."""
    if logger is None:
        logger = get_logger(__name__)
    logger.info(event, **payload)
