from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def default_format_chunk_metadata(chunk_text: str) -> Dict[str, Any]:
    """
    Safe default formatter when no LLM is configured yet.

    Returns values compatible with the architect's reranking/scoring pipeline.
    """
    text = chunk_text.lower()
    clinical_tags = []
    if any(k in text for k in ["anxiety", "panic", "worry", "gad"]):
        clinical_tags.append("anxiety")
    if any(k in text for k in ["depression", "sadness", "phq", "hopeless"]):
        clinical_tags.append("depression")
    if any(k in text for k in ["sleep", "insomnia"]):
        clinical_tags.append("sleep")
        
    tag_primary = clinical_tags[0] if clinical_tags else "general"
    if not clinical_tags:
        clinical_tags = ["general"]

    return {
        "tag_primary": tag_primary,
        "clinical_tags": ", ".join(clinical_tags),
        "difficulty": 3,
        "xp_reward": 10,
    }


def difficulty_to_int(difficulty: Any) -> int:
    """Map formatter difficulty (str or int) to 1..5 for Chroma metadata."""
    if isinstance(difficulty, int):
        return max(1, min(5, difficulty))
    s = str(difficulty).lower().strip()
    if s in ("low", "easy"):
        return 2
    if s in ("high", "hard"):
        return 4
    if s in ("medium", "moderate", "med"):
        return 3
    return 3


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

