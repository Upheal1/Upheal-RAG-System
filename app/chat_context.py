"""
Chat context loader — loads conversation history and long-term memory.

Reads history from ai_chat_messages and active memories from ai_user_memory.
Never modifies ai_user_memory in this phase.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from app import supabase_chat_repository as repo

logger = logging.getLogger("upheal.chat_context")

CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", "12"))
AI_MEMORY_LIMIT = int(os.getenv("AI_MEMORY_LIMIT", "8"))


async def load_history(
    session_id: str,
    user_token: str,
    limit: int = CHAT_HISTORY_LIMIT,
) -> List[Dict[str, Any]]:
    """Load recent user/assistant messages for a session, ordered chronologically."""
    rows = await repo.load_recent_messages(session_id, user_token, limit)
    logger.info(
        "history loaded  session=%s  messages=%d",
        session_id, len(rows),
    )
    return rows


async def load_memories(
    user_id: str,
    user_token: str,
    limit: int = AI_MEMORY_LIMIT,
) -> List[Dict[str, Any]]:
    """Load active memory rows for the authenticated user (read-only)."""
    rows = await repo.load_active_memories(user_id, user_token, limit)
    logger.info(
        "memories loaded  user=%s  active=%d",
        user_id, len(rows),
    )
    return rows


def format_memories_context(memories: List[Dict[str, Any]]) -> str:
    """Convert memory rows into a single compact system-context message.

    Returns empty string if there are no active memories.
    """
    if not memories:
        return ""

    lines: List[str] = []
    for m in memories:
        mem_type = m.get("memory_type", "unknown")
        content = m.get("content", "")
        confidence = m.get("confidence")
        if not content:
            continue
        confidence_str = f" (confidence: {confidence:.0%})" if confidence is not None else ""
        lines.append(f"[{mem_type}]{confidence_str} {content}")

    if not lines:
        return ""

    return (
        "## Long-Term Memory Context\n\n"
        "The following are memory records from previous conversations and reflections.\n"
        "Use them ONLY when relevant to the current conversation. "
        "Do NOT reveal hidden memory records directly. "
        "Do NOT claim uncertain memory as fact. "
        "Do NOT mention databases or internal memory systems. "
        "Do NOT use memory to diagnose the user.\n\n"
        + "\n".join(lines)
    )
