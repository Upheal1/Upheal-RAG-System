import pytest
from unittest.mock import MagicMock, patch

from scripts.verify_integrity import (
    MANDATORY_FIELDS,
    IntegrityReport,
    Violation,
    _check_metadata,
    _validate_field,
    main,
    scan_collection,
)


class TestValidateField:
    def test_difficulty_valid(self):
        assert _validate_field("difficulty", 3) is None
        assert _validate_field("difficulty", 1) is None
        assert _validate_field("difficulty", 5) is None

    def test_difficulty_out_of_range(self):
        assert "out of range" in _validate_field("difficulty", 0)
        assert "out of range" in _validate_field("difficulty", 6)

    def test_difficulty_not_int(self):
        assert "not an int" in _validate_field("difficulty", "high")
        assert "not an int" in _validate_field("difficulty", None)

    def test_xp_reward_valid(self):
        assert _validate_field("xp_reward", 0) is None
        assert _validate_field("xp_reward", 15) is None

    def test_xp_reward_negative(self):
        assert "negative" in _validate_field("xp_reward", -1)

    def test_xp_reward_not_int(self):
        assert "not an int" in _validate_field("xp_reward", "ten")

    def test_clinical_tags_valid(self):
        assert _validate_field("clinical_tags", "anxiety,depression") is None
        assert _validate_field("clinical_tags", "general") is None

    def test_clinical_tags_empty(self):
        assert "empty" in _validate_field("clinical_tags", "")
        assert "empty" in _validate_field("clinical_tags", "   ")

    def test_clinical_tags_none(self):
        assert "None" in _validate_field("clinical_tags", None)


class TestCheckMetadata:
    def test_valid_metadata(self):
        meta = {
            "difficulty": 2,
            "xp_reward": 10,
            "clinical_tags": "anxiety,grounding",
        }
        assert _check_metadata("task_1", meta) is None

    def test_missing_all_fields(self):
        v = _check_metadata("task_1", {})
        assert v is not None
        assert set(v.missing_fields) == set(MANDATORY_FIELDS)
        assert v.invalid_fields == []

    def test_missing_one_field(self):
        v = _check_metadata("task_1", {"difficulty": 2, "xp_reward": 10})
        assert v is not None
        assert v.missing_fields == ["clinical_tags"]

    def test_invalid_difficulty_and_xp(self):
        v = _check_metadata(
            "task_1",
            {"difficulty": 10, "xp_reward": -5, "clinical_tags": "anxiety"},
        )
        assert v is not None
        assert v.missing_fields == []
        assert len(v.invalid_fields) == 2
        assert any("difficulty" in f for f in v.invalid_fields)
        assert any("xp_reward" in f for f in v.invalid_fields)

    def test_none_metadata(self):
        v = _check_metadata("task_1", None)
        assert v is not None
        assert set(v.missing_fields) == set(MANDATORY_FIELDS)


class TestIntegrityReport:
    def test_is_clean_when_no_violations(self):
        r = IntegrityReport(collection_name="c", vector_db_path="/tmp/db")
        assert r.is_clean is True

    def test_is_clean_false_with_violations(self):
        r = IntegrityReport(
            collection_name="c",
            vector_db_path="/tmp/db",
            violations=[Violation(task_id="t1", missing_fields=["difficulty"])],
        )
        assert r.is_clean is False


class TestScanCollection:
    @patch("chromadb.PersistentClient")
    def test_scan_finds_violations(self, mock_persistent_client):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 3
        mock_collection.get.side_effect = [
            {
                "ids": ["t1", "t2", "t3"],
                "metadatas": [
                    {"difficulty": 2, "xp_reward": 10, "clinical_tags": "anxiety"},
                    {"difficulty": 2, "xp_reward": 10},  # missing clinical_tags
                    None,  # missing everything
                ],
            }
        ]
        mock_client.get_collection.return_value = mock_collection
        mock_persistent_client.return_value = mock_client

        report = scan_collection(vector_db_path="/tmp/db", collection_name="test")

        assert report.total_documents == 3
        assert len(report.violations) == 2
        assert report.violations[0].task_id == "t2"
        assert report.violations[1].task_id == "t3"

    @patch("chromadb.PersistentClient")
    def test_scan_clean_collection(self, mock_persistent_client):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.get.return_value = {
            "ids": ["t1", "t2"],
            "metadatas": [
                {"difficulty": 2, "xp_reward": 10, "clinical_tags": "anxiety"},
                {"difficulty": 3, "xp_reward": 15, "clinical_tags": "depression"},
            ],
        }
        mock_client.get_collection.return_value = mock_collection
        mock_persistent_client.return_value = mock_client

        report = scan_collection(vector_db_path="/tmp/db", collection_name="test")

        assert report.is_clean is True
        assert report.total_documents == 2

    @patch("chromadb.PersistentClient")
    def test_scan_paginates_large_collection(self, mock_persistent_client):
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 600
        # First batch
        batch1 = {
            "ids": [f"t{i}" for i in range(500)],
            "metadatas": [
                {"difficulty": 2, "xp_reward": 10, "clinical_tags": "anxiety"}
                for _ in range(500)
            ],
        }
        # Second batch
        batch2 = {
            "ids": [f"t{i}" for i in range(500, 600)],
            "metadatas": [
                {"difficulty": 2, "xp_reward": 10, "clinical_tags": "anxiety"}
                for _ in range(100)
            ],
        }
        mock_collection.get.side_effect = [batch1, batch2]
        mock_client.get_collection.return_value = mock_collection
        mock_persistent_client.return_value = mock_client

        report = scan_collection(vector_db_path="/tmp/db", collection_name="test")

        assert report.total_documents == 600
        assert report.is_clean is True
        assert mock_collection.get.call_count == 2


class TestMain:
    @patch("scripts.verify_integrity.scan_collection")
    def test_main_returns_zero_when_clean(self, mock_scan):
        mock_scan.return_value = IntegrityReport(
            collection_name="c", vector_db_path="/tmp/db", total_documents=5
        )
        assert main([]) == 0

    @patch("scripts.verify_integrity.scan_collection")
    def test_main_returns_one_when_violations(self, mock_scan):
        mock_scan.return_value = IntegrityReport(
            collection_name="c",
            vector_db_path="/tmp/db",
            total_documents=5,
            violations=[Violation(task_id="t1", missing_fields=["difficulty"])],
        )
        assert main([]) == 1

    @patch("scripts.verify_integrity.scan_collection")
    def test_main_passes_cli_args(self, mock_scan):
        mock_scan.return_value = IntegrityReport(
            collection_name="c", vector_db_path="/tmp/db"
        )
        main(["/custom/path", "custom_coll"])
        mock_scan.assert_called_once_with(
            vector_db_path="/custom/path", collection_name="custom_coll"
        )
