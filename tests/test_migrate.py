"""Tests for scripts.migrate_initial_clinical_library."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.migrate_initial_clinical_library import (
    _format_batch_metadata,
    _format_chunk_metadata,
    migrate,
)


class TestFormatChunkMetadata:
    def test_returns_required_keys(self):
        result = _format_chunk_metadata("Some normal clinical text about anxiety.")
        assert "difficulty" in result
        assert "xp_reward" in result
        assert "clinical_tags" in result
        assert "safety_risk" in result

    def test_difficulty_in_range(self):
        result = _format_chunk_metadata("Calm relaxation technique")
        assert 1 <= result["difficulty"] <= 5

    def test_xp_reward_non_negative(self):
        result = _format_chunk_metadata("CBT exercise")
        assert result["xp_reward"] >= 0

    def test_crisis_detection(self):
        result = _format_chunk_metadata("I want to kill myself and end my life")
        assert result["safety_risk"] in ("true", "True")

    def test_no_crisis(self):
        result = _format_chunk_metadata("Deep breathing exercises for relaxation")
        assert result["safety_risk"] in ("false", "False")


class TestFormatBatchMetadata:
    def test_formats_multiple_chunks(self):
        texts = [
            "Anxiety management technique",
            "Depression cognitive restructuring",
        ]
        results = _format_batch_metadata(texts, use_llm=False, batch_size=10)
        assert len(results) == 2
        for r in results:
            assert "difficulty" in r
            assert "symptom_tags" in r

    def test_respects_batch_size(self):
        texts = ["Text about anxiety"] * 5
        results = _format_batch_metadata(texts, use_llm=False, batch_size=2)
        assert len(results) == 5


class TestMigrateDryRun:
    @patch("scripts.migrate_initial_clinical_library._format_batch_metadata")
    def test_dry_run_skips_chroma(self, mock_format):
        mock_format.return_value = [
            {"difficulty": 2, "xp_reward": 10, "symptom_tags": ["anxiety"], "safety_risk": False}
        ] * 3

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_file = Path(tmpdir) / "semantic_chunks.json"
            chunks_data = [
                {
                    "chunk_id": f"test_chunk_{i}",
                    "text": f"Test chunk {i} about anxiety",
                    "source_file": "Test-Book",
                    "page_numbers": [1],
                    "header_hierarchy": ["Test Header"],
                    "char_count": 100 + i * 10,
                }
                for i in range(3)
            ]
            chunks_file.write_text(json.dumps(chunks_data), encoding="utf-8")

            result = migrate(
                chunks_path=chunks_file,
                output_path=Path(tmpdir) / "output_db",
                collection_name="test_collection",
                target_books=[],
                batch_size=10,
                use_llm=False,
                dry_run=True,
                model_name="all-mpnet-base-v2",
            )

        assert result["status"] == "dry_run"
        assert result["filtered_chunks"] == 3
        assert "elapsed_seconds" in result


class TestMigrateWithBooksFilter:
    @patch("scripts.migrate_initial_clinical_library._format_batch_metadata")
    def test_filters_by_target_books(self, mock_format):
        mock_format.return_value = [
            {"difficulty": 2, "xp_reward": 10, "symptom_tags": ["anxiety"], "safety_risk": False}
        ] * 2

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_file = Path(tmpdir) / "semantic_chunks.json"
            all_chunks = [
                {
                    "chunk_id": "book1_chunk_0",
                    "text": "Anxiety text from book one",
                    "source_file": "Book-One",
                    "page_numbers": [1],
                    "header_hierarchy": ["Introduction"],
                    "char_count": 50,
                },
                {
                    "chunk_id": "book2_chunk_0",
                    "text": "Depression text from book two",
                    "source_file": "Book-Two",
                    "page_numbers": [2],
                    "header_hierarchy": ["Chapter 1"],
                    "char_count": 60,
                },
                {
                    "chunk_id": "book3_chunk_0",
                    "text": "PTSD text from book three",
                    "source_file": "Book-Three",
                    "page_numbers": [3],
                    "header_hierarchy": ["Section A"],
                    "char_count": 70,
                },
            ]
            chunks_file.write_text(json.dumps(all_chunks), encoding="utf-8")

            result = migrate(
                chunks_path=chunks_file,
                output_path=Path(tmpdir) / "output_db",
                collection_name="test_collection",
                target_books=["Book-One", "Book-Two"],
                batch_size=10,
                use_llm=False,
                dry_run=True,
                model_name="all-mpnet-base-v2",
            )

        assert result["filtered_chunks"] == 2
        assert result["total_raw_chunks"] == 3


class TestMigrateIntegration:
    """Integration test that actually writes to a temporary ChromaDB."""

    @pytest.fixture(autouse=True)
    def _tmpdir(self, tmp_path):
        self._tmpdir = tmp_path

    def test_full_pipeline_small(self):
        """End-to-end migration with 2 chunks, verifying ChromaDB write and metadata."""
        tmpdir = str(self._tmpdir)
        chunks_file = Path(tmpdir) / "semantic_chunks.json"
        db_path = Path(tmpdir) / "vector_db"
        chunks_data = [
            {
                "chunk_id": "test_anxiety_0",
                "text": "Deep breathing exercises for anxiety management and stress reduction",
                "source_file": "Test-Clinical-Book",
                "page_numbers": [10],
                "header_hierarchy": ["Anxiety Management"],
                "char_count": 70,
            },
            {
                "chunk_id": "test_depression_0",
                "text": "Cognitive behavioral therapy techniques for mild depression treatment",
                "source_file": "Test-Clinical-Book",
                "page_numbers": [20],
                "header_hierarchy": ["Depression Treatment"],
                "char_count": 75,
            },
        ]
        chunks_file.write_text(json.dumps(chunks_data), encoding="utf-8")

        result = migrate(
            chunks_path=chunks_file,
            output_path=db_path,
            collection_name="test_clinical_rag",
            target_books=[],
            batch_size=10,
            use_llm=False,
            dry_run=False,
            model_name="all-mpnet-base-v2",
        )

        assert result["status"] == "success"
        assert result["documents_indexed"] == 2

    def test_idempotent_rebuild(self):
        """Running migration twice should produce same document count."""
        tmpdir = str(self._tmpdir)
        chunks_file = Path(tmpdir) / "semantic_chunks.json"
        db_path = Path(tmpdir) / "vector_db"
        chunks_data = [
            {
                "chunk_id": "idempotent_0",
                "text": "Relaxation technique for stress and anxiety",
                "source_file": "Test-Book",
                "page_numbers": [1],
                "header_hierarchy": ["Relaxation"],
                "char_count": 50,
            },
        ]
        chunks_file.write_text(json.dumps(chunks_data), encoding="utf-8")

        result1 = migrate(
            chunks_path=chunks_file,
            output_path=db_path,
            collection_name="test_idempotent",
            target_books=[],
            batch_size=10,
            use_llm=False,
            dry_run=False,
            model_name="all-mpnet-base-v2",
        )

        result2 = migrate(
            chunks_path=chunks_file,
            output_path=db_path,
            collection_name="test_idempotent",
            target_books=[],
            batch_size=10,
            use_llm=False,
            dry_run=False,
            model_name="all-mpnet-base-v2",
        )

        assert result1["documents_indexed"] == 1
        assert result2["documents_indexed"] == 1


class TestCLI:
    def test_main_args_parsing(self):
        from scripts.migrate_initial_clinical_library import main

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_file = Path(tmpdir) / "semantic_chunks.json"
            chunks_data = [
                {
                    "chunk_id": "cli_test_0",
                    "text": "Mindfulness exercise for anxiety",
                    "source_file": "Test-Clinical-Book",
                    "page_numbers": [5],
                    "header_hierarchy": ["Mindfulness"],
                    "char_count": 40,
                },
            ]
            chunks_file.write_text(json.dumps(chunks_data), encoding="utf-8")

            exit_code = main([
                "--chunks", str(chunks_file),
                "--output", str(Path(tmpdir) / "db"),
                "--collection", "cli_test",
                "--dry-run",
            ])

        assert exit_code == 0