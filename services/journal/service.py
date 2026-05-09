"""
Journal service for managing user journal entries.

Provides CRUD operations with soft-delete (archive) support.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from services.journal.schemas import (
    JournalEntry,
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalListResponse,
)
from services.shared.logging import get_logger
from services.shared.state import SupabaseSyncHook

logger = get_logger(__name__)


class JournalService:
    """Service for journal entry CRUD operations."""
    
    def __init__(self, supabase_client=None):
        self._client = supabase_client
        self._table = "journal_entries"
    
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            hook = SupabaseSyncHook(self._table)
            self._client = hook.client
        return self._client
    
    def create_entry(
        self,
        user_id: str,
        request: JournalEntryCreate,
    ) -> JournalEntry:
        """
        Create a new journal entry.
        
        Parameters
        ----------
        user_id : str
            User UUID
        request : JournalEntryCreate
            Entry data
            
        Returns
        -------
        JournalEntry
            Created entry
        """
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        row = {
            "id": entry_id,
            "user_id": user_id,
            "title": request.title,
            "content": request.content,
            "mood": request.mood,
            "mood_rating": request.mood_rating,
            "tags": request.tags,
            "created_at": now,
            "updated_at": now,
            "is_archived": False,
        }
        
        try:
            result = self.client.table(self._table).insert(row).execute()
            logger.info(
                "journal.entry.created",
                entry_id=entry_id,
                user_id=user_id,
            )
            return self._row_to_entry(result.data[0])
        except Exception as e:
            logger.error("journal.entry.create_failed", error=str(e))
            raise
    
    def get_entries(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        include_archived: bool = False,
    ) -> JournalListResponse:
        """
        Get journal entries for a user.
        
        Parameters
        ----------
        user_id : str
            User UUID
        page : int
            Page number (1-indexed)
        limit : int
            Entries per page
        include_archived : bool
            Whether to include archived entries
            
        Returns
        -------
        JournalListResponse
            Paginated list of entries
        """
        try:
            query = (
                self.client.table(self._table)
                .select("*", count="exact")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
            )
            
            if not include_archived:
                query = query.eq("is_archived", False)
            
            # Pagination
            offset = (page - 1) * limit
            query = query.range(offset, offset + limit - 1)
            
            result = query.execute()
            
            entries = [self._row_to_entry(row) for row in result.data]
            total_count = result.count or len(entries)
            
            logger.info(
                "journal.entries.listed",
                user_id=user_id,
                count=len(entries),
                page=page,
            )
            
            return JournalListResponse(
                entries=entries,
                total_count=total_count,
                page=page,
                limit=limit,
                has_more=total_count > offset + len(entries),
            )
            
        except Exception as e:
            logger.error("journal.entries.list_failed", error=str(e))
            raise
    
    def get_entry(self, entry_id: str, user_id: str) -> Optional[JournalEntry]:
        """
        Get a single journal entry.
        
        Parameters
        ----------
        entry_id : str
            Entry UUID
        user_id : str
            User UUID (for access control)
            
        Returns
        -------
        JournalEntry or None
            Entry if found and belongs to user
        """
        try:
            result = (
                self.client.table(self._table)
                .select("*")
                .eq("id", entry_id)
                .eq("user_id", user_id)
                .execute()
            )
            
            if not result.data:
                return None
            
            return self._row_to_entry(result.data[0])
            
        except Exception as e:
            logger.error("journal.entry.get_failed", error=str(e))
            raise
    
    def update_entry(
        self,
        entry_id: str,
        user_id: str,
        request: JournalEntryUpdate,
    ) -> Optional[JournalEntry]:
        """
        Update a journal entry.
        
        Parameters
        ----------
        entry_id : str
            Entry UUID
        user_id : str
            User UUID (for access control)
        request : JournalEntryUpdate
            Fields to update
            
        Returns
        -------
        JournalEntry or None
            Updated entry if found
        """
        # Build update dict with only provided fields
        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        if request.title is not None:
            update_data["title"] = request.title
        if request.content is not None:
            update_data["content"] = request.content
        if request.mood is not None:
            update_data["mood"] = request.mood
        if request.mood_rating is not None:
            update_data["mood_rating"] = request.mood_rating
        if request.tags is not None:
            update_data["tags"] = request.tags
        
        if len(update_data) == 1:  # Only updated_at
            # Nothing to update, return current entry
            return self.get_entry(entry_id, user_id)
        
        try:
            result = (
                self.client.table(self._table)
                .update(update_data)
                .eq("id", entry_id)
                .eq("user_id", user_id)
                .execute()
            )
            
            if not result.data:
                return None
            
            logger.info("journal.entry.updated", entry_id=entry_id)
            return self._row_to_entry(result.data[0])
            
        except Exception as e:
            logger.error("journal.entry.update_failed", error=str(e))
            raise
    
    def archive_entry(self, entry_id: str, user_id: str) -> bool:
        """
        Soft-delete (archive) a journal entry.
        
        Parameters
        ----------
        entry_id : str
            Entry UUID
        user_id : str
            User UUID (for access control)
            
        Returns
        -------
        bool
            True if archived successfully
        """
        try:
            result = (
                self.client.table(self._table)
                .update({
                    "is_archived": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                .eq("id", entry_id)
                .eq("user_id", user_id)
                .execute()
            )
            
            if result.data:
                logger.info("journal.entry.archived", entry_id=entry_id)
                return True
            return False
            
        except Exception as e:
            logger.error("journal.entry.archive_failed", error=str(e))
            raise
    
    def _row_to_entry(self, row: dict) -> JournalEntry:
        """Convert database row to JournalEntry model."""
        return JournalEntry(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            content=row["content"],
            mood=row.get("mood"),
            mood_rating=row.get("mood_rating"),
            tags=row.get("tags"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_archived=row.get("is_archived", False),
        )


def create_journal_service(supabase_client=None) -> JournalService:
    """Factory function to create JournalService."""
    return JournalService(supabase_client=supabase_client)
