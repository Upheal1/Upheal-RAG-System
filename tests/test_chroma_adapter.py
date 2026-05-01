import pytest
from unittest.mock import MagicMock, patch

from services.knowledge_base.chroma_adapter import (
    ChromaKnowledgeBase,
    _build_where_filter,
    _build_where_document_filter,
    _safety_risk_from_metadata,
    _utility_score_from_metadata,
    DIGITAL_DETOX_TAGS,
)
from services.shared.schemas import RetrievalQuery, UserContext


@pytest.fixture
def mock_kb():
    with patch.object(ChromaKnowledgeBase, "_ensure_loaded"):
        kb = ChromaKnowledgeBase()
        mock_model = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_model.encode.return_value = mock_embedding

        mock_col = MagicMock()
        kb._model = mock_model
        kb._collection = mock_col
        yield kb


class TestBuildWhereFilter:
    def test_tag_filter_from_anxiety_form_score(self):
        ctx = UserContext(
            user_id="1", timestamp="now", form_scores={"anxiety": 70, "depression": 30}
        )
        query = RetrievalQuery(query_text="anxiety exercises")
        w = _build_where_filter(ctx, query)
        assert w == {
            "$or": [
                {"tag_primary": "anxiety"},
                {"tag_primary": "depression"},
                {"tag_primary": "general"},
            ]
        }

    def test_dual_tag_filter(self):
        ctx = UserContext(
            user_id="1", timestamp="now", form_scores={"anxiety": 70, "depression": 80}
        )
        query = RetrievalQuery(query_text="anxiety depression")
        w = _build_where_filter(ctx, query)
        assert w == {
            "$or": [
                {"tag_primary": "anxiety"},
                {"tag_primary": "depression"},
                {"tag_primary": "general"},
            ]
        }

    def test_suicidal_omitted_from_filter(self):
        ctx = UserContext(
            user_id="1", timestamp="now", form_scores={"suicidal": 100, "anxiety": 50}
        )
        query = RetrievalQuery(query_text="anxiety")
        w = _build_where_filter(ctx, query)
        assert "suicidal" not in str(w)
        assert w == {
            "$or": [
                {"tag_primary": "anxiety"},
                {"tag_primary": "general"},
            ]
        }

    def test_max_difficulty_filter(self):
        ctx = UserContext(user_id="1", timestamp="now", form_scores={"anxiety": 50})
        query = RetrievalQuery(query_text="anxiety", max_difficulty=2)
        w = _build_where_filter(ctx, query)
        assert w == {
            "$and": [
                {"$or": [{"tag_primary": "anxiety"}, {"tag_primary": "general"}]},
                {"difficulty": {"$lte": 2}},
            ]
        }

    def test_combined_tag_and_difficulty_filter(self):
        ctx = UserContext(user_id="1", timestamp="now", form_scores={"anxiety": 70})
        query = RetrievalQuery(query_text="anxiety", max_difficulty=3)
        w = _build_where_filter(ctx, query)
        assert "tag_primary" in str(w)
        assert "difficulty" in str(w)

    def test_none_when_only_suicidal_and_general(self):
        ctx = UserContext(
            user_id="1", timestamp="now", form_scores={"suicidal": 50, "general": 20}
        )
        query = RetrievalQuery(query_text="wellness")
        assert _build_where_filter(ctx, query) is None

    def test_empty_form_scores_returns_none(self):
        ctx = UserContext(user_id="1", timestamp="now", form_scores={})
        query = RetrievalQuery(query_text="wellness")
        assert _build_where_filter(ctx, query) is None


class TestBuildWhereDocumentFilter:
    def test_none_when_query_text_empty(self):
        assert _build_where_document_filter("") is None
        assert _build_where_document_filter("ab") is None

    def test_contains_first_long_term(self):
        w = _build_where_document_filter("anxiety breathing exercise relaxation")
        assert w == {"$contains": "anxiety"}

    def test_lowercase_contains(self):
        w = _build_where_document_filter("ANXIETY")
        assert w == {"$contains": "anxiety"}


class TestSafetyRiskFromMetadata:
    def test_bool_true(self):
        assert _safety_risk_from_metadata({"safety_risk": True}) is True

    def test_string_true(self):
        assert _safety_risk_from_metadata({"safety_risk": "True"}) is True
        assert _safety_risk_from_metadata({"safety_risk": "true"}) is True
        assert _safety_risk_from_metadata({"safety_risk": "1"}) is True
        assert _safety_risk_from_metadata({"safety_risk": "yes"}) is True

    def test_bool_false(self):
        assert _safety_risk_from_metadata({"safety_risk": False}) is False

    def test_missing_defaults_false(self):
        assert _safety_risk_from_metadata({}) is False


class TestUtilityScoreFromMetadata:
    def test_float_value(self):
        assert _utility_score_from_metadata({"utility_score": 0.85}) == 0.85

    def test_string_float(self):
        assert _utility_score_from_metadata({"utility_score": "0.7"}) == 0.7

    def test_missing_defaults_05(self):
        assert _utility_score_from_metadata({}) == 0.5


class TestDigitalDetoxBoost:
    def test_digital_detox_tags_constant_defined(self):
        assert "digital-detox" in DIGITAL_DETOX_TAGS
        assert "screen-time" in DIGITAL_DETOX_TAGS


