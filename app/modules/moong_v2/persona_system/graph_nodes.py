"""
뭉 프로젝트 - LangGraph 노드 기본 구조
개발 정의서 1.2 항목 - 6개 노드 정의 (빈 함수 구조)
"""

from typing import Dict, Any, List
from datetime import datetime
import asyncio
import json

from .state_manager import PersonaUpdateState, NodeExecutionResult, MATE_MOONG_BASE
from .llm_client import LLMClient

# LLM 클라이언트 인스턴스 (Lazy Initialization handled by class)
llm_client = LLMClient()

def _get_structured_persona(state: PersonaUpdateState) -> Dict:
    """State에서 구조화된 페르소나 추출 (없으면 기본값)"""
    # 마지막 업데이트 확인
    if state.persona_evolution_log:
        last_update = state.persona_evolution_log[-1].get("ai_decision", {}).get("persona_update")
        if last_update:
            return last_update
            
    # 기본 메이트 뭉 값 반환
    return {
        "persona_type": "단짝 친구 '메이트 뭉'",
        "mbti": "ENFP",
        "temperature": 0.7,
        "energy_level": 0.8,
        "formality": 0.3,
        "talking_style": "친근한 짧은 반말",
        "nickname": "뭉",
        "guidelines": {
            "호칭": "닉네임 또는 야, 너로 편하게",
            "말투": "친근한 반말 사용",
            "미션": "자기 경험을 덧붙여 티키타카",
            "특징": "답변 끝에 반드시 질문 포함",
            "제약": "너무 진지하지 않게, 즐거운 에너지 유지"
        }
    }

def _format_history(history: List[Dict]) -> List[str]:
    """대화 기록 포맷팅"""
    formatted = []
    for h in history:
        if h.get("user"):
            formatted.append(f"User: {h['user']}")
        if h.get("ai"):
            formatted.append(f"AI: {h['ai']}")
    return formatted

# === Node 1: Testing-Scanner (감정 분석) ===
async def emotion_analysis_node(state: PersonaUpdateState) -> PersonaUpdateState:
    """
    감정 분석 - MOONG-1의 RAG 결과를 우선 사용
    """
    print(f"🔍 Node 1: 감정 분석 중... (Turn {state.turn_count})")
    
    # 🐛 디버깅: MOONG-1 데이터 확인
    print(f"   🐛 [DEBUG] moong1_emotion_data 존재: {bool(state.moong1_emotion_data)}")
    if state.moong1_emotion_data:
        print(f"   🐛 [DEBUG] 데이터 키: {list(state.moong1_emotion_data.keys())}")
        print(f"   🐛 [DEBUG] primary_emotions: {state.moong1_emotion_data.get('primary_emotions')}")
    
    # MOONG-1의 구체적 감정 분석 결과가 있으면 우선 사용
    if state.moong1_emotion_data and state.moong1_emotion_data.get('primary_emotions'):
        primary_emotions = state.moong1_emotion_data.get('primary_emotions', {})
        
        # 구체적 감정들 추출
        all_emotions = []
        for level, emotions in primary_emotions.items():
            all_emotions.extend(emotions)
        
        # 주요 감정 (첫 번째)
        main_emotion = all_emotions[0] if all_emotions else "중립"
        
        emotion_data = {
            "emotion": main_emotion,
            "all_emotions": all_emotions,
            "confidence": 0.9,
            "valence": 0.3 if any(neg in main_emotion for neg in ['슬픔', '우울', '화남', '불안', '속상']) else 0.7,
            "arousal": 0.6,
            "analysis_method": "MOONG-1_RAG",
            "emotion_summary": state.moong1_emotion_data.get('emotion_summary', {})
        }
        
        print(f"   ✅ MOONG-1 감정 사용: {main_emotion} (전체: {', '.join(all_emotions[:3])})")
    else:
        # Fallback: 키워드 기반 분석
        message = state.current_user_message.lower()
        
        positive_keywords = ['좋아', '행복', '기쁘', '즐거', '감사', '최고', '완벽', '사랑', '웃', '재미']
        negative_keywords = ['슬프', '우울', '힘들', '화나', '짜증', '싫어', '지쳐', '피곤', '답답', '외로', '싸우', '망쳤', '실패']
        
        positive_count = sum(1 for word in positive_keywords if word in message)
        negative_count = sum(1 for word in negative_keywords if word in message)
        
        if positive_count > negative_count:
            emotion = "긍정"
            valence = 0.7
        elif negative_count > positive_count:
            emotion = "부정"
            valence = 0.3
        else:
            emotion = "중립"
            valence = 0.5
        
        emotion_data = {
            "emotion": emotion,
            "confidence": 0.6,
            "valence": valence,
            "arousal": 0.5,
            "analysis_method": "keyword_fallback"
        }
        
        print(f"   ⚠️ Fallback 감정 분석: {emotion} (Valence: {valence})")
    
    state.add_sentiment_analysis(emotion_data)
    state.log_node_execution("emotion_analysis", {
        "emotion_detected": emotion_data["emotion"],
        "confidence": emotion_data["confidence"],
        "method": emotion_data["analysis_method"]
    })
    
    return state

