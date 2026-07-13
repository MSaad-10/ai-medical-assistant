from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging, log_requests_middleware
from app.db.database import engine, Base
from app.api import auth, documents, chat  # <-- ADD documents here

setup_logging()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend engine for AI Medical Assistant.",
    version="1.0.0"
)

@app.middleware("http")
async def logging_middleware(request, call_next):
    return await log_requests_middleware(request, call_next)

# Mount application domain routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router) # <-- 2. Register the chat router here

@app.get("/health", tags=["System Health"])
async def health_check():
    return {"status": "healthy"}