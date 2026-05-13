"""
Chat service schemas for LLM conversation management.

Supports user-assistant conversations with roadmap context.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""
    
    role: Literal["user", "assistant", "system"]
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: Optional[str] = None


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session ID, or null to create new session"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User message content"
    )
    roadmap_id: Optional[str] = Field(
        default=None,
        description="Optional roadmap context for personalized responses"
    )


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    
    session_id: str
    message_id: str
    assistant_message: ChatMessage
    history: List[ChatMessage]
    relevant_task_id: Optional[str] = Field(
        default=None,
        description="If AI suggests a specific task"
    )


class ChatSessionResponse(BaseModel):
    """Chat session information."""
    
    session_id: str
    user_id: str
    roadmap_id: Optional[str] = None
    created_at: str
    message_count: int


class ChatHistoryResponse(BaseModel):
    """Chat history for a session."""
    
    session_id: str
    messages: List[ChatMessage]
    total_count: int
