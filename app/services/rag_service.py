from loguru import logger
from sqlalchemy.orm import Session
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Redis

from app.core.config import settings

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
        # 1. Retrieve Context from Redis Vector Store
        logger.info("Connecting to Redis to fetch semantic context...")
        vector_store = Redis.from_existing_index(
            embedding=embeddings,
            index_name="medical_docs_index",
            redis_url=settings.REDIS_URL,
            schema="redis_schema.yaml"
        )
        
        # 2. Perform similarity search
        retrieved_docs = vector_store.similarity_search(query, k=6)
        
        # 3. Strict Security Filter: Ensure chunks belong exclusively to the authenticated user
        filtered_docs = [doc for doc in retrieved_docs if doc.metadata.get("user_id") == str(user_id)]

        # 4. Convert the LIST of documents into a single STRING
        context_text = "\n\n".join([doc.page_content for doc in filtered_docs])
        
        # 5. Build the prompt using the string (context_text), NOT the list
        system_prompt = (
            "You are a helpful medical assistant. Use the following context from the user's "
            "uploaded medical documents to answer their question accurately. If the answer "
            "is not contained in the context, state that clearly.\n\n" 
            f"Context:\n{context_text}"
        )
        
        messages = [
            ("system", system_prompt),
            ("human", query)
        ]

        logger.info("Streaming response from Gemini...")
        
        # 6. Stream the response chunks back to the client
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield chunk.content
                
    except Exception as e:
        logger.error(f"Streaming error occurred: {str(e)}")
        yield f"\n[CRITICAL SERVER ERROR]: {str(e)}"