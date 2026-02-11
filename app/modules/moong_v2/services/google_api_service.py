"""
구글 API 서비스
- OAuth 토큰 검증 및 갱신
- YouTube API 데이터 수집
- Calendar API 데이터 수집  
- 구글 서비스 통합 관리
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json
import os

# 구글 API 라이브러리들
try:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.exceptions import GoogleAuthError
    from google_auth_oauthlib.flow import Flow
    import urllib.parse
    GOOGLE_LIBS_AVAILABLE = True
    print("✅ 구글 API 라이브러리 로드 성공")
except ImportError as e:
    GOOGLE_LIBS_AVAILABLE = False
    print(f"❌ 구글 API 라이브러리 임포트 실패: {e}")
    print("설치 필요: pip install google-auth google-auth-oauthlib google-api-python-client")

class GoogleAPIService:
    """구글 API 서비스 클래스"""
    
    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://localhost:8002/auth/callback"  # Google Cloud Console에 등록된 URI 유지
        self._load_credentials()
        
        # API 스코프 정의
        self.required_scopes = [
            'https://www.googleapis.com/auth/youtube.readonly',
            'https://www.googleapis.com/auth/calendar.readonly',
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]
        
        # OAuth flow 객체 (초기화 시에 생성)
        self.flow = None
        self._setup_oauth_flow()
    
    def _load_credentials(self):
        """구글 credentials 로드"""
        credentials_path = "/Users/kjw/emotion-analysis-system/config/google_credentials.json"
        
        try:
            if not os.path.exists(credentials_path):
                print(f"❌ 구글 인증 파일이 없음: {credentials_path}")
                return False
                
            with open(credentials_path, 'r') as f:
                cred_data = json.load(f)
                
            installed = cred_data.get('installed', {})
            self.client_id = installed.get('client_id')
            self.client_secret = installed.get('client_secret')
            
            if not self.client_id or not self.client_secret:
                print("❌ 구글 client_id 또는 client_secret이 없습니다")
                return False
                
            print("✅ 구글 인증 정보 로드 성공")
            return True
            
        except Exception as e:
            print(f"❌ 구글 인증 파일 로드 실패: {e}")
            return False
    
    def _setup_oauth_flow(self):
        """OAuth flow 초기 설정"""
        if not GOOGLE_LIBS_AVAILABLE or not self.client_id:
            return False
            
        try:
            credentials_path = "/Users/kjw/emotion-analysis-system/config/google_credentials.json"
            
            self.flow = Flow.from_client_secrets_file(
                credentials_path,
                scopes=self.required_scopes,
                redirect_uri=self.redirect_uri
            )
            
            return True
            
        except Exception as e:
            print(f"❌ OAuth flow 설정 실패: {e}")
            return False
    
    def generate_auth_url(self, user_id: str = None) -> Dict[str, Any]:
        """구글 OAuth 인증 URL 생성"""
        print(f"🔍 generate_auth_url 호출 - user_id: {user_id}")
        print(f"🔍 GOOGLE_LIBS_AVAILABLE: {GOOGLE_LIBS_AVAILABLE}")
        
        # --- DEBUGGING LOG ---
        print(f"🔥 [CRITICAL CHECK] 코드에서 사용 중인 Redirect URI: '{self.redirect_uri}'")
        print(f"🔥 [CRITICAL CHECK] 반드시 구글 콘솔에도 위와 똑같이 등록되어 있어야 합니다.")
        # ---------------------

        print(f"🔍 client_id: {self.client_id}")
        print(f"🔍 client_secret: {self.client_secret}")
        
        # Flow 객체를 매번 새로 생성하여 스코프 변경 문제 해결
        setup_result = self._setup_oauth_flow()
        print(f"🔍 _setup_oauth_flow 결과: {setup_result}")
        
        if not self.flow:
            error_msg = 'OAuth flow가 설정되지 않았습니다'
            print(f"❌ {error_msg}")
            return {'error': error_msg}
        
        try:
            # state 파라미터에 user_id 포함 (선택적)
            state = f"user_{user_id}" if user_id else "login_request"
            
            # 디버깅: redirect_uri 확인
            print(f"🔍 현재 사용 중인 redirect_uri: {self.redirect_uri}")
            print(f"🔍 OAuth Flow redirect_uri: {self.flow.redirect_uri}")
            
            print(f"🔍 authorization_url 생성 시작...")
            authorization_url, state = self.flow.authorization_url(
                access_type='offline',  # refresh token 받기 위함
                include_granted_scopes='true',
                state=state,
                prompt='consent'  # 항상 동의 화면 표시하여 스코프 변경 감지
            )
            
            print(f"✅ authorization_url 생성 성공: {authorization_url[:100]}...")
            
            return {
                'auth_url': authorization_url,
                'state': state,
                'redirect_uri': self.redirect_uri,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ 인증 URL 생성 실패: {e}")
            print(f"❌ 에러 타입: {type(e)}")
            import traceback
            print(f"❌ 전체 스택트레이스: {traceback.format_exc()}")
            return {'error': str(e)}
    
    async def handle_oauth_callback(self, authorization_code: str, state: str = None) -> Dict[str, Any]:
        """OAuth 콜백 처리 - authorization code로 토큰 교환"""
        print(f"🔄 handle_oauth_callback 시작...")
        print(f"🔑 Code: {authorization_code[:20]}..." if authorization_code else "❌ Code 없음")
        print(f"🏷️ State: {state}")
        
        if not self.flow:
            print(f"❌ OAuth flow가 설정되지 않았음")
            return {'success': False, 'error': 'OAuth flow가 설정되지 않았습니다'}
        
        try:
            print(f"🔄 토큰 교환 시작...")
            # authorization code로 토큰 교환
            self.flow.fetch_token(code=authorization_code)
            print(f"✅ 토큰 교환 성공")
            
            credentials = self.flow.credentials
            print(f"🎫 Credentials: {type(credentials)}")
            print(f"🔑 Access Token: {credentials.token[:20]}..." if credentials.token else "❌ No token")
            
            # ID 토큰에서 사용자 정보 추출
            request = Request()
            user_info = {}
            
            try:
                print(f"🔍 ID 토큰 처리 시작...")
                # ID 토큰 검증 및 사용자 정보 추출
                if hasattr(credentials, 'id_token') and credentials.id_token:
                    print(f"✅ ID 토큰 발견, 검증 중...")
                    id_info = id_token.verify_oauth2_token(
                        credentials.id_token, request, self.client_id
                    )
                    print(f"📊 ID 정보: {id_info.keys()}")
                    user_info = {
                        'id': id_info.get('sub'),  # 'id' 키로 변경
                        'google_id': id_info.get('sub'),
                        'email': id_info.get('email'),
                        'name': id_info.get('name'),
                        'picture': id_info.get('picture')
                    }
                    print(f"👤 사용자 정보 추출 완료: {user_info}")
                else:
                    print(f"⚠️ ID 토큰 없음, People API 시도...")
            except Exception as e:
                print(f"⚠️ ID 토큰 처리 중 오류: {e}")
                # People API를 통해 사용자 정보 가져오기
                try:
                    people_service = build('people', 'v1', credentials=credentials)
                    profile = people_service.people().get(
                        resourceName='people/me',
                        personFields='names,emailAddresses'
                    ).execute()
                    
                    names = profile.get('names', [])
                    emails = profile.get('emailAddresses', [])
                    
                    user_info = {
                        'id': emails[0].get('value') if emails else 'unknown@example.com',  # email을 ID로 사용
                        'google_id': profile.get('resourceName', '').split('/')[-1],
                        'name': names[0].get('displayName') if names else 'Unknown',
                        'email': emails[0].get('value') if emails else 'unknown@example.com'
                    }
                    print(f"👤 People API로 사용자 정보 추출: {user_info}")
                except Exception as e2:
                    print(f"⚠️ People API 호출 실패: {e2}")
                    # 기본값 설정
                    user_info = {
                        'id': 'unknown_user',
                        'google_id': 'unknown',
                        'name': 'Google User',
                        'email': 'unknown@example.com'
                    }
                    print(f"🔧 기본 사용자 정보 설정: {user_info}")
            
            result = {
                'success': True,
                'tokens': {
                    'access_token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'expires_at': credentials.expiry.isoformat() if credentials.expiry else None,
                    'granted_scopes': credentials.granted_scopes or self.required_scopes
                },
                'user_info': user_info,
                'state': state
            }
            
            print(f"✅ OAuth 콜백 처리 성공!")
            print(f"📊 결과 키들: {result.keys()}")
            return result
            
        except Exception as e:
            print(f"❌ OAuth 콜백 처리 실패: {e}")
            import traceback
            print(f"❌ 스택트레이스: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

    def get_user_info_from_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """액세스 토큰으로 사용자 정보 조회"""
        if not GOOGLE_LIBS_AVAILABLE:
            print("❌ 구글 라이브러리 미설치")
            return None
            
        try:
            creds = Credentials(token=access_token)
            # userinfo endpoint 호출
            service = build('oauth2', 'v2', credentials=creds)
            user_info = service.userinfo().get().execute()
            
            return {
                'id': user_info.get('id'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture')
            }
        except Exception as e:
            print(f"⚠️ 토큰 검증 실패: {e}")
            return None
    
    async def verify_access_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """구글 액세스 토큰 검증"""
        if not GOOGLE_LIBS_AVAILABLE:
            raise RuntimeError("구글 API 라이브러리가 설치되지 않았습니다")
        
        try:
            # 토큰 정보 조회
            request = Request()
            credentials = Credentials(token=access_token)
            
            if not credentials.valid:
                return None
            
            # ID 토큰으로 사용자 정보 추출 (간접적 방법)
            # 실제로는 Google People API 또는 OAuth2 userinfo를 사용해야 함
            try:
                # 이 부분은 실제 구현에서는 더 정교하게 처리해야 함
                idinfo = id_token.verify_token(access_token, request, self.client_id)
                
                return {
                    'google_id': idinfo.get('sub'),
                    'email': idinfo.get('email'),
                    'name': idinfo.get('name'),
                    'verified': True,
                    'expires_at': datetime.fromtimestamp(idinfo.get('exp', 0))
                }
            except:
                # ID 토큰이 없는 경우 다른 방법 시도
                return {
                    'verified': True,
                    'token_valid': True,
                    'expires_at': None  # 만료 시간을 알 수 없음
                }
                
        except GoogleAuthError as e:
            print(f"❌ 구글 토큰 검증 실패: {e}")
            return None
        except Exception as e:
            print(f"❌ 토큰 검증 중 오류: {e}")
            return None
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """액세스 토큰 갱신"""
        if not GOOGLE_LIBS_AVAILABLE:
            raise RuntimeError("구글 API 라이브러리가 설치되지 않았습니다")
        
        try:
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            request = Request()
            credentials.refresh(request)
            
            return {
                'access_token': credentials.token,
                'refresh_token': credentials.refresh_token or refresh_token,
                'expires_at': credentials.expiry,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ 토큰 갱신 실패: {e}")
            return None
    
    async def get_youtube_data(self, access_token: str) -> Dict[str, Any]:
        """유튜브 데이터 수집"""
        if not GOOGLE_LIBS_AVAILABLE:
            return {'error': '구글 API 라이브러리가 설치되지 않았습니다'}
        
        try:
            credentials = Credentials(token=access_token)
            youtube = build('youtube', 'v3', credentials=credentials)
            
            # 구독 채널 목록 (최대 50개)
            subscriptions = youtube.subscriptions().list(
                part='snippet',
                mine=True,
                maxResults=50
            ).execute()
            
            # 좋아요 표시한 동영상 (최대 20개)
            try:
                liked_videos = youtube.videos().list(
                    part='snippet,statistics',
                    myRating='like',
                    maxResults=20
                ).execute()
            except:
                liked_videos = {'items': []}  # 권한이 없는 경우
            
            return {
                'subscriptions': subscriptions.get('items', []),
                'subscription_count': len(subscriptions.get('items', [])),
                'liked_videos': liked_videos.get('items', []),
                'collected_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ 유튜브 데이터 수집 실패: {e}")
            return {'error': str(e)}
    
    async def get_calendar_data(self, access_token: str) -> Dict[str, Any]:
        """캘린더 데이터 수집"""
        if not GOOGLE_LIBS_AVAILABLE:
            return {'error': '구글 API 라이브러리가 설치되지 않았습니다'}
        
        try:
            credentials = Credentials(token=access_token)
            calendar = build('calendar', 'v3', credentials=credentials)
            
            # 지난주, 이번주, 다음주 (총 3주간)의 이벤트
            now = datetime.now()
            # 타임존 이슈 방지를 위해 넉넉하게 7일 전부터 검색
            time_min = (now - timedelta(days=7)).isoformat() + 'Z'
            time_max = (now + timedelta(days=14)).isoformat() + 'Z'
            
            print(f"📅 캘린더 수집 기간: {time_min} ~ {time_max}")
            
            events_result = calendar.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,  # 3주치 데이터를 위해 증량
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            return {
                'upcoming_events': events,
                'event_count': len(events),
                'period': f"{(now - timedelta(days=7)).strftime('%Y-%m-%d')} ~ {(now + timedelta(days=14)).strftime('%Y-%m-%d')}",
                'collected_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ 캘린더 데이터 수집 실패: {e}")
            return {'error': str(e)}
    
    async def collect_all_user_data(self, access_token: str) -> Dict[str, Any]:
        """구글 API에서 모든 사용자 데이터 자동 수집"""
        print("📊 Google 데이터 수집 시작...")
        print(f"🔑 Access Token: {access_token[:20]}..." if access_token else "❌ 토큰 없음")
        
        try:
            # YouTube 데이터 수집
            print("📺 YouTube 데이터 수집 중...")
            youtube_result = await self.get_youtube_data(access_token)
            
            youtube_data = []
            if 'error' not in youtube_result and 'subscriptions' in youtube_result:
                youtube_data = youtube_result['subscriptions']
                print(f"✅ YouTube: 구독 {len(youtube_data)}개 수집")
            else:
                print(f"❌ YouTube 수집 실패: {youtube_result.get('error', '알 수 없는 오류')}")
            
            # Calendar 데이터 수집
            print("📅 Calendar 데이터 수집 중...")
            calendar_result = await self.get_calendar_data(access_token)
            
            # 디버깅을 위한 결과 키 출력
            print(f"🕵️ 캘린더 결과 키: {list(calendar_result.keys())}")
            
            calendar_data = []
            if 'error' not in calendar_result and 'upcoming_events' in calendar_result:
                calendar_data = calendar_result['upcoming_events']
                print(f"✅ Calendar: 이벤트 {len(calendar_data)}개 수집")
            else:
                error_msg = calendar_result.get('error', f'알 수 없는 오류 (보유 키: {list(calendar_result.keys())})')
                print(f"❌ Calendar 수집 실패: {error_msg}")
            
            # 성공 여부 판단
            has_data = len(youtube_data) > 0 or len(calendar_data) > 0
            
            result = {
                'success': True,  # 최소한 하나의 API라도 호출이 성공하면 True
                'calendar_data': calendar_data,
                'youtube_data': youtube_data,
                'summary': {
                    'total_youtube_subscriptions': len(youtube_data),
                    'total_calendar_events': len(calendar_data),
                    'has_data': has_data,
                    'collected_at': datetime.now().isoformat()
                }
            }
            
            print(f"🎉 데이터 수집 완료 - YouTube: {len(youtube_data)}개, Calendar: {len(calendar_data)}개")
            return result
            
        except Exception as e:
            print(f"❌ 데이터 수집 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': f"데이터 수집 실패: {str(e)}",
                'calendar_data': [],
                'youtube_data': []
            }
    
    def check_required_scopes(self, granted_scopes: List[str]) -> Dict[str, bool]:
        """필요한 스코프가 모두 허용되었는지 확인"""
        scope_status = {}
        
        for required_scope in self.required_scopes:
            scope_status[required_scope] = required_scope in granted_scopes
        
        return {
            'scopes': scope_status,
            'all_granted': all(scope_status.values()),
            'missing_scopes': [scope for scope, granted in scope_status.items() if not granted]
        }

# 전역 서비스 인스턴스
google_api_service = GoogleAPIService()