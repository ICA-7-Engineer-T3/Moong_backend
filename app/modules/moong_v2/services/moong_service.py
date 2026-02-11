"""
뭉 관리 서비스
- 뭉 생성/조회/관리
- 페르소나별 초기 설정
- 슬롯 연동
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from firebase_admin import firestore
import uuid
import os

# Firebase 연결 (main.py에서 초기화된 것 사용)
firebase_db = None
firebase_initialized = False

# LangGraph Import
try:
    from persona_system.workflow import persona_graph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("⚠️ LangGraph를 찾을 수 없습니다.")
    LANGGRAPH_AVAILABLE = False

def set_firebase_connection_moong(db, initialized):
    """main.py에서 Firebase 연결 상태를 받아오는 함수"""
    global firebase_db, firebase_initialized
    firebase_db = db
    firebase_initialized = initialized

class MoongService:
    """뭉 관리 서비스 클래스"""
    
    def __init__(self):
        self.collection_name = "moongs"
        self.slots_collection = "user_slots"
    
    def _check_firebase(self):
        """Firebase 연결 상태 확인"""
        if not firebase_initialized or not firebase_db:
            raise RuntimeError("Firebase가 초기화되지 않았습니다")
    
    def _generate_moong_id(self, user_id: str) -> str:
        """뭉 고유 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"moong_{user_id}_{timestamp}"

    async def _save_chat_log(self, moong_id: str, user_msg: str, bot_msg: str, metadata: Dict[str, Any]):
        """대화 내용을 Firestore 하위 컬렉션에 저장"""
        try:
            if not firebase_initialized or not firebase_db:
                return

            # MOONG-1의 RAG 기반 다중 감정 분석 결과 추출
            emotion_data = metadata.get('emotion_data', {})
            
            # 대화 로그 문서 생성
            log_data = {
                'user_message': user_msg,
                'bot_response': bot_msg,
                'timestamp': datetime.now(),
                'turn_info': {
                    'turn_count': metadata.get('turn', 0),
                    'persona_updated': metadata.get('persona_updated', False)
                },
                # MOONG-1 RAG 기반 다중 감정 분석 결과 저장
                'emotion_analysis': {
                    'primary_emotions': emotion_data.get('primary_emotions', {}),
                    'emotion_summary': emotion_data.get('emotion_summary', {}),
                    'similar_situations': emotion_data.get('similar_situations', []),
                    'source': 'MOONG-1 RAG'
                },
                # 간단 요약 (호환성)
                'emotion_snapshot': self._extract_primary_emotion(emotion_data)
            }
            
            # moongs/{moong_id}/messages 컬렉션에 추가
            # add()를 사용하여 문서 ID 자동 생성
            firebase_db.collection(self.collection_name).document(moong_id).collection('messages').add(log_data)
            
            # 💾 저장 완료 로그 (상세 정보 포함)
            print(f"\n💾 [Firebase] 대화 로그 저장 완료")
            print(f"   - Moong ID: {moong_id}")
            print(f"   - 주요 감정: {log_data['emotion_snapshot']}")
            
            # 저장된 다중 감정 데이터 요약 출력
            if emotion_data:
                primary_emotions = emotion_data.get('primary_emotions', {})
                if primary_emotions:
                    all_emotions = []
                    for level_emotions in primary_emotions.values():
                        all_emotions.extend(level_emotions)
                    if all_emotions:
                        print(f"   - 분석된 감정: {', '.join(all_emotions[:5])}")
                
                similar_count = len(emotion_data.get('similar_situations', []))
                if similar_count > 0:
                    print(f"   - 유사 상황: {similar_count}건")
            print("-" * 80)
            
        except Exception as e:
            print(f"⚠️ 대화 로그 저장 실패: {e}")
    
    def _extract_primary_emotion(self, emotion_data: dict) -> str:
        """다중 감정 데이터에서 주요 감정 추출"""
        try:
            primary_emotions = emotion_data.get('primary_emotions', {})
            if primary_emotions:
                # middle, low, high 중 가장 많은 감정 반환
                for level in ['middle', 'low', 'high']:
                    emotions = primary_emotions.get(level, [])
                    if emotions:
                        return emotions[0]  # 첫 번째 감정 반환
            return 'neutral'
        except:
            return 'neutral'

    def _get_initial_appearance(self, persona: str) -> Dict[str, Any]:
        """페르소나별 초기 외형 설정"""
        persona_colors = {
            "pet": "#90EE90",      # 연한 초록 (귀여운 애완동물)
            "mate": "#87CEEB",     # 하늘색 (친근한 친구)
            "guide": "#DDA0DD"     # 연보라 (지혜로운 가이드)
        }
        
        return {
            "appearance_type": "solid",
            "base_color": persona_colors.get(persona, "#90EE90"),
            "gradient_colors": None,
            "time_period": "day",
            "dominant_emotion": "TRUST",
            "opacity": 1.0
        }
    
    async def find_available_slot(self, user_id: str) -> Optional[int]:
        """사용 가능한 슬롯 찾기"""
        self._check_firebase()
        
        try:
            slots_doc = firebase_db.collection(self.slots_collection).document(user_id).get()
            
            if not slots_doc.exists:
                # 슬롯 정보가 없으면 1번 슬롯 반환 (초기화는 user_service에서 처리)
                return 1
            
            slots_data = slots_doc.to_dict()
            
            # 비어있는 슬롯 찾기
            for slot_num in [1, 2, 3]:
                slot_key = f"slot_{slot_num}"
                slot_info = slots_data.get(slot_key, {})
                if not slot_info.get('is_occupied', False):
                    return slot_num
            
            return None  # 모든 슬롯이 차있음
            
        except Exception as e:
            print(f"슬롯 조회 실패: {e}")
            return None
    
    async def get_recent_messages(self, user_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        [Phase 1] 단기 기억 로딩 (디버깅 강화)
        """
        try:
            self._check_firebase()
            
            # 1. 활성 뭉 찾기
            user_moongs = await self.get_user_moongs(user_id)
            if not user_moongs:
                print(f"⚠️ [Memory] 활성 뭉을 찾을 수 없음 (User: {user_id})")
                return []
            
            active_moong = user_moongs[0]
            moong_id = active_moong['moong_id']
            
            # 2. 메시지 컬렉션 조회
            messages_ref = firebase_db.collection(self.collection_name).document(moong_id).collection('messages')
            query = messages_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)
            docs = query.stream()
            
            # 3. 데이터 정제
            history = []
            count = 0 
            for doc in docs:
                data = doc.to_dict()
                # User Message
                if data.get('user_message'):
                    history.append({"role": "user", "content": data['user_message']})
                
                # Chatbot Response
                if data.get('bot_response'):
                    history.append({"role": "assistant", "content": data['bot_response']})
                count += 1
            
            # 최신순 -> 시간순으로 재정렬
            final_history = list(reversed(history))
            print(f"📚 [Memory] Loaded {len(final_history)} messages for {moong_id} (Docs: {count})")
            return final_history

        except Exception as e:
            print(f"⚠️ 대화 내역 조회 실패: {e}")
            return []

    async def create_moong(self, user_id: str, name: str, persona: str) -> Dict[str, Any]:
        """새 뭉 생성"""
        self._check_firebase()
        
        try:
            # 사용 가능한 슬롯 확인
            available_slot = await self.find_available_slot(user_id)
            if available_slot is None:
                raise ValueError("사용 가능한 슬롯이 없습니다. (최대 3개)")
            
            # 뭉 ID 생성
            moong_id = self._generate_moong_id(user_id)
            current_time = datetime.now()
            graduation_date = current_time + timedelta(days=30)  # 30일 후 강제 졸업
            
            # 뭉 초기 데이터 생성
            moong_data = {
                'user_id': user_id,
                'slot_number': available_slot,
                'name': name,
                'persona': persona,
                
                # 성장 관련
                'created_at': current_time,
                'current_stage': 1,  # 씨앗기
                'total_exp': 0,
                'daily_exp': 0,
                'conversation_count': 0,
                
                # 상호작용 관련
                'last_interaction': current_time,
                'six_hour_timer': current_time,  # 6시간 주기 활동
                
                # 외형 관련
                'appearance': self._get_initial_appearance(persona),
                'equipped_items': [],
                
                # 상태
                'status': 'growing',
                'force_graduation_date': graduation_date
            }
            
            # Firestore에 뭉 데이터 저장
            firebase_db.collection(self.collection_name).document(moong_id).set(moong_data)
            
            # 슬롯 점유 표시
            slot_update = {
                f'slot_{available_slot}': {
                    'is_occupied': True,
                    'moong_id': moong_id,
                    'last_interaction': current_time
                }
            }
            firebase_db.collection(self.slots_collection).document(user_id).set(slot_update, merge=True)
            
            # 생성된 뭉 정보 반환
            moong_data['moong_id'] = moong_id
            return moong_data
            
        except Exception as e:
            print(f"뭉 생성 실패: {e}")
            raise e
    
    async def get_moong(self, moong_id: str) -> Optional[Dict[str, Any]]:
        """뭉 정보 조회"""
        self._check_firebase()
        
        try:
            moong_doc = firebase_db.collection(self.collection_name).document(moong_id).get()
            
            if moong_doc.exists:
                moong_data = moong_doc.to_dict()
                moong_data['moong_id'] = moong_id
                
                # 성장 진행도 계산
                moong_data['growth_progress'] = self._calculate_growth_progress(moong_data)
                
                # 6시간 타이머 상태 확인
                moong_data['timer_status'] = self._check_six_hour_timer(moong_data)
                
                # 졸업까지 남은 일수 계산
                moong_data['days_until_graduation'] = self._calculate_days_until_graduation(moong_data)
                
                return moong_data
            
            return None
            
        except Exception as e:
            print(f"뭉 조회 실패: {e}")
            return None
    
    async def get_user_moongs(self, user_id: str) -> List[Dict[str, Any]]:
        """사용자의 모든 뭉 조회"""
        self._check_firebase()
        
        try:
            moongs_query = firebase_db.collection(self.collection_name).where('user_id', '==', user_id)
            docs = moongs_query.stream()
            
            moongs = []
            for doc in docs:
                moong_data = doc.to_dict()
                moong_data['moong_id'] = doc.id
                
                # 기본 상태 정보 추가
                moong_data['growth_progress'] = self._calculate_growth_progress(moong_data)
                moong_data['days_until_graduation'] = self._calculate_days_until_graduation(moong_data)
                
                moongs.append(moong_data)
            
            # 슬롯 번호 순으로 정렬
            moongs.sort(key=lambda x: x.get('slot_number', 999))
            
            return moongs
            
        except Exception as e:
            print(f"사용자 뭉 목록 조회 실패: {e}")
            return []
    
    def _calculate_growth_progress(self, moong_data: Dict[str, Any]) -> Dict[str, Any]:
        """성장 진행도 계산"""
        current_stage = moong_data.get('current_stage', 1)
        total_exp = moong_data.get('total_exp', 0)
        conversation_count = moong_data.get('conversation_count', 0)
        
        # 성장 임계값
        exp_thresholds = {1: 100, 2: 400, 3: 800, 4: 9999}
        conversation_thresholds = {1: 10, 2: 30, 3: 60, 4: 100}
        
        stage_max_exp = exp_thresholds.get(current_stage, 9999)
        stage_max_conversations = conversation_thresholds.get(current_stage, 100)
        
        return {
            "current_exp": total_exp,
            "stage_max_exp": stage_max_exp,
            "exp_percentage": min((total_exp / stage_max_exp) * 100, 100),
            "current_conversations": conversation_count,
            "stage_max_conversations": stage_max_conversations,
            "conversation_percentage": min((conversation_count / stage_max_conversations) * 100, 100),
            "can_level_up": (total_exp >= stage_max_exp and conversation_count >= stage_max_conversations)
        }
    
    def _check_six_hour_timer(self, moong_data: Dict[str, Any]) -> Dict[str, Any]:
        """6시간 타이머 상태 확인"""
        last_interaction = moong_data.get('six_hour_timer')
        current_time = datetime.now()
        
        if isinstance(last_interaction, datetime):
            # datetime 객체인 경우 timezone 정보 제거
            if last_interaction.tzinfo is not None:
                last_interaction = last_interaction.replace(tzinfo=None)
            time_diff = current_time - last_interaction
        else:
            # Firestore timestamp 처리
            if hasattr(last_interaction, 'replace'):
                last_interaction = last_interaction.replace(tzinfo=None)
                time_diff = current_time - last_interaction
            else:
                # 기본값으로 설정
                time_diff = timedelta(hours=7)  # 6시간을 넘어서 활성화되지 않은 상태
        
        six_hours = timedelta(hours=6)
        is_active = time_diff < six_hours
        
        if is_active:
            remaining_time = six_hours - time_diff
            next_available = last_interaction + six_hours
        else:
            remaining_time = timedelta(0)
            next_available = current_time
        
        return {
            "is_active": is_active,
            "remaining_minutes": int(remaining_time.total_seconds() / 60),
            "next_available_time": next_available.isoformat()
        }
    
    def _calculate_days_until_graduation(self, moong_data: Dict[str, Any]) -> int:
        """졸업까지 남은 일수 계산"""
        graduation_date = moong_data.get('force_graduation_date')
        current_time = datetime.now()
        
        if isinstance(graduation_date, datetime):
            # datetime 객체인 경우 timezone 정보 제거
            if graduation_date.tzinfo is not None:
                graduation_date = graduation_date.replace(tzinfo=None)
            time_diff = graduation_date - current_time
        else:
            # Firestore timestamp 처리
            if hasattr(graduation_date, 'replace'):
                graduation_date = graduation_date.replace(tzinfo=None)
                time_diff = graduation_date - current_time
            else:
                # 기본값으로 설정 (30일 후)
                time_diff = timedelta(days=30)
        
        return max(0, time_diff.days)

    async def process_message_background(self, user_id: str, message: str, bot_response: str, emotion_data: dict = None) -> None:
        """
        [Engine B] 백그라운드 처리 전용 (답변 생성 없이 상태 업데이트만 수행) 
        MOONG-1이 생성한 답변을 받아 DB에 저장하고, 워크플로우를 돌려 페르소나 상태를 업데이트함.
        emotion_data: MOONG-1의 RAG 기반 다중 감정 분석 결과
        """
        try:
            print(f"🔄 [MOONG-2] Background State Update Start (User: {user_id})")
            
            # 1. LangGraph 워크플로우 실행 (페르소나 변경/분석 감지용)
            # 답변은 MOONG-1 것을 사용하므로, 여기서 나온 답변은 무시하거나 '분석용'으로만 씀
            if LANGGRAPH_AVAILABLE:
                # 🐛 디버깅: emotion_data 확인
                print(f"   🐛 [DEBUG] emotion_data 전달 여부: {bool(emotion_data)}")
                if emotion_data:
                    print(f"   🐛 [DEBUG] emotion_data 키: {list(emotion_data.keys())}")
                
                # session_id만 전달하고 실제 응답은 무시
                # [최적화] mode='analysis_only'로 설정하여 불필요한 응답 생성 방지 + 외부 답변 주입
                graph_result = await persona_graph.process_message(
                    message, 
                    session_id=user_id, 
                    mode="analysis_only",
                    pre_generated_response=bot_response,
                    moong1_emotion_data=emotion_data  # MOONG-1의 구체적 감정 분석 전달
                )
            else:
                graph_result = {"success": False, "persona_updated": False}
            
            # --- DB Update Logic (Copied/Refactored from process_message) ---
            user_moongs = await self.get_user_moongs(user_id)
            if not user_moongs:
                return # 초기화 안된 유저 무시

            active_moong = user_moongs[0]
            moong_id = active_moong['moong_id']
            
            # 대화 카운트 증가
            current_count = active_moong.get('conversation_count', 0)
            new_conversation_count = current_count + 1
            
            update_data = {
                'conversation_count': new_conversation_count,
                'updated_at': datetime.now()
            }
            
            # 페르소나 업데이트 반영
            if graph_result.get('persona_updated', False):
                print("✨ [MOONG-2] Persona Update Triggered!")
                try:
                    wf_result = graph_result.get('persona_workflow_result', {})
                    # DeepSeek 응답 구조에 맞게 접근
                    new_update = {}
                    if hasattr(wf_result, 'get'):
                        new_update = wf_result.get('persona_update', {})
                    
                    # 실제 DeepSeek 응답 필드 사용
                    update_data['current_persona'] = {
                        'persona_type': new_update.get('persona_type', '메이트 뭉'),
                        'mbti': new_update.get('mbti', 'ENFP'),
                        'temperature': new_update.get('temperature', 0.7),
                        'energy_level': new_update.get('energy_level', 0.8),
                        'formality': new_update.get('formality', 0.3),
                        'talking_style': new_update.get('talking_style', '친근한 반말'),
                        'nickname': new_update.get('nickname', '뭉'),
                        'guidelines': new_update.get('guidelines', {}),
                        'last_reasoning': wf_result.get('reasoning', '') if hasattr(wf_result, 'get') else '',
                        'updated_at': datetime.now()
                    }
                    update_data['guidelines'] = new_update.get('guidelines', {}) # Root field update
                    print(f"   페르소나 타입: {update_data['current_persona']['persona_type']}")
                    print(f"   말투: {update_data['current_persona']['talking_style']}")
                except Exception as e:
                    print(f"⚠️ 페르소나 데이터 추출 실패: {e}")
                    import traceback
                    traceback.print_exc()

            # DB 저장
            firebase_db.collection(self.collection_name).document(moong_id).update(update_data)
            
            # 대화 로그 저장 (MOONG-1의 답변 + 감정 분석 결과 저장!)
            metadata = {
                **graph_result,
                'emotion_data': emotion_data  # MOONG-1 RAG 기반 다중 감정 분석 결과
            }
            await self._save_chat_log(
                moong_id=moong_id,
                user_msg=message,
                bot_msg=bot_response, # MOONG-1 Response
                metadata=metadata # Analysis data + emotion_data
            )
            print("✅ [MOONG-2] Background Update Complete.")
            
        except Exception as e:
            print(f"❌ [MOONG-2] Background Error: {e}")
            import traceback
            traceback.print_exc()

    async def process_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """사용자 메시지 처리 - LangGraph 워크플로우 연동"""
        try:
            print(f"🔍 디버그: process_message 시작 - user_id: {user_id}")
            
            # 1. LangGraph를 통해 메시지 처리 (핵심 로직)
            if LANGGRAPH_AVAILABLE:
                graph_result = await persona_graph.process_message(message, session_id=user_id)
            else:
                graph_result = {
                    "success": False, 
                    "response": "시스템 오류: 코어 모듈 로드 실패",
                    "persona_updated": False
                }
            
            # 사용자의 뭉 조회 (DB 업데이트용)
            user_moongs = await self.get_user_moongs(user_id)
            
            if not user_moongs:
                # 기본 뭉 자동 생성
                moong_data = await self.create_moong(user_id=user_id, name="뭉이", persona="mate")
                user_moongs = [moong_data]
            
            active_moong = user_moongs[0]
            moong_id = active_moong['moong_id']
            
            # 대화 횟수 증가 및 update_data 초기화 (NameError 해결)
            current_count = active_moong.get('conversation_count', 0)
            new_conversation_count = current_count + 1
            
            update_data = {
                'conversation_count': new_conversation_count,
                'updated_at': datetime.now()
            }
            
            # 페르소나 업데이트가 발생했다면 해당 정보도 DB에 저장
            updated_info = active_moong.get('current_persona', {})
            
            if graph_result.get('persona_updated', False):
                # LangGraph 결과에서 새 지침 추출
                wf_result = graph_result.get('persona_workflow_result', {})
                new_update = wf_result.get('persona_update', {})
                
                # Firestore에 저장할 데이터 구성
                update_data['current_persona'] = {
                    'instruction': new_update.get('instruction', active_moong.get('current_persona', {}).get('instruction', '')),
                    'guidelines': new_update.get('guidelines', {}),
                    'last_reasoning': wf_result.get('reasoning', ''),
                    'updated_at': datetime.now()
                }
                update_data['guidelines'] = new_update.get('guidelines', {}) # 별도 필드로도 저장 (접근 편의성)

            firebase_db.collection(self.collection_name).document(moong_id).update(update_data)
            
            # 업데이트된 데이터로 성장 정보 재계산
            updated_moong_data = active_moong.copy()
            updated_moong_data.update(update_data)
            growth_info = self._calculate_growth_progress(updated_moong_data)

            # [NEW] 대화 내용 기록 (메시지 컬렉션)
            await self._save_chat_log(
                moong_id=moong_id,
                user_msg=message,
                bot_msg=graph_result.get('response', ''),
                metadata=graph_result
            )
            
            # 퀘스트 상태 확인 (간이 구현)
            # 실제로는 별도 QuestService가 필요하지만, 여기서는 데모용으로 간단히 처리
            quests = [
                {
                    "id": "daily_talk_3",
                    "title": "오늘의 수다쟁이",
                    "description": "대화 3번 하기",
                    "target": 3,
                    "current": new_conversation_count % 10,  # 데모용으로 10단위 리셋처럼 보이게
                    "is_completed": (new_conversation_count % 10) >= 3,
                    "reward": "EXP +30"
                },
                {
                    "id": "daily_check",
                    "title": "감정 출석체크",
                    "description": "나의 감정 기록하기",
                    "target": 1,
                    "current": 1,
                    "is_completed": True,
                    "reward": "EXP +10"
                }
            ]

            # 결과 반환
            update_reason = ''
            if graph_result.get('persona_updated'):
                reasoning = graph_result.get('persona_workflow_result', {}).get('reasoning', '')
                update_reason = f'Turn {graph_result["turn"]}: {reasoning}'

            return {
                'response': graph_result['response'],
                'persona_updated': graph_result.get('persona_updated', False),
                'update_reason': update_reason,
                'current_turn': graph_result.get('turn', 0),
                'persona_workflow_result': graph_result.get('persona_workflow_result', {}),
                'growth_info': growth_info,
                'quests': quests
            }
            
        except Exception as e:
            print(f"❌ 메시지 처리 실패: {e}")
            import traceback
            print(f"❌ 상세 오류: {traceback.format_exc()}")
            return {
                'response': '메시지 처리 중 오류가 발생했습니다 😅',
                'persona_updated': False
            }

# 전역 서비스 인스턴스
moong_service = MoongService()