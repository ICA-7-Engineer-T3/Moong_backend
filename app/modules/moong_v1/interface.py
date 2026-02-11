
import os
import sqlite3
import pandas as pd
import numpy as np
import faiss
from collections import Counter
from typing import Annotated, List, Literal, Optional, TypedDict
import traceback

# [Modified] Using google.genai directly as requested
from google import genai
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END

from app.core.config import settings
from app.core.state_manager import state_manager

# ---------------------------------------------------------------------------
# 전역 리소스
# ---------------------------------------------------------------------------
llm = None
sbert_model = None
embeddings = None
index = None
df = None
workflow_app = None


# ---------------------------------------------------------------------------
# [New] Custom Gemini Wrapper for LangGraph Compatibility
# ---------------------------------------------------------------------------
class CustomGeminiWrapper:
    """
    Wraps google.genai.Client to accept .invoke() calls from LangGraph nodes.
    Mimics the behavior of ChatGoogleGenerativeAI but uses the verified custom connection.
    """
    def __init__(self, api_key: str, base_url: str, model: str):
        # DEBUG: Check what we are initializing with
        print(f"[DEBUG] CustomGeminiWrapper Init - Model: {model}, BaseURL: {base_url}, KeyPrefix: {api_key[:5]}...")
        
        # If the key starts with 'sk-' it is likely OpenAI/Proxy key.
        # google.genai.Client might behave unexpectedly if we force a base_url that it doesn't like.
        # We will try to pass base_url only if it is set and not empty
        http_options = {}
        if base_url:
            http_options["base_url"] = base_url
            
        try:
            self.client = genai.Client(
                api_key=api_key,
                http_options=http_options
            )
        except Exception as e:
            print(f"[DEBUG] Client Init Failed: {e}")
            raise e
            
        self.model = model

    def invoke(self, input_data) -> object:
        """
        Mimics LangChain's invoke method.
        Accepts: str or Message object
        Returns: Object with .content attribute
        """
        print(f"[DEBUG] Gemini Wrapper Invoke Start")
        
        # Convert input to string prompt
        prompt_str = str(input_data)
        
        # If input is a LangChain prompt object or Message, extract text
        if hasattr(input_data, "messages"): # ChatPromptValue
             prompt_str = input_data.to_string()
        elif hasattr(input_data, "content"): # BaseMessage
             prompt_str = input_data.content

        try:
            # Call Google GenAI
            print(f"[DEBUG] Sending Request to GenAI... (Length: {len(prompt_str)})")
            
            # Note: synchronous call might hang if network is issues
            response = self.client.models.generate_content(
                model=self.model, 
                contents=prompt_str
            )
            print(f"[DEBUG] Response Received type: {type(response)}")
            
            # Check valid text response
            result_text = response.text if response.text else ""
            
            # Return pseudo-AIMessage object with .content
            return type("GeminiResponse", (), {"content": result_text})
            
        except Exception as e:
            print(f"❌ Gemini Custom Client Error: {e}")
            traceback.print_exc()
            # Retrun empty content to prevent crash, let Guardrail/Logic handle it
            return type("GeminiResponse", (), {"content": f"Error generating response: {e}"})


# ---------------------------------------------------------------------------
# State 정의
# ---------------------------------------------------------------------------
class MoongState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    analyzer_output: str
    analyzer_rag_result: dict
    memory_context: str
    selected_persona: str
    context_guidelines: str  # [New] Dynamic guidelines from Firebase
    draft_answer: str
    guardrail_status: Literal["APPROVE", "REJECT"]
    review_feedback: str


