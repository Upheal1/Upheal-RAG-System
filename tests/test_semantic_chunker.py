import pytest
from services.ingestion.semantic_chunker import (
    Chunk,
    ChunkingResult,
    cosine_similarity,
    count_tokens,
    detect_topic_shift,
    get_chunk_overlap_info,
    semantic_chunk_text,
    split_into_sentences,
)


class TestSplitIntoSentences:
    def test_basic_sentence_split(self):
        text = (
            "This is the first sentence. This is the second sentence. "
            "And here is the third!"
        )
        result = split_into_sentences(text)
        assert len(result) == 3
        assert result[0] == "This is the first sentence."
        assert result[1] == "This is the second sentence."
        assert result[2] == "And here is the third!"

    def test_empty_text(self):
        assert split_into_sentences("") == []
        assert split_into_sentences("   ") == []

    def test_question_marks(self):
        text = "Is this a question? Is this another one?"
        result = split_into_sentences(text)
        assert len(result) == 2

    def test_exclamation_points(self):
        text = "Wow! Amazing! Incredible!"
        result = split_into_sentences(text)
        assert len(result) == 3


class TestCountTokens:
    def test_basic_count(self):
        text = "This is a test sentence with some words."
        assert count_tokens(text) > 0

    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_special_characters(self):
        text = "Hello, world! How are you? Fine."
        tokens = count_tokens(text)
        assert tokens > len(text.split())

    def test_multiple_spaces(self):
        text = "Hello    world"
        tokens = count_tokens(text)
        assert tokens > 0


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0
        assert cosine_similarity([1, 2], [3]) == 0.0

    def test_similar_vectors(self):
        a = [1.0, 2.0, 3.0]
        b = [1.1, 2.1, 3.1]
        similarity = cosine_similarity(a, b)
        assert similarity > 0.9


class TestDetectTopicShift:
    def test_no_shift_high_similarity(self):
        similar_emb = [1.0, 0.0, 0.0]
        prev_emb = [0.95, 0.05, 0.0]
        assert detect_topic_shift(similar_emb, prev_emb, threshold=0.7) is False

    def test_shift_detected_low_similarity(self):
        current_emb = [1.0, 0.0, 0.0]
        different_emb = [0.0, 1.0, 0.0]
        assert detect_topic_shift(current_emb, different_emb, threshold=0.7) is True

    def test_custom_threshold(self):
        a = [1.0, 0.0]
        b = [0.8, 0.2]
        assert detect_topic_shift(a, b, threshold=0.99) is True
        assert detect_topic_shift(a, b, threshold=0.5) is False


class TestSemanticChunkText:
    def test_empty_text_returns_empty(self):
        result = semantic_chunk_text("")
        assert result == []

    def test_single_short_text(self):
        text = "This is a short text."
        result = semantic_chunk_text(text, chunk_size=100)
        assert len(result) == 1
        assert result[0].text == text.strip()

    def test_multiple_chunks_created(self):
        text = (
            "First sentence here. Second sentence goes here. "
            "Third sentence is longer and contains more words. "
            "Fourth sentence continues the text. Fifth sentence adds more content. "
            "Sixth sentence makes it even longer. Seventh sentence is important. "
            "Eighth sentence finishes the document."
        )
        chunks = semantic_chunk_text(
            text,
            chunk_size=15,
            overlap_ratio=0.15,
            use_topic_shift=False,
        )
        assert len(chunks) > 1

    def test_chunks_have_required_fields(self):
        text = "One. Two. Three. Four. Five."
        chunks = semantic_chunk_text(
            text,
            chunk_size=5,
            overlap_ratio=0.15,
            use_topic_shift=False,
        )
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.index >= 0
            assert chunk.text
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char
            assert chunk.token_count > 0

    def test_overlap_ratio(self):
        text = (
            "Sentence one here. Sentence two goes here. Sentence three continues. " * 10
        )
        chunks = semantic_chunk_text(
            text,
            chunk_size=10,
            overlap_ratio=0.15,
            use_topic_shift=False,
        )
        assert len(chunks) > 1
        overlap_info = get_chunk_overlap_info(chunks, text)
        assert overlap_info["has_overlap"] is True

    def test_custom_chunk_size(self):
        text = "A. B. C. D. E. F. G. H. I. J."
        small_chunks = semantic_chunk_text(text, chunk_size=2, overlap_ratio=0.0)
        large_chunks = semantic_chunk_text(text, chunk_size=50, overlap_ratio=0.0)
        assert len(small_chunks) >= len(large_chunks)

    def test_min_sentences_per_chunk(self):
        text = "Short. Another. Third. Fourth. Fifth."
        result = semantic_chunk_text(
            text,
            chunk_size=50,
            min_sentences_per_chunk=2,
            use_topic_shift=False,
        )
        assert len(result) >= 1

    def test_with_topic_shift_detection(self):
        text = (
            "This is about cardiology. "
            "The heart pumps blood throughout the body. "
            "It beats rhythmically. "
            "Now let us discuss neurology. "
            "The brain controls all body functions. "
            "Neurons transmit signals."
        )
        chunks = semantic_chunk_text(
            text,
            chunk_size=10,
            use_topic_shift=True,
            topic_shift_threshold=0.5,
        )
        assert len(chunks) > 0


class TestGetChunkOverlapInfo:
    def test_empty_chunks(self):
        result = get_chunk_overlap_info([], "some text")
        assert result["chunk_count"] == 0
        assert result["has_overlap"] is False

    def test_single_chunk(self):
        chunk = Chunk(
            index=0,
            text="Only one chunk here.",
            start_char=0,
            end_char=20,
            token_count=4,
            topic_shift_detected=False,
        )
        result = get_chunk_overlap_info([chunk], chunk.text)
        assert result["chunk_count"] == 1

    def test_multiple_chunks(self):
        chunks = [
            Chunk(
                index=0,
                text="First chunk content.",
                start_char=0,
                end_char=20,
                token_count=3,
                topic_shift_detected=False,
            ),
            Chunk(
                index=1,
                text="Second chunk content.",
                start_char=20,
                end_char=45,
                token_count=3,
                topic_shift_detected=False,
            ),
        ]
        result = get_chunk_overlap_info(
            chunks, "First chunk content. Second chunk content."
        )
        assert result["chunk_count"] == 2


class TestIntegration:
    def test_chunk_text_structure(self):
        text = (
            "The patient presents with chest pain. "
            "ECG shows ST elevation in leads V1-V4. "
            "Troponin levels are elevated. "
            "This suggests acute myocardial infarction. "
            "Patient has history of hypertension. "
            "Also has type 2 diabetes mellitus."
        )
        result = semantic_chunk_text(
            text,
            chunk_size=15,
            overlap_ratio=0.15,
            use_topic_shift=False,
        )
        assert isinstance(result, list)
        assert all(isinstance(c, Chunk) for c in result)

    def test_token_count_reasonable(self):
        text = "Word " * 100
        result = semantic_chunk_text(text, chunk_size=50, overlap_ratio=0.0)
        for chunk in result:
            assert chunk.token_count > 0
            assert chunk.token_count <= 200

    def test_preserve_order(self):
        text = "First. Second. Third. Fourth. Fifth."
        result = semantic_chunk_text(text, chunk_size=5, overlap_ratio=0.0)
        if len(result) > 1:
            assert result[0].text.startswith("First")
            assert "Second" in result[-1].text or "Third" in result[-1].text
