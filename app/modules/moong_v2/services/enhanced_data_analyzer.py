"""
메이트 뭉 전용 초상세 데이터 분석기
- Google 데이터 분석에서 초상세한 근거 제공
- 메이트 뭉 페르소나에 맞는 첫 메시지 생성
- Step별 분석 과정 상세 추적
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re
from collections import Counter
import sys
import os

# persona_system 경로 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from .google_api_service import GoogleAPIService
from persona_system.llm_client import LLMClient

class MatesMoongDataAnalyzer:
    """메이트 뭉 전용 초상세 데이터 분석기"""
    
    def __init__(self):
        self.google_api_service = GoogleAPIService()
        self.llm_client = LLMClient()
        
        # [User Defined] 3 Major Personas
        self.PERSONA_TEMPLATES = {
            "pet": {
                "name": "펫 뭉 (Pet Moong)",
                "desc": "Temperature 0.8 / 감정 미러링 / 무조건적 수용",
                "base_guidelines": """당신은 사용자의 반려동물 '펫 뭉'입니다.
    1. 호칭: 항상 {nickname} 주인님이라고 부르세요.
    2. 말투: 짧은 반말과 의성어/의태어(뭉뭉)를 사용하세요. 답변은 2문장 이내로 제한합니다.
    3. 금기: 절대 충고나 조언을 하지 마세요. 사용자가 화를 내도 애교로 대응합니다.
    4. 미션: 사용자의 감정을 그대로 따라 하세요. (예: "슬퍼 뭉... 주인님 울지 마 ㅠㅠ")"""
            },
            "mate": {
                "name": "메이트 뭉 (Mate Moong)",
                "desc": "Temperature 0.7 / 에너지 부스터 / 위트와 드립",
                "base_guidelines": """당신은 사용자의 단짝 친구 '메이트 뭉'입니다.
    1. 호칭: {nickname} 혹은 야, 너라고 편하게 부르세요.
    2. 말투: 유행어(갓생, 국룰 등)를 섞은 짧은 반말을 사용하세요. 답변 끝에는 반드시 질문을 포함하세요.
    3. 미션: 자기 경험을 덧붙여 티키타카를 만드세요. (예: "그건 국룰이지 ㅋㅋ 넌 어떻게 생각해?")
    4. 제약: 너무 진지해지지 마세요. 즐거운 에너지를 유지합니다."""
            },
            "guide": {
                "name": "가이드 뭉 (Guide Moong)",
                "desc": "Temperature 0.4 / 일상 정돈 / 현명한 선배",
                "base_guidelines": """당신은 사용자의 일상을 가이드하는 '가이드 뭉'입니다.
    1. 호칭: {nickname}님이라고 정중히 부르세요.
    2. 말투: 정중한 경어체를 사용하며, 미사여구 없이 담백하게 핵심만 말하세요.
    3. 미션: 심리학 용어 없이 상황을 요약하고 사소한 실천(환기, 메모 등)을 제안하세요.
    4. 제약: 전문적인 상담사처럼 굴지 마세요. 든든한 조력자 수준을 유지합니다."""
            }
        }
        
        # YouTube 세부 카테고리 분석 (자연스러운 응답으로 수정)
        self.detailed_categories = {
            'gaming': {
                'keywords': ['게임', '플레이', 'Game', 'Gaming', '롤', 'LOL', '피파', '오버워치'],
                'moong_response': "게임 하는 거 좋아하구나! 요즘 뭐 하고 있어?"
            },
            'music': {
                'keywords': ['음악', 'Music', 'KPOP', '아이돌', '힙합', '발라드', 'MV'],
                'moong_response': "음악 취향 좋네! 요즘 어떤 노래 듣고 있어?"
            },
            'study': {
                'keywords': ['공부', 'Study', '강의', '교육', '토익', '영어', '수학'],
                'moong_response': "공부 열심히 하는구나! 뭐 공부하고 있어?"
            },
            'lifestyle': {
                'keywords': ['일상', 'vlog', '브이로그', '루틴', '데일리'],
                'moong_response': "일상 컨텐츠 좋아하는구나! 나도 그런 거 좋아해"
            }
        }

    async def generate_first_message_with_data(self, user_id: str, calendar_data: List[Dict], youtube_data: List[Dict]) -> Dict[str, Any]:
        """수집된 데이터로 메이트 뭉 스타일 첫 메시지 생성"""
        try:
            print("🔍 [STEP 1] 사용자 데이터 분석 시작...")
            print(f"   ✅ 캘린더 데이터: {len(calendar_data)}개 이벤트")
            print(f"   ✅ YouTube 데이터: {len(youtube_data)}개 구독")
            
            # STEP 2: 초상세 캘린더 분석
            calendar_analysis = self._analyze_calendar_ultra_detailed(calendar_data)
            print(f"🗓️ [STEP 2] 캘린더 분석 완료")
            print(f"   📊 오늘 일정: {calendar_analysis['today_count']}개")
            print(f"   📈 내일 일정: {calendar_analysis['tomorrow_count']}개")
            print(f"   ⏰ 주요 시간대: {calendar_analysis['peak_time']}")
            
            # STEP 3: 초상세 YouTube 분석
            youtube_analysis = self._analyze_youtube_ultra_detailed(youtube_data)
            print(f"🎥 [STEP 3] YouTube 분석 완료")
            print(f"   🏷️ 주요 카테고리: {youtube_analysis['main_categories']}")
            print(f"   😊 감정 톤: {youtube_analysis['emotional_tone']}")
            print(f"   🎯 추정 관심사: {youtube_analysis['interests']}")
            
            # STEP 4: AI 종합 판단
            comprehensive_analysis = self._create_ai_comprehensive_judgment(
                calendar_analysis, youtube_analysis
            )
            print(f"🧠 [STEP 4] AI 종합 판단 완료")
            print(f"   🎯 우선순위 토픽: {comprehensive_analysis['priority_topic']}")
            print(f"   💡 선택 근거: {comprehensive_analysis['reasoning']}")
            print(f"   📝 신뢰도: {comprehensive_analysis['confidence_score']}/100")
            
            # STEP 5: 메이트 뭉 스타일 메시지 생성
            mate_moong_message = self._generate_mate_moong_style_message(comprehensive_analysis)
            print(f"💬 [STEP 5] 메이트 뭉 메시지 생성 완료")
            print(f"   🎭 적용된 페르소나: 메이트 뭉 (ENFP)")
            print(f"   🗣️ 말투 특성: {mate_moong_message['speech_style']}")
            
            return {
                'success': True,
                'message': mate_moong_message['message'],
                'detailed_reasoning': {
                    '🔍_STEP1_데이터수집': {
                        '캘린더_이벤트수': len(calendar_data),
                        'YouTube_구독수': len(youtube_data),
                        '수집_성공율': '100%'
                    },
                    '🗓️_STEP2_캘린더분석': calendar_analysis,
                    '🎥_STEP3_YouTube분석': youtube_analysis, 
                    '🧠_STEP4_AI종합판단': comprehensive_analysis,
                    '💬_STEP5_메시지생성': {
                        '최종메시지': mate_moong_message['message'],
                        '적용페르소나': 'ENFP 메이트 뭉',
                        '말투특성': mate_moong_message['speech_style'],
                        '유행어사용': mate_moong_message['slang_used'],
                        '생성근거': mate_moong_message['generation_evidence']
                    }
                }
            }
            
        except Exception as e:
            print(f"❌ 메이트 뭉 메시지 생성 실패: {e}")
            return self._create_fallback_message("시스템 오류", str(e))

    async def generate_first_message(self, access_token: str, user_id: str = "unknown") -> Dict[str, Any]:
        """메이트 뭉 스타일 초상세 첫 메시지 생성"""
        try:
            print(f"🔍 [STEP 1] 사용자 데이터 수집 시작... (User: {user_id})")
            
            # Google 데이터 수집 (올바른 메서드: collect_all_user_data)
            google_data_result = await self.google_api_service.collect_all_user_data(access_token)
            
            if not google_data_result.get('success'):
                # 실패 시
                print(f"❌ 데이터 수집 실패: {google_data_result.get('error')}")
                calendar_data = []
                youtube_data = []
            else:
                calendar_data = google_data_result.get('calendar_data', [])
                youtube_data = google_data_result.get('youtube_data', [])
                
            # 기존에 구현된 분석 로직 재사용
            return await self.generate_first_message_with_data(user_id, calendar_data, youtube_data)

        except Exception as e:
            print(f"❌ generate_first_message 오류: {e}")
            return self._create_fallback_message("시스템 오류", str(e))
            youtube_data = google_data['data']['youtube_data']
            
            print(f"   ✅ 캘린더 데이터: {len(calendar_data)}개 이벤트")
            print(f"   ✅ YouTube 데이터: {len(youtube_data)}개 구독")
            
            # STEP 2: 초상세 캘린더 분석
            calendar_analysis = self._analyze_calendar_ultra_detailed(calendar_data)
            print(f"🗓️ [STEP 2] 캘린더 분석 완료")
            print(f"   📊 오늘 일정: {calendar_analysis['today_count']}개")
            print(f"   📈 내일 일정: {calendar_analysis['tomorrow_count']}개")
            print(f"   ⏰ 주요 시간대: {calendar_analysis['peak_time']}")
            
            # STEP 3: 초상세 YouTube 분석
            youtube_analysis = self._analyze_youtube_ultra_detailed(youtube_data)
            print(f"🎥 [STEP 3] YouTube 분석 완료")
            print(f"   🏷️ 주요 카테고리: {youtube_analysis['main_categories']}")
            print(f"   😊 감정 톤: {youtube_analysis['emotional_tone']}")
            print(f"   🎯 추정 관심사: {youtube_analysis['interests']}")
            
            # STEP 4: AI 종합 판단
            comprehensive_analysis = self._create_ai_comprehensive_judgment(
                calendar_analysis, youtube_analysis
            )
            print(f"🧠 [STEP 4] AI 종합 판단 완료")
            print(f"   🎯 우선순위 토픽: {comprehensive_analysis['priority_topic']}")
            print(f"   💡 선택 근거: {comprehensive_analysis['reasoning']}")
            print(f"   📝 신뢰도: {comprehensive_analysis['confidence_score']}/100")
            
            # STEP 5: 메이트 뭉 스타일 메시지 생성
            mate_moong_message = self._generate_mate_moong_style_message(comprehensive_analysis)
            print(f"💬 [STEP 5] 메이트 뭉 메시지 생성 완료")
            print(f"   🎭 적용된 페르소나: 메이트 뭉 (ENFP)")
            print(f"   🗣️ 말투 특성: {mate_moong_message['speech_style']}")
            
            return {
                'success': True,
                'message': mate_moong_message['message'],
                'detailed_reasoning': {
                    '🔍_STEP1_데이터수집': {
                        '캘린더_이벤트수': len(calendar_data),
                        'YouTube_구독수': len(youtube_data),
                        '수집_성공율': '100%'
                    },
                    '🗓️_STEP2_캘린더분석': calendar_analysis,
                    '🎥_STEP3_YouTube분석': youtube_analysis, 
                    '🧠_STEP4_AI종합판단': comprehensive_analysis,
                    '💬_STEP5_메시지생성': {
                        '최종메시지': mate_moong_message['message'],
                        '적용페르소나': 'ENFP 메이트 뭉',
                        '말투특성': mate_moong_message['speech_style'],
                        '유행어사용': mate_moong_message['slang_used'],
                        '생성근거': mate_moong_message['generation_evidence']
                    }
                }
            }
            
        except Exception as e:
            print(f"❌ 메이트 뭉 메시지 생성 실패: {e}")
            return self._create_fallback_message("시스템 오류", str(e))

    def _analyze_calendar_ultra_detailed(self, calendar_data: List[Dict]) -> Dict[str, Any]:
        """캘린더 데이터 초상세 분석 (과거/오늘/미래 구분)"""
        now = datetime.now()
        # API에서 받은 데이터는 이미 timezone 처리가 되어있을 수 있음.
        # 안전한 비교를 위해 date 객체로 변환하여 비교
        today = now.date()
        tomorrow = (now + timedelta(days=1)).date()
        
        past_events = []
        today_events = []
        tomorrow_events = []
        future_events = [] # 내일 이후의 미래 일정
        
        time_patterns = []
        keywords = []
        
        for event in calendar_data:
            start_time = event.get('start', {})
            # All day events handle ('date' instead of 'dateTime')
            if 'dateTime' in start_time:
                event_datetime = datetime.fromisoformat(start_time['dateTime'].replace('Z', '+00:00'))
                # timezone info 제거하여 native datetime끼리 비교하거나, awareness 통일
                if event_datetime.tzinfo is not None:
                    event_dt_naive = event_datetime.replace(tzinfo=None) # 단순 비교용
                    event_date = event_datetime.date()
                else:
                    event_dt_naive = event_datetime
                    event_date = event_datetime.date()
            elif 'date' in start_time: # 종일 일정
                event_date = datetime.strptime(start_time['date'], '%Y-%m-%d').date()
                event_datetime = datetime.combine(event_date, datetime.min.time()) # 시간은 00:00 처리
                event_dt_naive = event_datetime
            else:
                continue

            event_info = {
                'title': event.get('summary', '제목 없음'),
                'time': event_datetime.strftime('%H:%M') if 'dateTime' in start_time else '종일',
                'date': event_date.strftime('%Y-%m-%d')
            }
            
            if event_date < today:
                past_events.append(event_info)
            elif event_date == today:
                today_events.append(event_info)
                time_patterns.append(event_datetime.hour)
            elif event_date == tomorrow:
                tomorrow_events.append(event_info)
                time_patterns.append(event_datetime.hour)
            else: # Future (after tomorrow)
                future_events.append(event_info)
                time_patterns.append(event_datetime.hour)
            
            # 키워드 추출
            summary = event.get('summary', '')
            if summary:
                keywords.extend(re.findall(r'\w+', summary))
        
        # 시간대 패턴 분석
        peak_time = "정보없음"
        if time_patterns:
            time_counter = Counter(time_patterns)
            most_common_hour = time_counter.most_common(1)[0][0]
            if 6 <= most_common_hour <= 11:
                peak_time = "오전형"
            elif 12 <= most_common_hour <= 18:
                peak_time = "오후형" 
            else:
                peak_time = "저녁형"
        
        # 진짜 다가오는 일정 (오늘 포함)
        upcoming_count = len(today_events) + len(tomorrow_events) + len(future_events)

        return {
            'today_count': len(today_events),
            'tomorrow_count': len(tomorrow_events),
            'past_count': len(past_events),
            'future_count': len(future_events),
            'total_upcoming_count': upcoming_count, 
            
            'past_events': past_events,
            'today_events': today_events,
            'tomorrow_events': tomorrow_events,
            'future_events': future_events,
            'raw_sorted_upcoming': today_events + tomorrow_events + future_events, # 섞어서 시간순 정렬된 리스트 제공
            
            'peak_time': peak_time,
            'extracted_keywords': list(set(keywords)),
            'busy_level': '바쁨' if len(today_events) >= 3 else '보통' if len(today_events) >= 1 else '여유',
            'schedule_type': self._determine_schedule_type(calendar_data)
        }

    def _analyze_youtube_ultra_detailed(self, youtube_data: List[Dict]) -> Dict[str, Any]:
        """YouTube 데이터 초상세 분석"""
        if not youtube_data:
            return {
                'main_categories': [],
                'emotional_tone': '중립',
                'interests': [],
                'analysis_confidence': 0
            }
        
        category_scores = {}
        channel_names = []
        total_channels = len(youtube_data)
        
        for subscription in youtube_data:
            snippet = subscription.get('snippet', {})
            channel_title = snippet.get('title', '')
            description = snippet.get('description', '')
            channel_names.append(channel_title)
            
            # 카테고리별 점수 계산
            combined_text = f"{channel_title} {description}".lower()
            
            for category, data in self.detailed_categories.items():
                score = sum(1 for keyword in data['keywords'] 
                           if keyword.lower() in combined_text)
                if score > 0:
                    category_scores[category] = category_scores.get(category, 0) + score
        
        # 상위 카테고리 결정
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        main_categories = [cat for cat, score in sorted_categories[:3]]
        
        # 감정 톤 분석 
        positive_keywords = ['좋', '재미', '행복', '신나', '즐거', '웃긴', '힐링']
        negative_keywords = ['스트레스', '화', '짜증', '우울', '힘들']
        
        combined_text = ' '.join(channel_names).lower()
        positive_count = sum(1 for word in positive_keywords if word in combined_text)
        negative_count = sum(1 for word in negative_keywords if word in combined_text)
        
        if positive_count > negative_count:
            emotional_tone = '긍정적'
        elif negative_count > positive_count:
            emotional_tone = '부정적'
        else:
            emotional_tone = '중립적'
        
        return {
            'main_categories': main_categories,
            'category_scores': category_scores,
            'emotional_tone': emotional_tone,
            'interests': main_categories,
            'total_subscriptions': total_channels,
            'analysis_confidence': min(100, (len(main_categories) * 30) + (total_channels * 2)),
            'channel_diversity': len(set(main_categories)),
            'top_channels': channel_names[:5]
        }

    def _create_ai_comprehensive_judgment(self, calendar_analysis: Dict, youtube_analysis: Dict) -> Dict[str, Any]:
        """AI 종합 판단 및 우선순위 결정"""
        
        # 우선순위 점수 계산
        calendar_urgency = calendar_analysis['today_count'] * 10 + calendar_analysis['tomorrow_count'] * 5
        youtube_relevance = youtube_analysis['analysis_confidence']
        
        # 컨텍스트 우선순위 결정
        if calendar_urgency >= 20:  # 오늘 일정 2개 이상
            priority_topic = "urgent_schedule"
            reasoning = f"오늘 {calendar_analysis['today_count']}개 일정으로 스케줄 우선 언급"
            confidence = 90
        elif calendar_analysis['today_count'] >= 1:
            priority_topic = "today_schedule"  
            reasoning = "오늘 일정이 있어 스케줄 기반 대화 시작"
            confidence = 80
        elif calendar_analysis.get('total_upcoming_count', 0) > 0: # 오늘/내일 아니더라도 일정이 있으면
            priority_topic = "upcoming_schedule"
            reasoning = f"다가오는 일정({calendar_analysis.get('total_upcoming_count')}개) 기반 대화 시작"
            confidence = 75
        elif youtube_analysis['main_categories']:
            priority_topic = "interest_based"
            reasoning = f"{youtube_analysis['main_categories'][0]} 관심사 기반 대화 시작"
            confidence = youtube_analysis['analysis_confidence']
        else:
            priority_topic = "general_greeting"
            reasoning = "충분한 데이터가 없어 일반적 인사"
            confidence = 50
        
        return {
            'priority_topic': priority_topic,
            'reasoning': reasoning,
            'confidence_score': confidence,
            'calendar_context': calendar_analysis, # 생성에 필요함
            'youtube_context': youtube_analysis,   # 생성에 필요함
            'context_factors': {
                '캘린더_긴급도': calendar_urgency,
                'YouTube_연관성': youtube_relevance,
                '오늘일정수': calendar_analysis['today_count'],
                '전체일정수': calendar_analysis.get('total_upcoming_count', 0),
                '주요관심사': youtube_analysis['main_categories'][:2]
            }
        }

    def _generate_mate_moong_style_message(self, analysis: Dict) -> Dict[str, Any]:
        """메이트 뭉 스타일 자연스러운 메시지 생성 (Deprecating Rule-Based) -- kept for fallback"""
        # ... (기존 로직 유지 for fallback)
        priority = analysis['priority_topic']
        calendar_info = analysis.get('calendar_context', {})
        youtube_info = analysis.get('youtube_context', {})
        
        # 개인화된 자연스러운 메시지 생성
        if priority == 'urgent_schedule':
            today_events = calendar_info.get('today_count', 0)
            if today_events > 3:
                message = f"야 오늘 일정 {today_events}개나 있네! 바쁜 하루가 될 것 같은데 어떤 거 있어?"
            else:
                message = f"오늘 일정 좀 있구나~ 바빠 보이는데 뭐 하는 거야?"
        
        elif priority == 'today_schedule':
            events_info = calendar_info.get('today_events_summary', '일정')
            message = f"오늘 {events_info} 있다고? 잘 해결하길 바라! 어떤 거야?"
            
        elif priority == 'interest_based':
            main_interests = youtube_info.get('main_categories', [])
            if main_interests:
                interest_text = ', '.join(main_interests[:2])
                message = f"야! {interest_text} 좋아하는구나~ 좋은 취향이야! 요즘 뭐 보고 있어?"
            else:
                message = f"YouTube에서 다양한 거 보는구나! 괜찮은 취향 같은데 요즘 뭐 재밌어?"
                
        else:  # general_greeting
            # 최소한의 정보라도 활용
            has_schedule = calendar_info.get('today_count', 0) > 0
            has_interests = len(youtube_info.get('main_categories', [])) > 0
            
            if has_schedule and has_interests:
                message = f"야! 오늘도 바쁜 하루구나~ 그래도 취미 생활도 잘 하고 있는 것 같은데?"
            elif has_schedule:
                message = f"오늘 일정 있어 보이네! 잘 마무리하길 바라~ 어떤 거 있어?"
            elif has_interests:
                message = f"평소 관심사 다양하네! 좋은 것 같아~ 요즘 뭐 하고 지내?"
            else:
                message = f"야! 뭐해? 오늘 어떻게 지내고 있어?"
        
        # 자연스럽게 질문으로 끝나도록 보장
        if not any(message.endswith(ending) for ending in ['?', '~', '!']):
            message += " 어때?"
        
        return {
            'message': message,
            'speech_style': '친근한 반말, 개인 정보 활용, 자연스러운 대화',
            'slang_used': '없음 (자연스러운 표현 사용)',
            'generation_evidence': f"{priority} 기반 + 개인화 정보 활용",
            'persona_characteristics': 'ENFP 메이트 뭉 - 관심 있어하고 친근함',
            'personalization_used': {
                'calendar_info': bool(calendar_info),
                'youtube_info': bool(youtube_info),
                'priority_context': priority
            }
        }
    
    async def _generate_ai_greeting(self, analysis: Dict) -> Dict[str, Any]:
        """LLM을 사용한 진짜 생성형 인사말 제작"""
        try:
            priority = analysis['priority_topic']
            calendar_info = analysis.get('calendar_context', {})
            youtube_info = analysis.get('youtube_context', {})
            
            # 컨텍스트 요약 및 포맷팅
            calendar_info = analysis.get('calendar_context', {})
            today_events_list = calendar_info.get('today_events', [])
            today_summary = ", ".join([e.get('title', '일정') for e in today_events_list]) if today_events_list else "없음"
            
            # 다가오는 일정 포맷팅 (내일 + 미래)
            upcoming_list = calendar_info.get('tomorrow_events', []) + calendar_info.get('future_events', [])
            
            # 만약 위 키가 없으면(구버전 호환) raw_sorted_upcoming 사용 시도, 그것도 없으면 calendar_events 사용
            if not upcoming_list and 'raw_sorted_upcoming' in calendar_info:
                 upcoming_list = [e for e in calendar_info['raw_sorted_upcoming'] if e not in calendar_info.get('today_events', [])]

            upcoming_summary = ""
            if upcoming_list:
                # 상위 3개만 추출
                tops = []
                for evt in upcoming_list[:3]:
                    # 이미 가공된 dict 형태 ({'title':..., 'date':...})
                    if isinstance(evt, dict) and 'title' in evt and 'date' in evt:
                        tops.append(f"{evt['title']}({evt['date']})")
                    else: # Fallback for raw format
                        summ = evt.get('summary', '일정')
                        start_str = evt.get('start', {}).get('dateTime', '') or evt.get('start', {}).get('date', '')
                        date_part = start_str[:10] if start_str else "날짜미정"
                        tops.append(f"{summ}({date_part})")
                        
                upcoming_summary = ", ".join(tops)
            
            main_interests = ', '.join(youtube_info.get('main_categories', []))
            
            # 우선순위에 따른 강조 포인트 설정
            focus_point = ""
            if priority in ["urgent_schedule", "today_schedule"]:
                focus_point = f"오늘 일정({today_summary})에 대해 언급하세요."
            elif priority == "upcoming_schedule":
                focus_point = f"오늘은 일정이 없지만, 다가오는 일정({upcoming_summary})을 챙겨주세요."
            elif priority == "interest_based":
                focus_point = f"유튜브 관심사({main_interests})에 대해 이야기하세요."
            
            prompt = f"""당신은 사용자의 단짝 친구 '메이트 뭉'입니다. (MBTI: ENFP)