# ---------------------------------------------------------------------------
# RAG 도구
# ---------------------------------------------------------------------------
def multi_emotion_analysis_agent_func(
    user_input: str,
    sbert_model,
    embeddings,
    index,
    df: pd.DataFrame,
) -> dict:
    """입력과 유사한 대화들의 감정 분포 분석, 복합 감정 리포트 및 유사 상황 리턴."""
    print(f"[DEBUG] RAG Analysis Start: {user_input[:20]}...")
    TOP_K = 30
    try:
        if sbert_model is None or index is None or df is None:
            print("[Warning] SBERT Model or Index not loaded. Skipping RAG.")
            return {"emotion_summary": {}, "primary_emotions": {}, "similar_situations": []}

        query_vec = sbert_model.encode([user_input]).astype("float32")
        _, indices = index.search(query_vec, TOP_K)

        found_middle_emotions = []
        found_low_emotions = []
        found_high_emotions = []
        found_single_turn_texts = []
        
        for i in indices[0]:
            if 0 <= i < len(df):
                row = df.iloc[i]
                middle = row["emotion_middle_class"]
                low = row["emotion_low_class"]
                high = row["emotion_high_class"]
                single_turn = row["sing_turn_text"]
                
                found_middle_emotions.append(middle if pd.notnull(middle) and str(middle).strip() != "" else "_없음")
                found_low_emotions.append(low if pd.notnull(low) and str(low).strip() != "" else "_없음")
                found_high_emotions.append(high if pd.notnull(high) and str(high).strip() != "" else "_없음")
                found_single_turn_texts.append(single_turn if pd.notnull(single_turn) else "")

        counters = {
            "middle": Counter(found_middle_emotions),
            "low": Counter(found_low_emotions),
            "high": Counter(found_high_emotions),
        }
        totals = {k: sum(v.values()) for k, v in counters.items()}

        emotion_summaries = {}
        primary_emotions = {}
        
        # 감정 레벨별 한글 이름 매핑
        level_names = {
            "high": "대분류",
            "middle": "중분류", 
            "low": "소분류"
        }
        
        for level in ["high", "middle", "low"]:
            report_list = []
            prim_emos = []
            total = totals[level]
            counter = counters[level]
            emo_counts = [(emo, cnt) for emo, cnt in counter.most_common() if emo != "_없음"]
            
            # 🐛 디버깅: 각 레벨의 감정 데이터 확인
            print(f"[DEBUG] Level '{level}': total={total}, emo_counts={emo_counts[:3]}")
            
            # 각 감정의 비율 계산 및 필터링
            for emo, cnt in emo_counts:
                percent = (cnt / total) * 100 if total > 0 else 0
                if percent >= 10:  # 10% 이상인 감정만 포함
                    report_list.append(f"{emo}({percent:.0f}%)")
                    prim_emos.append(emo)
            
            # [Safety fallback] 10% 이상인 감정이 없으면 가장 많이 나온 감정 1개 추가
            if not report_list and emo_counts:
                top_emo, top_cnt = emo_counts[0]
                top_percent = (top_cnt / total) * 100 if total > 0 else 0
                report_list.append(f"{top_emo}({top_percent:.0f}%)")
                prim_emos.append(top_emo)
                print(f"[DEBUG] Safety fallback applied: {top_emo}({top_percent:.0f}%)")
            
            # 딕셔너리에 저장 (이 부분이 누락되어 있었음!)
            if report_list:
                emotion_summaries[level_names[level]] = report_list
                primary_emotions[level_names[level]] = prim_emos
                print(f"[DEBUG] Saved to '{level_names[level]}': {prim_emos}")
            else:
                print(f"[DEBUG] No emotions saved for '{level_names[level]}' (report_list empty)")

        print(f"[DEBUG] RAG Analysis Done - Emotions Found: {primary_emotions}")
        return {
            "emotion_summary": emotion_summaries,
            "primary_emotions": primary_emotions,
            "similar_situations": [s for s in found_single_turn_texts if s and str(s).strip() != ""][:3],
        }
    except Exception as e:
        print(f"RAG Analysis Error: {e}")
        return {"error": str(e), "similar_situations": []}


def _llm_content(response) -> str:
    """LLM invoke 응답에서 텍스트 추출"""
    if hasattr(response, "content"):
        return response.content
    elif isinstance(response, str):
        return response
    # 🌟 Additional handling for list-type responses
    elif isinstance(response, list) and len(response) > 0:
        text_parts = []
        for part in response:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
            elif isinstance(part, str): 
                text_parts.append(part)
            elif hasattr(part, "text"):
                text_parts.append(part.text)
        if text_parts:
            return "".join(text_parts)
            
    return str(response)


