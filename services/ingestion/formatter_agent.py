"""
services/ingestion/formatter_agent.py
==============================

Formatter Agent for the UpHeal ingestion pipeline.

This module handles:
1. **LLM Integration** - OpenAI GPT or Google Gemini for intelligent chunk labeling
2. **Per-chunk metadata** - difficulty, xp_reward, symptom_tags, safety_risk
3. **ClinicalTask validation** - Output validates against schema
4. **Crisis detection** - Keywords trigger safety_risk = True
5. **Token/cost guard** - Batch size cap to control costs

Usage
-----
    from services.ingestion.formatter_agent import format_chunk, format_chunks_batch

    # Single chunk
    metadata = format_chunk("Your chunk text here...")

    # Batch with cost control
    results = format_chunks_batch(chunks, max_batch_size=10)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from services.shared.schemas import ClinicalTask


logger = None


def _get_logger():
    global logger
    if logger is None:
        from services.shared.logging import get_logger
        logger = get_logger(__name__)
    return logger


LLM_PROVIDER_OPENAI = "openai"
LLM_PROVIDER_GEMINI = "gemini"
LLM_PROVIDER_OLLAMA = "ollama"
LLM_PROVIDER_NONE = "none"

DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 25

CRISIS_KEYWORDS = [
    "suicide",
    "suicidal",
    "self-harm",
    "self harm",
    "kill myself",
    "end my life",
    "want to die",
    "harm myself",
    "cut myself",
    "overdose",
    "hang myself",
    "jump off",
    "walk into traffic",
    "kill me",
]

SYMPTOM_TAG_KEYWORDS = {
    "anxiety": ["anxiety", "panic", "worry", "gad", "nervous", "tense", "restless"],
    "depression": ["depression", "sadness", "phq", "hopeless", "empty", "worthless", "low mood"],
    "sleep": ["sleep", "insomnia", "fatigue", "tired", "exhausted", "sleep quality"],
    "ptsd": ["ptsd", "trauma", "flashback", "nightmare", "avoidance", "hypervigilance"],
    "ocd": ["ocd", "compulsion", "obsession", "ritual", "contamination"],
    "social": ["social", "shy", "introvert", "withdrawal", "avoid people"],
    "anger": ["anger", "irritability", "rage", "frustration"],
    "substance": ["substance", "alcohol", "drug", "addiction", "abuse"],
}


@dataclass
class FormatterResult:
    """Result of formatting a single chunk."""

    difficulty: int
    xp_reward: int
    symptom_tags: List[str]
    safety_risk: bool
    raw_response: Optional[str] = None


def _detect_crisis_keywords(text: str) -> bool:
    """Check if text contains crisis keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CRISIS_KEYWORDS)


def _extract_symptom_tags(text: str) -> List[str]:
    """Extract symptom tags from text using keyword matching."""
    text_lower = text.lower()
    found_tags = []

    for tag, keywords in SYMPTOM_TAG_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found_tags.append(tag)

    return found_tags if found_tags else ["general"]


def _difficulty_to_int(difficulty: Any) -> int:
    """Map formatter difficulty (str or int) to 1..5 for ClinicalTask."""
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


def _xp_reward_from_difficulty(difficulty: int) -> int:
    """Map difficulty (1-5) to XP reward."""
    xp_map = {1: 5, 2: 10, 3: 15, 4: 20, 5: 30}
    return xp_map.get(difficulty, 10)


def _get_llm_provider() -> str:
    """Determine which LLM provider to use based on environment."""
    if os.environ.get("OPENAI_API_KEY"):
        return LLM_PROVIDER_OPENAI
    if os.environ.get("GEMINI_API_KEY"):
        return LLM_PROVIDER_GEMINI
    if os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_MODEL"):
        return LLM_PROVIDER_OLLAMA
    return LLM_PROVIDER_NONE


