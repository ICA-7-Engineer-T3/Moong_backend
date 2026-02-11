"""
뭉 프로젝트 - LangGraph 워크플로우 정의
5턴 주기 페르소나 업데이트 플로우 구현
"""

from typing import Dict, List, Optional, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import asyncio

from .state_manager import PersonaUpdateState, session_manager
from .graph_nodes import (
    emotion_analysis_node,
    turn_router_node, 
    context_summarizer_node,
    ai_persona_updater_node,
    quest_manager_node,
    ui_displayer_node,
    basic_response_node
)

class PersonaUpdateGraph:
    """뭉 페르소나 업데이트 LangGraph 워크플로우"""
    
    def __init__(self):
        self.graph = None
        self.memory = MemorySaver()
        self._build_graph()
    
    def _build_graph(self):
        """LangGraph 워크플로우 구성"""
        print("🏗️  LangGraph 워크플로우 구성 중...")
        
        # StateGraph 생성
        workflow = StateGraph(PersonaUpdateState)
        
        # === 노드 추가 ===
        workflow.add_node("emotion_analysis", emotion_analysis_node)
        workflow.add_node("turn_router", turn_router_node)
        workflow.add_node("context_summarizer", context_summarizer_node)
        workflow.add_node("ai_persona_updater", ai_persona_updater_node)
        workflow.add_node("quest_manager", quest_manager_node)
        workflow.add_node("ui_displayer", ui_displayer_node)
        workflow.add_node("basic_response", basic_response_node)
        
        # === 시작점 설정 ===
        workflow.set_entry_point("emotion_analysis")
        
        # === 엣지 정의 (조건부 라우팅) ===
        
        # 감정 분석 → 턴 라우터
        workflow.add_edge("emotion_analysis", "turn_router")
        
        # 턴 라우터 → 조건부 분기 (핵심 로직)
        def route_after_turn_analysis(state: PersonaUpdateState) -> Literal["context_summarizer", "basic_response", END]:
            """3턴 주기에 따른 라우팅 결정"""
            if state.should_update_persona():
                print(f"   🔀 라우팅: context_summarizer (3턴 도달)")
                return "context_summarizer"
            else:
                # [최적화] 분석 전용 모드일 경우, 기본 응답 생성 생략
                if state.analysis_only_mode:
                    print(f"   🔀 라우팅: END (분석 모드 - 응답 생성 생략)")
                    return END
                
                print(f"   🔀 라우팅: basic_response (3턴 미도달)")
                return "basic_response"
        
        workflow.add_conditional_edges(
            "turn_router",
            route_after_turn_analysis,
            {
                "context_summarizer": "context_summarizer",
                "basic_response": "basic_response",
                END: END
            }
        )
        
        # === 3턴 도달시 플로우 (AI 페르소나 업데이트) ===
        # 맥락 요약 → AI 페르소나 업데이터
        workflow.add_edge("context_summarizer", "ai_persona_updater")
        
        # AI 페르소나 업데이터 → 퀘스트 매니저
        workflow.add_edge("ai_persona_updater", "quest_manager")
        
        # 퀘스트 매니저 → UI 표시
        workflow.add_edge("quest_manager", "ui_displayer")
        
        # === 종료 지점 ===
        # 기본 응답 → 종료
        workflow.add_edge("basic_response", END)
        
        # UI 표시 → 종료  
        workflow.add_edge("ui_displayer", END)
        
        # 그래프 컴파일
        self.graph = workflow.compile(checkpointer=self.memory)
        print("✅ LangGraph 워크플로우 구성 완료!")
    
    async def process_message(self, user_message: str, session_id: str = "default", mode: str = "full", pre_generated_response: str = "", moong1_emotion_data: dict = None) -> Dict:
        """
        메시지 처리 및 상태 업데이트 실행
        mode: 'full' (답변생성 포함), 'analysis_only' (답변생성 생략)
        pre_generated_response: analysis_only 모드일 때, 외부에서 생성된 답변을 대화 이력에 기록
        moong1_emotion_data: MOONG-1의 RAG 기반 구체적 감정 분석 결과 (primary_emotions, emotion_summary 등)
        """
        print(f"🎯 메시지 처리 시작: '{user_message}' (세션: {session_id}, 모드: {mode})")
        
        # 세션 상태 가져오기
        state = session_manager.get_or_create_session(session_id)
        
        # 사용자 메시지 설정
        state.current_user_message = user_message
        state.analysis_only_mode = (mode == "analysis_only")
        
        # MOONG-1의 감정 분석 결과 주입
        if moong1_emotion_data:
            state.moong1_emotion_data = moong1_emotion_data
            print(f"   🎯 [DEBUG] MOONG-1 감정 데이터 주입됨: {list(moong1_emotion_data.keys())}")
        else:
            print(f"   ⚠️ [DEBUG] MOONG-1 감정 데이터 없음")
        
        # [중요] Analysis Mode에서는 대화 이력에 봇 응답을 미리 채우지 않음 (Engine A가 함) -> 수정: 외부 답변이 있으면 채움
        # LangGraph 로직 흐름상 사용자 턴 기록
        initial_bot_response = pre_generated_response if mode == "analysis_only" else ""
        state.add_conversation_turn(user_message, initial_bot_response)
        
        print(f"📊 현재 턴: {state.turn_count} | 다음 업데이트: {3 - (state.turn_count % 3)}턴 후")
        
        # LangGraph 실행
        try:
            config = {"configurable": {"thread_id": session_id}}
            
            final_state = await self.graph.ainvoke(state, config)
            
            # LangGraph 반환값이 dict일 경우 처리
            if isinstance(final_state, dict):
                # dict에서 state 정보 추출
                for key, value in final_state.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
                final_state = state
            
            # 최종 응답 설정 (MOONG-1이 이미 응답을 생성했으므로 여기서는 불필요)
            # MOONG-2는 백그라운드 상태 관리만 담당
            if not final_state.final_response:
                final_state.final_response = "[MOONG-2 분석 완료]"
            
            # 대화 이력 업데이트
            if final_state.conversation_history:
                final_state.conversation_history[-1]["ai"] = final_state.final_response
            
            # 세션 상태 업데이트
            session_manager.sessions[session_id] = final_state
            
            print(f"✅ 메시지 처리 완료: 사용자 입력 '{final_state.current_user_message[:30]}...'")

            
            # 페르소나 업데이트 상세 로그 추출
            workflow_log = None
            if final_state.turn_count % 3 == 0 and final_state.persona_evolution_log:
                last_log = final_state.persona_evolution_log[-1]
                workflow_log = last_log.get("ai_decision", {})
                
                # 프론트엔드 포맷으로 변환용 데이터 추가
                workflow_log['changes'] = workflow_log.get("changes", [])
                workflow_log['reasoning'] = workflow_log.get("reasoning", "")
                workflow_log['context_summary'] = last_log.get("context_summary", "요약 없음")
                
                # 비교 분석을 위한 이전 데이터 추적
                workflow_log['previous_instruction'] = last_log.get("previous_instruction", "초기 설정")
                
                # 대화 요약 추가
                workflow_log['context_summary'] = last_log.get("context_summary", "요약 없음")
            
            return {
                "success": True,
                "response": final_state.final_response,
                "turn": final_state.turn_count,
                "persona_updated": final_state.turn_count % 3 == 0,
                "emotion_detected": final_state.sentiment_log[-1]["emotion"] if final_state.sentiment_log else "중립",
                "next_update_in": 3 - (final_state.turn_count % 3) if final_state.turn_count % 3 != 0 else 3,
                "persona_workflow_result": workflow_log
            }
            
        except Exception as e:
            print(f"❌ LangGraph 실행 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "죄송해요, 일시적인 오류가 발생했어요. 다시 시도해주세요!"
            }
    
    async def get_session_status(self, session_id: str = "default") -> Dict:
        """세션 상태 조회"""
        if session_id not in session_manager.sessions:
            return {"error": "세션을 찾을 수 없습니다"}
        
        state = session_manager.sessions[session_id]
        
        return {
            "session_id": session_id,
            "current_turn": state.turn_count,
            "total_conversations": len(state.conversation_history),
            "current_persona": "메이트 뭉",  # Week 3에서 동적으로 변경
            "emotion_history": state.sentiment_log[-5:],  # 최근 5턴
            "next_update_in": 5 - (state.turn_count % 5) if state.turn_count % 5 != 0 else 5,
            "persistent_emotion_flag": state.persistent_emotion_flag,
            "last_update_turn": state.last_update_turn
        }

# 전역 그래프 인스턴스
persona_graph = PersonaUpdateGraph()

# === 테스트 함수 ===
async def test_workflow():
    """워크플로우 전체 테스트"""
    print("🧪 LangGraph 워크플로우 테스트 시작...")
    
    test_messages = [
        "안녕 뭉아!",
        "오늘 기분 좋아!",
        "뭐 하고 있었어?", 
        "심심해서 왔어",
        "5턴째야! 업데이트 되나?"  # 5턴째 - 페르소나 업데이트 트리거
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n--- 테스트 턴 {i} ---")
        result = await persona_graph.process_message(message, "test_session")
        
        if result["success"]:
            print(f"응답: {result['response']}")
            print(f"감정: {result['emotion_detected']}")
            print(f"업데이트됨: {result['persona_updated']}")
        else:
            print(f"오류: {result['error']}")
        
        # 세션 상태 확인
        if i == 5:  # 5턴째 상태 확인
            status = await persona_graph.get_session_status("test_session")
            print(f"\n📊 5턴째 세션 상태:")
            print(f"   총 대화: {status['total_conversations']}")
            print(f"   마지막 업데이트: {status['last_update_turn']}")
    
    print("\n🎉 워크플로우 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_workflow())