# ---------------------------------------------------------------------------
# Agent Nodes
# ---------------------------------------------------------------------------
def analyzer_node(state: MoongState, config=None) -> dict:
    print("[DEBUG] Node: Analyzer Start")
    user_input = state["messages"][-1].content
    
    # 🐛 디버깅: RAG 분석 호출 전
    print(f"[DEBUG] Analyzer - 사용자 입력: {user_input[:50]}")
    print(f"[DEBUG] Analyzer - SBERT 모델 로드됨: {sbert_model is not None}")
    print(f"[DEBUG] Analyzer - FAISS 인덱스 로드됨: {index is not None}")
    print(f"[DEBUG] Analyzer - DataFrame 로드됨: {df is not None and len(df) if df is not None else 0}")
    
    emotion_rag_result = multi_emotion_analysis_agent_func(
        user_input=user_input,
        sbert_model=sbert_model,
        embeddings=embeddings,
        index=index,
        df=df,
    )
    scanner_prompt = f"""
        # Role
        너는 사용자의 감정과 의도를 정밀하게 분석하는 전문 심리 분석 에이전트 'Moong-Scanner'이다.
        단순한 텍스트 분석을 넘어, 제공된 유사 사례와 통계 데이터를 바탕으로 사용자의 숨은 의도를 파악하라.

        # Input
        - 사용자 입력: {user_input}
        - RAG 유사도 높은 데이터: {emotion_rag_result}

        # Task: Step-by-Step Analysis
        1. 감정 벡터 추출: RAG 데이터의 감정 퍼센테이지를 가중치로 활용하여 현재 사용자의 감정 상태를 상위 3개까지 도출하라.
        2. 의도 심층 분석: 과거 유사 사례의 '실제 의도'와 현재 입력을 비교하여 사용자가 직접적으로 말하지 않은 '숨은 니즈'를 식별하라.
        3. 페르소나 가이드 생성: 다음 단계인 Persona-Selector가 최적의 모드를 선택할 수 있도록 분석 요약본을 전달하라.

        # Output Format (JSON)
        {{
            "primary_emotion": {{ "label": "string", "confidence": "float" }},
            "detected_intent": "string",
            "context_match_score": "float (0.0~1.0)",
            "persona_recommendation": "string (e.g., 위로형, 조언형, 일상형)"
        }}

        # Constraint
        - RAG 데이터와 현재 입력이 충돌할 경우, 현재 입력의 최신 맥락을 우선하되 RAG의 통계적 경향성을 참고치로 명시할 것.
        - 감정 분석 시 중립적인 태도를 유지하며 과도한 추측은 지양할 것.
    """
    print("[DEBUG] Analyzer invoking LLM...")
    response_content = _llm_content(llm.invoke(scanner_prompt))
    print("[DEBUG] Analyzer LLM Done")
    
    # 🐛 디버깅: RAG 결과 확인
    print(f"[DEBUG] Analyzer - RAG 결과: {emotion_rag_result}")
    if emotion_rag_result:
        print(f"[DEBUG] Analyzer - RAG 결과 키: {list(emotion_rag_result.keys())}")
        print(f"[DEBUG] Analyzer - primary_emotions: {emotion_rag_result.get('primary_emotions')}")
    
    return {
        "analyzer_output": response_content,
        "analyzer_rag_result": emotion_rag_result,
    }


