"""
Pydantic request/response schemas for chat endpoints.
"""
from typing import Optional, List, Any
from pydantic import BaseModel


class SourceItem(BaseModel):
    """A source citation returned with an answer."""
    title: str
    url: str
    score: float


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""
    question: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response for POST /api/chat."""
    session_id: str
    answer: str
    sources: List[SourceItem] = []
    from_cache: bool = False
    chunks_retrieved: int = 0


class MessageItem(BaseModel):
    """A single message in a session history."""
    id: int
    role: str
    content: str
    sources: Optional[Any] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Response for GET /api/sessions."""
    session_id: str
    messages: List[MessageItem] = []
