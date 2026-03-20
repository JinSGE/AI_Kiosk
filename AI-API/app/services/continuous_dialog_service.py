# app/services/continuous_dialog_service.py

import logging
import os
from typing import Optional, Dict, Any

# GPT 관련 의존성 선택적 임포트
try:
    import openai
except ImportError:
    openai = None

from app.models.text_generation import GPTContextualGenerator

logger = logging.getLogger(__name__)

class GPTEnhancedContinuousDialogService:
    """
    GPT를 활용한 향상된 연속 대화 서비스
    - 대화 컨텍스트 생성
    - 대화 상태 관리
    """
    
    def __init__(
        self, 
        kiosk_service=None, 
        openai_api_key: Optional[str] = None
    ):
        """
        대화 서비스 초기화
        
        :param kiosk_service: 키오스크 서비스 인스턴스
        :param openai_api_key: OpenAI API 키 (선택적)
        """
        self.kiosk_service = kiosk_service
        
        # API 키 처리
        # 1. 직접 전달된 키
        # 2. 환경 변수 
        # 3. None
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        # GPT 컨텍스트 생성기 초기화 (API 키 전달)
        self.gpt_context_generator = GPTContextualGenerator(
            api_key=self.openai_api_key
        )
        
        # 대화 상태 관리
        self.conversation_history = []
        self.max_history_length = 10
        
        # 로깅
        if self.gpt_context_generator.openai_client:
            logger.info("GPT 기반 대화 서비스 초기화 완료")
        else:
            logger.warning("OpenAI API 키 없음. GPT 기능 제한적")
    
    def _add_to_conversation_history(self, role: str, content: str):
        """대화 이력에 메시지 추가"""
        self.conversation_history.append({"role": role, "content": content})
        
        # 최대 길이 제한
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    async def start_dialog_session(self):
        """대화 세션 시작"""
        logger.info("대화 세션 시작")
        
        # 필요한 경우 키오스크 서비스의 초기화 메서드 호출
        if self.kiosk_service:
            await self.kiosk_service.reset_conversation()
        
        # 인사말 생성 (키오스크 서비스 또는 기본 인사말)
        if self.kiosk_service:
            greeting_result = await self.kiosk_service.greet_customer()
            greeting_text = greeting_result.get('text', '안녕하세요. 어서오세요.')
        else:
            greeting_text = '안녕하세요. 어서오세요.'
        
        # 대화 이력에 인사말 추가
        self._add_to_conversation_history("assistant", greeting_text)
        
        return {
            "success": True,
            "message": greeting_text
        }
    
    async def process_user_input(self, user_input: str):
        """
        사용자 입력 처리
        
        :param user_input: 사용자 입력 텍스트
        :return: 처리된 응답
        """
        # 대화 이력에 사용자 입력 추가
        self._add_to_conversation_history("user", user_input)
        
        # GPT 컨텍스트 생성기를 사용하여 응답 생성
        try:
            # 키오스크 서비스를 통한 텍스트 처리 (우선)
            if self.kiosk_service:
                result = await self.kiosk_service.process_text_input(user_input)
                response_text = result.get('response_text', '')
            else:
                # GPT 컨텍스트 생성기로 대체
                response_text = self.gpt_context_generator.generate_context(
                    user_input, 
                    self.conversation_history
                )
            
            # 대화 이력에 응답 추가
            self._add_to_conversation_history("assistant", response_text)
            
            return {
                "success": True,
                "response": response_text
            }
        
        except Exception as e:
            logger.error(f"입력 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def stop_dialog_session(self):
        """대화 세션 종료"""
        logger.info("대화 세션 종료")
        
        # 대화 이력 초기화
        self.conversation_history = []
        
        # 키오스크 서비스가 있다면 대화 초기화
        if self.kiosk_service:
            await self.kiosk_service.reset_conversation()
        
        return {
            "success": True,
            "message": "대화 세션이 종료되었습니다."
        }

import asyncio
import logging
import time
import os
import tempfile
import json
import openai
from typing import Dict, Any, Optional, List, Callable

from app.config import settings
from app.services.kiosk_service import KioskService
from app.models.fsm import State, GPTEnhancedFSM
from app.models.rag_models import GPTEnhancedRAGResponse, GPTQueryEnhancer
from app.models.text_generation import GPTContextualGenerator

logger = logging.getLogger(__name__)

openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    openai_api_key = openai_api_key.strip()  # 혹시 모를 공백 제거
use_gpt = openai_api_key is not None
if use_gpt:
    try:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        logger.info(f"OpenAI 클라이언트 초기화 완료, API 키 길이: {len(openai_api_key)}")
        logger.info("대화 서비스에서 GPT 기능 활성화")
    except Exception as e:
        logger.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
        use_gpt = False
        
class GPTEnhancedContinuousDialogService:
    """GPT API로 강화된 연속 대화 서비스 - 버튼 없이 지속적인 대화를 처리하며 GPT로 맥락 인식 향상"""
    
    def __init__(self, kiosk_service: KioskService, openai_api_key: Optional[str] = None):
        self.kiosk_service = kiosk_service
        self.is_listening = False
        self.session_timeout = 21600  # 세션 타임아웃 (초)
        self.silence_timeout = 1.0  # 무음 감지 타임아웃 (초)
        self.vad_threshold = 0.3    # 음성 활동 감지 임계값
        
        # GPT 관련 설정
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            logger.warning("OpenAI API 키가 설정되지 않았습니다. GPT 기능이 제한됩니다.")
        else:
            # OpenAI 클라이언트 초기화
            self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
        
        # GPT 인핸서 초기화
        self.gpt_context_generator = GPTContextualGenerator()
        
        # 대화 이력
        self.conversation_history = []
        self.max_history_length = 10  # 최대 대화 기록 길이
        
        # 콜백 함수 설정
        self.on_session_start = None
        self.on_session_end = None
        self.on_speech_detected = None
        self.on_silence_detected = None
        self.on_response_start = None
        self.on_response_end = None
        
        logger.info("GPT 강화 연속 대화 서비스 초기화 완료")
    
    async def gpt_analyze_intent(self, text: str) -> Dict[str, Any]:
        """GPT를 사용하여 사용자 발화의 의도와 슬롯을 심층 분석"""
        try:
            if not self.openai_api_key:
                logger.warning("OpenAI API 키가 없어 기본 의도 분석으로 폴백합니다.")
                return {"intent": "unknown", "slots": {}}
            
            # GPT API 호출
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        당신은 카페 키오스크 대화 분석기입니다. 사용자의 발화를 분석하여:
                        1. 의도(intent): greeting, order, option, confirm, payment, help, exit 중 하나
                        2. 슬롯(slots): 메뉴(menu), 수량(count), 온도(temperature), 크기(size), 추가 옵션(option),
                           결제 방법(payment_method), 포장/매장(takeout) 등 주문 관련 정보
                        
                        다음 JSON 형식으로 반환하세요:
                        {
                            "intent": "의도",
                            "slots": {
                                "menu": "메뉴명",
                                "count": 수량,
                                "temperature": "온도옵션",
                                "size": "사이즈",
                                "option": ["옵션1", "옵션2"],
                                "payment_method": "결제방법"
                            }
                        }
                        """
                    },
                    {
                        "role": "user", 
                        "content": f"다음 발화를 분석해주세요: '{text}'"
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            # JSON 파싱
            analysis = json.loads(response.choices[0].message.content)
            logger.info(f"GPT 의도 분석 결과: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"GPT 의도 분석 실패: {str(e)}")
            return {"intent": "unknown", "slots": {}}
    
    async def gpt_enhance_response(self, original_response: str, user_query: str, context: Dict[str, Any]) -> str:
        """GPT를 사용하여 응답을 개선하고 자연스러운 대화 흐름 생성"""
        try:
            if not self.openai_api_key:
                logger.warning("OpenAI API 키가 없어 기본 응답을 그대로 사용합니다.")
                return original_response
            
            # 카페 키오스크 맥락에 맞게 응답 개선 프롬프트
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        당신은 카페 키오스크 응답 생성기입니다. 기존 응답을 더 자연스럽고, 공감적이며, 
                        맥락에 맞게 개선해주세요. 다음 가이드라인을 따르세요:
                        
                        1. 응답의 핵심 정보(메뉴, 가격, 옵션 등)는 정확히 유지하세요.
                        2. 고객과의 자연스러운 대화 흐름을 만드세요.
                        3. 정보는 유지하되 응답이 블로그나 나무위키 같은 형식이 아닌 일상적인 대화체가 되도록 하세요.
                        4. 고객의 주문 의도를 정확히 반영하세요.
                        5. 카페 키오스크 답게 친절하고 전문적인 톤을 유지하세요.
                        6. 길이 제한에 얽매이지 말고 자연스러운 흐름으로 응답하세요.
                        7. 단, 너무 길지 않도록 핵심만 전달하세요. (일반적으로 2~4문장이 적당)
                        """
                    },
                    {
                        "role": "user", 
                        "content": json.dumps({
                            "user_query": user_query,
                            "original_response": original_response,
                            "context": context
                        })
                    }
                ]
            )
            
            improved_response = response.choices[0].message.content.strip()
            logger.info(f"GPT 응답 개선: '{original_response}' -> '{improved_response}'")
            return improved_response
            
        except Exception as e:
            logger.error(f"GPT 응답 개선 실패: {str(e)}")
            return original_response
    
    def _add_to_conversation_history(self, speaker: str, text: str) -> None:
        """대화 이력에 새 메시지 추가 및 길이 관리"""
        self.conversation_history.append({"speaker": speaker, "text": text})
        
        # 최대 길이 제한
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def _ensure_complete_sentence(self, text: str) -> str:
        """응답이 완전한 문장으로 끝나도록 확인"""
        # 마침표, 물음표, 느낌표로 끝나는지 확인
        if text and not text.rstrip().endswith(('.', '?', '!')):
            # 문장 중간에 끊긴 것으로 보이면 마침표 추가
            if len(text) > 20:  # 충분히 긴 텍스트인 경우만
                text = text.rstrip() + '.'
        return text

    async def start_dialog_session(self, 
                                   on_session_start: Optional[Callable] = None,
                                   on_session_end: Optional[Callable] = None,
                                   on_speech_detected: Optional[Callable] = None,
                                   on_response_start: Optional[Callable] = None,
                                   on_response_end: Optional[Callable] = None) -> Dict[str, Any]:
        """
        GPT 강화된 대화 세션 시작
        
        Args:
            on_session_start: 세션 시작 콜백
            on_session_end: 세션 종료 콜백
            on_speech_detected: 음성 감지 콜백
            on_response_start: 응답 시작 콜백
            on_response_end: 응답 종료 콜백
            
        Returns:
            세션 결과
        """
        # 콜백 설정
        self.on_session_start = on_session_start
        self.on_session_end = on_session_end
        self.on_speech_detected = on_speech_detected
        self.on_response_start = on_response_start
        self.on_response_end = on_response_end
        
        # 이미 진행 중인 세션이 있으면 취소
        if self.is_listening:
            await self.stop_dialog_session()
        
        # 세션 초기화
        self.is_listening = True
        await self.kiosk_service.reset_conversation()
        self.conversation_history = []  # 대화 이력 초기화
        start_time = time.time()
        listen_attempts = 0
        session_result = {
            "success": True,
            "completed": False,
            "duration": 0,
            "turns": [],
            "final_state": ""
        }
        
        # 세션 시작 콜백 호출
        if self.on_session_start:
            await self.on_session_start()
        
        # 인사말 생성
        greeting_result = await self.kiosk_service.greet_customer()
        
        # 첫 번째 턴 기록
        session_result["turns"].append({
            "speaker": "system",
            "text": greeting_result["text"],
            "audio_path": greeting_result["audio_path"]
        })
        
        # 대화 이력에 추가
        self._add_to_conversation_history("system", greeting_result["text"])
        
        # 응답 시작 콜백 호출
        if self.on_response_start:
            await self.on_response_start(greeting_result["text"])
        
        # 응답 종료 콜백 호출
        if self.on_response_end:
            await self.on_response_end(greeting_result["audio_path"])
        
        # 주 대화 루프
        try:
            while self.is_listening:
                # 세션 타임아웃 확인
                current_time = time.time()
                elapsed_time = current_time - start_time
                if elapsed_time >= self.session_timeout:
                    logger.info(f"세션 타임아웃: {elapsed_time:.1f}초 경과")
                    session_result["completed"] = False
                    session_result["reason"] = "timeout"
                    break
                
                # 음성 감지 콜백 호출
                if self.on_speech_detected:
                    await self.on_speech_detected()
                
                # VAD 기반 음성 인식 실행
                user_speech = await self._listen_for_speech_with_vad(max_duration=10.0)
                
                # 음성이 감지되지 않았으면 자동 재시도
                if not user_speech:
                    await asyncio.sleep(0.5)
                    listen_attempts += 1
                    
                    # 일정 횟수 이상 실패하면 안내 메시지 출력
                    if listen_attempts >= 3 and listen_attempts % 3 == 0:
                        # GPT로 상황에 맞는 안내 메시지 생성
                        context = {
                            "current_state": self.kiosk_service.pipeline_service.current_state,
                            "attempt_count": listen_attempts,
                            "elapsed_time": elapsed_time
                        }
                        
                        base_reminder = "무엇을 도와드릴까요? 주문하실 메뉴를 말씀해 주세요."
                        
                        # GPT 강화 응답 생성
                        if self.openai_api_key:
                            try:
                                reminder_text = await self.gpt_enhance_response(
                                    base_reminder, 
                                    "(무음)", 
                                    context
                                )
                            except Exception as e:
                                logger.error(f"GPT 안내 메시지 생성 실패: {str(e)}")
                                reminder_text = base_reminder
                        else:
                            reminder_text = base_reminder
                        
                        # 응답 시작 콜백 호출
                        if self.on_response_start:
                            await self.on_response_start(reminder_text)
                        
                        # TTS 실행
                        reminder_result = await self.kiosk_service.tts_service.synthesize(
                            reminder_text,
                            play_audio=True
                        )
                        
                        # 응답 종료 콜백 호출
                        if self.on_response_end:
                            await self.on_response_end(reminder_result.get("audio_path", ""))
                        
                        # 턴 기록
                        session_result["turns"].append({
                            "speaker": "system",
                            "text": reminder_text,
                            "audio_path": reminder_result.get("audio_path", "")
                        })
                        
                        # 대화 이력에 추가
                        self._add_to_conversation_history("system", reminder_text)
                    
                    continue
                
                # 인식된 음성이 있으면 처리
                listen_attempts = 0  # 성공 시 실패 카운터 리셋

                # 사용자 발화 로깅
                logger.info(f"사용자 발화: '{user_speech}'")
                print(f"사용자: '{user_speech}'")
                
                # 대화 이력에 추가
                self._add_to_conversation_history("user", user_speech)
                
                # GPT로 의도와 슬롯 분석 (비동기로 동시에 처리하여 파이프라인 지연 최소화)
                gpt_analysis_task = asyncio.create_task(self.gpt_analyze_intent(user_speech))
                
                # 사용자 발화가 종료 의도인지 확인
                if user_speech.lower() in ["종료", "그만", "취소", "나가기", "그만하기", "주문 취소"]:
                    # 종료 안내 메시지 (GPT로 개선)
                    base_farewell = "주문이 취소되었습니다. 이용해주셔서 감사합니다."
                    
                    # GPT 강화 응답
                    if self.openai_api_key:
                        try:
                            farewell_text = await self.gpt_enhance_response(
                                base_farewell, 
                                user_speech, 
                                {"action": "cancel_order"}
                            )
                        except Exception as e:
                            logger.error(f"GPT 종료 메시지 생성 실패: {str(e)}")
                            farewell_text = base_farewell
                    else:
                        farewell_text = base_farewell
                    
                    # 로깅 추가
                    logger.info(f"시스템 응답: '{farewell_text}'")
                    print(f"시스템: '{farewell_text}'")
                    
                    # 응답 시작 콜백 호출
                    if self.on_response_start:
                        await self.on_response_start(farewell_text)
                    
                    # TTS 실행
                    farewell_result = await self.kiosk_service.tts_service.synthesize(
                        farewell_text,
                        play_audio=True
                    )
                    
                    # 응답 종료 콜백 호출
                    if self.on_response_end:
                        await self.on_response_end(farewell_result.get("audio_path", ""))
                    
                    # 턴 기록 및 세션 종료
                    session_result["turns"].append({
                        "speaker": "user",
                        "text": user_speech
                    })
                    
                    session_result["turns"].append({
                        "speaker": "system",
                        "text": farewell_text,
                        "audio_path": farewell_result.get("audio_path", "")
                    })
                    
                    session_result["completed"] = True
                    session_result["reason"] = "user_cancel"
                    break
                
                # GPT 분석 결과 가져오기 (백그라운드에서 진행 중)
                try:
                    gpt_analysis = await asyncio.wait_for(gpt_analysis_task, timeout=1.0)
                    
                    # GPT 분석 결과가 유효한 경우 파이프라인 상태 업데이트
                    if gpt_analysis and "intent" in gpt_analysis and "slots" in gpt_analysis:
                        # 상태 업데이트를 위한 유용한 슬롯 정보가 있는 경우에만 적용
                        valid_slots = False
                        for key in ["menu", "option", "temperature", "size", "count", "payment_method"]:
                            if key in gpt_analysis["slots"] and gpt_analysis["slots"][key]:
                                valid_slots = True
                                break
                        
                        if valid_slots:
                            logger.info(f"GPT 분석 적용: {gpt_analysis}")
                            
                            # 현재 파이프라인 상태에 GPT 분석 결과 반영
                            # 메뉴 인식 개선
                            if "menu" in gpt_analysis["slots"] and gpt_analysis["slots"]["menu"]:
                                self.kiosk_service.pipeline_service.current_slots["menu"] = gpt_analysis["slots"]["menu"]
                            
                            # 옵션 인식 개선
                            if "option" in gpt_analysis["slots"] and gpt_analysis["slots"]["option"]:
                                self.kiosk_service.pipeline_service.current_slots["option"] = gpt_analysis["slots"]["option"]
                            
                            # 온도 옵션 개선
                            if "temperature" in gpt_analysis["slots"] and gpt_analysis["slots"]["temperature"]:
                                self.kiosk_service.pipeline_service.current_slots["temperature"] = gpt_analysis["slots"]["temperature"]
                            
                            # 상태 변경 로직
                            if gpt_analysis["intent"] == "payment" or "payment_method" in gpt_analysis["slots"]:
                                # 결제 의도 감지 시 결제 상태로 자동 전환
                                self.kiosk_service.pipeline_service.current_state = "payment"
                except asyncio.TimeoutError:
                    logger.warning("GPT 분석 시간 초과, 기본 처리로 진행합니다.")
                except Exception as e:
                    logger.error(f"GPT 분석 적용 실패: {str(e)}")
                
                # 일반 사용자 발화 처리
                process_result = await self.kiosk_service.process_text_input(user_speech)

                # GPT로 응답 개선
                if self.openai_api_key:
                    try:
                        # 기존 응답을 GPT로 자연스럽게 강화
                        enhanced_response = await self.gpt_enhance_response(
                            process_result["response_text"],
                            user_speech,
                            {
                                "current_state": self.kiosk_service.pipeline_service.current_state,
                                "conversation_history": self.conversation_history[-5:],  # 최근 5개 대화만 전달
                                "detected_slots": self.kiosk_service.pipeline_service.current_slots
                            }
                        )
                        
                        # 개선된 응답으로 교체
                        process_result["response_text"] = self._ensure_complete_sentence(process_result["response_text"])
                    except Exception as e:
                        logger.error(f"GPT 응답 개선 실패: {str(e)}")
                
                # 시스템 응답 로깅
                logger.info(f"시스템 응답: '{process_result['response_text']}'")
                print(f"시스템: '{process_result['response_text']}'")
                
                # 턴 기록
                session_result["turns"].append({
                    "speaker": "user",
                    "text": user_speech
                })
                
                session_result["turns"].append({
                    "speaker": "system",
                    "text": process_result["response_text"],
                    "audio_path": process_result["audio_path"]
                })
                
                # 대화 이력에 추가
                self._add_to_conversation_history("system", process_result["response_text"])
                
                # 응답 시작 콜백 호출
                if self.on_response_start:
                    await self.on_response_start(process_result["response_text"])
                
                # 응답 종료 콜백 호출
                if self.on_response_end:
                    await self.on_response_end(process_result["audio_path"])
                
                # 대화 상태 확인
                current_state = self.kiosk_service.pipeline_service.current_state
                session_result["final_state"] = current_state
                
                # 주문 완료 상태인지 확인
                if current_state in ["farewell", "payment"]:
                    logger.info(f"주문 완료 감지: {current_state}")
                    session_result["completed"] = True
                    session_result["reason"] = "order_completed"
                    break
                
                # 잠시 대기 (AI 응답과 사용자 발화 사이)
                await asyncio.sleep(1.0)
        
        except Exception as e:
            logger.error(f"대화 세션 처리 중 오류 발생: {str(e)}")
            session_result["success"] = False
            session_result["error"] = str(e)
            
        finally:
            # 세션 종료
            self.is_listening = False
            end_time = time.time()
            session_result["duration"] = end_time - start_time
            
            # 세션 종료 콜백 호출
            if self.on_session_end:
                await self.on_session_end(session_result)
            
            # 상태 초기화
            await self.kiosk_service.reset_conversation()
            
            logger.info(f"대화 세션 종료: {session_result['duration']:.1f}초, 턴 수: {len(session_result['turns'])//2}")
            
            # 세션 완료 후 잠시 대기
            await asyncio.sleep(1.0)
            
            # 주문이 완료되었거나 취소되었거나 타임아웃된 경우 새 세션 자동 시작
            if session_result["completed"] or session_result.get("reason") == "timeout":
                logger.info("주문 완료/취소 또는 타임아웃 감지, 새 대화 세션 자동 시작")
                asyncio.create_task(self.start_dialog_session(
                    self.on_session_start,
                    self.on_session_end,
                    self.on_speech_detected,
                    self.on_response_start,
                    self.on_response_end
                ))
            
            return session_result
    
    async def stop_dialog_session(self) -> bool:
        """진행 중인 대화 세션 중지"""
        if self.is_listening:
            self.is_listening = False
            logger.info("대화 세션 중지 요청")
            await asyncio.sleep(0.5)  # 대화 루프가 정상 종료될 시간 부여
            return True
        return False
    
    async def _listen_for_speech_with_vad(self, wait_timeout: float = 1.0, max_duration: float = 7.0) -> Optional[str]:
        """
        개선된 음성 활동 감지(VAD) 메서드
        - 보다 직접적이고 간결한 음성 캡처
        - 첫 음성 감지 후 최대 7초 동안 지속적으로 음성 수집
        
        Args:
            wait_timeout: 초기 음성 감지 대기 시간 (초)
            max_duration: 음성 캡처 최대 시간 (초)
        
        Returns:
            인식된 텍스트 또는 None
        """
        try:
            import pyaudio
            import wave
            import time
            import numpy as np
            
            # VAD 모듈 가져오기
            try:
                import webrtcvad
                use_vad = True
                # 최대 민감도로 설정
                vad = webrtcvad.Vad(3)
                logger.info("VAD 활성화: webrtcvad 모듈 로드 성공 (최대 민감도)")
            except ImportError:
                use_vad = False
                logger.error("webrtcvad 임포트 실패, 에너지 기반 VAD 사용")
            except Exception as e:
                use_vad = False
                logger.error(f"webrtcvad 초기화 오류: {str(e)}, 에너지 기반 VAD 사용")
            
            # 오디오 설정 최적화
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            CHUNK_DURATION_MS = 20  # VAD에 최적화된 청크 크기
            CHUNK = int(RATE * CHUNK_DURATION_MS / 1000)
            
            # 음성 감지 민감도 조정
            ENERGY_THRESHOLD = 300  # 음성 감지를 위한 에너지 임계값
            
            # 임시 파일 경로 설정
            import os
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "audio_input")
            os.makedirs(temp_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            wav_path = os.path.join(temp_dir, f"vad_input_{timestamp}.wav")
            
            # 오디오 스트림 초기화
            p = pyaudio.PyAudio()
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            logger.info(f"음성 감지 대기 중... (최대 {wait_timeout:.1f}초 대기)")
            
            # 녹음 변수 초기화
            frames = []
            is_speech_detected = False
            speech_start_time = None
            start_time = time.time()
            wait_end_time = start_time + wait_timeout
            
            try:
                # 음성 감지 및 녹음 루프
                while time.time() < wait_end_time + max_duration:
                    current_time = time.time()
                    
                    # 프레임 읽기
                    frame = stream.read(CHUNK, exception_on_overflow=False)
                    
                    # VAD 또는 에너지 기반 음성 감지
                    if use_vad:
                        try:
                            is_speech = vad.is_speech(frame, RATE)
                        except Exception:
                            # VAD 실패 시 에너지 기반 대체
                            data = np.frombuffer(frame, dtype=np.int16)
                            energy = np.sqrt(np.mean(data**2))
                            is_speech = energy > ENERGY_THRESHOLD
                    else:
                        # 에너지 기반 음성 감지
                        data = np.frombuffer(frame, dtype=np.int16)
                        energy = np.sqrt(np.mean(data**2))
                        is_speech = energy > ENERGY_THRESHOLD
                    
                    # 첫 음성 감지 시
                    if is_speech and not is_speech_detected:
                        is_speech_detected = True
                        speech_start_time = current_time
                        logger.info("음성 감지됨, 녹음 시작")
                    
                    # 음성 감지 후 처리
                    if is_speech_detected:
                        frames.append(frame)
                        
                        # 최대 녹음 시간 확인
                        if current_time - speech_start_time >= max_duration:
                            logger.info(f"최대 녹음 시간({max_duration:.1f}초) 도달, 녹음 종료")
                            break
                    
                    # 대기 시간 초과 확인
                    if current_time > wait_end_time + max_duration:
                        logger.info("최대 대기 시간 초과, 음성 감지 종료")
                        break
                    
                    # 잠시 대기 (CPU 부하 방지)
                    await asyncio.sleep(0.01)
            
            finally:
                # 스트림 정리
                stream.stop_stream()
                stream.close()
                p.terminate()
            
            # 충분한 음성 데이터 확인
            if not is_speech_detected or len(frames) < RATE // CHUNK // 4:
                logger.info("의미 있는 음성이 감지되지 않았습니다.")
                return None
            
            # WAV 파일로 저장
            wf = wave.open(wav_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            # 파일 크기 및 녹음 시간 계산
            file_size = os.path.getsize(wav_path)
            recording_seconds = len(frames) * CHUNK_DURATION_MS / 1000
            logger.info(f"음성 녹음 완료: {wav_path} ({recording_seconds:.2f}초, {file_size}바이트)")
            
            # STT 처리
            with open(wav_path, 'rb') as audio_file:
                stt_result = await self.kiosk_service.stt_service.transcribe(audio_file)
            
            if not stt_result["success"] or not stt_result.get("text"):
                logger.info("음성 인식 결과 없음")
                return None
            
            # 인식된 텍스트 가져오기
            recognized_text = stt_result.get("text")
            logger.info(f"STT 결과: '{recognized_text}'")
            
            return recognized_text
            
        except Exception as e:
            # 오류 발생 시 오류 메시지 로깅하고, None 반환
            logger.error(f"음성 감지 중 예외 발생: {str(e)}")
            return None