# === Node 2: Turn-Router (3턴 주기 분기) ===
async def turn_router_node(state: PersonaUpdateState) -> PersonaUpdateState:
    """
    3턴 주기로 페르소나 업데이트 여부 결정
    """
    print(f"🔀 Node 2: 턴 라우팅... (Turn {state.turn_count})")
    
    should_update = state.should_update_persona()
    
    if should_update:
        next_route = "context_summarizer"
        message = f"3턴 도달! 페르소나 업데이트 플로우 시작"
        print(f"   ✨ {message}")
    else:
        next_route = "basic_response"
        turns_left = 3 - (state.turn_count % 3)
        message = f"기본 응답 모드 (업데이트까지 {turns_left}턴 남음)"
        print(f"   📝 {message}")
    
    state.log_node_execution("turn_router", {
        "should_update": should_update,
        "next_route": next_route,
        "turns_to_update": 3 - (state.turn_count % 3) if not should_update else 0
    })
    
    return state

# === Node 3: Moong-Summarizer (맥락 압축) ===
async def context_summarizer_node(state: PersonaUpdateState) -> PersonaUpdateState:
    """
    최근 3턴 대화를 실제 내용 기반으로 요약
    """
    print(f"📄 Node 3: 맥락 요약 중... (Turn {state.turn_count})")
    
    recent_conversations = state.get_recent_conversations(3)
    recent_emotions = state.get_recent_emotions(3)
    
    # 실제 대화 내용 기반 요약
    conversation_texts = []
    for conv in recent_conversations:
        if conv.get('user'):
            conversation_texts.append(f"사용자: {conv['user']}")
        if conv.get('ai'):
            conversation_texts.append(f"뭉: {conv['ai']}")
    
    emotion_summary = ""
    if recent_emotions:
        emotion_counts = {}
        for e in recent_emotions:
            emotion = e.get('emotion', '중립')
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        dominant_emotion = max(emotion_counts, key=emotion_counts.get)
        emotion_summary = f" 주요 감정: {dominant_emotion}."
    
    context_summary = f"""최근 {len(recent_conversations)}턴 대화 내용:
{chr(10).join(conversation_texts[-6:])}
{emotion_summary}"""
    
    state.context_summary = context_summary.strip()
    state.log_node_execution("context_summarizer", {
        "conversations_analyzed": len(recent_conversations),
        "emotions_analyzed": len(recent_emotions),
        "summary_length": len(context_summary)
    })
    
    print(f"   요약 완료: {len(recent_conversations)}턴, {len(conversation_texts)}개 메시지 분석")
    return state

# === Node 4: Persona-Selector (AI 페르소나 업데이터) ⭐ ===
async def ai_persona_updater_node(state: PersonaUpdateState) -> PersonaUpdateState:
    """
    DeepSeek API 2단계 호출로 페르소나 업데이트 및 답변 생성
    """
    print(f"🤖 Node 4: AI 페르소나 업데이트... (Turn {state.turn_count})")
    
    current_persona = _get_structured_persona(state)
    
    # 1. 페르소나 분석 및 업데이트 (LLM 호출)
    analysis_result = await llm_client.analyze_persona(
        user_message=state.current_user_message,
        current_persona=current_persona
    )
    
    if analysis_result["success"]:
        # 업데이트 반영
        new_persona_update = analysis_result["persona_update"]
        reasoning = analysis_result["reasoning"]
        changes = analysis_result["changes"]
        
        # 로그 기록
        state.persona_evolution_log.append({
            "turn": state.turn_count,
            "timestamp": datetime.now().isoformat(),
            "ai_decision": analysis_result,
            "previous_instruction": state.current_instruction,
            "context_summary": state.context_summary
        })
        
        # 지침 텍스트 업데이트 (UI 표시용)
        guidelines_txt = "\n".join([f"- {k}: {v}" for k,v in new_persona_update.get("guidelines", {}).items()])
        new_instruction = f"""😎 [{new_persona_update.get('persona_type')}] {new_persona_update.get('nickname')}
        
* 핵심 설정: Temp {new_persona_update.get('temperature')} / Energy {new_persona_update.get('energy_level')}
* 지침:
{guidelines_txt}

* MBTI: {new_persona_update.get('mbti')}
* 말투: {new_persona_update.get('talking_style')}
"""
        state.current_instruction = new_instruction
        state.last_update_turn = state.turn_count
        
        # 2. 업데이트된 페르소나로 답변 생성 (LLM 호출)
        final_response = await llm_client.generate_response(
            user_message=state.current_user_message,
            updated_persona=new_persona_update,
            conversation_history=_format_history(state.conversation_history)
        )
        
        print(f"   AI 업데이트 및 응답 완료: {reasoning}")
        
    else:
        # 실패 시 기존 페르소나 유지 및 기본 응답
        print(f"   ⚠️ AI 분석 실패: {analysis_result.get('error')}")
        final_response = await llm_client.generate_response(
            user_message=state.current_user_message,
            updated_persona=current_persona,
            conversation_history=_format_history(state.conversation_history)
        )
        reasoning = "API 오류로 업데이트 건너뜀"
        changes = []

    state.final_response = final_response
    
    state.log_node_execution("ai_persona_updater", {
        "ai_decision_applied": analysis_result["success"],
        "changes_count": len(changes),
        "reasoning": reasoning
    })
    
    return state

