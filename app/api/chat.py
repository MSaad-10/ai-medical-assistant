from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.core.security import get_current_user
from app.services.rag_service import generate_chat_stream

router = APIRouter(prefix="/api/chat", tags=["Chat & Retrieval"])

class ChatRequestSchema(BaseModel):
    query: str = Field(..., description="The medical question asked by the user.")
    session_id: str = Field(..., description="A unique string identifying the chat conversation.")

@router.post("/stream")
async def chat_stream(
    request: ChatRequestSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Processes a medical query using RAG and streams the Gemini response back via Server-Sent Events (SSE).
    """
    
    async def sse_generator():
        # Wrap the generator to format the text into the standard SSE text/event-stream syntax
        async for text_chunk in generate_chat_stream(request.query, request.session_id, current_user.id, db):
            yield f"data: {text_chunk}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")