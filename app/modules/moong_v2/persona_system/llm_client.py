
"""
LLM Client for Persona System
DeepSeek-V3 via HuggingFace Inference API
"""

import os
import json
import traceback
import ssl
import aiohttp
from typing import Dict, List, Any
from app.core.config import settings

class LLMClient:
    def __init__(self):
        print(f"🤖 LLM 클라이언트 초기화 (DeepSeek-V3):")
        
        self.hf_api_key = settings.HUGGINGFACE_API_KEY or ""
        self.model_id = "deepseek-ai/DeepSeek-V3"
        self.api_url = "https://router.huggingface.co/v1/chat/completions"
        self.session = None
        
        print(f"   - API Key Prefix: {self.hf_api_key[:5] if self.hf_api_key else 'None'}...")
        print(f"   - Model: {self.model_id}")
        print(f"   - Endpoint: {self.api_url}")
        
        if not self.hf_api_key:
            print("   ⚠️ Warning: HUGGINGFACE_API_KEY not set!")
        else:
            print("   ✅ DeepSeek Client Configured Successfully")
    
    async def get_session(self):
        """HTTP 세션 관리 (SSL 인증서 검증 비활성화)"""
        if self.session is None or self.session.closed:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session

    def build_persona_analysis_prompt(self, persona_state) -> str:
        """1차 호출: 페르소나 분석 전용 프롬프트"""
        p = persona_state
        guidelines = p.get('guidelines', {}) if isinstance(p, dict) else p.guidelines
        
        guidelines_str = "\n".join([f"  - {k}: {v}" for k, v in guidelines.items()])
        
        # Safe access helper
        def get_attr(obj, key, default):
            return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
            
        persona_type = get_attr(p, 'persona_type', 'Unknown')
        mbti = get_attr(p, 'mbti', 'Unknown')
        energy_level = get_attr(p, 'energy_level', 0.5)
        formality = get_attr(p, 'formality', 0.5)
        talking_style = get_attr(p, 'talking_style', 'Unknown')
        nickname = get_attr(p, 'nickname', 'Moong')

        prompt = f"""당신은 페르소나 분석 전문가입니다.

현재 페르소나 상태:
- 타입: {persona_type}
- MBTI: {mbti}
- 에너지 레벨: {energy_level}/1.0
- 격식도: {formality}/1.0
- 말투: {talking_style}
- 닉네임: {nickname}

현재 지침:
{guidelines_str}

사용자 메시지를 분석하여 페르소나와 지침을 어떻게 변경할지 결정하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "persona_update": {{
    "persona_type": "변경된 타입 (예: pet, guide, friend 등)",
    "mbti": "변경된 MBTI",
    "temperature": 0.0~1.0,
    "talking_style": "변경된 말투 설명",
    "energy_level": 0.0~1.0,
    "formality": 0.0~1.0,
    "nickname": "변경된 닉네임",
    "guidelines": {{
      "호칭": "변경된 호칭",
      "말투": "변경된 말투",
      "미션": "변경된 미션",
      "특징": "변경된 특징",
      "제약": "변경된 제약"
    }}
  }},
  "reasoning": "변경 이유를 상세히 설명",
  "changes": [
    "구체적 변경사항 1",
    "구체적 변경사항 2"
  ]
}}

JSON 외의 텍스트, 마크다운(```json 등) 없이 순수 JSON만 출력하세요."""
        return prompt.strip()
            
    async def analyze_persona(self, user_message: str, current_persona, model_id: str = None) -> Dict:
        """1차 API 호출: 페르소나 분석 (DeepSeek-V3)"""
        if not self.hf_api_key:
            return {"success": False, "error": "HuggingFace API Key not set"}

        try:
            session = await self.get_session()
            headers = {
                "Authorization": f"Bearer {self.hf_api_key}",
                "Content-Type": "application/json"
            }
            
            # 페르소나 분석 프롬프트
            analysis_prompt = self.build_persona_analysis_prompt(current_persona)
            
            system_content = f"""당신은 페르소나 분석 전문가입니다.

{analysis_prompt}"""

            # DeepSeek API 요청
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"사용자 메시지: '{user_message}'\n\n위 메시지를 분석하여 페르소나 업데이트 JSON을 생성하세요."}
            ]
            
            payload = {
                "model": self.model_id,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.4,
                "stream": False
            }
            
            print(f"      [DeepSeek] Persona Analysis API 호출 중...")
            
            async with session.post(self.api_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    response_text = result["choices"][0]["message"]["content"]
                    
                    # JSON 추출 및 정제
                    try:
                        content = response_text
                        if "```json" in content:
                            json_start = content.find("```json") + 7
                            json_end = content.find("```", json_start)
                            json_str = content[json_start:json_end].strip()
                        elif "```" in content:
                            json_start = content.find("```") + 3
                            json_end = content.find("```", json_start)
                            json_str = content[json_start:json_end].strip()
                        else:
                            json_str = content.strip()
                        
                        # Cleanup
                        import re
                        json_str = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', json_str)
                        
                        persona_data = json.loads(json_str)
                        
                        print(f"      ✅ 페르소나 분석 완료")
                        return {
                            "success": True,
                            "persona_update": persona_data.get("persona_update", {}),
                            "reasoning": persona_data.get("reasoning", "분석 완료"),
                            "changes": persona_data.get("changes", [])
                        }
                    except json.JSONDecodeError as e:
                        print(f"   ⚠️ JSON 파싱 실패: {str(e)}")
                        return {
                            "success": False,
                            "error": f"JSON 파싱 실패: {str(e)}",
                            "raw_content": content[:500]
                        }
                else:
                    error_text = await response.text()
                    print(f"   ❌ API Error {response.status}: {error_text[:200]}")
                    return {"success": False, "error": f"API Error: {response.status}"}

        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_response(self, user_message: str, updated_persona, conversation_history: List[str] = [], model_id: str = None) -> str:
        """2차 API 호출: 답변 생성 (DeepSeek-V3)"""
        if not self.hf_api_key:
            return "죄송해요, API 설정에 문제가 있어요."

        try:
            session = await self.get_session()
            headers = {
                "Authorization": f"Bearer {self.hf_api_key}",
                "Content-Type": "application/json"
            }
            
            # Safe Access
            p = updated_persona
            guidelines = p.get('guidelines', {}) if isinstance(p, dict) else p.guidelines
            
            def get_attr(obj, key, default):
                return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
                
            guidelines_str = "\n".join([f"  - {k}: {v}" for k, v in guidelines.items()])
            
            persona_type = get_attr(p, 'persona_type', 'Unknown')
            mbti = get_attr(p, 'mbti', 'Unknown')
            
            system_prompt = f"""당신은 '메이트 뭉'입니다. 아래 페르소나와 지침에 따라 답변하세요.
스타일: {get_attr(p, 'talking_style', '친근하게')}
MBTI: {mbti}

[지침]
{guidelines_str}

순수 대화만 생성하고, JSON이나 분석은 포함하지 마세요."""

            # 대화 히스토리 구성
            messages = [{"role": "system", "content": system_prompt}]
            
            # 최근 5개 대화만 포함
            for msg in conversation_history[-5:]:
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                    messages.append(msg)
                elif isinstance(msg, str):
                    # 문자열 형식 히스토리 파싱 시도
                    if msg.startswith("User:"):
                        messages.append({"role": "user", "content": msg.replace("User:", "").strip()})
                    elif msg.startswith("AI:"):
                        messages.append({"role": "assistant", "content": msg.replace("AI:", "").strip()})
            
            messages.append({"role": "user", "content": user_message})
            
            payload = {
                "model": self.model_id,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.7,
                "stream": False
            }
            
            print(f"      [DeepSeek] Response Generation API 호출 중...")
            
            async with session.post(self.api_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    answer = result["choices"][0]["message"]["content"]
                    print(f"      ✅ 답변 생성 완료 (길이: {len(answer)})")
                    return answer
                else:
                    error_text = await response.text()
                    print(f"   ❌ API Error {response.status}: {error_text[:200]}")
                    return "죄송해요, 답변 생성 중 오류가 발생했어요."

        except Exception as e:
            traceback.print_exc()
            return f"오류가 발생했어요: {str(e)}"
