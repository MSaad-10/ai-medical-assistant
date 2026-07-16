from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Medical Assistant"
    
    # API keys
    GOOGLE_API_KEY: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379"
    DATABASE_URL: str = "sqlite:///./medical_assistant.db"

    # JWT Authentication Settings
    SECRET_KEY: str = "super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Use to ignore extra .env variables (like HF_TOKEN) when using Gemini model
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()