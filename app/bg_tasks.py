from app.modules.moong_v2.services.moong_service import moong_service
from fastapi import BackgroundTasks
import asyncio

async def background_moong2_process(user_id: str, message: str, bot_response: str, emotion_data: dict = None):
    """
    Engine B: Background Task
    - 사용자 메시지로 턴 계산 및 페르소나 업데이트 (DB)
    - 대화 내역 저장 (user + bot response + emotion data)
    """
    print(f"🔄 [Engine B] Background Processing for {user_id}...")
    try:
        # MOONG-1의 감정 분석 결과를 MOONG-2에 전달
        await moong_service.process_message_background(user_id, message, bot_response, emotion_data)
        
    except Exception as e:
        print(f"❌ [Engine B] Failed: {e}")
