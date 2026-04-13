"""
tests/test_logging.py
=====================

Unit tests for ``services/shared/logging.py``.
"""

from __future__ import annotations

import json
import logging
import sys
from io import StringIO
from pathlib import Path

import pytest

from services.shared.logging import (
    JSONFormatter,
    _StructuredLogger,
    _derive_service_name,
    configure_logging,
    get_logger,
    log_chunk_created,
    log_chroma_upsert,
    log_formatter_done,
    log_pdf_start,
)


class TestDeriveServiceName:
    def test_strips_services_prefix(self) -> None:
        assert (
            _derive_service_name("services.ingestion.pdf_utils")
            == "ingestion.pdf_utils"
        )

    def test_strips_multiple_services_levels(self) -> None:
        assert (
            _derive_service_name("services.knowledge_base.chroma_adapter")
            == "knowledge_base.chroma_adapter"
        )

    def test_handles_gateway_path(self) -> None:
        assert _derive_service_name("services.gateway.main") == "gateway.main"

    def test_preserves_non_services_paths(self) -> None:
        assert _derive_service_name("some.other.module") == "some.other.module"

    def test_no_services_in_path(self) -> None:
        assert _derive_service_name("pdf_utils") == "pdf_utils"


class TestStructuredLogger:
    def test_info_creates_json_with_event_and_payload(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JSONFormatter())

        base_logger = logging.getLogger("test.info_event")
        base_logger.setLevel(logging.INFO)
        base_logger.handlers.clear()
        base_logger.addHandler(handler)

        logger = _StructuredLogger(base_logger, service="ingestion.pdf_utils")
        logger.info(
            "ingestion.pdf.start", source_path="/data/test.pdf", sha256="abc123"
        )

        raw = output.getvalue()
        entry = json.loads(raw)

        assert entry["service"] == "ingestion.pdf_utils"
        assert entry["event"] == "ingestion.pdf.start"
        assert entry["payload"]["source_path"] == "/data/test.pdf"
        assert entry["payload"]["sha256"] == "abc123"
        assert "timestamp" in entry

    def test_warning_includes_payload(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JSONFormatter())

        base_logger = logging.getLogger("test.warning")
        base_logger.setLevel(logging.WARNING)
        base_logger.handlers.clear()
        base_logger.addHandler(handler)

        logger = _StructuredLogger(base_logger, service="test.service")
        logger.warning("test.warning", count=42)

        raw = output.getvalue()
        entry = json.loads(raw)

        assert entry["event"] == "test.warning"
        assert entry["payload"]["count"] == 42

    def test_error_includes_error_field(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JSONFormatter())

        base_logger = logging.getLogger("test.error")
        base_logger.setLevel(logging.ERROR)
        base_logger.handlers.clear()
        base_logger.addHandler(handler)

        logger = _StructuredLogger(base_logger, service="test.service")
        try:
            raise ValueError("test error")
        except ValueError:
            logger.error("test.error", code=500)

        raw = output.getvalue()
        entry = json.loads(raw)

        assert "error" in entry
        assert entry["error"]["message"] == "test.error"


