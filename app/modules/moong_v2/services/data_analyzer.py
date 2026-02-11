"""
구글 API 데이터 분석 서비스
- YouTube 구독 채널에서 관심사 추출
- Calendar 일정에서 오늘/내일 이벤트 추출
- 첫 대화 생성을 위한 데이터 가공
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import re
from collections import Counter

class GoogleDataAnalyzer:
    """구글 API 데이터 분석 클래스"""
    
    def __init__(self):
        # YouTube 카테고리 키워드 맵핑
        self.youtube_categories = {
            'Gaming': ['게임', '플레이', 'Game', 'Gaming', 'PlayStation', 'Xbox', 'Switch'],
            'Music': ['음악', 'Music', 'Song', '노래', 'MV', 'Official', 'Cover'],
            'Cooking': ['요리', 'Cook', 'Recipe', 'Food', '맛집', '레시피'],
            'Tech': ['테크', 'Tech', 'Review', '리뷰', 'iPhone', 'Samsung', '컴퓨터'],
            'Beauty': ['뷰티', 'Beauty', 'Makeup', '화장품', '스킨케어'],
            'Sports': ['스포츠', 'Sports', '축구', '야구', '농구', 'Football', 'Soccer'],
            'Travel': ['여행', 'Travel', 'Trip', '맛집', '관광'],
            'Education': ['교육', 'Education', '강의', 'Lecture', '공부', 'Study'],
            'Comedy': ['코미디', 'Comedy', '개그', '웃긴', 'Funny'],
            'News': ['뉴스', 'News', '시사', 'Politics', '정치']
        }
    
    def analyze_youtube_data(self, youtube_data: Dict[str, Any]) -> Dict[str, Any]:
        """YouTube 데이터 분석하여 관심사 추출"""
        try:
            subscriptions = youtube_data.get('subscriptions', [])
            if not subscriptions:
                return {'interests': [], 'main_interest': None}
            
            # 구독 채널명에서 키워드 추출
            all_keywords = []
            channel_names = []
            
            for sub in subscriptions:
                channel_name = sub.get('snippet', {}).get('title', '')
                description = sub.get('snippet', {}).get('description', '')
                channel_names.append(channel_name)
                
                # 채널명과 설명에서 키워드 찾기
                text_to_analyze = f"{channel_name} {description}".lower()
                
                for category, keywords in self.youtube_categories.items():
                    for keyword in keywords:
                        if keyword.lower() in text_to_analyze:
                            all_keywords.append(category)
            
            # 관심사 빈도수 계산
            interest_counts = Counter(all_keywords)
            top_interests = interest_counts.most_common(3)
            
            interests = [interest[0] for interest in top_interests]
            main_interest = interests[0] if interests else None
            
            return {
                'interests': interests,
                'main_interest': main_interest,
                'channel_count': len(subscriptions),
                'sample_channels': channel_names[:3],  # 상위 3개 채널명
                'interest_distribution': dict(interest_counts)
            }
            
        except Exception as e:
            print(f"❌ YouTube 데이터 분석 실패: {e}")
            return {'interests': [], 'main_interest': None}
    
    def analyze_calendar_data(self, calendar_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calendar 데이터 분석하여 오늘/내일 일정 추출"""
        try:
            events = calendar_data.get('upcoming_events', [])
            if not events:
                return {'today_events': [], 'tomorrow_events': [], 'has_upcoming': False}
            
            now = datetime.now()
            today = now.date()
            tomorrow = (now + timedelta(days=1)).date()
            
            today_events = []
            tomorrow_events = []
            
            for event in events:
                try:
                    # 이벤트 시작 시간 파싱
                    start = event.get('start', {})
                    start_datetime = start.get('dateTime') or start.get('date')
                    
                    if start_datetime:
                        # ISO 포맷 시간 파싱
                        if 'T' in start_datetime:
                            event_date = datetime.fromisoformat(start_datetime.replace('Z', '+00:00')).date()
                        else:
                            event_date = datetime.fromisoformat(start_datetime).date()
                        
                        event_info = {
                            'title': event.get('summary', '제목 없음'),
                            'time': start_datetime,
                            'description': event.get('description', '')
                        }
                        
                        if event_date == today:
                            today_events.append(event_info)
                        elif event_date == tomorrow:
                            tomorrow_events.append(event_info)
                            
                except Exception as e:
                    print(f"⚠️ 이벤트 파싱 실패: {e}")
                    continue
            
            return {
                'today_events': today_events,
                'tomorrow_events': tomorrow_events,
                'has_upcoming': len(today_events) > 0 or len(tomorrow_events) > 0,
                'total_events': len(events)
            }
            
        except Exception as e:
            print(f"❌ Calendar 데이터 분석 실패: {e}")
            return {'today_events': [], 'tomorrow_events': [], 'has_upcoming': False}
    
    def generate_first_message(self, user_info: Dict[str, Any], 
                              youtube_analysis: Dict[str, Any], 
                              calendar_analysis: Dict[str, Any], 
                              persona: str = 'pet') -> Dict[str, Any]:
        """분석 결과를 바탕으로 첫 대화 메시지 생성 (상세 근거 포함)"""
        try:
            name = user_info.get('name', '').split(' ')[0] if user_info.get('name') else '친구'
            
            # 분석 근거 수집
            analysis_evidence = {
                'user_profile': {
                    'name': user_info.get('name', '알 수 없음'),
                    'email': user_info.get('email', '알 수 없음'),
                    'google_id': user_info.get('google_id', '알 수 없음')
                },
                'youtube_insights': {
                    'subscription_count': len(youtube_analysis.get('interests', [])),
                    'main_interest': youtube_analysis.get('main_interest'),
                    'all_interests': youtube_analysis.get('interests', []),
                    'interest_diversity': len(set(youtube_analysis.get('interests', [])))
                },
                'calendar_insights': {
                    'today_events_count': len(calendar_analysis.get('today_events', [])),
                    'tomorrow_events_count': len(calendar_analysis.get('tomorrow_events', [])),
                    'has_upcoming': calendar_analysis.get('has_upcoming', False),
                    'today_events': calendar_analysis.get('today_events', []),
                    'tomorrow_events': calendar_analysis.get('tomorrow_events', [])
                }
            }
            
            # 페르소나별 말투 정의
            persona_styles = {
                'pet': {
                    'greeting': f"안녕 {name}! 🐱",
                    'schedule_prefix': "오늘 ",
                    'schedule_suffix': " 있구나! 어떤 거야?",
                    'interest_prefix': "평소 ",
                    'interest_suffix': " 좋아하는구나! 뭐가 제일 재밌어?",
                    'default': f"안녕 {name}! 오늘 뭐 하고 놀까? 😊"
                },
                'mate': {
                    'greeting': f"안녕하세요 {name}님! 😊",
                    'schedule_prefix': "오늘 ",
                    'schedule_suffix': " 있으시네요! 준비는 잘 되고 있나요?",
                    'interest_prefix': "평소 ",
                    'interest_suffix': " 관심이 많으시군요! 요즘 어떤 거 보고 계세요?",
                    'default': f"안녕하세요 {name}님! 오늘 하루 어떻게 보내고 계신가요?"
                },
                'guide': {
                    'greeting': f"반갑습니다, {name}님. 🌟",
                    'schedule_prefix': "오늘 ",
                    'schedule_suffix': " 예정이시군요. 준비하실 것이 있으시면 도움드리겠습니다.",
                    'interest_prefix': "",
                    'interest_suffix': " 분야에 관심이 많으시네요. 관련 정보나 조언이 필요하시면 언제든 말씀해 주세요.",
                    'default': f"반갑습니다, {name}님. 오늘 어떤 도움이 필요하신가요?"
                }
            }
            
            style = persona_styles.get(persona, persona_styles['pet'])
            message_generation_logic = []
            
            # 메시지 생성 우선순위 로직
            message = ""
            context_type = ""
            context_data = {}
            
            # 1순위: 오늘 일정 확인
            if calendar_analysis.get('today_events'):
                event = calendar_analysis['today_events'][0]
                event_title = event.get('summary', event.get('title', '일정'))
                message = f"{style['greeting']} {style['schedule_prefix']}{event_title}{style['schedule_suffix']}"
                context_type = 'today_schedule'
                context_data = event
                message_generation_logic.append(f"✅ 오늘 일정 발견: '{event_title}' - 가장 우선순위로 선택")
                if len(calendar_analysis['today_events']) > 1:
                    message_generation_logic.append(f"📝 참고: 오늘 총 {len(calendar_analysis['today_events'])}개 일정 중 첫 번째 선택")
            
            # 2순위: 내일 일정 확인
            elif calendar_analysis.get('tomorrow_events'):
                event = calendar_analysis['tomorrow_events'][0]
                event_title = event.get('summary', event.get('title', '일정'))
                message = f"{style['greeting']} 내일 {event_title} 있으시네요! 준비는 어떠세요?"
                context_type = 'tomorrow_schedule'
                context_data = event
                message_generation_logic.append(f"✅ 내일 일정 발견: '{event_title}' - 오늘 일정 없어서 내일 일정으로 선택")
                message_generation_logic.append("📝 우선순위: 오늘 일정(없음) → 내일 일정(선택됨)")
            
            # 3순위: YouTube 관심사 기반
            elif youtube_analysis.get('main_interest'):
                interest = youtube_analysis['main_interest']
                interests_list = youtube_analysis.get('interests', [])
                message = f"{style['greeting']} {style['interest_prefix']}{interest}{style['interest_suffix']}"
                context_type = 'youtube_interest'
                context_data = {'main_interest': interest, 'all_interests': interests_list}
                message_generation_logic.append(f"✅ 주 관심사 발견: '{interest}' - 일정이 없어서 YouTube 분석으로 전환")
                message_generation_logic.append(f"📺 YouTube 분석: 구독 채널에서 '{interest}' 관련 콘텐츠가 가장 많음")
                if len(interests_list) > 1:
                    message_generation_logic.append(f"🎯 다른 관심사: {', '.join(interests_list[:3])} 등 총 {len(interests_list)}개")
            
            # 4순위: 기본 메시지
            else:
                message = style['default']
                context_type = 'default'
                context_data = {'reason': 'no_data'}
                message_generation_logic.append("⚠️ 분석 가능한 데이터 부족 - 기본 인사말 사용")
                message_generation_logic.append("📊 분석 시도: 오늘 일정(없음) → 내일 일정(없음) → YouTube 관심사(없음) → 기본값")
            
            # 상세 생성 근거 작성
            detailed_reasoning = {
                'message_priority_logic': message_generation_logic,
                'data_analysis_summary': {
                    'calendar_data_available': len(calendar_analysis.get('today_events', [])) > 0 or len(calendar_analysis.get('tomorrow_events', [])) > 0,
                    'youtube_data_available': len(youtube_analysis.get('interests', [])) > 0,
                    'user_profile_complete': bool(user_info.get('name')),
                    'selected_approach': context_type
                },
                'persona_application': {
                    'selected_persona': persona,
                    'greeting_style': style['greeting'],
                    'tone_characteristics': f"{'친근하고 귀여운' if persona == 'pet' else '정중하고 친근한' if persona == 'mate' else '전문적이고 도움이 되는'} 말투 적용"
                }
            }
            
            return {
                'message': message,
                'context_type': context_type,
                'context_data': context_data,
                'analysis_evidence': analysis_evidence,
                'detailed_reasoning': detailed_reasoning,
                'persona_used': persona,
                'generation_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ 첫 메시지 생성 실패: {e}")
            return {
                'message': f"안녕하세요! 만나서 반가워요! 😊",
                'context_type': 'error',
                'context_data': {'error': str(e)},
                'persona': persona
            }

# 전역 분석기 인스턴스
google_data_analyzer = GoogleDataAnalyzer()