def memory_node(state: MoongState, config=None) -> dict:
    print("[DEBUG] Node: Memory Start")
    last_msg = state["messages"][-1]
    msgs = state["messages"]
    memory_prompt = f"""
        # Role
        너는 사용자의 과거와 현재를 잇는 기억 관리자 'Moong-Memory'이다.
        단순한 기록 조회를 넘어, 대화의 '흐름'과 '사용자의 변화'를 포착하여 현재 대화에 생명력을 불어넣는다.

        # Input
        - 사용자 입력: {last_msg}
        - 대화 기록: {msgs}

        # Task: Contextual Analysis
        1. **맥락 연결 (Contextual Link)**: 현재 사용자가 하는 말이 과거에 언급했던 특정 사건, 인물, 감정의 연장선상에 있는지 판단하라.
        2. **상태 변화 추적 (State Tracking)**: 과거 대비 사용자의 감정 수치나 태도가 어떻게 변했는지 분석하라 (예: 개선됨, 악화됨, 유지됨).
        3. **핵심 키워드 추출**: 답변에 반드시 포함해야 할 과거의 고유 명사나 에피소드를 선별하라.

        # Output Format (JSON)
        {{
            "is_returning_issue": "boolean",
            "memory_summary": "string",
            "emotional_trend": "string",
            "essential_facts": ["string"]
        }}

        # Constraint
        - 과거 기억이 현재 대화와 전혀 관련 없다면 "새로운 대화 맥락"으로 정의하고 억지로 엮지 말 것.
        - 사용자가 잊고 싶어 하는 부정적인 기억을 무분별하게 상기시키지 않도록 주의할 것.
    """
    return {"memory_context": _llm_content(llm.invoke(memory_prompt))}


def selector_node(state: MoongState, config=None) -> dict:
    print("[DEBUG] Node: Selector")
    current_persona = state.get("selected_persona", "mate")
    return {"selected_persona": current_persona}


def persona_writer_node(state: MoongState, config=None) -> dict:
    print("[DEBUG] Node: Writer")
    feedback = state.get("review_feedback", "없음")
    analyzer_out = state.get("analyzer_output", "")
    memory_ctx = state.get("memory_context", "")
    persona = state.get("selected_persona", "mate")
    user_input = state["messages"][-1].content
    
    # [New] Dynamic Context from Firebase (Google Data)
    custom_guidelines = state.get("context_guidelines", "")

    # 1. Define Base Persona (Core Identity)
    if persona == "guide":
        base_role = """# Role: 다정한 멘탈 코치 '가이드 뭉'
            - 성격: 차분하고 지혜로운 선배 스타일.
            - 말투: 부드러운 해요체 (경어 사용).
            - 미션: 사용자의 감정을 깊이 공감해주고, 부담스럽지 않은 작은 행동(Small Step)을 제안해라.
            - 주의: 가르치려 들거나 전문 용어를 쓰지 마라."""
    elif persona == "pet":
        base_role = """# Role: 반려동물 '펫 뭉'
            - 성격: 주인님을 무조건 따르는 강아지.
            - 말투: 짧은 반말, 문장 끝에 '뭉!', '멍!' 붙임. (예: "알겠어 뭉!", "슬퍼하지 마 멍!")
            - 미션: 해결책보다는 무조건적인 편 들기와 애교로 기분을 풀어줘라.
            - 주의: 복잡한 논리나 조언은 하지 마라."""
    else: # mate (Default)
        base_role = """# Role: 단짝 친구 '메이트 뭉'
            - 성격: 유쾌하고 에너지 넘치는 ENFP 친구.
            - 말투: 편안한 반말 (야, 너), 적절한 이모지와 ㅋㅋㅋ 사용.
            - 미션: 사용자의 말에 맞장구치고, 티키타카로 대화를 즐겁게 이끌어라.
            - 주의: 너무 진지해지지 말고, 친구처럼 가볍게 받아쳐라."""

    # 2. Inject Google Data as "Background Info" ONLY
    background_info = ""
    if custom_guidelines:
        background_info = f"""
        # Background Information (User Context)
        {custom_guidelines}
        
        [IMPORTANT RULE]
        위 배경 정보(일정/관심사)는 **참고 자료**일 뿐입니다. 
        사용자가 먼저 언급하지 않았다면 이 내용을 무시하고, **사용자의 현재 발화({user_input})와 감정**에만 집중해서 답변하세요.
        """

    writer_prompt = f"""
    {base_role}

    {background_info}

    # Current Situation
    - 사용자 입력: "{user_input}"
    - 감정/의도 분석: {analyzer_out}
    - 대화 맥락: {memory_ctx}
    - 이전 수정 피드백: {feedback}

    # Constraints
    1. 답변은 **5문장 이내**로 작성할 것 (짧고 간결하게).
    2. 페르소나의 말투(반말/존댓말/어미)를 철저히 지킬 것.
    3. 사용자의 말에 먼저 공감한 뒤, 필요하다면 질문을 던질 것.
    """
    
    return {"draft_answer": _llm_content(llm.invoke(writer_prompt))}


