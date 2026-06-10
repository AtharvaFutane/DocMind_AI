"""
Chat endpoints for Q&A with indexed documentation.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.models.chat import ChatSession, ChatMessage

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ask a question about the indexed documentation.
    Supports multi-turn conversations via session_id.
    """
    rag = request.app.state.rag

    # Get or create session
    session_id = body.session_id or str(uuid.uuid4())
    session = await db.get(ChatSession, session_id)

    if not session:
        session = ChatSession(id=session_id)
        db.add(session)
        await db.commit()

    # Get conversation history for this session
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .limit(10)
    )
    history_msgs = result.scalars().all()
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_msgs
    ]

    # Run RAG pipeline with exception handling
    try:
        rag_result = await rag.answer(
            question=body.question,
            conversation_history=conversation_history,
        )
    except Exception as e:
        import openai
        error_msg = str(e)
        if "Quota exceeded" in error_msg or "RateLimitError" in error_msg or "429" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Gemini API Free Tier quota exceeded (limit is 20 requests per day). Please wait or upgrade your Google AI Studio billing details."
            )
        elif isinstance(e, openai.RateLimitError):
            raise HTTPException(
                status_code=429,
                detail="API Rate limit exceeded. Please wait a moment before retrying."
            )
        elif isinstance(e, openai.APIError):
            raise HTTPException(
                status_code=502,
                detail=f"Gemini API Error: {error_msg}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate response: {error_msg}"
            )

    # Persist messages
    user_msg = ChatMessage(
        session_id=session_id, role="user", content=body.question
    )
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=rag_result["answer"],
        sources=rag_result["sources"],
    )
    db.add_all([user_msg, assistant_msg])
    await db.commit()

    return ChatResponse(
        session_id=session_id,
        answer=rag_result["answer"],
        sources=rag_result["sources"],
        from_cache=rag_result["from_cache"],
        chunks_retrieved=rag_result["chunks_retrieved"],
    )


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    """Retrieve full message history for a chat session."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "sources": msg.sources,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    """Delete a chat session and all its messages."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
    await db.commit()
    return {"message": f"Session {session_id} deleted"}
