import os
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Redis
from loguru import logger

from app.core.config import settings

# Initialize Gemini Embeddings using the latest active model
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2", 
    google_api_key=settings.GOOGLE_API_KEY
)

def process_and_store_pdf(file_path: str, document_id: int, user_id: int) -> bool:
    """Extracts text from a PDF, chunks it, and stores the vectors in Redis Stack."""
    try:
        # 1. Extract Text
        logger.info(f"Loading PDF for document ID {document_id}")
        loader = PyMuPDFLoader(file_path)
        documents = loader.load()

        # 2. Split Text into Contextual Chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)

        # 3. Inject Metadata for Security Isolation
        for chunk in chunks:
            chunk.metadata.update({
                "user_id": str(user_id),
                "document_id": str(document_id)
            })

        # 4. Store in Redis
        logger.info(f"Embedding {len(chunks)} chunks into Redis...")
        vs = Redis.from_documents(
            chunks,
            embeddings,
            redis_url=settings.REDIS_URL,
            index_name="medical_docs_index"  
        )
        
        # MAGICAL FIX: Explicitly dump the database schema to a local file
        vs.write_schema("redis_schema.yaml")
        
        logger.info(f"Successfully stored vectors for document ID {document_id}.")
        return True

    except Exception as e:
        logger.error(f"Failed to process PDF: {str(e)}")
        raise e