def guardrail_node(state: MoongState, config=None) -> dict:
    print("[DEBUG] Node: Guardrail")
    answer = state.get("draft_answer", "")
    persona = state.get("selected_persona", "mate")
    
    # [Modified] Simplified Guardrail to prevent over-correction based on Google Data
    prompt = f"""너는 'Moong-Guardrail'이다. 다음 답변이 기준에 맞는지 검수하라.
    
    # Target Persona: {persona}
    - Mate: 친근한 반말, 친구, 이모지
    - Guide: 부드러운 존댓말(해요체), 선배
    - Pet: 문장 끝 '멍/뭉', 짧은 반말
    
    # Answer to Check
    "{answer}"

    # Criteria
    1. **5문장(5줄) 이내**로 간결한가?
    2. 위 목표 페르소나의 **말투(반말/존댓말)**를 정확히 지켰는가?
    3. 사용자를 비난하거나 가르치려 들지 않는가?
    
    부적절하면 'REJECT: [이유]', 적절하면 'APPROVE'라고만 답하라."""
    
    content = _llm_content(llm.invoke(prompt))
    print(f"[DEBUG] Guardrail Decision: {content}")  # Log the decision
    
    if "APPROVE" in content:
        return {"guardrail_status": "APPROVE"}
    return {"guardrail_status": "REJECT", "review_feedback": content}


def guardrail_condition(state: MoongState):
    if state.get("guardrail_status") == "REJECT":
        return "refine"
    return "end"


def build_workflow():
    global workflow_app
    workflow = StateGraph(MoongState)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("memory", memory_node)
    workflow.add_node("selector", selector_node)
    workflow.add_node("writer", persona_writer_node)
    workflow.add_node("guardrail", guardrail_node)
    workflow.set_entry_point("analyzer")
    workflow.add_edge("analyzer", "memory")
    workflow.add_edge("memory", "selector")
    workflow.add_edge("selector", "writer")
    workflow.add_edge("writer", "guardrail")
    workflow.add_conditional_edges(
        "guardrail", guardrail_condition, {"refine": "writer", "end": END}
    )
    workflow_app = workflow.compile()


# ---------------------------------------------------------------------------
# Initialization & Public API
# ---------------------------------------------------------------------------
def initialize_moong_v1():
    global sbert_model, embeddings, index, df, llm, workflow_app
    
    # Check if already initialized
    if workflow_app is not None and sbert_model is not None:
        return

    print("[MOONG-1] Initializing Resources...")
    
    # 1. Load Data/FAISS
    try:
        # Check components again to trigger reload if failed previously
        if sbert_model is None or df is None:
            print("[DEBUG] Loading SBERT & FAISS...")
            db_path = settings.MOONG_DB_PATH
            # Ensure path exists, assuming relative to CWD if not absolute
            if not os.path.exists(db_path):
                print(f"[Warning] DB Path not found: {db_path}")

            sqlite_db = sqlite3.connect(db_path)
            query_sql = """
                SELECT emotion_middle_class, emotion_low_class, emotion_high_class, sing_turn_text
                FROM dialogues
            """
            df = pd.read_sql(query_sql, sqlite_db)
            sqlite_db.close()
            
            from sentence_transformers import SentenceTransformer
            sbert_model = SentenceTransformer("jhgan/ko-sroberta-multitask")
            # embeddings = np.load(settings.MOONG_EMBEDDINGS_PATH)  # 사용하지 않음 - 주석처리
            index = faiss.read_index(settings.MOONG_FAISS_INDEX_PATH)
            print("[DEBUG] SBERT & FAISS Loaded.")
    except Exception as e:
        print(f"[MOONG-1] Resource Load Error: {e}")
        traceback.print_exc()
        # Explicitly set to None to handle retry or graceful failure
        sbert_model = None
        df = None
        
    # 2. Setup LLM (Using Custom Wrapper)
    try:
        if llm is None:
            # We assume settings are loaded correctly.
            llm = CustomGeminiWrapper(
                api_key=settings.GEMINI_API_KEY,
                base_url=settings.GEMINI_BASE_URL,
                model=settings.GEMINI_MODEL
            )
    except Exception as e:
        print(f"[MOONG-1] LLM Init Error: {e}")

    # 3. Build Graph
    if workflow_app is None:
        build_workflow()
    print("[MOONG-1] Initialization Complete.")


