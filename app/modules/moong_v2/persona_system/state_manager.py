"""
뭉 프로젝트 - 초개인화 페르소나 업데이트 시스템
LangGraph State 객체 및 기본 구조 정의
"""

from typing import Dict, List, Optional, Annotated
from pydantic import BaseModel, Field
from datetime import datetime
import os

# 메이트 뭉 기본 페르소나 정의 (변경 불가 핵심 정체성)
MATE_MOONG_BASE = """😎 [페르소나 2] 메이트 뭉 (Mate Moong)

당신은 사용자의 단짝 친구 '메이트 뭉'입니다.

* 핵심 설정: Temperature 0.7 / 에너지 부스터
* 지침:
    1. 호칭: {닉네임} 혹은 야, 너라고 편하게 부르세요.
    2. 말투: 자연스럽고 친근한 반말을 사용하세요. 답변 끝에는 반드시 질문을 포함하세요.
    3. 미션: 자기 경험을 덧붙여 티키타카를 만드세요.
    4. 제약: 너무 진지해지지 마세요. 즐거운 에너지를 유지합니다.

* MBTI: ENFP (에너지 넘치고 친근한 성격)
* 말투 특성: 친근한 반말, 자연스러운 표현, 질문으로 마무리
* 에너지 레벨: 높음 (7/10)
"""

class PersonaUpdateState(BaseModel):
    """
    LangGraph에서 사용할 전체 상태 객체
    개발 정의서 1.1 항목 완전 구현
    """
    
    # [NEW] Analysis Mode Flag
    # True인 경우, 답변 생성(Generator) 단계를 생략하고 상태 분석/업데이트만 진행함
    analysis_only_mode: bool = Field(default=False, description="답변 생성 생략 모드")
    
    # [NEW] MOONG-1 감정 분석 결과
    moong1_emotion_data: Dict = Field(default_factory=dict, description="MOONG-1의 RAG 기반 구체적 감정 분석 결과")

    # === 턴 관리 ===
    turn_count: int = Field(default=1, description="1부터 시작, 5턴마다 리셋")
    session_id: str = Field(default="default", description="세션 식별자")
    
    # === 감정 및 대화 데이터 ===
    sentiment_log: List[Dict] = Field(default_factory=list, description="매턴 감정 분석 결과 누적")
    conversation_history: List[Dict] = Field(default_factory=list, description="사용자↔AI 대화 이력")
    context_summary: str = Field(default="", description="최근 5턴 압축 요약")
    
    # === 페르소나 관리 ===
    current_instruction: str = Field(default=MATE_MOONG_BASE, description="현재 적용중인 지침")
    persona_evolution_log: List[Dict] = Field(default_factory=list, description="AI 업데이트 이력")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="마지막 업데이트 시간")
    
    # === 장기 패턴 추적 ===
    persistent_emotion_flag: bool = Field(default=False, description="부정감정 5회 이상 지속시 True")
    negative_emotion_count: int = Field(default=0, description="부정감정 연속 카운트")
    
    # === AI 결정 추적 ===
    ai_reasoning_history: List[Dict] = Field(default_factory=list, description="AI의 판단 근거 로그")
    last_update_turn: int = Field(default=0, description="마지막 페르소나 업데이트 턴")
    
    # === 시스템 상태 ===
    current_node: str = Field(default="start", description="현재 실행중인 노드")
    node_execution_log: List[Dict] = Field(default_factory=list, description="노드 실행 이력")
    
    # === 사용자 메시지 ===
    current_user_message: str = Field(default="", description="현재 처리중인 사용자 메시지")
    final_response: str = Field(default="", description="최종 AI 응답")
    
    def add_conversation_turn(self, user_message: str, ai_response: str = ""):
        """대화 턴 추가 및 턴 카운트 증가"""
        self.conversation_history.append({
            "turn": self.turn_count,
            "timestamp": datetime.now().isoformat(),
            "user": user_message,
            "ai": ai_response
        })
        self.turn_count += 1
    
    def add_sentiment_analysis(self, emotion_data: Dict):
        """감정 분석 결과 추가"""
        emotion_entry = {
            "turn": self.turn_count,
            "timestamp": datetime.now().isoformat(),
            **emotion_data
        }
        self.sentiment_log.append(emotion_entry)
        
        # 부정감정 연속 카운트 업데이트
        if emotion_data.get("valence", 0) < 0.3:  # 부정감정 기준
            self.negative_emotion_count += 1
        else:
            self.negative_emotion_count = 0
            
        # 지속 플래그 업데이트
        self.persistent_emotion_flag = self.negative_emotion_count >= 5
    
    def log_node_execution(self, node_name: str, execution_data: Dict = None):
        """노드 실행 로그 추가"""
        log_entry = {
            "node": node_name,
            "turn": self.turn_count,
            "timestamp": datetime.now().isoformat(),
            "data": execution_data or {}
        }
        self.node_execution_log.append(log_entry)
        self.current_node = node_name
    
    def should_update_persona(self) -> bool:
        """3턴 주기 페르소나 업데이트 여부 확인"""
        return self.turn_count % 3 == 0
    
    def get_recent_conversations(self, count: int = 5) -> List[Dict]:
        """최근 N턴 대화 이력 반환"""
        return self.conversation_history[-count:] if len(self.conversation_history) >= count else self.conversation_history
    
    def get_recent_emotions(self, count: int = 5) -> List[Dict]:
        """최근 N턴 감정 분석 결과 반환"""
        return self.sentiment_log[-count:] if len(self.sentiment_log) >= count else self.sentiment_log

