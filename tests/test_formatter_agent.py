import pytest
from services.ingestion.formatter_agent import (
    CRISIS_KEYWORDS,
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
    SYMPTOM_TAG_KEYWORDS,
    _detect_crisis_keywords,
    _difficulty_to_int,
    _extract_symptom_tags,
    _format_chunk_fallback,
    _get_llm_provider,
    _xp_reward_from_difficulty,
    format_chunk,
    format_chunk_metadata,
    format_chunks_batch,
    to_clinical_task,
)


class TestCrisisKeywordDetection:
    def test_suicide_keyword(self):
        assert _detect_crisis_keywords("I want to kill myself") is True
        assert _detect_crisis_keywords("suicidal thoughts") is True

    def test_self_harm_keyword(self):
        assert _detect_crisis_keywords("I want to self-harm") is True
        assert _detect_crisis_keywords("cut myself") is True

    def test_no_crisis(self):
        assert _detect_crisis_keywords("I feel anxious today") is False
        assert _detect_crisis_keywords("sleep problems") is False

    def test_case_insensitive(self):
        assert _detect_crisis_keywords("SUICIDE") is True
        assert _detect_crisis_keywords("Self-Harm") is True


class TestSymptomTagExtraction:
    def test_anxiety_tag(self):
        tags = _extract_symptom_tags("I feel very anxious and nervous")
        assert "anxiety" in tags

    def test_depression_tag(self):
        tags = _extract_symptom_tags("Feeling hopeless and depressed")
        assert "depression" in tags

    def test_sleep_tag(self):
        tags = _extract_symptom_tags("Insomnia and fatigue")
        assert "sleep" in tags

    def test_multiple_tags(self):
        tags = _extract_symptom_tags("Anxiety and depression symptoms")
        assert "anxiety" in tags
        assert "depression" in tags

    def test_general_fallback(self):
        tags = _extract_symptom_tags("Some random text without clinical terms")
        assert "general" in tags


class TestDifficultyMapping:
    def test_integer_input(self):
        assert _difficulty_to_int(3) == 3
        assert _difficulty_to_int(1) == 1
        assert _difficulty_to_int(5) == 5

    def test_clamp_out_of_range(self):
        assert _difficulty_to_int(10) == 5
        assert _difficulty_to_int(0) == 1

    def test_string_low(self):
        assert _difficulty_to_int("low") == 2
        assert _difficulty_to_int("easy") == 2

    def test_string_high(self):
        assert _difficulty_to_int("high") == 4
        assert _difficulty_to_int("hard") == 4

    def test_string_medium(self):
        assert _difficulty_to_int("medium") == 3
        assert _difficulty_to_int("moderate") == 3


class TestXpReward:
    def test_xp_mapping(self):
        assert _xp_reward_from_difficulty(1) == 5
        assert _xp_reward_from_difficulty(2) == 10
        assert _xp_reward_from_difficulty(3) == 15
        assert _xp_reward_from_difficulty(4) == 20
        assert _xp_reward_from_difficulty(5) == 30


class TestFormatChunk:
    def test_basic_format(self):
        result = format_chunk("I feel anxious today", use_llm=False)
        assert "difficulty" in result
        assert "xp_reward" in result
        assert "symptom_tags" in result
        assert "safety_risk" in result
        assert result["difficulty"] in [1, 2, 3, 4, 5]

    def test_crisis_sets_safety_risk(self):
        result = format_chunk("I want to kill myself", use_llm=False)
        assert result["safety_risk"] is True
        assert result["difficulty"] == 5

    def test_normal_chunk_safety_risk_false(self):
        result = format_chunk("Normal text about anxiety", use_llm=False)
        assert result["safety_risk"] is False


class TestFormatChunksBatch:
    def test_batch_processing(self):
        chunks = ["chunk1", "chunk2", "chunk3"]
        results = format_chunks_batch(chunks, use_llm=False)
        assert len(results) == 3

    def test_batch_size_limit(self):
        chunks = ["chunk"] * 50
        results = format_chunks_batch(chunks, max_batch_size=10, use_llm=False)
        assert len(results) == min(10, MAX_BATCH_SIZE)

    def test_max_batch_size_cap(self):
        chunks = ["chunk"] * 100
        results = format_chunks_batch(chunks, max_batch_size=1000, use_llm=False)
        assert len(results) == MAX_BATCH_SIZE


class TestLLMProvider:
    def test_no_provider_returns_none(self):
        provider = _get_llm_provider()
        assert provider in ["openai", "gemini", "none"]


class TestToClinicalTask:
    def test_creates_valid_clinical_task(self):
        task = to_clinical_task(
            chunk_text="I feel anxious",
            task_id="task_001",
            source_reference="test.pdf",
            use_llm=False,
        )
        assert task.task_id == "task_001"
        assert task.content == "I feel anxious"
        assert task.source_reference == "test.pdf"
        assert isinstance(task.symptom_tags, list)
        assert task.difficulty in [1, 2, 3, 4, 5]

    def test_clinical_task_with_crisis(self):
        task = to_clinical_task(
            chunk_text="I want to kill myself",
            task_id="task_crisis",
            source_reference="crisis.pdf",
            use_llm=False,
        )
        assert task.metadata["safety_risk"] is True
        assert task.difficulty == 5


class TestFormatChunkMetadata:
    def test_legacy_interface(self):
        def custom_formatter(text):
            return {"difficulty": 4, "xp_reward": 20, "symptom_tags": ["test"]}

        result = format_chunk_metadata("some text", formatter=custom_formatter)
        assert result["difficulty"] == 4

    def test_default_fallback(self):
        result = format_chunk_metadata("test text")
        assert "difficulty" in result
