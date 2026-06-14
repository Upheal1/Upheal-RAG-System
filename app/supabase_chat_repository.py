"""
Supabase REST/PostgREST chat repository.

Uses the authenticated user's JWT (via require_auth) with Row-Level Security.
Never uses a service-role key.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

logger = logging.getLogger("upheal.supabase_repo")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")


def _check_config() -> None:
    if not SUPABASE_URL:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    if not SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(status_code=503, detail="Supabase publishable key not configured")


def _auth_headers(user_token: str) -> Dict[str, str]:
    return {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _safe_raise(status: int, detail: str) -> None:
    """Raise HTTPException without exposing internals."""
    raise HTTPException(status_code=status, detail=detail)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

async def create_session(user_id: str, user_token: str, title: str) -> str:
    """Create a new ai_chat_sessions row. Returns the new session UUID."""
    _check_config()
    payload = {
        "user_id": user_id,
        "session_title": title[:80],
        "started_at": "now()",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/ai_chat_sessions",
                headers=_auth_headers(user_token),
                json=payload,
                timeout=10,
            )
    except httpx.TimeoutException:
        _safe_raise(503, "Supabase session creation timed out")
    except httpx.RequestError:
        logger.warning("Supabase session creation network error", exc_info=True)
        _safe_raise(503, "Supabase unavailable")

    if resp.status_code == 401:
        _safe_raise(401, "Invalid or expired access token")
    if resp.status_code >= 500:
        _safe_raise(503, "Supabase error during session creation")
    if resp.status_code not in (200, 201):
        logger.warning("create_session HTTP %s: %s", resp.status_code, resp.text[:200])
        _safe_raise(503, "Failed to create chat session")

    try:
        rows = resp.json()
    except ValueError:
        _safe_raise(503, "Supabase returned invalid JSON for session creation")
    if not rows or not isinstance(rows, list):
        _safe_raise(503, "Unexpected session creation response")
    sid: Optional[str] = rows[0].get("id")
    if not sid:
        _safe_raise(503, "Missing session id in creation response")
    return sid


async def get_session(session_id: str, user_token: str) -> Dict[str, Any]:
    """Load a session by id. Returns the row dict. RLS ensures ownership."""
    _check_config()
    # Validate UUID format
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid session ID format")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/ai_chat_sessions",
                headers=_auth_headers(user_token),
                params={
                    "id": f"eq.{session_id}",
                    "select": "*",
                },
                timeout=10,
            )
    except httpx.TimeoutException:
        _safe_raise(503, "Supabase session lookup timed out")
    except httpx.RequestError:
        logger.warning("Supabase session lookup network error", exc_info=True)
        _safe_raise(503, "Supabase unavailable")

    if resp.status_code == 401:
        _safe_raise(401, "Invalid or expired access token")
    if resp.status_code >= 500:
        _safe_raise(503, "Supabase error during session lookup")
    if resp.status_code != 200:
        _safe_raise(503, "Failed to look up chat session")

    try:
        rows = resp.json()
    except ValueError:
        _safe_raise(503, "Supabase returned invalid JSON for session lookup")

    if not rows or not isinstance(rows, list) or len(rows) == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    return rows[0]


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

async def save_message(
    session_id: str,
    user_id: str,
    user_token: str,
    *,
    role: str,
    content: str,
    input_type: str = "text",
    text_emotion: Optional[str] = None,
    voice_emotion: Optional[str] = None,
    emotion_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """Insert a row into ai_chat_messages. Returns the created row."""
    _check_config()
    payload: Dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "input_type": input_type,
    }
    if text_emotion is not None:
        payload["detected_text_emotion"] = text_emotion
    if voice_emotion is not None:
        payload["detected_voice_emotion"] = voice_emotion
    if emotion_confidence is not None:
        payload["emotion_confidence"] = emotion_confidence

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/ai_chat_messages",
                headers=_auth_headers(user_token),
                json=payload,
                timeout=10,
            )
    except httpx.TimeoutException:
        _safe_raise(503, "Supabase message save timed out")
    except httpx.RequestError:
        logger.warning("Supabase message save network error", exc_info=True)
        _safe_raise(503, "Supabase unavailable")

    if resp.status_code == 401:
        _safe_raise(401, "Invalid or expired access token")
    if resp.status_code >= 500:
        _safe_raise(503, "Supabase error during message save")
    if resp.status_code not in (200, 201):
        logger.warning("save_message HTTP %s: %s", resp.status_code, resp.text[:200])
        _safe_raise(503, "Failed to save chat message")

    try:
        rows = resp.json()
    except ValueError:
        _safe_raise(503, "Supabase returned invalid JSON for message save")
    if not rows or not isinstance(rows, list):
        _safe_raise(503, "Unexpected message save response")
    return rows[0]


async def load_recent_messages(
    session_id: str,
    user_token: str,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    """Load recent messages for a session, ordered chronologically."""
    _check_config()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/ai_chat_messages",
                headers=_auth_headers(user_token),
                params={
                    "session_id": f"eq.{session_id}",
                    "order": "created_at.asc",
                    "limit": str(limit),
                    "select": "role,content,input_type,detected_text_emotion,detected_voice_emotion,emotion_confidence,created_at,id",
                },
                timeout=10,
            )
    except httpx.TimeoutException:
        _safe_raise(503, "Supabase history load timed out")
    except httpx.RequestError:
        logger.warning("Supabase history load network error", exc_info=True)
        _safe_raise(503, "Supabase unavailable")

    if resp.status_code == 401:
        _safe_raise(401, "Invalid or expired access token")
    if resp.status_code >= 500:
        _safe_raise(503, "Supabase error during history load")
    if resp.status_code != 200:
        _safe_raise(503, "Failed to load chat history")

    try:
        rows = resp.json()
    except ValueError:
        _safe_raise(503, "Supabase returned invalid JSON for history")
    return rows if isinstance(rows, list) else []


# ---------------------------------------------------------------------------
# AI User Memory (read-only)
# ---------------------------------------------------------------------------

async def load_active_memories(
    user_id: str,
    user_token: str,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Load active memory rows for a user. Read-only — no writes."""
    _check_config()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/ai_user_memory",
                headers=_auth_headers(user_token),
                params={
                    "user_id": f"eq.{user_id}",
                    "is_active": "eq.true",
                    "order": "last_used_at.desc",
                    "limit": str(limit),
                    "select": "memory_type,content,confidence,source_type",
                },
                timeout=10,
            )
    except httpx.TimeoutException:
        _safe_raise(503, "Supabase memory load timed out")
    except httpx.RequestError:
        logger.warning("Supabase memory load network error", exc_info=True)
        _safe_raise(503, "Supabase unavailable")

    if resp.status_code == 401:
        _safe_raise(401, "Invalid or expired access token")
    if resp.status_code >= 500:
        _safe_raise(503, "Supabase error during memory load")
    if resp.status_code != 200:
        _safe_raise(503, "Failed to load memory")

    try:
        rows = resp.json()
    except ValueError:
        _safe_raise(503, "Supabase returned invalid JSON for memory")
    return rows if isinstance(rows, list) else []
