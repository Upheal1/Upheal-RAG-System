"""
Journal service schemas for user journal entries.

Supports mood tracking, tags, and entry management.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class JournalEntryCreate(BaseModel):
    """Request to create a journal entry."""
    
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)
    mood: Optional[str] = Field(default=None, max_length=50)
    mood_rating: Optional[int] = Field(default=None, ge=1, le=10)
    tags: Optional[List[str]] = Field(default=None, max_length=10)


class JournalEntryUpdate(BaseModel):
    """Request to update a journal entry."""
    
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    content: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    mood: Optional[str] = Field(default=None, max_length=50)
    mood_rating: Optional[int] = Field(default=None, ge=1, le=10)
    tags: Optional[List[str]] = Field(default=None, max_length=10)


class JournalEntry(BaseModel):
    """Journal entry model."""
    
    id: str
    user_id: str
    title: str
    content: str
    mood: Optional[str] = None
    mood_rating: Optional[int] = None
    tags: Optional[List[str]] = None
    created_at: str
    updated_at: str
    is_archived: bool = False
    
    model_config = {"from_attributes": True}


class JournalListResponse(BaseModel):
    """Response for listing journal entries."""
    
    entries: List[JournalEntry]
    total_count: int
    page: int
    limit: int
    has_more: bool