class NodeExecutionResult(BaseModel):
    """노드 실행 결과 표준 형식"""
    success: bool = True
    message: str = ""
    data: Dict = Field(default_factory=dict)
    next_node: Optional[str] = None
    error: Optional[str] = None

# 세션 관리
class SessionManager:
    """세션별 상태 관리 클래스"""
    
    def __init__(self):
        self.sessions: Dict[str, PersonaUpdateState] = {}
    
    def get_or_create_session(self, session_id: str) -> PersonaUpdateState:
        """세션 가져오기 또는 새로 생성"""
        if session_id not in self.sessions:
            self.sessions[session_id] = PersonaUpdateState(session_id=session_id)
            print(f"🆕 새 세션 생성: {session_id}")
        return self.sessions[session_id]
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """오래된 세션 정리 (추후 구현)"""
        pass

# 전역 세션 매니저
session_manager = SessionManager()

if __name__ == "__main__":
    # State 객체 테스트
    print("🧪 PersonaUpdateState 테스트 시작...")
    
    # 기본 상태 생성
    state = PersonaUpdateState()
    print(f"✅ 초기 턴: {state.turn_count}")
    print(f"✅ 기본 지침: {state.current_instruction[:50]}...")
    
    # 대화 추가 테스트
    state.add_conversation_turn("안녕 뭉아!", "안녕! 오늘 뭐 했어?")
    print(f"✅ 대화 추가 후 턴: {state.turn_count}")
    
    # 감정 분석 추가 테스트
    state.add_sentiment_analysis({
        "emotion": "기쁨",
        "confidence": 0.8,
        "valence": 0.7
    })
    print(f"✅ 감정 로그 개수: {len(state.sentiment_log)}")
    
    # 5턴 업데이트 체크
    for i in range(4):
        state.add_conversation_turn(f"메시지 {i+2}", f"응답 {i+2}")
    
    print(f"✅ 5턴 도달: {state.should_update_persona()}")
    print(f"✅ 현재 턴: {state.turn_count}")
    
    print("🎉 State 객체 테스트 완료!")

