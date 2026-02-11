"""
뭉 관련 데이터 모델
- 뭉 인스턴스
- 성장 데이터
- 외형 정보
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum

class MoongPersona(str, Enum):
    """뭉 페르소나 타입"""
    PET = "pet"      # 애완동물
    MATE = "mate"    # 동료/친구
    GUIDE = "guide"  # 가이드/멘토

class MoongStage(int, Enum):
    """뭉 성장 단계"""
    SEED = 1      # 씨앗기 (1~7일)
    SPROUT = 2    # 새싹기 (8~14일)
    GROWTH = 3    # 성장기 (15~24일)
    MATURE = 4    # 성숙기 (25~30일)

class MoongAppearance(BaseModel):
    """뭉 외형 정보"""
    appearance_type: str = "solid"  # solid, gradient
    base_color: str = "#90EE90"
    gradient_colors: Optional[Dict[str, str]] = None
    time_period: str = "day"  # day, night
    dominant_emotion: str = "TRUST"
    opacity: float = 1.0

class MoongStatus(str, Enum):
    """뭉 상태"""
    GROWING = "growing"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class Moong(BaseModel):
    """뭉 인스턴스 모델"""
    moong_id: str
    user_id: str
    slot_number: int = Field(ge=1, le=3)
    name: str
    persona: MoongPersona
    
    # 성장 관련
    created_at: datetime
    current_stage: MoongStage = MoongStage.SEED
    total_exp: int = 0
    daily_exp: int = 0
    conversation_count: int = 0
    
    # 상호작용 관련
    last_interaction: datetime
    six_hour_timer: datetime
    
    # 외형 관련
    appearance: MoongAppearance = MoongAppearance()
    equipped_items: List[str] = []
    
    # 상태
    status: MoongStatus = MoongStatus.GROWING
    force_graduation_date: datetime  # 생성일 + 30일

class ExpGainRequest(BaseModel):
    """경험치 획득 요청"""
    source: str  # conversation, care, auto
    amount: int = Field(ge=1, le=100)
    emotion_data: Optional[Dict[str, Any]] = None

class ConversationRequest(BaseModel):
    """대화 요청"""
    message: str = Field(min_length=1, max_length=1000)
    context: Optional[Dict[str, Any]] = None

class ConversationResponse(BaseModel):
    """대화 응답"""
    moong_response: str
    emotion_analysis: Dict[str, Any]
    exp_gained: int
    conversation_count: int
    updated_appearance: MoongAppearance

class MoongCreationRequest(BaseModel):
    """뭉 생성 요청"""
    name: str = Field(min_length=1, max_length=20)
    persona: MoongPersona

class MoongStatusResponse(BaseModel):
    """뭉 상태 응답"""
    moong_id: str
    name: str
    persona: str
    current_stage: int
    exp_progress: Dict[str, Any]
    conversation_progress: Dict[str, Any]
    appearance: MoongAppearance
    timer_status: Dict[str, Any]
    days_until_graduation: int
    equipped_items: List[str]

# 성장 관련 상수들
STAGE_EXP_THRESHOLDS = {
    1: 100,   # 씨앗기 -> 새싹기
    2: 400,   # 새싹기 -> 성장기  
    3: 800,   # 성장기 -> 성숙기
    4: 9999   # 성숙기 유지
}

STAGE_CONVERSATION_THRESHOLDS = {
    1: 10,   # 씨앗기: 10회 대화
    2: 30,   # 새싹기: 30회 대화
    3: 60,   # 성장기: 60회 대화
    4: 100   # 성숙기: 100회 대화
}