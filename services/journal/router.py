"""
Journal API router for user journal entries.

Endpoints:
    GET  /api/journal          - List entries
    POST /api/journal          - Create entry
    GET  /api/journal/{id}     - Get single entry
    PUT  /api/journal/{id}     - Update entry
    DELETE /api/journal/{id}   - Archive entry
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from services.gateway.auth_middleware import AuthenticatedUser, get_current_user
from services.journal.schemas import (
    JournalEntry,
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalListResponse,
)
from services.journal.service import create_journal_service
from services.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get(
    "",
    response_model=JournalListResponse,
    responses={401: {"description": "Unauthorized"}},
)
async def list_journal_entries(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    include_archived: bool = False,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JournalListResponse:
    """
    List journal entries for the authenticated user.
    
    Parameters:
        page: Page number (1-indexed)
        limit: Entries per page (max 100)
        include_archived: Include soft-deleted entries
    
    Returns:
        Paginated list of journal entries
    """
    try:
        service = create_journal_service()
        return service.get_entries(
            user_id=str(user.user_id),
            page=page,
            limit=limit,
            include_archived=include_archived,
        )
    except Exception as e:
        logger.exception("journal.list.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve journal entries: {e}",
        )


@router.post(
    "",
    response_model=JournalEntry,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
    },
)
async def create_journal_entry(
    request: JournalEntryCreate,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JournalEntry:
    """
    Create a new journal entry.
    
    Returns:
        Created journal entry
    """
    try:
        service = create_journal_service()
        return service.create_entry(
            user_id=str(user.user_id),
            request=request,
        )
    except Exception as e:
        logger.exception("journal.create.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create journal entry: {e}",
        )


@router.get(
    "/{entry_id}",
    response_model=JournalEntry,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Entry not found"},
    },
)
async def get_journal_entry(
    entry_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JournalEntry:
    """
    Get a single journal entry by ID.
    
    Returns:
        Journal entry if found
    """
    try:
        service = create_journal_service()
        entry = service.get_entry(entry_id, str(user.user_id))
        
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journal entry not found",
            )
        
        return entry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("journal.get.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve journal entry: {e}",
        )


@router.put(
    "/{entry_id}",
    response_model=JournalEntry,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Entry not found"},
        422: {"description": "Validation error"},
    },
)
async def update_journal_entry(
    entry_id: str,
    request: JournalEntryUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
) -> JournalEntry:
    """
    Update a journal entry.
    
    Only provided fields will be updated.
    
    Returns:
        Updated journal entry
    """
    try:
        service = create_journal_service()
        entry = service.update_entry(entry_id, str(user.user_id), request)
        
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journal entry not found",
            )
        
        return entry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("journal.update.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update journal entry: {e}",
        )


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Entry not found"},
    },
)
async def archive_journal_entry(
    entry_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """
    Archive (soft-delete) a journal entry.
    
    Returns:
        204 No Content on success
    """
    try:
        service = create_journal_service()
        success = service.archive_entry(entry_id, str(user.user_id))
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Journal entry not found",
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("journal.archive.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive journal entry: {e}",
        )