# PersonaUpdateState 클래스에 추가 메서드들
def add_detailed_status_methods(cls):
    """PersonaUpdateState 클래스에 상세 상태 조회 메서드들 추가"""
    
    def get_detailed_persona_status(self) -> Dict:
        """현재 페르소나 상태를 상세히 반환"""
        
        # 현재 지침에서 MBTI 추출 (간단한 패턴 매칭)
        current_mbti = "알 수 없음"
        if "ENFP" in self.current_instruction:
            current_mbti = "ENFP"
        elif "ISFJ" in self.current_instruction:
            current_mbti = "ISFJ"
        elif "ENTJ" in self.current_instruction:
            current_mbti = "ENTJ"
        # 다른 MBTI 타입들도 추가 가능
        
        return {
            "페르소나_상태": {
                "현재_턴": self.turn_count,
                "세션_ID": self.session_id,
                "마지막_업데이트_턴": self.last_update_turn,
                "다음_업데이트까지": 5 - (self.turn_count % 5) if self.turn_count % 5 != 0 else 5
            },
            "현재_지침": {
                "지침_내용": self.current_instruction,
                "지침_길이": len(self.current_instruction),
                "추출된_MBTI": current_mbti,
                "마지막_수정시간": self.updated_at
            },
            "감정_분석_현황": {
                "총_분석_횟수": len(self.sentiment_log),
                "부정감정_연속_횟수": self.negative_emotion_count,
                "부정감정_지속_플래그": self.persistent_emotion_flag,
                "최근_5턴_감정": [log.get("emotion", "알 수 없음") for log in self.sentiment_log[-5:]]
            },
            "페르소나_진화_이력": {
                "총_업데이트_횟수": len(self.persona_evolution_log),
                "업데이트_이력": self.persona_evolution_log[-3:] if self.persona_evolution_log else [],  # 최근 3개만
                "AI_판단_이력": self.ai_reasoning_history[-3:] if self.ai_reasoning_history else []
            },
            "대화_현황": {
                "총_대화_수": len(self.conversation_history),
                "현재_컨텍스트_요약": self.context_summary or "아직 요약 없음",
                "최근_대화": self.conversation_history[-2:] if self.conversation_history else []
            }
        }
    
    def get_persona_update_analysis(self, new_instruction: str, reasoning: str) -> Dict:
        """페르소나 업데이트 변화 분석"""
        old_instruction = self.current_instruction
        
        # 변화 분석
        changes_detected = {
            "지침_길이_변화": len(new_instruction) - len(old_instruction),
            "주요_키워드_변화": self._analyze_keyword_changes(old_instruction, new_instruction),
            "말투_변화": self._analyze_tone_changes(old_instruction, new_instruction),
            "새로운_MBTI": self._extract_mbti(new_instruction),
            "이전_MBTI": self._extract_mbti(old_instruction)
        }
        
        return {
            "업데이트_정보": {
                "업데이트_턴": self.turn_count,
                "업데이트_시간": datetime.now().isoformat(),
                "업데이트_근거": reasoning,
                "변화_트리거": f"턴 {self.turn_count}: {self.sentiment_log[-1].get('emotion', '알 수 없음') if self.sentiment_log else '초기값'}"
            },
            "변화_분석": changes_detected,
            "이전_vs_새로운": {
                "이전_지침": old_instruction[:200] + "..." if len(old_instruction) > 200 else old_instruction,
                "새로운_지침": new_instruction[:200] + "..." if len(new_instruction) > 200 else new_instruction,
                "변화_요약": f"지침이 {len(new_instruction) - len(old_instruction):+d}자 변경되었으며, AI 분석에 따라 {reasoning[:100]}..."
            },
            "영향_예측": {
                "예상_말투_변화": changes_detected["말투_변화"],
                "예상_반응_변화": "더 공감적" if "공감" in reasoning else "더 활발함" if "에너지" in reasoning else "미세 조정",
                "적용_시점": f"다음 대화(턴 {self.turn_count + 1})부터"
            }
        }
    
    def _analyze_keyword_changes(self, old_text: str, new_text: str) -> List[str]:
        """지침의 키워드 변화 분석"""
        old_keywords = set(old_text.lower().split())
        new_keywords = set(new_text.lower().split())
        
        added = list(new_keywords - old_keywords)[:5]  # 최대 5개
        removed = list(old_keywords - new_keywords)[:5]  # 최대 5개
        
        changes = []
        if added:
            changes.append(f"추가된 키워드: {', '.join(added)}")
        if removed:
            changes.append(f"제거된 키워드: {', '.join(removed)}")
            
        return changes or ["키워드 변화 없음"]
    
    def _analyze_tone_changes(self, old_text: str, new_text: str) -> str:
        """말투 변화 분석"""
        tone_indicators = {
            "친근함": ["친구", "편하게", "반말", "야", "너"],
            "정중함": ["존댓말", "님", "습니다", "요"],
            "활발함": ["ㅋㅋ", "!", "에너지", "신나게"],
            "차분함": ["차근차근", "천천히", "신중하게"]
        }
        
        old_tones = []
        new_tones = []
        
        for tone, words in tone_indicators.items():
            if any(word in old_text for word in words):
                old_tones.append(tone)
            if any(word in new_text for word in words):
                new_tones.append(tone)
        
        if old_tones == new_tones:
            return "말투 변화 없음"
        else:
            return f"{'/'.join(old_tones) or '기본'} → {'/'.join(new_tones) or '기본'}"
    
    def _extract_mbti(self, text: str) -> str:
        """텍스트에서 MBTI 추출"""
        mbti_types = ["ENFP", "ISFJ", "ENTJ", "INFP", "ESTJ", "ISTP", "ENFJ", "ISFP", 
                     "ENTP", "ISTJ", "ESFJ", "INTP", "ESTP", "INFJ", "ESFP", "INTJ"]
        
        for mbti in mbti_types:
            if mbti in text:
                return mbti
        return "미지정"
    
    # 클래스에 메서드들 추가
    cls.get_detailed_persona_status = get_detailed_persona_status
    cls.get_persona_update_analysis = get_persona_update_analysis
    cls._analyze_keyword_changes = _analyze_keyword_changes
    cls._analyze_tone_changes = _analyze_tone_changes
    cls._extract_mbti = _extract_mbti
    
    return cls

