import os
import shutil
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from app.db.database import get_db
from app.db.models import User, Document
from app.core.security import get_current_user
from app.services.vector_store import process_and_store_pdf

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accepts a PDF, registers it in SQLite, and triggers the Redis embedding pipeline."""
    
    if not file.filename.endswith(".pdf"):
        logger.warning(f"User {current_user.username} attempted to upload a non-PDF file.")
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    logger.info(f"User {current_user.username} uploading file: {file.filename}")

    # 1. Create a metadata record in SQLite
    new_doc = Document(filename=file.filename, user_id=current_user.id)
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    temp_file_path = ""
    try:
        # 2. Save the uploaded file temporarily to disk
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name

        # 3. Process the file and store vectors in Redis
        process_and_store_pdf(temp_file_path, new_doc.id, current_user.id)

    except Exception as e:
        # Rollback SQLite database entry if embedding fails
        logger.error("Rolling back database entry due to processing failure.")
        db.delete(new_doc)
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to parse and embed document.")
        
    finally:
        # 4. Clean up the temporary file from the server
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return {
        "message": "Document successfully embedded and stored.",
        "document_id": new_doc.id,
        "filename": file.filename
    }