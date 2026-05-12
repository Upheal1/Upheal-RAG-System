"""
Chat API router for LLM conversations.

Endpoints:
    POST /api/chat          - Send message, get AI response
    GET  /api/chat/{session_id}/history - Get session history
"""

from fastapi import APIRouter, Depends, HTTPException, status

from services.chat.schemas import ChatHistoryResponse, ChatRequest, ChatResponse
from services.chat.service import create_chat_service
from services.gateway.auth_middleware import AuthenticatedUser, get_current_user
from services.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
    },
)
async def send_chat_message(
    request: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> ChatResponse:
    """
    Send a chat message and get AI response.
    
    - If session_id is provided, continues existing conversation
    - If session_id is null, creates new chat session
    - Optional roadmap_id provides context for personalized responses
    
    Returns:
        ChatResponse with assistant message and session info
    """
    try:
        service = create_chat_service()
        return service.send_message(
            user_id=str(user.user_id),
            request=request,
        )
    except ValueError as e:
        logger.warning("chat.send.validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("chat.send.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat message: {e}",
        )


@router.get(
    "/{session_id}/history",
    response_model=ChatHistoryResponse,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Session not found"},
    },
)
async def get_chat_history(
    session_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> ChatHistoryResponse:
    """
    Get message history for a chat session.
    
    Only returns sessions belonging to the authenticated user.
    
    Returns:
        ChatHistoryResponse with list of messages
    """
    try:
        service = create_chat_service()
        messages = service.get_session_history(
            session_id=session_id,
            user_id=str(user.user_id),
        )
        
        return ChatHistoryResponse(
            session_id=session_id,
            messages=messages,
            total_count=len(messages),
        )
    except ValueError as e:
        logger.warning("chat.history.not_found", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    except Exception as e:
        logger.exception("chat.history.error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chat history: {e}",
        )
