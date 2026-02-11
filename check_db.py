import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
from datetime import datetime

# 설정 (app/core/config.py 참조)
CRED_PATH = "config/firebase_service_account.json"
PROJECT_ID = "emotion-analysis-system"

def verify_db():
    print("🔥 Firebase DB 데이터 조회 시작...")
    
    # 1. 인증 정보 확인
    if not os.path.exists(CRED_PATH):
        print(f"❌ 오류: 인증 파일이 없습니다 ({CRED_PATH})")
        return

    # 2. Firebase 초기화
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(CRED_PATH)
            firebase_admin.initialize_app(cred, {"projectId": PROJECT_ID})
        db = firestore.client()
        print("✅ Firebase 연결 성공")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return

    # 3. 데이터 조회 (특정 사용자가 없으면 전체 조회)
    target_user = "test_user_01"
    moongs_ref = db.collection("moongs")
    
    # 먼저 target_user로 시도
    # query = moongs_ref.where("user_id", "==", target_user)
    # results = list(query.stream())
    
    # [수정] 모든 문서 다 가져와서 출력 (개발용)
    print(f"\n🔍 전체 사용자 뭉(Moong) 데이터 스캔 중...")
    results = list(moongs_ref.stream())

    if not results:
        print("⚠️ 데이터가 없습니다! (먼저 curl 명령어로 대화를 진행해주세요)")
        return

    for doc in results:
        data = doc.to_dict()
        print(f"\n📂 [문서] Moong ID: {doc.id}")
        print(f"   👤 User ID: {data.get('user_id')}") # 누가 주인인지 출력
        print("-" * 50)
        
        # 핵심 정보 출력
        print(f"📌 이름: {data.get('name')} ({data.get('persona')} 타입)")
        print(f"🗣️ 대화 횟수: {data.get('conversation_count')}회")
        print(f"🕒 최근 수정: {data.get('updated_at')}")
        
        # 페르소나 업데이트 정보 확인
        cp = data.get('current_persona', {})
        print(f"\n[🧠 페르소나(지능) 상태]")
        if cp:
            print(f"▶ 지침(Instruction): {cp.get('instruction')}")
            print(f"▶ 판단 근거: {cp.get('last_reasoning')}")
            
            guidelines = cp.get('guidelines', {})
            if guidelines:
                print("▶ 세부 가이드라인:")
                for k, v in guidelines.items():
                    print(f"   - {k}: {v}")
        else:
            print("   (아직 페르소나 업데이트 기록 없음)")
            
        print("\n[💬 최근 대화 로그 (messages 컬렉션)]")
        # 하위 컬렉션 조회
        msgs_ref = moongs_ref.document(doc.id).collection('messages')
        # 시간순 정렬
        msgs = msgs_ref.order_by('timestamp').limit(5).stream()
        
        msg_list = list(msgs)
        if msg_list:
            for m in msg_list:
                md = m.to_dict()
                t = md.get('timestamp')
                ts = t.strftime("%H:%M:%S") if t else "?"
                print(f"   ⏰ [{ts}] User: {md.get('user_message')} -> Bot: {md.get('bot_response')}")
        else:
            print("   (저장된 대화 내역 없음)")

        print("=" * 50)

if __name__ == "__main__":
    verify_db()
