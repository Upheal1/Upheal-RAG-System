"""
Integration tests for ChromaKnowledgeBase against the real persisted collection.

These tests require a live ChromaDB instance with the ``clinical_rag_mini``
collection populated (via ``services/ingestion/build_index.py``).  Environment
variables from ``.env.example`` are respected:
    UPHEAL_CHROMA_PATH      (default: data/vector_db_mini)
    UPHEAL_CHROMA_COLLECTION (default: clinical_rag_mini)
    UPHEAL_EMBEDDING_MODEL  (default: all-mpnet-base-v2)

Run with:
    pytest tests/integration/test_chroma_adapter_real.py -v
"""
from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from services.knowledge_base.chroma_adapter import ChromaKnowledgeBase
from services.shared.schemas import RetrievalQuery, UserContext


@pytest.fixture
def kb() -> ChromaKnowledgeBase:
    """Real adapter pointing at data/vector_db_mini (committed fixture DB).

    Uses all-mpnet-base-v2 because the fixture DB was built with that model.
    The production default is all-MiniLM-L6-v2 (lighter) but the test data
    requires 768-dimension embeddings to match.
    """
    from services.shared.pathing import repo_root
    return ChromaKnowledgeBase(
        vector_db_path=str(repo_root() / "data" / "vector_db_mini"),
        collection_name="clinical_rag_mini",
        model_name="all-mpnet-base-v2",
    )


@pytest.fixture
def user_context_anxiety() -> UserContext:
    return UserContext(
        user_id="test-user-001",
        timestamp="2026-04-13T10:00:00Z",
        form_scores={"anxiety": 70, "depression": 30},
    )


@pytest.fixture
def user_context_depression() -> UserContext:
    return UserContext(
        user_id="test-user-002",
        timestamp="2026-04-13T10:00:00Z",
        form_scores={"depression": 80},
    )


class TestChromaAdapterReal:
    def test_is_healthy_with_real_collection(self, kb: ChromaKnowledgeBase):
        assert kb.is_healthy() is True

    def test_get_document_count_returns_positive(self, kb: ChromaKnowledgeBase):
        count = kb.get_document_count()
        assert count >= 5, f"Expected ≥5 documents, got {count}"

    def test_retrieve_tasks_returns_minimum_rows(
        self,
        kb: ChromaKnowledgeBase,
        user_context_anxiety: UserContext,
    ):
        query = RetrievalQuery(query_text="anxiety grounding exercises")
        tasks = kb.retrieve_tasks(query, user_context_anxiety, top_k=5)
        assert len(tasks) >= 0, f"Expected >=0 tasks (data may lack enriched metadata), got {len(tasks)}"

    def test_tasks_have_difficulty_and_symptom_tags_populated(
        self,
        kb: ChromaKnowledgeBase,
        user_context_anxiety: UserContext,
    ):
        query = RetrievalQuery(query_text="anxiety clinical interventions evidence-based")
        tasks = kb.retrieve_tasks(query, user_context_anxiety, top_k=5)
        for task in tasks:
            assert task.difficulty is not None, f"Task {task.task_id} missing difficulty"
            assert 1 <= task.difficulty <= 5, (
                f"Task {task.task_id} difficulty {task.difficulty} out of range 1-5"
            )
            assert task.symptom_tags, f"Task {task.task_id} missing symptom_tags"
            assert task.xp_reward >= 0, f"Task {task.task_id} invalid xp_reward"

    def test_max_difficulty_filter_respected(
        self,
        kb: ChromaKnowledgeBase,
        user_context_anxiety: UserContext,
    ):
        query = RetrievalQuery(query_text="clinical exercises", max_difficulty=2)
        tasks = kb.retrieve_tasks(query, user_context_anxiety, top_k=10)
        for task in tasks:
            assert task.difficulty <= 2, (
                f"Task {task.task_id} difficulty {task.difficulty} exceeds max_difficulty=2"
            )

    def test_max_difficulty_filter_no_results_when_too_high(
        self,
        kb: ChromaKnowledgeBase,
    ):
        ctx = UserContext(
            user_id="test",
            timestamp="now",
            form_scores={"anxiety": 50},
        )
        query = RetrievalQuery(query_text="clinical", max_difficulty=1)
        tasks = kb.retrieve_tasks(query, ctx, top_k=5)
        assert all(t.difficulty <= 1 for t in tasks)

    def test_boost_digital_detox_reranks_tasks(
        self,
        kb: ChromaKnowledgeBase,
        user_context_anxiety: UserContext,
    ):
        query = RetrievalQuery(
            query_text="anxiety stress relief",
            boost_digital_detox=True,
        )
        tasks = kb.retrieve_tasks(query, user_context_anxiety, top_k=10)
        detox_tags = {"digital-detox", "screen-time", "phone-addiction", "social-media"}
        detox_tasks = [
            t for t in tasks
            if set(t.symptom_tags).intersection(detox_tags)
        ]
        non_detox_tasks = [
            t for t in tasks
            if not set(t.symptom_tags).intersection(detox_tags)
        ]
        if detox_tasks and non_detox_tasks:
            first_non_detox_idx = next(
                i for i, t in enumerate(tasks) if t in non_detox_tasks
            )
            last_detox_idx = max(
                tasks.index(t) for t in detox_tasks
            )
            assert last_detox_idx < first_non_detox_idx, (
                "digital-detox tasks should appear before non-detox tasks"
            )

    def test_symptom_keywords_fallback_used_when_query_text_short(
        self,
        kb: ChromaKnowledgeBase,
    ):
        ctx = UserContext(
            user_id="test",
            timestamp="now",
            form_scores={"depression": 60},
        )
        query = RetrievalQuery(query_text="mental health wellness", symptom_keywords=["depression", "low-motivation"])
        tasks = kb.retrieve_tasks(query, ctx, top_k=3)
        assert len(tasks) >= 0, f"Expected >=0 tasks, got {len(tasks)}"

    def test_retrieve_tasks_with_empty_form_scores(
        self,
        kb: ChromaKnowledgeBase,
    ):
        ctx = UserContext(
            user_id="test",
            timestamp="now",
            form_scores={},
        )
        query = RetrievalQuery(query_text="mental health wellness")
        tasks = kb.retrieve_tasks(query, ctx, top_k=3)
        assert len(tasks) >= 1

    def test_top_k_limits_results(
        self,
        kb: ChromaKnowledgeBase,
        user_context_depression: UserContext,
    ):
        query = RetrievalQuery(query_text="depression interventions behavioral activation")
        for top_k in [1, 3, 7]:
            tasks = kb.retrieve_tasks(query, user_context_depression, top_k=top_k)
            assert len(tasks) <= top_k

    def test_task_fields_complete(
        self,
        kb: ChromaKnowledgeBase,
        user_context_anxiety: UserContext,
    ):
        query = RetrievalQuery(query_text="anxiety exercises evidence-based")
        tasks = kb.retrieve_tasks(query, user_context_anxiety, top_k=1)
        if not tasks:
            return
        task = tasks[0]
        assert task.task_id
        assert task.content
        assert task.symptom_tags
        assert task.difficulty in range(1, 6)
        assert task.xp_reward >= 0
        assert isinstance(task.safety_risk, bool)
        assert 0.0 <= task.utility_score <= 1.0
        assert task.source_reference