def _call_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    """Call OpenAI API."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )
        return response.choices[0].message.content
    except ImportError:
        _get_logger().warning(
            "formatter.openai_not_installed",
            message="openai package not installed",
        )
        return ""
    except Exception as e:
        _get_logger().warning(
            "formatter.openai_error",
            error=str(e),
            message="OpenAI API call failed",
        )
        return ""


def _call_gemini(prompt: str, model: str = "gemini-2.0-flash") -> str:
    """Call Google Gemini API."""
    try:
        import google.genai as genai

        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config={"temperature": 0.3, "max_output_tokens": 200},
        )
        return response.text
    except ImportError:
        _get_logger().warning(
            "formatter.gemini_not_installed",
            message="google-genai package not installed",
        )
        return ""
    except Exception as e:
        _get_logger().warning(
            "formatter.gemini_error",
            error=str(e),
            message="Gemini API call failed",
        )
        return ""


def _call_ollama(prompt: str, model: str = DEFAULT_OLLAMA_MODEL) -> str:
    """Call Ollama API for local LLM inference."""
    try:
        import requests

        base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
        response = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "temperature": 0.3,
                "max_tokens": 200,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except ImportError:
        _get_logger().warning(
            "formatter.ollama_not_installed",
            message="requests package not installed",
        )
        return ""
    except Exception as e:
        _get_logger().warning(
            "formatter.ollama_error",
            error=str(e),
            message="Ollama API call failed",
        )
        return ""


def _build_llm_prompt(chunk_text: str) -> str:
    """Build prompt for LLM to analyze chunk."""
    return f"""Analyze this clinical text chunk and provide metadata.

Text: {chunk_text[:500]}

Respond with JSON (only, no text):
{{
  "difficulty": <1-5>,
  "symptom_tags": ["tag1", "tag2"],
  "safety_risk": <true/false>
}}

Rules:
- Set safety_risk=true if text mentions self-harm, suicide, or crisis
- symptom_tags: anxiety, depression, sleep, ptsd, ocd, social, anger, substance, or general
- difficulty: 1=easiest, 5=hardest"""


def format_chunk_with_llm(chunk_text: str) -> FormatterResult:
    """
    Format a chunk using LLM for intelligent labeling.

    Returns FormatterResult with difficulty, xp_reward, symptom_tags, safety_risk.
    """
    provider = _get_llm_provider()

    if provider == LLM_PROVIDER_NONE:
        return _format_chunk_fallback(chunk_text)

    crisis_detected = _detect_crisis_keywords(chunk_text)
    if crisis_detected:
        return FormatterResult(
            difficulty=5,
            xp_reward=30,
            symptom_tags=_extract_symptom_tags(chunk_text),
            safety_risk=True,
            raw_response="crisis_keyword_detected",
        )

    prompt = _build_llm_prompt(chunk_text)

    if provider == LLM_PROVIDER_OPENAI:
        raw_response = _call_openai(prompt)
    elif provider == LLM_PROVIDER_GEMINI:
        raw_response = _call_gemini(prompt)
    elif provider == LLM_PROVIDER_OLLAMA:
        raw_response = _call_ollama(prompt)
    else:
        return _format_chunk_fallback(chunk_text)

    return _parse_llm_response(chunk_text, raw_response, crisis_detected)


def _parse_llm_response(
    chunk_text: str,
    raw_response: str,
    crisis_detected: bool,
) -> FormatterResult:
    """Parse LLM response and extract metadata."""
    import json

    difficulty = 3
    symptom_tags = ["general"]
    safety_risk = crisis_detected

    try:
        data = json.loads(raw_response)
        difficulty = _difficulty_to_int(data.get("difficulty", 3))
        tags = data.get("symptom_tags", [])
        if isinstance(tags, list):
            symptom_tags = [t for t in tags if t in SYMPTOM_TAG_KEYWORDS]
            if not symptom_tags:
                symptom_tags = ["general"]
        if data.get("safety_risk"):
            safety_risk = True
    except (json.JSONDecodeError, TypeError) as e:
        _get_logger().warning(
            "formatter.parse_error",
            error=str(e),
            message="Failed to parse LLM response, using fallback",
        )
        symptom_tags = _extract_symptom_tags(chunk_text)

    return FormatterResult(
        difficulty=difficulty,
        xp_reward=_xp_reward_from_difficulty(difficulty),
        symptom_tags=symptom_tags,
        safety_risk=safety_risk,
        raw_response=raw_response,
    )


def _format_chunk_fallback(chunk_text: str) -> FormatterResult:
    """Fallback formatter using keyword matching."""
    crisis = _detect_crisis_keywords(chunk_text)
    tags = _extract_symptom_tags(chunk_text)

    difficulty = 3
    xp = 15

    if crisis:
        difficulty = 5
        xp = 30

    return FormatterResult(
        difficulty=difficulty,
        xp_reward=xp,
        symptom_tags=tags,
        safety_risk=crisis,
    )


def format_chunk(
    chunk_text: str,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    Format a single chunk and return metadata dict.

    Args:
        chunk_text: Text content to format
        use_llm: Whether to use LLM (if available)

    Returns:
        Dict with: difficulty, xp_reward, symptom_tags, safety_risk
    """
    if use_llm:
        result = format_chunk_with_llm(chunk_text)
    else:
        result = _format_chunk_fallback(chunk_text)

    return {
        "difficulty": result.difficulty,
        "xp_reward": result.xp_reward,
        "symptom_tags": result.symptom_tags,
        "safety_risk": result.safety_risk,
    }


