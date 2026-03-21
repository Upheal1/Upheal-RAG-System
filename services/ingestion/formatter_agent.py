from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def default_format_chunk_metadata(chunk_text: str) -> Dict[str, Any]:
    """
    Safe default formatter when no LLM is configured yet.

    Returns values compatible with the architect's reranking/scoring pipeline.
    """
    text = chunk_text.lower()
    clinical_tags = []
    if "anxiety" in text:
        clinical_tags.append("anxiety")
    if "depression" in text:
        clinical_tags.append("depression")
    if not clinical_tags:
        clinical_tags = ["general"]

    return {
        "xp_reward": 0,
        "difficulty": "medium",
        "clinical_tags": clinical_tags,
    }


def format_chunk_metadata(
    chunk_text: str,
    formatter: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Pluggable formatter-agent interface.

    `formatter` is expected to be a pure function:
        chunk_text -> {xp_reward, difficulty, clinical_tags}
    """
    fn = formatter or default_format_chunk_metadata
    return fn(chunk_text)

