from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
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
    @patch("pathlib.Path.is_file")
    def test_returns_metadata_timestamp(self, mock_is_file):
        mock_is_file.return_value = True
        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value={"last_ingestion": "2026-04-13T10:00:00Z"}):
                result = _last_ingestion_from_metadata()
                assert result == "2026-04-13T10:00:00Z"

    @patch("pathlib.Path.is_file")
    def test_returns_none_when_no_metadata(self, mock_is_file):
        mock_is_file.return_value = False
        assert _last_ingestion_from_metadata() is None


class TestHealthCheck:
    @patch.object(Path, "iterdir")
    @patch.object(Path, "exists")
    @patch.object(Path, "is_dir")
    def test_healthy_response(self, mock_is_dir, mock_exists, mock_iterdir):
        mock_is_dir.return_value = True
        mock_exists.return_value = True
        mock_iterdir.return_value = [
            Path("x/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            Path("x/chroma.sqlite3"),
        ]
        resp = health_check()
        assert resp.indexed_tasks >= 1
        assert resp.storage_status == "healthy"

    @patch.object(Path, "is_dir")
    def test_degraded_when_empty(self, mock_is_dir):
        mock_is_dir.return_value = False
        resp = health_check()
        assert resp.indexed_tasks == 0
        assert resp.storage_status == "unavailable"

    @patch.object(Path, "exists")
    @patch.object(Path, "is_dir")
    def test_unavailable_when_no_db_file(self, mock_is_dir, mock_exists):
        mock_is_dir.return_value = True
        mock_exists.return_value = False
        resp = health_check()
        assert resp.storage_status == "unavailable"


class TestHealthEndpointHTTP:
    def test_http_200_and_shape(self):
        app = FastAPI()
        app.include_router(router, prefix="/knowledge_base")
        client = TestClient(app)

        with patch("pathlib.Path.is_dir", return_value=True), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.iterdir", return_value=[]):
            r = client.get("/knowledge_base/health")
            assert r.status_code == 200
            data = r.json()
            assert "indexed_tasks" in data
            assert "storage_status" in data
            assert "last_ingestion" in data