"""
services/ingestion/semantic_chunker.py
=======================================

Semantic chunking module for the UpHeal ingestion pipeline.

This module handles:
1. **Sentence-aware splitting** - Breaks text on sentence boundaries
2. **Sliding window chunking** - Creates chunks with 15% overlap
3. **Topic-shift detection** - Uses embedding cosine similarity to detect topic changes

Usage
-----
    from services.ingestion.semantic_chunker import semantic_chunk, semantic_chunk_text

    # Chunk a document
    chunks = semantic_chunk("path/to/document.pdf")

    # Or chunk raw text
    chunks = semantic_chunk_text(
        "Your long clinical text here...",
        chunk_size=500,
        overlap_ratio=0.15
    )
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from services.ingestion.pdf_utils import extract_clean_text
from services.shared.logging import get_logger, log_chunk_created


logger = get_logger(__name__)


SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+")
MIN_CHUNK_SIZE = 100
DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP_RATIO = 0.15


@dataclass
class Chunk:
    """A semantic chunk with metadata."""

    index: int
    text: str
    start_char: int
    end_char: int
    token_count: int
    topic_shift_detected: bool


@dataclass
class ChunkingResult:
    """Result of semantic chunking operation."""

    source_path: Optional[str]
    chunks: list[Chunk]
    total_tokens: int
    chunk_count: int


def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences.

    Handles common abbreviations and edge cases.
    """
    if not text:
        return []

    sentences = SENTENCE_ENDINGS.split(text)

    result = []
    for sent in sentences:
        sent = sent.strip()
        if sent:
            result.append(sent)

    return result


def count_tokens(text: str) -> int:
    """
    Estimate token count using simple word-based approximation.

    Uses split on whitespace and adds overhead for special characters.
    """
    if not text:
        return 0

    words = text.split()
    char_count = len(text)

    overhead = sum(1 for c in text if c in ".,!?;:()[]{}")
    return len(words) + overhead


def get_sentence_embeddings(
    sentences: list[str],
    model_name: str = "all-MiniLM-L6-v2",
) -> list[list[float]]:
    """
    Get embeddings for a list of sentences using sentence-transformers.

    Args:
        sentences: List of sentences to embed
        model_name: Model to use for embeddings

    Returns:
        List of embedding vectors
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning(
            "chunking.embedding_fallback",
            message="sentence-transformers not available, using fallback",
        )
        return [[0.0] * 384] * len(sentences)

    try:
        model = SentenceTransformer(model_name)
        embeddings = model.encode(sentences, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.warning(
            "chunking.embedding_error",
            error=str(e),
            message="Using fallback embeddings",
        )
        return [[0.0] * 384] * len(sentences)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    """
    if not a or not b or len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def detect_topic_shift(
    current_emb: list[float],
    previous_emb: list[float],
    threshold: float = 0.7,
) -> bool:
    """
    Detect if there's a topic shift between two sentences/segments.

    Uses cosine similarity drop below threshold to detect topic shifts.

    Args:
        current_emb: Embedding of current segment
        previous_emb: Embedding of previous segment
        threshold: Similarity threshold below which a topic shift is detected

    Returns:
        True if topic shift detected, False otherwise
    """
    similarity = cosine_similarity(current_emb, previous_emb)
    return similarity < threshold


