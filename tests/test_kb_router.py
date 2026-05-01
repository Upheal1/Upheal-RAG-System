from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.knowledge_base.router import (
    KnowledgeBaseHealthResponse,
    _determine_storage_status,
    _last_ingestion_from_metadata,
    health_check,
    router,
)


class TestDetermineStorageStatus:
    def test_healthy_when_healthy_and_nonzero(self):
        assert _determine_storage_status(True, 10) == "healthy"

    def test_degraded_when_healthy_but_empty(self):
        assert _determine_storage_status(True, 0) == "degraded"

    def test_unavailable_when_not_healthy(self):
        assert _determine_storage_status(False, 0) == "unavailable"
        assert _determine_storage_status(False, 10) == "unavailable"


class TestLastIngestionFromMetadata:
    @patch("services.knowledge_base.router._kb.get_collection_metadata")
    def test_returns_metadata_timestamp(self, mock_meta):
        mock_meta.return_value = {"last_ingestion": "2026-04-13T10:00:00Z"}
        assert _last_ingestion_from_metadata() == "2026-04-13T10:00:00Z"

    @patch("services.knowledge_base.router._kb.get_collection_metadata")
    def test_returns_none_when_no_metadata(self, mock_meta):
        mock_meta.return_value = {}
        assert _last_ingestion_from_metadata() is None


class TestHealthCheck:
    @patch("services.knowledge_base.router._kb.is_healthy")
    @patch("services.knowledge_base.router._kb.get_document_count")
    @patch("services.knowledge_base.router._kb.get_collection_metadata")
    def test_healthy_response(self, mock_meta, mock_count, mock_healthy):
        mock_healthy.return_value = True
        mock_count.return_value = 42
        mock_meta.return_value = {"last_ingestion": "2026-04-13T10:00:00Z"}

        resp = health_check()
        assert resp.indexed_tasks == 42
        assert resp.storage_status == "healthy"
        assert resp.last_ingestion == "2026-04-13T10:00:00Z"

    @patch("services.knowledge_base.router._kb.is_healthy")
    @patch("services.knowledge_base.router._kb.get_document_count")
    @patch("services.knowledge_base.router._kb.get_collection_metadata")
    def test_degraded_when_empty(self, mock_meta, mock_count, mock_healthy):
        mock_healthy.return_value = True
        mock_count.return_value = 0
        mock_meta.return_value = {}

        resp = health_check()
        assert resp.indexed_tasks == 0
        assert resp.storage_status == "degraded"
        assert resp.last_ingestion is None

    @patch("services.knowledge_base.router._kb.is_healthy")
    @patch("services.knowledge_base.router._kb.get_document_count")
    @patch("services.knowledge_base.router._kb.get_collection_metadata")
    def test_unavailable_when_unreachable(self, mock_meta, mock_count, mock_healthy):
        mock_healthy.return_value = False
        mock_count.return_value = 0
        mock_meta.return_value = {}

        resp = health_check()
        assert resp.storage_status == "unavailable"


class TestHealthEndpointHTTP:
    def test_http_200_and_shape(self):
        # We mount the router under a dummy app to exercise the endpoint via HTTP.
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/knowledge_base")
        client = TestClient(app)

        with patch("services.knowledge_base.router._kb.is_healthy", return_value=True), \
             patch("services.knowledge_base.router._kb.get_document_count", return_value=5), \
             patch("services.knowledge_base.router._kb.get_collection_metadata", return_value={}):
            r = client.get("/knowledge_base/health")
            assert r.status_code == 200
            data = r.json()
            assert "indexed_tasks" in data
            assert "storage_status" in data
            assert "last_ingestion" in data
            assert data["indexed_tasks"] == 5
            assert data["storage_status"] == "healthy"