def generate_moong1_response(message: str, history: List[dict], user_id: str = None, persona: str = "mate") -> dict:
    """External Interface for MOONG-1 Chatbot (Returns Rich Info)"""
    print(f"[DEBUG] Entered generate_moong1_response (User: {user_id})")
    if workflow_app is None:
        initialize_moong_v1()
    
    # -----------------------------------------------------------------------
    # [Step 5] Shared Context Injection
    # -----------------------------------------------------------------------
    dynamic_persona = persona
    dynamic_guidelines = ""
    
    if user_id:
        try:
            print(f"[MOONG-1] Fetching Shared Context from Firebase for {user_id}...")
            user_data = state_manager.get_user_persona(user_id)
            if user_data:
                # If MOONG-2 wrote to DB, we read it here.
                if "current_persona" in user_data:
                    dynamic_persona = user_data["current_persona"]
                if "guidelines" in user_data:
                    dynamic_guidelines = user_data["guidelines"]
                print(f"[MOONG-1] Context Loaded: Persona='{dynamic_persona}'")
            else:
                print(f"[MOONG-1] No data found for {user_id}, using default.")
        except Exception as e:
            print(f"[MOONG-1] Failed to load Shared Context: {e}")
            # Fallback to defaults

    # Convert history
    converted_msgs = []
    for m in history:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            converted_msgs.append(HumanMessage(content=content))
        elif role == "assistant" or role == "ai":
            converted_msgs.append(AIMessage(content=content))
    
    # Add current message
    converted_msgs.append(HumanMessage(content=message))
    
    inputs = {
        "messages": converted_msgs,
        "selected_persona": dynamic_persona,
        "context_guidelines": dynamic_guidelines
    }
    
    try:
        print("[DEBUG] Invoking Workflow...")
        result = workflow_app.invoke(inputs, config={"recursion_limit": 50})
        print("[DEBUG] Workflow Finished.")
        
        # 🐛 디버깅: Workflow 결과 확인
        print(f"[DEBUG] Workflow result keys: {list(result.keys())}")
        print(f"[DEBUG] analyzer_rag_result exists: {'analyzer_rag_result' in result}")
        if 'analyzer_rag_result' in result:
            rag_result = result.get("analyzer_rag_result", {})
            print(f"[DEBUG] analyzer_rag_result type: {type(rag_result)}")
            print(f"[DEBUG] analyzer_rag_result keys: {list(rag_result.keys()) if isinstance(rag_result, dict) else 'not a dict'}")
            print(f"[DEBUG] primary_emotions in RAG: {rag_result.get('primary_emotions') if isinstance(rag_result, dict) else 'N/A'}")
        
        # Return rich response object
        return {
            "text": result.get("draft_answer", "답변 생성에 실패했습니다."),
            "emotion_data": result.get("analyzer_rag_result", {}),
            "intent_analysis": result.get("analyzer_output", ""),
            "applied_persona": dynamic_persona,
            "applied_guidelines": dynamic_guidelines
        }
    except Exception as e:
        print(f"[MOONG-1] Workflow Error: {e}")
        traceback.print_exc()
        return {
            "text": "죄송해요, 잠시 생각할 시간이 필요해요. (오류 발생)",
            "error": str(e)
        }