class TestConvenienceHelpers:
    def test_log_pdf_start(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JSONFormatter())

        base_logger = logging.getLogger("test.pdf_start")
        base_logger.setLevel(logging.INFO)
        base_logger.handlers.clear()
        base_logger.addHandler(handler)

        logger = _StructuredLogger(base_logger, service="ingestion.pdf_utils")
        log_pdf_start("/data/clinical_pdfs/inbox/dsm5.pdf", "sha256abc", logger=logger)

        raw = output.getvalue()
        entry = json.loads(raw)

        assert entry["event"] == "ingestion.pdf.start"
        assert entry["payload"]["source_path"] == "/data/clinical_pdfs/inbox/dsm5.pdf"
        assert entry["payload"]["sha256"] == "sha256abc"

    def test_log_chunk_created(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JSONFormatter())

        base_logger = logging.getLogger("test.chunk")
        base_logger.setLevel(logging.INFO)
        base_logger.handlers.clear()
        base_logger.addHandler(handler)

        logger = _StructuredLogger(base_logger, service="ingestion.pdf_utils")
        log_chunk_created(
            0, "/data/test.pdf", [0, 1500], task_id="task-001", logger=logger
        )

        raw = output.getvalue()
        entry = json.loads(raw)

        assert entry["event"] == "ingestion.chunk.created"
        assert entry["payload"]["chunk_index"] == 0
        assert entry["payload"]["byte_span"] == [0, 1500]
        assert entry["payload"]["task_id"] == "task-001"

    def test_log_formatter_done(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JSONFormatter())

        base_logger = logging.getLogger("test.formatter")
        base_logger.setLevel(logging.INFO)
        base_logger.handlers.clear()
        base_logger.addHandler(handler)

        logger = _StructuredLogger(base_logger, service="ingestion.formatter_agent")
        log_formatter_done(
            "task-001",
            difficulty=3,
            xp_reward=75,
            symptom_tags=["anxiety", "sleep"],
            safety_risk=False,
            logger=logger,
        )

        raw = output.getvalue()
        entry = json.loads(raw)

        assert entry["event"] == "ingestion.formatter.done"
        assert entry["payload"]["task_id"] == "task-001"
        assert entry["payload"]["difficulty"] == 3
        assert entry["payload"]["xp_reward"] == 75
        assert entry["payload"]["symptom_tags"] == ["anxiety", "sleep"]
        assert entry["payload"]["safety_risk"] is False

    def test_log_chroma_upsert(self) -> None:
        output = StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JSONFormatter())

        base_logger = logging.getLogger("test.chroma")
        base_logger.setLevel(logging.INFO)
        base_logger.handlers.clear()
        base_logger.addHandler(handler)

        logger = _StructuredLogger(base_logger, service="knowledge_base.chroma_adapter")
        log_chroma_upsert(
            "clinical_rag", ["task-001", "task-002"], count=2, logger=logger
        )

        raw = output.getvalue()
        entry = json.loads(raw)

        assert entry["event"] == "kb.chroma.upsert"
        assert entry["payload"]["collection"] == "clinical_rag"
        assert entry["payload"]["ids"] == ["task-001", "task-002"]
        assert entry["payload"]["count"] == 2


class TestConfigureLogging:
    def test_configure_with_json_format(self, tmp_path: Path) -> None:
        import services.shared.logging as logging_mod

        logging_mod._global_configured = False

        log_file = tmp_path / "test.log"

        configure_logging(level=logging.INFO, output_path=log_file, json_format=True)

        logger = get_logger("test.configure")
        logger.info("test.event", key="value")

        assert log_file.exists()
        raw = log_file.read_text(encoding="utf-8").strip()
        entry = json.loads(raw)

        assert entry["event"] == "test.event"
        assert entry["payload"]["key"] == "value"

    def test_configure_idempotent(self) -> None:
        """Second call to configure_logging should not add duplicate handlers."""
        import services.shared.logging as logging_mod

        logging_mod._global_configured = False

        configure_logging(level=logging.INFO)
        configure_logging(level=logging.DEBUG)

        root = logging.getLogger()
        handler_count = len(root.handlers)
        assert handler_count == 1, f"Expected 1 handler, got {handler_count}"


class TestJSONFormatter:
    def test_formats_valid_json(self) -> None:
        formatter = JSONFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.service = "test.service"
        record.event = "test.event"
        record.payload = {"foo": "bar"}

        output = formatter.format(record)
        entry = json.loads(output)

        assert entry["service"] == "test.service"
        assert entry["event"] == "test.event"
        assert entry["payload"] == {"foo": "bar"}
        assert "timestamp" in entry

    def test_error_level_includes_error_field(self) -> None:
        formatter = JSONFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error message",
            args=(),
            exc_info=None,
        )
        record.service = "test.service"
        record.event = "test.error"
        record.payload = {}

        output = formatter.format(record)
        entry = json.loads(output)

        assert "error" in entry
        assert entry["error"]["message"] == "error message"

    def test_default_service_falls_back_to_name(self) -> None:
        formatter = JSONFormatter()

        record = logging.LogRecord(
            name="my.module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.event = "log"
        record.payload = {}

        output = formatter.format(record)
        entry = json.loads(output)

        assert entry["service"] == "my.module"
