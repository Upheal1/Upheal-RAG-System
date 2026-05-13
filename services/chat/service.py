"""
Chat service for LLM conversations.

Manages chat sessions, message history, and generates AI responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from services.chat.schemas import ChatMessage, ChatRequest, ChatResponse
from services.shared.logging import get_logger
from services.shared.state import SupabaseSyncHook

logger = get_logger(__name__)


class ChatService:
    """Service for managing chat conversations."""
    
    def __init__(self, supabase_client=None):
        self._client = supabase_client
        self._sessions_table = "chat_sessions"
        self._messages_table = "chat_messages"
    
    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            hook = SupabaseSyncHook(self._sessions_table)
            self._client = hook.client
        return self._client
    
    def send_message(
        self,
        user_id: str,
        request: ChatRequest,
    ) -> ChatResponse:
        """
        Send a message and get AI response.
        
        Parameters
        ----------
        user_id : str
            User UUID
        request : ChatRequest
            Chat request with message and optional session_id
            
        Returns
        -------
        ChatResponse
            AI response with session info
        """
        # Get or create session
        session_id = request.session_id or self._create_session(user_id, request.roadmap_id)
        
        # Store user message
        user_message = ChatMessage(
            role="user",
            content=request.message,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._store_message(session_id, user_message)
        
        # Get conversation history
        history = self._get_session_history(session_id)
        
        # Generate AI response (placeholder - integrate with actual LLM)
        assistant_message = self._generate_response(request.message, history, request.roadmap_id)
        
        # Store assistant message
        self._store_message(session_id, assistant_message)
        
        # Update history with new message
        history.append(assistant_message)
        
        logger.info(
            "chat.message.sent",
            user_id=user_id,
            session_id=session_id,
            message_length=len(request.message),
        )
        
        return ChatResponse(
            session_id=session_id,
            message_id=str(uuid.uuid4()),
            assistant_message=assistant_message,
            history=history,
            relevant_task_id=None,  # TODO: Extract from AI response
        )
    
    def _create_session(
        self,
        user_id: str,
        roadmap_id: Optional[str] = None,
    ) -> str:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        
        row = {
            "id": session_id,
            "user_id": user_id,
            "roadmap_id": roadmap_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            self.client.table(self._sessions_table).insert(row).execute()
            logger.info("chat.session.created", session_id=session_id, user_id=user_id)
        except Exception as e:
            logger.error("chat.session.create_failed", error=str(e))
            raise
        
        return session_id
    
    def _store_message(self, session_id: str, message: ChatMessage) -> None:
        """Store a message in the database."""
        row = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": message.role,
            "content": message.content,
            "metadata": message.metadata,
            "created_at": message.created_at or datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            self.client.table(self._messages_table).insert(row).execute()
        except Exception as e:
            logger.error("chat.message.store_failed", error=str(e))
            raise
    
    def get_session_history(self, session_id: str, user_id: str) -> List[ChatMessage]:
        """
        Get message history for a session.
        
        Parameters
        ----------
        session_id : str
            Session UUID
        user_id : str
            User UUID (for access control)
            
        Returns
        -------
        List[ChatMessage]
            List of messages in chronological order
        """
        # Verify session belongs to user
        session_response = (
            self.client.table(self._sessions_table)
            .select("*")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not session_response.data:
            raise ValueError("Session not found or access denied")
        
        return self._get_session_history(session_id)
    
    def _get_session_history(self, session_id: str) -> List[ChatMessage]:
        """Internal: get session history without access check."""
        response = (
            self.client.table(self._messages_table)
            .select("*")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        
        messages = []
        for row in response.data or []:
            messages.append(ChatMessage(
                role=row["role"],
                content=row["content"],
                metadata=row.get("metadata", {}),
                created_at=row["created_at"],
            ))
        
        return messages
    
    def _generate_response(
        self,
        user_message: str,
        history: List[ChatMessage],
        roadmap_id: Optional[str] = None,
    ) -> ChatMessage:
        """
        Generate AI response to user message.
        
        This is a placeholder implementation. Integrate with actual LLM:
        - OpenAI GPT
        - Anthropic Claude
        - Local model via Ollama
        """
        # TODO: Integrate with actual LLM service
        # For now, return a helpful placeholder response
        
        response_content = (
            "I understand you're asking about: '{}'\n\n"
            "I'm here to support your mental health journey. "
            "For now, I can help you with:\n"
            "- Understanding your roadmap tasks\n"
            "- Providing encouragement\n"
            "- Explaining therapeutic techniques\n\n"
            "How can I assist you today?"
        ).format(user_message[:100])
        
        return ChatMessage(
            role="assistant",
            content=response_content,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


def create_chat_service(supabase_client=None) -> ChatService:
    """Factory function to create ChatService."""
    return ChatService(supabase_client=supabase_client)