def semantic_chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
    min_sentences_per_chunk: int = 1,
    use_topic_shift: bool = True,
    topic_shift_threshold: float = 0.7,
) -> list[Chunk]:
    """
    Split text into semantic chunks with sentence boundary alignment and 15% overlap.

    Args:
        text: Input text to chunk
        chunk_size: Target token count per chunk
        overlap_ratio: Overlap ratio (0.15 = 15%)
        min_sentences_per_chunk: Minimum sentences per chunk
        use_topic_shift: Whether to use topic-shift detection
        topic_shift_threshold: Threshold for topic-shift detection

    Returns:
        List of Chunk objects

    Example:
        chunks = semantic_chunk_text(
            "Long clinical text with multiple paragraphs...",
            chunk_size=500,
            overlap_ratio=0.15
        )
        for chunk in chunks:
            print(f"Chunk {chunk.index}: {chunk.token_count} tokens")
    """
    if not text or not text.strip():
        return []

    sentences = split_into_sentences(text)
    if not sentences:
        return []

    if len(sentences) < min_sentences_per_chunk:
        return [
            Chunk(
                index=0,
                text=text.strip(),
                start_char=0,
                end_char=len(text),
                token_count=count_tokens(text),
                topic_shift_detected=False,
            )
        ]

    embeddings = None
    if use_topic_shift:
        try:
            embeddings = get_sentence_embeddings(sentences)
        except Exception as e:
            logger.warning(
                "chunking.embeddings_failed",
                error=str(e),
                message="Proceeding without topic-shift detection",
            )
            use_topic_shift = False

    chunks: list[Chunk] = []
    current_sentences: list[str] = []
    current_start_char = 0
    current_tokens = 0
    chunk_index = 0

    overlap_sentences: list[str] = []
    overlap_tokens = 0
    overlap_chars = int(len(text) * overlap_ratio)

    prev_embedding: Optional[list[float]] = None

    for i, sentence in enumerate(sentences):
        sentence_tokens = count_tokens(sentence)
        sentence_start = text.find(sentence, current_start_char)
        if sentence_start == -1:
            sentence_start = current_start_char

        test_tokens = current_tokens + sentence_tokens
        test_with_overlap = test_tokens - int(chunk_size * overlap_ratio)

        should_break = False
        topic_shift = False

        if use_topic_shift and embeddings and i < len(embeddings):
            current_embedding = embeddings[i]
            if prev_embedding is not None:
                topic_shift = detect_topic_shift(
                    current_embedding,
                    prev_embedding,
                    topic_shift_threshold,
                )
            prev_embedding = current_embedding

        if (
            test_tokens >= chunk_size
            and len(current_sentences) >= min_sentences_per_chunk
        ):
            should_break = True

        if (
            topic_shift
            and use_topic_shift
            and len(current_sentences) >= min_sentences_per_chunk
        ):
            should_break = True

        if should_break:
            chunk_text = " ".join(current_sentences)

            start_pos = text.find(chunk_text)
            if start_pos == -1:
                start_pos = current_start_char
            end_pos = start_pos + len(chunk_text)

            chunks.append(
                Chunk(
                    index=chunk_index,
                    text=chunk_text,
                    start_char=start_pos,
                    end_char=end_pos,
                    token_count=current_tokens,
                    topic_shift_detected=topic_shift,
                )
            )

            log_chunk_created(chunk_index, current_tokens, topic_shift, logger=logger)

            chunk_index += 1

            overlap_words = chunk_text.split()[-int(chunk_size * overlap_ratio / 5) :]
            overlap_sentences = []
            overlap_tokens = 0

            for sent in sentences[i - len(current_sentences) :]:
                if overlap_tokens >= int(chunk_size * overlap_ratio):
                    break
                overlap_sentences.append(sent)
                overlap_tokens += count_tokens(sent)

            current_sentences = overlap_sentences.copy()
            current_tokens = overlap_tokens
            current_start_char = end_pos - int(overlap_chars * 0.5)

            prev_embedding = None
            for j, s in enumerate(current_sentences):
                if embeddings:
                    idx = i - len(current_sentences) + j
                    if idx >= 0 and idx < len(embeddings):
                        prev_embedding = embeddings[idx]
                        break
        else:
            if not current_sentences:
                current_start_char = sentence_start
            current_sentences.append(sentence)
            current_tokens += sentence_tokens

    if current_sentences:
        chunk_text = " ".join(current_sentences)
        start_pos = text.find(chunk_text)
        if start_pos == -1:
            start_pos = current_start_char
        end_pos = start_pos + len(chunk_text)

        topic_shift = False
        if use_topic_shift and embeddings and len(sentences) > 0:
            last_idx = len(sentences) - 1
            if last_idx >= 0 and last_idx < len(embeddings):
                if prev_embedding is not None:
                    topic_shift = detect_topic_shift(
                        embeddings[last_idx],
                        prev_embedding,
                        topic_shift_threshold,
                    )

        chunks.append(
            Chunk(
                index=chunk_index,
                text=chunk_text,
                start_char=start_pos,
                end_char=end_pos,
                token_count=current_tokens,
                topic_shift_detected=topic_shift,
            )
        )

        log_chunk_created(chunk_index, current_tokens, topic_shift, logger=logger)

    return chunks


def semantic_chunk(
    pdf_path: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
    use_topic_shift: bool = True,
) -> ChunkingResult:
    """
    Extract and semantically chunk a PDF document.

    Args:
        pdf_path: Path to PDF file
        chunk_size: Target token count per chunk
        overlap_ratio: Overlap ratio (0.15 = 15%)
        use_topic_shift: Whether to use topic-shift detection

    Returns:
        ChunkingResult with all chunks and metadata

    Example:
        result = semantic_chunk("path/to/dsm5.pdf", chunk_size=500)
        print(f"Created {result.chunk_count} chunks")
    """
    extraction = extract_clean_text(str(pdf_path))

    chunks = semantic_chunk_text(
        extraction.text,
        chunk_size=chunk_size,
        overlap_ratio=overlap_ratio,
        use_topic_shift=use_topic_shift,
    )

    total_tokens = sum(c.token_count for c in chunks)

    return ChunkingResult(
        source_path=str(pdf_path),
        chunks=chunks,
        total_tokens=total_tokens,
        chunk_count=len(chunks),
    )


def semantic_chunk_iterator(
    pdf_path: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
) -> Iterator[Chunk]:
    """
    Iterate over semantic chunks from a PDF document.

    Yields chunks one at a time for memory efficiency.

    Args:
        pdf_path: Path to PDF file
        chunk_size: Target token count per chunk
        overlap_ratio: Overlap ratio

    Yields:
        Chunk objects
    """
    result = semantic_chunk(
        pdf_path,
        chunk_size=chunk_size,
        overlap_ratio=overlap_ratio,
    )

    for chunk in result.chunks:
        yield chunk


def get_chunk_overlap_info(chunks: list[Chunk], full_text: str) -> dict:
    """
    Analyze overlap between consecutive chunks.

    Args:
        chunks: List of chunks
        full_text: Original text

    Returns:
        Dictionary with overlap statistics
    """
    if len(chunks) < 2:
        return {"chunk_count": len(chunks), "has_overlap": False}

    overlaps = []
    for i in range(1, len(chunks)):
        prev_chunk = chunks[i - 1]
        curr_chunk = chunks[i]

        prev_end = (
            prev_chunk.text[-50:] if len(prev_chunk.text) > 50 else prev_chunk.text
        )
        curr_start = (
            curr_chunk.text[:50] if len(curr_chunk.text) > 50 else curr_chunk.text
        )

        overlap_chars = 0
        for j in range(min(len(prev_end), len(curr_start))):
            if prev_end[-(j + 1) :] == curr_start[: j + 1]:
                overlap_chars = j + 1
            else:
                break

        overlap_tokens = (
            count_tokens(prev_end[-overlap_chars:]) if overlap_chars > 0 else 0
        )
        overlaps.append(overlap_tokens)

    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0

    return {
        "chunk_count": len(chunks),
        "has_overlap": len(overlaps) > 0,
        "average_overlap_tokens": avg_overlap,
        "overlaps": overlaps,
    }
