"""
설정 관리 모듈
- 환경 변수 관리
- 서버 설정
- 외부 API 설정
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
import structlog

logger = structlog.get_logger(__name__)

class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # Server 설정
    app_name: str = "Moong Middleware Server"
    app_version: str = "1.0.0"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Firebase 설정
    firebase_project_id: str = "moong-project"
    firebase_service_account_path: str = "/Users/kjw/emotion-analysis-system/config/firebase_service_account.json"
    
    # 감정 분석 백엔드 설정
    emotion_backend_url: str = "http://localhost:8001"
    emotion_backend_timeout: int = 30
    
    # JWT 설정
    secret_key: str = "moong-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # 로그 설정
    log_level: str = "INFO"
    
    # 개발환경 설정
    cors_origins: list = ["*"]  # 프로덕션에서는 특정 도메인만 허용
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields in .env file

# 전역 설정 인스턴스
settings = Settings()

def get_settings() -> Settings:
    """설정 인스턴스 반환"""
    return settings