def format_chunks_batch(
    chunks: List[str],
    max_batch_size: int = DEFAULT_BATCH_SIZE,
    use_llm: bool = True,
) -> List[Dict[str, Any]]:
    """
    Format multiple chunks with token/cost guard.

    Args:
        chunks: List of chunk texts
        max_batch_size: Maximum chunks to process in one call (cost control)
        use_llm: Whether to use LLM

    Returns:
        List of metadata dicts
    """
    safe_batch_size = min(max_batch_size, MAX_BATCH_SIZE)
    chunks_to_process = chunks[:safe_batch_size]

    log = _get_logger()
    log.info(
        "formatter.batch_start",
        total_chunks=len(chunks),
        processing=len(chunks_to_process),
        max_batch=safe_batch_size,
    )

    results = []
    for i, chunk in enumerate(chunks_to_process):
        try:
            metadata = format_chunk(chunk, use_llm=use_llm)
            results.append(metadata)
        except Exception as e:
            log.warning(
                "formatter.chunk_error",
                chunk_index=i,
                error=str(e),
            )
            results.append({
                "difficulty": 3,
                "xp_reward": 15,
                "symptom_tags": ["general"],
                "safety_risk": False,
            })

    return results


def format_chunk_metadata(
    chunk_text: str,
    formatter: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Pluggable formatter-agent interface (legacy compatibility).

    `formatter` is expected to be a pure function:
        chunk_text -> {xp_reward, difficulty, symptom_tags}
    """
    if formatter:
        return formatter(chunk_text)
    return format_chunk(chunk_text)


def to_clinical_task(
    chunk_text: str,
    task_id: str,
    source_reference: str,
    use_llm: bool = True,
) -> ClinicalTask:
    """
    Convert a formatted chunk to ClinicalTask schema.

    Args:
        chunk_text: Text content
        task_id: Unique task ID
        source_reference: Source document/path
        use_llm: Whether to use LLM

    Returns:
        ClinicalTask instance
    """
    metadata = format_chunk(chunk_text, use_llm=use_llm)

    return ClinicalTask(
        task_id=task_id,
        content=chunk_text,
        symptom_tags=metadata["symptom_tags"],
        difficulty=metadata["difficulty"],
        xp_reward=metadata["xp_reward"],
        source_reference=source_reference,
        metadata={"safety_risk": metadata["safety_risk"]},
    )