# PersonaUpdateState에 메서드들 추가
PersonaUpdateState = add_detailed_status_methods(PersonaUpdateState)

class PersonaStateManager:
    """페르소나 상태 관리를 위한 메인 매니저 클래스"""
    
    def __init__(self):
        self.session_manager = session_manager
        self.default_persona = MATE_MOONG_BASE
        
    def get_session_state(self, session_id: str = "default") -> PersonaUpdateState:
        """세션별 상태 객체 반환"""
        return self.session_manager.get_or_create_session(session_id)
    
    def get_detailed_status(self, session_id: str = "default") -> Dict:
        """상세한 페르소나 상태 정보 반환"""
        state = self.get_session_state(session_id)
        return state.get_detailed_persona_status()
    
    def get_detailed_persona_status(self, session_id: str = "default") -> Dict:
        """get_detailed_status와 동일한 메서드 (호환성을 위해 추가)"""
        return self.get_detailed_status(session_id)
    
    def update_persona(self, session_id: str, new_instruction: str, reasoning: str) -> Dict:
        """페르소나 업데이트 및 분석 정보 반환"""
        state = self.get_session_state(session_id)
        
        # 변화 분석
        analysis = state.get_persona_update_analysis(new_instruction, reasoning)
        
        # 실제 업데이트
        state.current_instruction = new_instruction
        state.last_update_turn = state.turn_count
        state.updated_at = datetime.now().isoformat()
        
        # 업데이트 로그 추가
        state.persona_evolution_log.append({
            "turn": state.turn_count,
            "timestamp": datetime.now().isoformat(),
            "previous_instruction": analysis["이전_vs_새로운"]["이전_지침"],
            "new_instruction": new_instruction,
            "reasoning": reasoning,
            "changes": analysis["변화_분석"]
        })
        
        return analysis
    
    def add_conversation(self, session_id: str, user_message: str, ai_response: str = "") -> Dict:
        """대화 추가 및 기본 정보 반환"""
        state = self.get_session_state(session_id)
        state.add_conversation_turn(user_message, ai_response)
        
        return {
            "turn_added": state.turn_count - 1,
            "should_update_persona": state.should_update_persona(),
            "current_turn": state.turn_count
        }
    
    def add_sentiment(self, session_id: str, emotion_data: Dict) -> Dict:
        """감정 분석 결과 추가"""
        state = self.get_session_state(session_id)
        state.add_sentiment_analysis(emotion_data)
        
        return {
            "emotion_added": emotion_data,
            "negative_count": state.negative_emotion_count,
            "persistent_flag": state.persistent_emotion_flag
        }
    
    def get_current_instruction(self, session_id: str = "default") -> str:
        """현재 지침 반환"""
        state = self.get_session_state(session_id)
        return state.current_instruction
    
    def reset_session(self, session_id: str) -> Dict:
        """세션 초기화"""
        if session_id in self.session_manager.sessions:
            del self.session_manager.sessions[session_id]
        
        new_state = self.get_session_state(session_id)
        return {
            "session_reset": True,
            "new_session_id": session_id,
            "initial_turn": new_state.turn_count
        }