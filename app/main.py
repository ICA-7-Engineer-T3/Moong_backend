import os
import uvicorn
import sys
from fastapi import FastAPI, Request, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Core Config
from app.core.config import settings

# --- Module Imports ---
# Make sure we can find the modules if they are not installed as packages
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "modules", "moong_v2"))
sys.path.append(os.path.join(BASE_DIR, "modules", "moong_v1"))

# Services (MOONG-2)
from app.modules.moong_v2.services.google_api_service import google_api_service
from app.modules.moong_v2.services.enhanced_data_analyzer import enhanced_analyzer
from app.modules.moong_v2.services.moong_service import moong_service  # Updated import
from app.modules.moong_v2.persona_system.state_manager import session_manager

# Services (MOONG-1)
from app.modules.moong_v1.interface import generate_moong1_response
from app.bg_tasks import background_moong2_process
from fastapi import BackgroundTasks # Import BackgroundTasks

# App Init (with Lifespan)
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import credentials, firestore
from app.modules.moong_v2.services.moong_service import set_firebase_connection_moong

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🔥 Server Startup: Initializing Firebase...")
    try:
        cred_path = settings.FIREBASE_SERVICE_ACCOUNT_PATH
        if not firebase_admin._apps:
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
                print("   ✅ Firebase Admin Initialized")
            else:
                print(f"   ⚠️ Credential file not found at: {cred_path}")
        
        # Get Firestore Client
        db = firestore.client()
        
        # Inject into MoongService
        set_firebase_connection_moong(db, True)
        print("   ✅ MoongService Connected to Firebase")
        
    except Exception as e:
        print(f"   ❌ Firebase Init Failed: {e}")
    
    yield
    # Shutdown
    print("💤 Server Shutdown")

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION, lifespan=lifespan)

# Middleware
# Session for OAuth state handling
app.add_middleware(SessionMiddleware, secret_key="super-secret-moong-key")
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None # Optional, will use authenticated user id if missing
    persona: Optional[str] = "mate"

class ChatResponse(BaseModel):
    response: str
    persona_context: Optional[Dict[str, Any]] = None
    turn_count: int
    persona_updated: bool

# --- Root ---
@app.get("/")
async def root():
    return {
        "message": "Moong Integrated Server Running", 
        "version": settings.VERSION,
        "endpoints": {
            "auth": "/auth/login",
            "chat": "/chat", 
            "init": "/api/init"
        }
    }

import json
from fastapi.responses import Response

def PrettyJSONResponse(content: dict, status_code: int = 200):
    """
    한글 깨짐 방지 및 예쁜 출력을 위한 커스텀 응답
    """
    json_str = json.dumps(content, ensure_ascii=False, indent=2)
    return Response(content=json_str, status_code=status_code, media_type="application/json; charset=utf-8")

# --- Security & Auth Dependency ---
security_scheme = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> str:
    """
    Validate Google Access Token and return User ID.
    If validation fails, raises 401.
    """
    token = credentials.credentials
    user_info = google_api_service.get_user_info_from_token(token)
    
    if not user_info or not user_info.get("id"):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info["id"]

# --- AUTH (Google) ---
@app.get("/auth/login")
async def login(request: Request):
    """Start Google OAuth Flow"""
    auth_data = google_api_service.generate_auth_url()
    if "error" in auth_data: 
        raise HTTPException(status_code=500, detail=auth_data["error"])
    return RedirectResponse(auth_data["auth_url"])

@app.get("/auth/callback")
async def callback(request: Request):
    """Handle Google OAuth Callback"""
    code = request.query_params.get("code")
    if not code: 
        return PrettyJSONResponse({"error": "No code provided"}, status_code=400)
    
    result = await google_api_service.handle_oauth_callback(code)
    if not result.get("success"): 
        return PrettyJSONResponse(result, status_code=400)
    
    # Success: Return Token & Auto-Init
    tokens = result.get("tokens", {})
    # Define access_token correctly
    access_token = tokens.get("access_token")
    user_info = result.get("user_info", {})
    google_user_id = user_info.get("id")
    
    init_result = {}
    if google_user_id and access_token:
        print(f"🚀 Performing Auto-Initialization for User ID: {google_user_id}...")
        try:
            # Pass correct arguments (access_token, user_id)
            init_result = await enhanced_analyzer.generate_first_message(access_token=access_token, user_id=google_user_id)
        except Exception as e:
            print(f"⚠️ Auto-init failed: {e}")
            init_result = {"error": f"Init failed: {str(e)}"}
    else:
        print("⚠️ Cannot perform Auto-Init: google_user_id or access_token missing")

    return PrettyJSONResponse({
        "message": "Login & Initialization Success", 
        "auth": {
            "tokens": tokens, 
            "user_info": user_info
        },
        "init_result": init_result
    })

