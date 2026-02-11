"""
Firebase 설정 및 초기화 모듈
- Firestore 데이터베이스 연결
- Firebase Admin SDK 설정
- 서비스 계정 인증
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

class FirebaseConfig:
    """Firebase 설정 관리 클래스"""
    
    def __init__(self):
        self.db: Optional[firestore.Client] = None
        self.initialized = False
        self.service_account_path = "/Users/kjw/emotion-analysis-system/config/firebase_service_account.json"
    
    def initialize_firebase(self) -> bool:
        """Firebase 초기화"""
        try:
            if self.initialized:
                logger.info("Firebase already initialized")
                return True
            
            # 서비스 계정 키 파일 확인
            if not os.path.exists(self.service_account_path):
                logger.error(f"Firebase service account file not found: {self.service_account_path}")
                logger.info("Firebase 콘솔에서 서비스 계정 키를 다운로드하고 설정해주세요.")
                return False
            
            # Firebase 앱이 이미 초기화되지 않은 경우에만 초기화
            if not firebase_admin._apps:
                cred = credentials.Certificate(self.service_account_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase app initialized successfully")
            
            # Firestore 클라이언트 생성
            self.db = firestore.client()
            self.initialized = True
            
            logger.info("✅ Firebase 초기화 완료!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase 초기화 실패: {e}")
            return False
    
    def get_db(self) -> Optional[firestore.Client]:
        """Firestore 클라이언트 반환"""
        if not self.initialized:
            self.initialize_firebase()
        return self.db
    
    def verify_auth_token(self, token: str) -> Optional[dict]:
        """Firebase Auth 토큰 검증"""
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as e:
            logger.error(f"토큰 검증 실패: {e}")
            return None

# 전역 Firebase 인스턴스
firebase_config = FirebaseConfig()

def get_firestore_db() -> Optional[firestore.Client]:
    """Firestore 데이터베이스 인스턴스 반환"""
    return firebase_config.get_db()

def verify_user_token(token: str) -> Optional[dict]:
    """사용자 토큰 검증"""
    return firebase_config.verify_auth_token(token)