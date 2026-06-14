"""
Chat service — orchestrates session management, context loading,
message persistence, and LLM invocation for text-turn.

Voice-turn will reuse the same session/context/prompt layers in a future phase.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app import supabase_chat_repository as repo
from app import chat_context
from app.prompt_builder import build_messages, format_emotion_context
from app.runpod_llm_client import call_runpod_llm

logger = logging.getLogger("upheal.chat_service")


def _extract_emotion_fields(emotion_result: Optional[Dict[str, Any]]) -> tuple:
    """Return (top_emotion, confidence) or (None, None)."""
    if not emotion_result:
        return None, None
    top = emotion_result.get("top_emotion") or emotion_result.get("emotion")
    conf = emotion_result.get("confidence")
    if conf is not None:
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = None
    return top, conf


async def handle_text_turn(
    *,
    user_id: str,
    user_token: str,
    message: str,
    session_id: Optional[str],
    temperature: float = 0.3,
    max_tokens: int = 220,
    text_emotion: Optional[Dict[str, Any]] = None,
    is_social: bool = False,
) -> Dict[str, Any]:
    """Run the full text-turn pipeline and return the API response dict.

    Returns: {"answer": str, "session_id": str, "request_id": str}

    session_id will never be None in a successful response.
    """
    # ── Session management ───────────────────────────────────────────
    if session_id:
        # Validate session exists and is owned by this user (RLS enforces)
        session = await repo.get_session(session_id, user_token)
        sid: str = session["id"]
        logger.info("session reused  user=%s  session=%s", user_id, sid)
    else:
        title = message.strip()[:80]
        sid = await repo.create_session(user_id, user_token, title)
        logger.info("session created  user=%s  session=%s", user_id, sid)

    # ── Save user message ────────────────────────────────────────────
    emotion_top, emotion_conf = _extract_emotion_fields(text_emotion)
    await repo.save_message(
        session_id=sid,
        user_id=user_id,
        user_token=user_token,
        role="user",
        content=message,
        input_type="text",
        text_emotion=emotion_top,
        voice_emotion=None,
        emotion_confidence=emotion_conf,
    )
    logger.info(
        "user msg saved  user=%s  session=%s  len=%d  emotion=%s",
        user_id, sid, len(message), emotion_top,
    )

    # ── Load context ─────────────────────────────────────────────────
    # History (from DB, NOT including the message we just saved —
    # the repo returns chronologically; the save above is the latest)
    history_rows = await chat_context.load_history(sid, user_token)
    # Drop the message we just saved (the last one) to avoid duplication
    history_msgs: List[Dict[str, str]] = []
    for row in history_rows:
        r = row.get("role", "")
        c = row.get("content", "")
        if r in ("user", "assistant") and c:
            history_msgs.append({"role": r, "content": c})
    # Remove the last user message (which is the one we just saved)
    if history_msgs and history_msgs[-1]["role"] == "user":
        history_msgs.pop()

    # Memory context
    memories = await chat_context.load_memories(user_id, user_token)
    memory_context = chat_context.format_memories_context(memories)

    # Emotion context
    emotion_context = ""
    if text_emotion:
        emotion_context = format_emotion_context(text_emotion, None)

    # ── Build prompt and call LLM ────────────────────────────────────
    messages = build_messages(
        user_message=message,
        is_social=is_social,
        memory_context=memory_context,
        emotion_context=emotion_context,
        history_messages=history_msgs,
    )
    logger.info(
        "llm call  user=%s  session=%s  msgs=%d  history=%d  memories=%d  emotion=%s",
        user_id, sid, len(messages), len(history_msgs), len(memories),
        bool(emotion_context),
    )

    assert len(messages) <= 20, f"Too many messages: {len(messages)}"

    answer = await call_runpod_llm(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # ── Save assistant message ───────────────────────────────────────
    await repo.save_message(
        session_id=sid,
        user_id=user_id,
        user_token=user_token,
        role="assistant",
        content=answer,
        input_type="text",
    )
    logger.info("assistant msg saved  user=%s  session=%s  len=%d", user_id, sid, len(answer))

    return {
        "answer": answer,
        "session_id": sid,
        "request_id": f"req_{int(time.time() * 1000)}",
    }


async def load_session_history(
    session_id: str,
    user_token: str,
) -> Dict[str, Any]:
    """Load the full message history for a session (for the GET endpoint)."""
    # Validates ownership via RLS
    await repo.get_session(session_id, user_token)
    rows = await chat_context.load_history(session_id, user_token, limit=200)

    messages: List[Dict[str, Any]] = []
    for row in rows:
        messages.append({
            "id": row.get("id"),
            "role": row.get("role"),
            "content": row.get("content"),
            "input_type": row.get("input_type"),
            "detected_text_emotion": row.get("detected_text_emotion"),
            "detected_voice_emotion": row.get("detected_voice_emotion"),
            "emotion_confidence": row.get("emotion_confidence"),
            "created_at": row.get("created_at"),
        })

    return {
        "session_id": session_id,
        "messages": messages,
    }