# --- INIT (Data Analysis) ---
@app.post("/api/init")
async def init_chat(request: Request):
    """Analyze User Data & Generate Greeting"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # For dev/testing allowing bypass if needed, or strictly enforce:
        # raise HTTPException(status_code=401, detail="Missing Bearer Token")
        print("Warning: No Auth Token provided. Using dummy/cached data if available.")
        token = "dummy_token"
    else:
        token = auth_header.split(" ")[1]
    
    # Run Analysis (Calendar, YouTube, etc.)
    greeting_result = await enhanced_analyzer.generate_first_message(access_token=token)
    
    # [Debug Log] Print the generated greeting to terminal for verification
    if greeting_result:
        print(f"\n👋 [First Greeting Generated]:")
        print(f"   Message: \"{greeting_result.get('message', 'No message generated')}\"")
        print(f"   Persona: {greeting_result.get('persona_name', 'Unknown')}")
        print("-" * 50)
        
    return greeting_result

# --- CHAT (Dual Engine) ---
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest, 
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    """
    [Integrated Chat Flow]
    - Engine A (Foreground): MOONG-1 (Generate Response with RAG & Deep Emotion)
    - Engine B (Background): MOONG-2 (Update Persona State & DB)
    """
    # Authenticated User ID (from Token) overrides payload session_id
    current_user_id = user_id 
    print(f"📨 Chat Request: {req.message} (User: {current_user_id})")
    
    # === Engine A: MOONG-1 (Response Generation) ===
    # 1. [Phase 1] DB에서 최근 대화 내역(Context) 불러오기
    # Firestore에서 최근 10건(5턴) 정도를 가져옴
    db_history = await moong_service.get_recent_messages(user_id=current_user_id, limit=6)
    
    # 2. [Debug] Engine A에게 전달되는 기억 확인
    if db_history:
        print(f"🧠 [Engine A] Injecting History: {db_history[-2:]} ... (Total {len(db_history)})")
    else:
        print(f"🧠 [Engine A] No History Injected (First Turn or Error)")

    # Moong-1 generates the response using the current persona state found in DB
    moong1_result = generate_moong1_response(
        message=req.message,
        history=db_history, # Injected DB History
        user_id=current_user_id,
        persona=req.persona
    )
    
    final_response_text = moong1_result.get("text", "...")
    
    # MOONG-1의 감정 분석 결과 추출
    emotion_analysis = moong1_result.get("emotion_data", {})
    
    # 📊 구체적 감정 분석 결과 로그 출력 (개발용)
    print(f"\n{'='*80}")
    print(f"📊 [MOONG-1 RAG] 구체적 감정 분석 결과")
    print(f"{'='*80}")
    
    if emotion_analysis:
        # 1. 구체적 감정들 (primary_emotions)
        primary_emotions = emotion_analysis.get('primary_emotions', {})
        if primary_emotions:
            print(f"\n🎯 분석된 구체적 감정들:")
            for level, emotions in primary_emotions.items():
                if emotions:
                    print(f"   [{level}] {' | '.join(emotions)}")
        else:
            print(f"\n⚠️  구체적 감정 데이터 없음 (RAG 매칭 실패)")
        
        # 2. 감정 통계 (비율 포함)
        emotion_summary = emotion_analysis.get('emotion_summary', {})
        if emotion_summary:
            print(f"\n📊 감정 통계 (비율):")
            for level, summary in emotion_summary.items():
                if summary:
                    print(f"   [{level}] {' | '.join(summary)}")
        
        # 3. 유사 상황 (참고)
        similar_situations = emotion_analysis.get('similar_situations', [])
        if similar_situations:
            print(f"\n🔍 유사 상황 참고 ({len(similar_situations)}건):")
            for i, situation in enumerate(similar_situations[:3], 1):
                display_text = situation[:60] + "..." if len(situation) > 60 else situation
                print(f"   {i}. {display_text}")
    else:
        print(f"\n⚠️  MOONG-1 감정 분석 데이터 없음")
    
    print(f"{'='*80}\n")
    print("-" * 80)
    
    # === Engine B: MOONG-2 (Background State Management) ===
    # Updates DB, increments counters, and potentially updates Persona every 3 turns
    background_tasks.add_task(
        background_moong2_process,
        user_id=current_user_id,
        message=req.message,
        bot_response=final_response_text,
        emotion_data=emotion_analysis  # 감정 데이터 전달
    )
    
    # 3. Return Response Immediately
    return {
        "response": final_response_text,
        "persona_context": {
            "applied_persona": moong1_result.get("applied_persona"),
            "emotion": moong1_result.get("emotion_data", {}).get("emotion")
        },
        "turn_count": -1, # Managed in background
        "persona_updated": False # Managed in background
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)
