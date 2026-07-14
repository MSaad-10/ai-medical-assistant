from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger
from fpdf import FPDF

from app.db.database import get_db
from app.db.models import User, ChatHistory
from app.core.security import get_current_user
from app.services.rag_service import generate_chat_stream

router = APIRouter(prefix="/api/chat", tags=["Chat & Retrieval"])

class ChatRequestSchema(BaseModel):
    query: str = Field(..., description="The medical question asked by the user.")
    session_id: str = Field(..., description="A unique string identifying the chat conversation.")

class ExportChatSchema(BaseModel):
    session_id: str = Field(..., description="The session identifier")

@router.post("/stream")
async def chat_stream(
    request: ChatRequestSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Processes a medical query using RAG and streams the Gemini response back via Server-Sent Events (SSE).
    Automatically saves the full conversation to the SQLite database.
    """
    async def sse_generator():
        try:
            async for text_chunk in generate_chat_stream(request.query, request.session_id, current_user.id, db):
                yield f"data: {text_chunk}\n\n"
        except Exception as e:
            logger.error(f"Stream completely crashed: {str(e)}")
            yield f"data: [CRITICAL SERVER ERROR]: {str(e)}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@router.post("/export", response_class=Response)
async def export_chat_pdf(
    request: ExportChatSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches chat history from the database based on session_id and generates a formatted PDF report.
    """
    try:
        chat_history = db.query(ChatHistory).filter(
            ChatHistory.session_id == request.session_id,
            ChatHistory.user_id == current_user.id
        ).order_by(ChatHistory.id).all()

        if not chat_history:
            return Response(content="No chat history found for this session.", status_code=404)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "AI Medical Assistant - Consultation Report", ln=True, align="C")
        
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(120, 120, 120)  # Gray
        pdf.cell(0, 10, f"Session ID: {request.session_id} | User ID: {current_user.id}", ln=True, align="C")
        pdf.ln(10) # Add a line break
        
        for msg in chat_history:
            if msg.role.lower() == "user":
                # User Formatting
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(0, 51, 102)  # Dark Blue
                pdf.cell(0, 8, "Patient Query:", ln=True)
                
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(0, 0, 0) # Black
                pdf.multi_cell(0, 6, msg.content)
                pdf.ln(5)
            else:
                # AI Assistant Formatting
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(0, 102, 51)  # Dark Green
                pdf.cell(0, 8, "AI Medical Assistant:", ln=True)
                
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(0, 0, 0) # Black
                pdf.multi_cell(0, 6, msg.content)
                pdf.ln(10)
                
        pdf_bytes = bytes(pdf.output())
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=consultation_{request.session_id}.pdf"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to generate PDF: {str(e)}")
        return Response(content=f"Error generating PDF: {str(e)}", status_code=500)