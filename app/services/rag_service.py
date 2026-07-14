from loguru import logger
from sqlalchemy.orm import Session
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Redis

from app.core.config import settings
from app.db.models import ChatHistory

# Initialize the Gemini LLM with streaming explicitly enabled
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash", 
    google_api_key=settings.GOOGLE_API_KEY,
    streaming=True
)

# Use the exact same embedding model as the ingestion pipeline
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2", 
    google_api_key=settings.GOOGLE_API_KEY
)

async def generate_chat_stream(query: str, session_id: str, user_id: int, db: Session):
    try:
        # Retrieve Context from Redis Vector Store
        logger.info("Connecting to Redis to fetch semantic context...")
        vector_store = Redis.from_existing_index(
            embedding=embeddings,
            index_name="medical_docs_index",
            redis_url=settings.REDIS_URL,
            schema="redis_schema.yaml"
        )
        
        # Similarity search
        retrieved_docs = vector_store.similarity_search(query, k=6)
        
        # Ensure chunks belong to authenticated user
        filtered_docs = [doc for doc in retrieved_docs if doc.metadata.get("user_id") == str(user_id)]

        # Converting list of document into a single string
        context_text = "\n\n".join([doc.page_content for doc in filtered_docs])
        
        # Strict Guardrails
        system_prompt = (
            "You are a professional AI Medical Assistant. Your primary role is to answer "
            "medical-related queries based strictly on the provided context from the user's uploaded documents.\n\n"
            "### STRICT GUIDELINES:\n"
            "1. SCOPE: You must ONLY answer medical-related general queries or questions directly related to the provided context. If the user asks a non-medical question (e.g., programming, cooking, general knowledge), politely decline and state that you can only assist with medical inquiries.\n"
            "2. MEDICAL SAFETY (CRITICAL): If the user asks for a diagnosis, a prescription, specific medicine recommendations, or dosage advice that typically requires a physician's input, you MUST refuse to provide it and reply with the EXACT following phrase: 'Please discuss this with your physician at your next visit, or call the office if it is urgent.'\n"
            "3. ACCURACY: If the answer to a medical question is not contained within the provided context, state that clearly and do not hallucinate or make up information.\n\n"
            f"### CONTEXT:\n{context_text}"
        )
        
        messages = [
            ("system", system_prompt),
            ("human", query)
        ]

        logger.info("Streaming response from Gemini...")
        
        full_ai_response = ""
        
        # Response Streaming
        async for chunk in llm.astream(messages):
            if chunk.content:
                content_str = ""
                if isinstance(chunk.content, str):
                    content_str = chunk.content
                elif isinstance(chunk.content, list):
                    for part in chunk.content:
                        if isinstance(part, dict) and "text" in part:
                            content_str += part["text"]
                        elif isinstance(part, str):
                            content_str += part
                
                if content_str:
                    full_ai_response += content_str
                    yield content_str
                
        user_msg = ChatHistory(session_id=session_id, user_id=user_id, role="user", content=query)
        ai_msg = ChatHistory(session_id=session_id, user_id=user_id, role="assistant", content=full_ai_response)
        
        db.add(user_msg)
        db.add(ai_msg)
        db.commit()
                
    except Exception as e:
        logger.error(f"Streaming error occurred: {str(e)}")
        yield f"\n[CRITICAL SERVER ERROR]: {str(e)}"