# === Node 5: Quest-Manager (ReAct 기반 개입) ===
async def quest_manager_node(state: PersonaUpdateState) -> PersonaUpdateState:
    """
    persistent_emotion_flag 체크하여 행동 기반 퀘스트 추가
    Week 4에서 ReAct 로직 구현 예정
    """
    print(f"🎯 Node 5: 퀘스트 관리... (Turn {state.turn_count})")
    
    if state.persistent_emotion_flag:
        quest_added = "산책 퀘스트 추가 (더미)"
        print(f"   🚨 부정감정 지속 감지! {quest_added}")
    else:
        quest_added = "퀘스트 불필요"
        print(f"   ✅ 감정 상태 양호")
    
    state.log_node_execution("quest_manager", {
        "persistent_emotion_flag": state.persistent_emotion_flag,
        "negative_emotion_count": state.negative_emotion_count,
        "quest_added": quest_added
    })
    
    return state

# === Node 6: UI-Displayer (웹 시각화) ===
async def ui_displayer_node(state: PersonaUpdateState) -> PersonaUpdateState:
    """
    실시간 페르소나 상태를 웹으로 시각화
    Week 1에서 기본 구조, Week 4에서 실시간 업데이트 구현
    """
    print(f"🌐 Node 6: UI 업데이트... (Turn {state.turn_count})")
    
    ui_data = {
        "current_turn": state.turn_count,
        "next_update_in": 3 - (state.turn_count % 3) if not state.should_update_persona() else 0,
        "persona_status": "기본 메이트 뭉",
        "emotion_status": state.sentiment_log[-1]["emotion"] if state.sentiment_log else "중립",
        "last_update": state.last_update_turn
    }
    
    state.log_node_execution("ui_displayer", ui_data)
    
    print(f"   UI 데이터 준비 완료: Turn {ui_data['current_turn']}")
    return state

# === 기본 응답 노드 (3턴 미도달시 사용) ===
async def basic_response_node(state: PersonaUpdateState) -> PersonaUpdateState:
    """
    3턴 미도달시 현재 페르소나 지침으로 응답
    """
    print(f"💬 기본 응답 생성... (Turn {state.turn_count})")
    
    current_persona = _get_structured_persona(state)
    
    # LLM을 사용하여 응답 생성
    basic_response = await llm_client.generate_response(
        user_message=state.current_user_message,
        updated_persona=current_persona,
        conversation_history=_format_history(state.conversation_history)
    )
    
    state.final_response = basic_response
    state.log_node_execution("basic_response", {
        "response_type": "llm_generated",
        "response_length": len(basic_response)
    })
    
    print(f"   AI 응답 완료: {basic_response[:30]}...")
    return state

# === 노드 실행 함수 맵핑 ===
NODE_FUNCTIONS = {
    "emotion_analysis": emotion_analysis_node,
    "turn_router": turn_router_node,
    "context_summarizer": context_summarizer_node,
    "ai_persona_updater": ai_persona_updater_node,
    "quest_manager": quest_manager_node,
    "ui_displayer": ui_displayer_node,
    "basic_response": basic_response_node
}

async def execute_node(node_name: str, state: PersonaUpdateState) -> PersonaUpdateState:
    """노드 실행 래퍼 함수"""
    if node_name not in NODE_FUNCTIONS:
        raise ValueError(f"Unknown node: {node_name}")
    
    start_time = datetime.now()
    result_state = await NODE_FUNCTIONS[node_name](state)
    end_time = datetime.now()
    
    execution_time = (end_time - start_time).total_seconds()
    print(f"⏱️  {node_name} 실행 시간: {execution_time:.3f}초")
    
    return result_state

if __name__ == "__main__":
    # 노드 기본 구조 테스트
    print("🧪 LangGraph 노드 기본 구조 테스트...")
    
    async def test_nodes():
        from .state_manager import PersonaUpdateState
        
        state = PersonaUpdateState()
        state.current_user_message = "안녕하세요!"
        
        # 순차적으로 노드 실행 테스트
        print("\n=== Node 실행 테스트 ===")
        
        # 1. 감정 분석
        state = await execute_node("emotion_analysis", state)
        
        # 2. 턴 라우터 
        state = await execute_node("turn_router", state)
        
        # 3. 기본 응답 (5턴 미도달)
        state = await execute_node("basic_response", state)
        
        print(f"\n✅ 테스트 완료! 최종 턴: {state.turn_count}")
        print(f"✅ 실행된 노드 수: {len(state.node_execution_log)}")
    
    asyncio.run(test_nodes())