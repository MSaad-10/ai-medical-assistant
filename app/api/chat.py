import os
import urllib.request
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger
from fpdf import FPDF
import markdown  # for formatting the output

from app.db.database import get_db
from app.db.models import User, ChatHistory
from app.core.security import get_current_user
from app.services.rag_service import generate_chat_stream

router = APIRouter(prefix="/api/chat", tags=["Chat & Retrieval"])

# --- Schemas ---

class ChatRequestSchema(BaseModel):
    query: str = Field(..., description="The medical question asked by the user.")
    session_id: str = Field(..., description="A unique string identifying the chat conversation.")

class ExportChatSchema(BaseModel):
    session_id: str = Field(..., description="The session identifier")

# --- Helper Function for Unicode Fonts ---
def ensure_unicode_fonts_exist():
    """
    Downloads the full open-source DejaVuSans font family.
    We need the full family (Regular, Bold, Italic, Bold-Italic) 
    because HTML formatting will crash if it tries to render an <i> or <em> tag
    without the italic font actively registered in FPDF.
    """
    fonts_dir = "fonts"
    os.makedirs(fonts_dir, exist_ok=True)
    
    # Using jsDelivr CDN
    base_url = "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.0/ttf/"
    
    font_files = {
        "DejaVuSans.ttf": base_url + "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf": base_url + "DejaVuSans-Bold.ttf",
        "DejaVuSans-Oblique.ttf": base_url + "DejaVuSans-Oblique.ttf",
        "DejaVuSans-BoldOblique.ttf": base_url + "DejaVuSans-BoldOblique.ttf"
    }
    
    local_paths = {}
    for filename, url in font_files.items():
        path = os.path.join(fonts_dir, filename)
        local_paths[filename] = path
        
        if not os.path.exists(path):
            logger.info(f"Downloading {filename} for HTML PDF Generation...")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
                out_file.write(response.read())
                
    return local_paths

# --- Endpoints ---

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
    Fetches chat history from the database based on session_id and generates a Markdown-formatted PDF report.
    """
    try:
        # 1. Automatically fetch chat history from the database
        chat_history = db.query(ChatHistory).filter(
            ChatHistory.session_id == request.session_id,
            ChatHistory.user_id == current_user.id
        ).order_by(ChatHistory.id).all()

        if not chat_history:
            return Response(content="No chat history found for this session.", status_code=404)

        # 2. Load the full Font Family
        font_paths = ensure_unicode_fonts_exist()

        # 3. Initialize PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Register the downloaded Unicode fonts inside the PDF engine
        pdf.add_font("DejaVu", "", font_paths["DejaVuSans.ttf"])
        pdf.add_font("DejaVu", "B", font_paths["DejaVuSans-Bold.ttf"])
        pdf.add_font("DejaVu", "I", font_paths["DejaVuSans-Oblique.ttf"])
        pdf.add_font("DejaVu", "BI", font_paths["DejaVuSans-BoldOblique.ttf"])
        
        # Add Header/Title
        pdf.set_font("DejaVu", "B", 16)
        pdf.cell(0, 10, "AI Medical Assistant - Consultation Report", ln=True, align="C")
        
        # Add Meta Data
        pdf.set_font("DejaVu", "I", 10)
        pdf.set_text_color(120, 120, 120)  # Gray
        pdf.cell(0, 10, f"Session ID: {request.session_id} | User ID: {current_user.id}", ln=True, align="C")
        pdf.ln(10) # Add a line break
        
        # 4. Render Chat Messages 
        for msg in chat_history:
            if msg.role.lower() == "user":
                # User Formatting (Standard Text)
                pdf.set_font("DejaVu", "B", 12)
                pdf.set_text_color(0, 51, 102)  # Dark Blue
                pdf.cell(0, 8, "Patient Query:", ln=True)
                
                pdf.set_font("DejaVu", "", 11)
                pdf.set_text_color(0, 0, 0) # Black
                pdf.multi_cell(0, 6, msg.content)
                pdf.ln(5)
            else:
                # AI Assistant Formatting (Markdown/HTML Parsing)
                pdf.set_font("DejaVu", "B", 12)
                pdf.set_text_color(0, 102, 51)  # Dark Green
                pdf.cell(0, 8, "AI Medical Assistant:", ln=True)
                
                # Reset font before parsing HTML so the engine can switch to B/I styles smoothly
                pdf.set_font("DejaVu", "", 11)
                pdf.set_text_color(0, 0, 0) # Black
                
                # Convert the AI's Markdown text into HTML structure
                html_content = markdown.markdown(msg.content)
                
                # Let FPDF render the HTML natively (Creates real bullet points, bolding, and spacing)
                pdf.write_html(html_content)
                pdf.ln(10)
                
        # Export PDF as raw bytes
        pdf_bytes = bytes(pdf.output())
        
        # Return the bytes as a downloadable PDF file
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