class TestRetrieveTasks:
    def test_retrieve_tasks_with_retrieval_query(self, mock_kb: ChromaKnowledgeBase):
        mock_kb._collection.query.return_value = {
            "ids": [["kb_1", "kb_2", "kb_3"]],
            "documents": [
                [
                    "5-4-3-2-1 grounding technique",
                    "Progressive muscle relaxation",
                    "Cognitive restructuring for anxiety",
                ]
            ],
            "metadatas": [
                [
                    {
                        "tag_primary": "anxiety",
                        "difficulty": 2,
                        "clinical_tags": "anxiety, grounding",
                        "safety_risk": False,
                        "utility_score": 0.75,
                    },
                    {
                        "tag_primary": "anxiety",
                        "difficulty": 3,
                        "clinical_tags": "anxiety, stress",
                        "safety_risk": False,
                        "utility_score": 0.65,
                    },
                    {
                        "tag_primary": "anxiety",
                        "difficulty": 4,
                        "clinical_tags": "anxiety, cognitive",
                        "safety_risk": False,
                        "utility_score": 0.8,
                    },
                ]
            ],
            "distances": [[0.05, 0.15, 0.25]],
        }

        ctx = UserContext(user_id="1", timestamp="now", form_scores={"anxiety": 60})
        query = RetrievalQuery(query_text="anxiety exercises", max_difficulty=3)

        tasks = mock_kb.retrieve_tasks(query, ctx, top_k=3)

        assert len(tasks) == 3
        assert tasks[0].task_id == "kb_1"
        assert tasks[0].symptom_tags == ["anxiety", "grounding"]
        assert tasks[0].difficulty == 2
        assert tasks[0].safety_risk is False
        assert tasks[0].utility_score == 0.75
        assert "similarity" in tasks[0].metadata
        assert mock_kb._collection.query.called

    def test_retrieve_tasks_boost_digital_detox(self, mock_kb: ChromaKnowledgeBase):
        mock_kb._collection.query.return_value = {
            "ids": [["kb_1", "kb_2"]],
            "documents": [
                [
                    "Digital detox planning worksheet",
                    "Grounding breathing exercise",
                ]
            ],
            "metadatas": [
                [
                    {
                        "tag_primary": "general",
                        "difficulty": 2,
                        "clinical_tags": "digital-detox, screen-time",
                        "safety_risk": False,
                        "utility_score": 0.7,
                    },
                    {
                        "tag_primary": "anxiety",
                        "difficulty": 1,
                        "clinical_tags": "anxiety, grounding",
                        "safety_risk": False,
                        "utility_score": 0.65,
                    },
                ]
            ],
            "distances": [[0.1, 0.2]],
        }

        ctx = UserContext(user_id="1", timestamp="now", form_scores={"anxiety": 50})
        query = RetrievalQuery(
            query_text="anxiety digital detox",
            boost_digital_detox=True,
        )

        tasks = mock_kb.retrieve_tasks(query, ctx, top_k=5)

        detox_task = next(t for t in tasks if "digital-detox" in t.symptom_tags)
        grounding_task = next(t for t in tasks if "grounding" in t.symptom_tags)
        assert tasks.index(detox_task) < tasks.index(grounding_task)

    def test_retrieve_tasks_respects_top_k(self, mock_kb: ChromaKnowledgeBase):
        mock_kb._collection.query.return_value = {
            "ids": [[f"kb_{i}" for i in range(10)]],
            "documents": [[f"document {i}" for i in range(10)]],
            "metadatas": [[{"tag_primary": "general", "difficulty": 3, "clinical_tags": "general"} for _ in range(10)]],
            "distances": [[0.1] * 10],
        }

        ctx = UserContext(user_id="1", timestamp="now", form_scores={"general": 50})
        query = RetrievalQuery(query_text="wellness")

        for k in [1, 3, 7]:
            tasks = mock_kb.retrieve_tasks(query, ctx, top_k=k)
            assert len(tasks) <= k


class TestIsHealthy:
    def test_is_healthy_true(self, mock_kb: ChromaKnowledgeBase):
        mock_kb._collection.count.return_value = 10
        assert mock_kb.is_healthy() is True

    def test_is_healthy_false_on_exception(self, mock_kb: ChromaKnowledgeBase):
        mock_kb._collection.count.side_effect = Exception("DB Down")
        assert mock_kb.is_healthy() is False


class TestGetDocumentCount:
    def test_returns_count(self, mock_kb: ChromaKnowledgeBase):
        mock_kb._collection.count.return_value = 42
        assert mock_kb.get_document_count() == 42

    def test_returns_zero_on_exception(self, mock_kb: ChromaKnowledgeBase):
        mock_kb._collection.count.side_effect = Exception("DB Down")
        assert mock_kb.get_document_count() == 0


def test_hnsw_config_passed_to_collection_creation():
    kb = ChromaKnowledgeBase(
        vector_db_path="/tmp/test_db",
        collection_name="test_coll",
        hnsw_ef_search=64,
        hnsw_ef_construction=100,
        hnsw_m=8,
    )
    assert kb.hnsw_ef_search == 64
    assert kb.hnsw_ef_construction == 100
    assert kb.hnsw_m == 8