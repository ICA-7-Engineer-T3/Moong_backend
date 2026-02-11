import firebase_admin
from firebase_admin import credentials, firestore
import os

# 설정
CRED_PATH = "config/firebase_service_account.json"
PROJECT_ID = "emotion-analysis-system"
TARGET_USER = "test_user_01"  # 테스트용 유저 ID만 골라서 삭제

def delete_collection(coll_ref, batch_size):
    """컬렉션 내부 문서 재귀적 삭제"""
    docs = list(coll_ref.limit(batch_size).stream())
    deleted = 0

    for doc in docs:
        print(f"   🗑️ 삭제 중: {doc.id}")
        
        # 하위 컬렉션(messages) 확인 및 삭제
        sub_collections = doc.reference.collections()
        for sub in sub_collections:
            delete_collection(sub, batch_size)
            
        doc.reference.delete()
        deleted += 1

    if deleted >= batch_size:
        return delete_collection(coll_ref, batch_size)

def reset_data():
    print("🔥 [경고] 데이터베이스 전체 초기화를 시작합니다...")
    print("   모든 사용자의 데이터(뭉, 대화내역, 슬롯)가 영구 삭제됩니다.")
    confirm = input("   정말 진행하시겠습니까? (y/n): ")
    
    if confirm.lower() != 'y':
        print("   ❌ 취소되었습니다.")
        return

    # 1. 초기화
    if not firebase_admin._apps:
        cred = credentials.Certificate(CRED_PATH)
        firebase_admin.initialize_app(cred, {"projectId": PROJECT_ID})
    db = firestore.client()

    # 2. Moongs 컬렉션 전체 삭제
    print("\n[1/2] moongs 컬렉션 삭제 중...")
    delete_collection(db.collection("moongs"), 10)

    # 3. User Slots 전체 삭제
    print("\n[2/2] user_slots 컬렉션 삭제 중...")
    delete_collection(db.collection("user_slots"), 10)

    print("\n✨ 전체 DB 리셋 완료! (Zero Base 상태)")

if __name__ == "__main__":
    reset_data()
