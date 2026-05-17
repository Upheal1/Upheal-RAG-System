"""
tests/test_state.py
===================

Unit tests for ``services/shared/state.py``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.shared.state import (
    OfflineRetryExhausted,
    SyncConflictError,
    SupabaseSyncHook,
    books_dir,
    chroma_collection_name,
    config_path,
    data_root,
    embedding_model_name,
    ensure_data_dirs,
    file_sha256,
    list_pdf_books,
    load_config,
    rag_chunks_dir,
    resolve_path,
    retry_with_backoff,
    save_config,
    semantic_chunks_path,
    vector_db_path,
)


# ---------------------------------------------------------------------------
# Pathing helpers
# ---------------------------------------------------------------------------


class TestDataRoot:
    def test_default_points_to_repo_data(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            path = data_root()
        assert path.name == "data"
        assert path.is_absolute()

    def test_env_override(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_data"
        custom.mkdir()
        with patch.dict(os.environ, {"UPHEAL_DATA_DIR": str(custom)}):
            assert data_root() == custom


class TestResolvePath:
    def test_joins_under_data_root(self) -> None:
        result = resolve_path("books", "dsm5.pdf")
        assert "data" in str(result)
        assert result.name == "dsm5.pdf"

    def test_single_component(self) -> None:
        result = resolve_path("books")
        assert result.name == "books"


class TestBooksDir:
    def test_returns_data_books(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = books_dir()
        assert result.name == "books"
        assert "data" in str(result)


class TestRagChunksDir:
    def test_returns_data_rag_chunks(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = rag_chunks_dir()
        assert result.name == "rag_chunks"


class TestVectorDbPath:
    def test_default_enriched_path(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = vector_db_path()
        assert "vector_db_mini_enriched" in str(result)

    def test_env_override(self, tmp_path: Path) -> None:
        custom = tmp_path / "my_db"
        with patch.dict(os.environ, {"UPHEAL_CHROMA_PATH": str(custom)}):
            assert vector_db_path() == custom


class TestChromaCollectionName:
    def test_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert chroma_collection_name() == "clinical_rag_mini"

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"UPHEAL_CHROMA_COLLECTION": "my_coll"}):
            assert chroma_collection_name() == "my_coll"


class TestEmbeddingModelName:
    def test_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert embedding_model_name() == "all-MiniLM-L6-v2"

    def test_env_override(self) -> None:
        with patch.dict(os.environ, {"UPHEAL_EMBEDDING_MODEL": "custom-model"}):
            assert embedding_model_name() == "custom-model"


class TestSemanticChunksPath:
    def test_returns_chunks_json(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = semantic_chunks_path()
        assert result.name == "semantic_chunks.json"
        assert "rag_chunks" in str(result)


class TestConfigPath:
    def test_returns_config_json(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = config_path()
        assert result.name == "config.json"


class TestListPdfBooks:
    def test_returns_pdf_stems(self, tmp_path: Path) -> None:
        pdf_dir = tmp_path / "books"
        pdf_dir.mkdir()
        (pdf_dir / "DSM-5-TR.pdf").write_bytes(b"%PDF-1.4")
        (pdf_dir / "CBT-Handbook.pdf").write_bytes(b"%PDF-1.4")
        (pdf_dir / "notes.txt").write_text("not a pdf")

        with patch.dict(os.environ, {"UPHEAL_DATA_DIR": str(tmp_path)}, clear=False):
            result = list_pdf_books()
        assert "DSM-5-TR" in result
        assert "CBT-Handbook" in result

    def test_returns_empty_when_dir_missing(self, tmp_path: Path) -> None:
        empty = tmp_path / "no_books_here"
        empty.mkdir()
        with patch.dict(os.environ, {"UPHEAL_DATA_DIR": str(empty)}, clear=False):
            assert list_pdf_books() == []


class TestEnsureDataDirs:
    def test_creates_subdirs(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"UPHEAL_DATA_DIR": str(tmp_path)}):
            ensure_data_dirs()
            assert (tmp_path / "books").is_dir()
            assert (tmp_path / "rag_chunks").is_dir()


# ---------------------------------------------------------------------------
# SyncConflictError
# ---------------------------------------------------------------------------


class TestSyncConflictError:
    def test_is_exception(self) -> None:
        with pytest.raises(SyncConflictError, match="conflict"):
            raise SyncConflictError("conflict on clinical_tasks")


# ---------------------------------------------------------------------------
# SupabaseSyncHook — unit tests with mocked client
# ---------------------------------------------------------------------------


class TestSupabaseSyncHook:
    def _make_hook(self, table: str = "clinical_tasks") -> SupabaseSyncHook:
        mock_client = MagicMock()
        hook = SupabaseSyncHook(table=table, client=mock_client)
        return hook

    def test_insert_row_sets_version(self) -> None:
        hook = self._make_hook()
        hook.client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "abc", "version": 1}]
        )

        result = hook.insert_row({"id": "abc", "title": "Test"})
        assert result["version"] == 1
        call_args = hook.client.table.return_value.insert.call_args[0][0]
        assert call_args["version"] == 1
        # title should pass through
        assert call_args["title"] == "Test"

    def test_insert_row_preserves_existing_version(self) -> None:
        hook = self._make_hook()
        hook.client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "abc", "version": 5}]
        )

        result = hook.insert_row({"id": "abc", "version": 5})
        assert result["version"] == 5

    def test_fetch_one_returns_row(self) -> None:
        hook = self._make_hook()
        expected = {"id": "abc", "version": 3}
        query_mock = MagicMock()
        query_mock.eq.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.execute.return_value = MagicMock(data=[expected])
        hook.client.table.return_value.select.return_value = query_mock

        row = hook.fetch_one({"id": "abc"})
        assert row == expected

    def test_fetch_one_returns_none_when_empty(self) -> None:
        hook = self._make_hook()
        hook.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        row = hook.fetch_one({"id": "missing"})
        assert row is None

    def test_upsert_row_updates_when_existing(self) -> None:
        hook = self._make_hook()
        existing = {"id": "abc", "version": 2, "title": "old"}
        hook.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[existing]
        )
        hook.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "abc", "version": 3, "title": "new"}]
        )

        result = hook.upsert_row(
            {"id": "abc", "title": "new"},
            expected_version=2,
            conflict_cols=["id"],
        )
        assert result["version"] == 3

    def test_upsert_row_inserts_when_new(self) -> None:
        hook = self._make_hook()
        hook.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        hook.client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "new", "version": 1}]
        )

        result = hook.upsert_row(
            {"id": "new", "title": "fresh"},
            expected_version=0,
            conflict_cols=["id"],
        )
        assert result["version"] == 1

    def test_upsert_row_raises_conflict_on_stale_version(self) -> None:
        hook = self._make_hook()
        existing = {"id": "abc", "version": 5}
        hook.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[existing]
        )

        with pytest.raises(SyncConflictError, match="expected version 3"):
            hook.upsert_row(
                {"id": "abc", "title": "stale"},
                expected_version=3,
                conflict_cols=["id"],
            )

    def test_delete_row_calls_delete(self) -> None:
        hook = self._make_hook()
        hook.client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        hook.delete_row({"id": "abc"})
        hook.client.table.assert_called_with("clinical_tasks")

    def test_lazy_client_construction_raises_on_env_missing(self) -> None:
        hook = SupabaseSyncHook(table="test", client=None)
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError, match="UPHEAL_SUPABASE_URL"):
                _ = hook.client


# ---------------------------------------------------------------------------
# retry_with_backoff
# ---------------------------------------------------------------------------


class TestRetryWithBackoff:
    def test_succeeds_immediately(self) -> None:
        result = retry_with_backoff(lambda: 42, max_retries=3)
        assert result == 42

    def test_retries_on_failure_then_succeeds(self) -> None:
        calls = [0]
        calls_to_fail = 2

        def flaky():
            calls[0] += 1
            if calls[0] <= calls_to_fail:
                raise ConnectionError("network error")
            return "ok"

        with patch("services.shared.state.time.sleep"):
            result = retry_with_backoff(flaky, max_retries=3)
        assert result == "ok"

    def test_raises_exhausted_after_max_retries(self) -> None:
        def always_fail():
            raise ConnectionError("down")

        with patch("services.shared.state.time.sleep"):
            with pytest.raises(OfflineRetryExhausted, match="3 attempts failed"):
                retry_with_backoff(always_fail, max_retries=2)

    def test_does_not_retry_non_retryable_error(self) -> None:
        def fail_auth():
            raise PermissionError("forbidden")

        with pytest.raises(OfflineRetryExhausted):
            retry_with_backoff(fail_auth, max_retries=3)

    def test_custom_is_retryable(self) -> None:
        calls = [0]

        def sometimes():
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("retryable")
            return "done"

        def is_val(val: BaseException) -> bool:
            return isinstance(val, ValueError)

        with patch("services.shared.state.time.sleep"):
            result = retry_with_backoff(
                sometimes, max_retries=3, is_retryable=is_val
            )
        assert result == "done"

    def test_backoff_starts_at_initial(self) -> None:
        sleeps: list = []
        call_count = [0]

        def record_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        def always_conn_fail():
            call_count[0] += 1
            raise ConnectionError("timeout")

        with patch("services.shared.state.time.sleep", side_effect=record_sleep):
            with pytest.raises(OfflineRetryExhausted):
                retry_with_backoff(
                    always_conn_fail,
                    max_retries=4,
                    initial_backoff=1.0,
                    multiplier=2.0,
                    max_backoff=60.0,
                )

        assert sleeps[0] == 1.0
        assert sleeps[1] == 2.0
        assert sleeps[2] == 4.0
        assert sleeps[3] == 8.0

    def test_backoff_caps_at_max(self) -> None:
        sleeps: list = []

        def record_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        def always_fail():
            raise ConnectionError("timeout")

        with patch("services.shared.state.time.sleep", side_effect=record_sleep):
            with pytest.raises(OfflineRetryExhausted):
                retry_with_backoff(
                    always_fail,
                    max_retries=7,
                    initial_backoff=1.0,
                    multiplier=2.0,
                    max_backoff=10.0,
                )

        assert max(sleeps) <= 10.0
        assert sleeps[-1] == 10.0

    def test_default_backoff_sequence_1_2_4(self) -> None:
        """The spec says: 1s, 2s, 4s, … cap 60s."""
        sleeps: list = []

        def record_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        def always_fail():
            raise ConnectionError("down")

        with patch("services.shared.state.time.sleep", side_effect=record_sleep):
            with pytest.raises(OfflineRetryExhausted):
                retry_with_backoff(always_fail, max_retries=3)

        assert sleeps[0] == 1.0
        assert sleeps[1] == 2.0
        assert sleeps[2] == 4.0


# ---------------------------------------------------------------------------
# file_sha256
# ---------------------------------------------------------------------------


class TestFileSha256:
    def test_computes_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        h = file_sha256(f)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("aaa", encoding="utf-8")
        f2.write_text("bbb", encoding="utf-8")
        assert file_sha256(f1) != file_sha256(f2)


# ---------------------------------------------------------------------------
# load_config / save_config
# ---------------------------------------------------------------------------


class TestLoadSaveConfig:
    def test_load_returns_empty_dict_when_missing(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"UPHEAL_DATA_DIR": str(tmp_path)}):
            cfg = load_config()
        assert cfg == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        with patch.dict(os.environ, {"UPHEAL_DATA_DIR": str(tmp_path)}):
            save_config({"last_ingestion": "2026-05-01T00:00:00Z", "count": 42})
            cfg = load_config()
        assert cfg["last_ingestion"] == "2026-05-01T00:00:00Z"
        assert cfg["count"] == 42

    def test_save_creates_parent_dir(self, tmp_path: Path) -> None:
        custom = tmp_path / "deep" / "nested"
        with patch.dict(os.environ, {"UPHEAL_DATA_DIR": str(custom)}):
            save_config({"key": "val"})
        assert (custom / "config.json").exists()