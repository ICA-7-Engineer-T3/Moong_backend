from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    APP_NAME: str = "Integrated MOONG Server"
    VERSION: str = "3.0.0"
    DEBUG: bool = True
    FIREBASE_PROJECT_ID: str = "emotion-analysis-system"
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "config/firebase_service_account.json"
    GOOGLE_CREDENTIALS_PATH: str = "config/google_credentials.json"
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8080/auth/callback"
    YOUTUBE_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: str = "sk-d1a36f1f530347be9eed8b69aa95c3b3"
    GEMINI_BASE_URL: str = "https://api.agihalo.com"
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    MOONG_DB_PATH: str = "DBs/total_data.db"
    MOONG_EMBEDDINGS_PATH: str = "DBs/faiss_embeddings.npy"
    MOONG_FAISS_INDEX_PATH: str = "DBs/faiss_index.faiss"
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