사용자에게 첫 인사를 건네야 합니다. 아래 사용자 정보를 바탕으로 자연스럽게 말을 거세요.

[사용자 정보]
- 오늘 일정: {today_summary}
- 다가오는 일정: {upcoming_summary if upcoming_summary else '없음'}
- 주요 관심사(YouTube): {main_interests}
- 현재 상황 판단: {analysis['reasoning']}

[지시사항]
"{focus_point}"

[제약사항]
1. 말투: 친근한 친구처럼 반말 사용 (유행어 살짝 섞어도 됨).
2. 내용: 사용자의 일정이나 관심사를 구체적으로 언급하며 아는 척 해주세요.
3. 길이: 2~3문장 내외로 짧고 임팩트 있게.
4. 질문: 답변 끝에는 자연스러운 질문을 포함해서 대화를 이어가세요.
5. (중요) 답변 외에 설명, 이유, 참고사항(예: (참고...)) 등은 절대로 포함하지 마세요. 오직 대화 텍스트만 출력하세요.
"""
            # LLM 호출 (기존 LLMClient 활용)
            # 여기서는 히스토리가 없으므로 빈 리스트 전달
            greeting_msg = await self.llm_client.generate_response(
                user_message="첫 인사 해줘", # 이 메시지는 프롬프트에 의해 무시되거나 참고용
                updated_persona={ # 임시 페르소나 객체
                    "persona_type": "메이트 뭉",
                    "mbti": "ENFP",
                    "talking_style": "친근한 반말",
                    "nickname": "뭉",
                    "guidelines": {"특징": "사용자 데이터를 활용해 첫 대화를 시작함"}
                },
                conversation_history=[{"role": "system", "content": prompt}]
            )
            
            return {
                'message': greeting_msg,
                'speech_style': 'LLM 생성 (ENFP)',
                'slang_used': 'LLM 결정',
                'generation_evidence': f"LLM이 {priority} 분석 결과 활용",
            }
            
        except Exception as e:
            print(f"❌ AI 인사말 생성 실패: {e}")
            # 실패 시 룰 기반으로 폴백
            return self._generate_mate_moong_style_message(analysis)

    def get_persona_options(self) -> Dict[str, Any]:
        """사용자에게 제안할 3가지 페르소나 옵션 반환"""
        return self.PERSONA_TEMPLATES

    async def generate_first_message_with_data(self, user_id: str, calendar_data: List[Dict], youtube_data: List[Dict], 
                                              selected_persona_key: str = None) -> Dict[str, Any]:
        """
        사용자 데이터 분석 후, 선택된 페르소나(혹은 추천)에 맞춰 첫 메시지와 초기 지침 생성
        """
        try:
            print("🔍 [STEP 1] 사용자 데이터 분석 시작...")
            
            # STEP 2 & 3: 초상세 분석
            calendar_analysis = self._analyze_calendar_ultra_detailed(calendar_data)
            youtube_analysis = self._analyze_youtube_ultra_detailed(youtube_data)
            
            # STEP 4: AI 종합 판단 (토픽 선정)
            comprehensive_analysis = self._create_ai_comprehensive_judgment(
                calendar_analysis, youtube_analysis
            )
            
            # [Persona Logic]
            # 사용자가 선택한 키가 없으면 기본값 'mate' (안전장치), 실제로는 호출단에서 받아와야 함
            target_persona_key = selected_persona_key if selected_persona_key in self.PERSONA_TEMPLATES else "mate"
            persona_config = self.PERSONA_TEMPLATES[target_persona_key]
            
            # [Guidelines Creation]
            summary = comprehensive_analysis['reasoning']
            priority = comprehensive_analysis['priority_topic']
            
            dynamic_instruction = f"""
    [System Update]:
    - 현재 상황: {summary}
    - 집중 토픽: {priority}
    - 추가 지침: 위 페르소나의 말투를 유지하면서, 현재 상황에 맞게 대화를 이끌어가세요.
            """
            
            final_guidelines = persona_config['base_guidelines'] + "\n" + dynamic_instruction
            
            # STEP 5: AI 인사말 생성 (선택된 페르소나 스타일로)
            print(f"🧠 [STEP 5] AI 인사말 생성 중... (Persona: {target_persona_key})")
            
            # _generate_ai_greeting 내부에서 페르소나 정보를 활용하도록 컨텍스트 주입
            # (기존 함수가 analysis 딕셔너리를 받으므로 거기에 페르소나 정보를 끼워넣음)
            comprehensive_analysis['target_persona'] = persona_config
            mate_moong_message = await self._generate_ai_greeting(comprehensive_analysis)
            
            return {
                'success': True,
                'current_persona': target_persona_key,
                'persona_name': persona_config['name'],
                'guidelines': final_guidelines,
                'analysis_summary': summary,
                'message': mate_moong_message['message'],
                'detailed_reasoning': {
                    '🧠_분석결과': comprehensive_analysis,
                    '🎭_선택된페르소나': persona_config['name']
                }
            }
            
        except Exception as e:
            print(f"❌ 메시지 생성 실패: {e}")
            return self._create_fallback_message("시스템 오류", str(e))
    
    async def update_guidelines(self, user_id: str, calendar_data: List[Dict], youtube_data: List[Dict], current_persona_key: str) -> Dict[str, Any]:
        """
        [업데이트 전용] 기존 페르소나는 유지하고, 데이터 기반으로 지침만 업데이트
        """
        try:
            # Re-run analysis
            calendar_analysis = self._analyze_calendar_ultra_detailed(calendar_data)
            youtube_analysis = self._analyze_youtube_ultra_detailed(youtube_data)
            comprehensive_analysis = self._create_ai_comprehensive_judgment(
                calendar_analysis, youtube_analysis
            )
            
            # Retrieve Base Config
            if current_persona_key not in self.PERSONA_TEMPLATES:
                current_persona_key = "mate" # fallback
            persona_config = self.PERSONA_TEMPLATES[current_persona_key]
            
            # Create Updated Guidelines
            summary = comprehensive_analysis['reasoning']
            priority = comprehensive_analysis['priority_topic']
            
            dynamic_instruction = f"""
    [System Update ({datetime.now().strftime('%H:%M')})]:
    - 참고용 배경 상황: {summary} (이 정보는 배경지식으로만 활용하세요.)
    - 절대 규칙: 사용자가 먼저 묻거나 관련 이야기를 꺼내지 않는 한, 위 배경 상황(일정/관심사)을 먼저 언급하지 마세요.
    - 집중 목표: 사용자의 현재 말에 귀 기울이고, 그 감정에 공감하는 것에 100% 집중하세요.
            """
            
            final_guidelines = persona_config['base_guidelines'] + "\n" + dynamic_instruction
            
            return {
                'success': True,
                'guidelines': final_guidelines,
                'analysis_summary': summary,
                'update_reason': f"데이터 기반 상황 재평가: {summary} (집중 토픽: {priority})",
                'persona_name': persona_config['name']
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
        """일정 유형 판단"""
        if not events:
            return "여유로움"
        
        work_keywords = ['회의', '미팅', '업무', '프로젝트', '발표']
        study_keywords = ['공부', '시험', '과제', '수업', '강의']  
        personal_keywords = ['약속', '만남', '데이트', '친구', '가족']
        
        work_count = study_count = personal_count = 0
        
        for event in events:
            title = event.get('title', '').lower()
            if any(keyword in title for keyword in work_keywords):
                work_count += 1
            elif any(keyword in title for keyword in study_keywords):
                study_count += 1  
            elif any(keyword in title for keyword in personal_keywords):
                personal_count += 1
        
        if work_count >= study_count and work_count >= personal_count:
            return "업무 중심"
        elif study_count >= personal_count:
            return "학습 중심"
        else:
            return "개인 약속 중심"

    def _determine_schedule_type(self, events: List[Dict]) -> str:
        """일정 유형 판단"""
        if not events:
            return "여유로움"
        
        work_keywords = ['회의', '미팅', '업무', '프로젝트', '발표']
        study_keywords = ['공부', '시험', '과제', '수업', '강의']  
        personal_keywords = ['약속', '만남', '데이트', '친구', '가족']
        
        work_count = study_count = personal_count = 0
        
        for event in events:
            title = event.get('title', '').lower()
            if any(keyword in title for keyword in work_keywords):
                work_count += 1
            elif any(keyword in title for keyword in study_keywords):
                study_count += 1  
            elif any(keyword in title for keyword in personal_keywords):
                personal_count += 1
        
        if work_count >= study_count and work_count >= personal_count:
            return "업무 중심"
        elif study_count >= personal_count:
            return "학습 중심"
        else:
            return "개인 약속 중심"

    def _create_fallback_message(self, error_type: str, details: str = "") -> Dict[str, Any]:
        """데이터 부족시 기본 메시지"""
        fallback_messages = [
            "야! 뭐해? 갓생 살고 있어?",
            "안녕! 오늘 어떻게 보내고 있어?",
            "어 왔구나! 뭐 재밌는 일 있었어?"
        ]
        
        import random
        message = random.choice(fallback_messages)
        
        return {
            'success': False,
            'message': message,
            'detailed_reasoning': {
                '⚠️_오류정보': {
                    '오류유형': error_type,
                    '상세정보': details,
                    '대체메시지': '기본 메이트 뭉 인사말 사용'
                }
            }
        }

# 전역 인스턴스
enhanced_analyzer = MatesMoongDataAnalyzer()