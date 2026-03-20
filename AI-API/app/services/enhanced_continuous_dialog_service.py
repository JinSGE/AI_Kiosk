# app/services/enhanced_continuous_dialog_service.py
import re
import asyncio
import logging
import time
import os
import tempfile
import json
import uuid
import openai

from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING
from app.config import settings
from app.services.notification_service import (
    notify_cart_update, 
    notify_cart_reset, 
    notify_menu_loading
)
from app.utils.order_utils import extract_order_info, update_cart_with_merge

# 전역 변수로 인사말 플래그 추가
_greeting_shown = False  # 인사말 표시 여부를 추적하는 전역 변수

# 타입 힌팅을 위한 조건부 import
if TYPE_CHECKING:
    from app.services.kiosk_service import KioskService
    from app.services.enhanced_pipeline_service import EnhancedPipelineService

logger = logging.getLogger(__name__)

class EnhancedContinuousDialogService:
    """GPT로 향상된 연속 대화 서비스 - GPT로 전체 대화 흐름 통합"""
    
    def __init__(self, 
                 kiosk_service: Optional['KioskService'] = None, 
                 openai_api_key: Optional[str] = None):
        
        self.kiosk_service = kiosk_service
        self.is_listening = False
        self.session_timeout = 21600  # 세션 타임아웃 (초)
        self.silence_timeout = 1.0  # 무음 감지 타임아웃 (초)
        self.silence_counter = 0    # 연속 무음 카운터
        self.max_silence_count = 1000 # 최대 허용 연속 무음 횟수
        self.conversation_id = f"dialog-{uuid.uuid4()}"
        
        # 인사말 관련 플래그 추가
        global _greeting_shown
        self._greeting_shown = _greeting_shown

        # 중복 처리 방지 변수
        self._last_processed_input = None
        self._last_result = None
        self._processing = False
        self._last_order_info = None  # 이 줄을 추가합니다
        
        # 처리 최적화 관련 설정
        self.enable_duplicate_checking = os.environ.get("ENABLE_DUPLICATE_CHECKING", "True").lower() == "true"
        self.enable_gpt_correction = False  # GPT 교정 기능 비활성화
        self.simplified_processing = True   # 간소화된 처리 모드 활성화
        
        # GPT 관련 설정
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.use_gpt = bool(self.openai_api_key)
        
        if self.use_gpt:
            try:
                self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
                logger.info(f"OpenAI 클라이언트 초기화 완료, API 키 길이: {len(self.openai_api_key)}")
            except Exception as e:
                logger.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
                self.use_gpt = False
        
        # 파이프라인 서비스 대체 (필요시)
        self._pipeline_service = None
        if self.kiosk_service and self.use_gpt:
            self._setup_enhanced_pipeline()
        
        # 대화 이력
        self.conversation_history = []
        self.max_history_length = 10
        
        # 콜백 함수
        self.on_session_start = None
        self.on_session_end = None
        self.on_speech_detected = None
        self.on_silence_detected = None
        self.on_response_start = None
        self.on_response_end = None
        
        # 사용자 편의성 개선
        self.command_shortcuts = {
            "안녕": "인사",
            "메뉴": "메뉴 보여줘",
            "추천": "메뉴 추천해줘",
            "취소": "주문 취소",
            "완료": "주문 완료",
            "장바구니": "장바구니 초기화"
        }
        
        # 주문 컨텍스트 (사용자 경험 개선)
        self.order_context = {
            "detected_intents": [],  # 감지된 의도 목록
            "suggested_next": "",    # 다음 제안 동작
            "frequent_menus": [],    # 자주 주문하는 메뉴 (향후 확장)
            "last_mentioned_menu": "",  # 마지막으로 언급된 메뉴
            "menu_count": 0          # 메뉴 수량
        }
        
        logger.info("향상된 연속 대화 서비스 초기화 완료")
    
    def _setup_enhanced_pipeline(self):
        """
        개선된 파이프라인 서비스 설정
        순환 참조를 피하기 위해 동적으로 import
        """
        try:
            from app.services.enhanced_pipeline_service import EnhancedPipelineService
            self._pipeline_service = EnhancedPipelineService(
                self.kiosk_service.stt_service,
                self.kiosk_service.rag_service,
                self.kiosk_service.tts_service,
                self.openai_api_key
            )
            logger.info("키오스크 서비스의 파이프라인을 개선된 파이프라인으로 교체했습니다.")
        except Exception as e:
            logger.error(f"파이프라인 서비스 설정 실패: {str(e)}")

    @property
    def pipeline_service(self):
        """파이프라인 서비스 접근자"""
        if not self._pipeline_service and self.kiosk_service:
            self._setup_enhanced_pipeline()
        return self._pipeline_service or self.kiosk_service.pipeline_service

    def _add_to_conversation_history(self, role: str, text: str) -> None:
        """대화 이력에 메시지 추가"""
        self.conversation_history.append({"role": role, "content": text})
        
        # 최대 길이 제한
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]

    # 메뉴 추출 함수
    def _extract_menu_from_text(self, text: str) -> Dict[str, Any]:
        """
        텍스트에서 모든 메뉴와 수량 정보 추출 - 문장 분리 없이 전체 텍스트에서 모든 메뉴 찾기
        """
        from app.services.nlp_processor import MENU_DATA
        
        result = {
            "has_menu": False,
            "menu_names": [],  # 여러 메뉴를 저장하기 위한 리스트
            "menu_name": "",   # 호환성 유지
            "quantities": {},  # 각 메뉴별 수량
            "quantity": 1,     # 호환성 유지
            "menu_text": "",   # 주문 텍스트
            "is_multi_menu": False  # 다중 메뉴 여부 표시 플래그 추가
        }

        # 메뉴 목록 가져오기
        menu_list = []
        try:
            menu_list = [menu["name"] for menu in MENU_DATA.get("menus", [])]
        except:
            menu_list = ["아메리카노", "카페 라떼", "카페 모카", "바닐라 라떼", "카라멜 마끼아또", 
                        "초코 라떼", "그린 라떼", "복숭아 아이스 티", "레몬에이드", "허브 티"]
        
        # 길이 순으로 정렬된 메뉴 목록 (긴 메뉴 이름 먼저 확인)
        sorted_menu_list = sorted(menu_list, key=len, reverse=True)
        
        # 전체 텍스트에서 모든 메뉴 찾기
        found_menus = []
        
        # 각 메뉴에 대해 텍스트 전체를 검색
        for menu in sorted_menu_list:
            if menu in text:
                # 수량 추출 로직 - 자신의 메서드 호출로 변경
                quantity = self._parse_quantity(text, menu)
                
                # 이미 찾은 메뉴인지 확인 (중복 방지)
                if menu not in result["quantities"]:
                    found_menus.append(menu)
                    result["quantities"][menu] = quantity
                    logger.info(f"전체 텍스트에서 메뉴 '{menu}' 발견, 수량: {quantity}")
        
        # 각 토큰(단어) 기반 메뉴 찾기 - 공백으로 분리된 각 단어 또는 구문에서 메뉴 찾기
        words = text.split()
        for i, word in enumerate(words):
            # 각 단어와 그 앞뒤 몇 개의 단어를 결합하여 검사
            for j in range(1, min(4, len(words) - i + 1)):
                phrase = ' '.join(words[i:i+j])
                for menu in sorted_menu_list:
                    if menu in phrase and menu not in result["quantities"]:
                        quantity = self._parse_quantity(phrase, menu)
                        found_menus.append(menu)
                        result["quantities"][menu] = quantity
                        logger.info(f"단어 분석에서 메뉴 '{menu}' 발견, 수량: {quantity}")
        
        # 특수 케이스: 여러 메뉴가 "랑", "와", "과" 등의 접속사로 연결된 경우를 명시적으로 처리
        connector_keywords = ["랑", "와", "과", "하고", "이랑", "그리고", "또", "및"]
        has_connectors = any(conn in text for conn in connector_keywords)
        
        # 여러 메뉴 연결 패턴이 감지되었지만 제한된 메뉴만 발견된 경우 추가 검사
        if has_connectors:
            for conn in connector_keywords:
                if conn in text:
                    parts = text.split(conn)  # 접속사로 분리
                    for i, part in enumerate(parts):
                        part = part.strip()
                        # 이미 처리된 메뉴는 건너뜀
                        already_found = False
                        for found_menu in found_menus:
                            if found_menu in part:
                                already_found = True
                                break
                        
                        if already_found:
                            continue
                            
                        # 추가 메뉴 찾기
                        for menu in sorted_menu_list:
                            if menu in part and menu not in [m for m in found_menus]:
                                quantity = self._parse_quantity(part, menu)
                                found_menus.append(menu)
                                result["quantities"][menu] = quantity
                                logger.info(f"접속사 분리 후 메뉴 '{menu}' 발견, 수량: {quantity}")
        
        # 결과 업데이트
        if found_menus:
            result["has_menu"] = True
            result["menu_names"] = found_menus
            
            # 다중 메뉴 여부 설정
            result["is_multi_menu"] = len(found_menus) > 1
            logger.info(f"발견된 메뉴 총 개수: {len(found_menus)} - 다중 메뉴 여부: {result['is_multi_menu']}")
            
            if found_menus:
                result["menu_name"] = found_menus[0]  # 첫 번째 메뉴를 대표 메뉴로 설정 (호환성 유지)
                
                # 첫 번째 메뉴의 수량을 quantity에 저장 (호환성 유지)
                result["quantity"] = result["quantities"].get(found_menus[0], 1)
            
            # 다중 메뉴 주문 텍스트 구성
            order_parts = []
            for menu in found_menus:
                quantity = result["quantities"].get(menu, 1)
                order_parts.append(f"{menu} {quantity}잔")
            
            # 모든 메뉴를 포함한 주문 텍스트
            result["menu_text"] = ", ".join(order_parts) + " 주문"
            logger.info(f"메뉴 추출 결과: {result['menu_text']}")
        
        return result

    def _parse_quantity(self, text: str, menu_name: str) -> int:
        """특정 메뉴의 수량 추출"""
        # 기본 수량은 1
        quantity = 1
        
        # "[메뉴] N잔" 같은 명시적 패턴 확인
        pattern1 = rf"{menu_name}\s*(\d+)\s*잔"
        match1 = re.search(pattern1, text)
        
        if match1:
            try:
                quantity = int(match1.group(1))
                logger.info(f"명시적 수량 감지: {menu_name} {quantity}잔 (숫자)")
                return quantity
            except ValueError:
                pass  # 변환 오류 시 다음 패턴 확인
        
        # "메뉴 한 잔" 형태 처리
        if f"{menu_name} 한 잔" in text or f"{menu_name} 한잔" in text or f"{menu_name}한잔" in text:
            logger.info(f"명시적 수량 감지: {menu_name} 1잔 (한 잔)")
            return 1
        
        # 한글 수량 표현 처리
        quantity_map = {"하나": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5, 
                    "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5}
        
        for num_word, value in quantity_map.items():
            pattern = rf'{menu_name}\s*{num_word}\s*잔'
            if re.search(pattern, text):
                logger.info(f"한글 수량 감지: {menu_name} {value}잔 (한글)")
                return value
        
        logger.info(f"기본 수량 적용: {menu_name} 1잔 (명시적 수량 없음)")
        return quantity
    
    def _is_cart_reset_command(self, text: str) -> bool:
        """텍스트에서 장바구니 초기화 명령 감지"""
        reset_keywords = ["장바구니 초기화", "장바구니 비우기", "카트 초기화", "카트 비우기", "장바구니 삭제", "주문 초기화"]
        return any(keyword in text for keyword in reset_keywords)

    # 주문 컨텍스트 업데이트 함수
    def _update_order_context(self, current_state: str, user_input: str, system_response: str):
        """주문 컨텍스트 업데이트 - 사용자 경험 개선"""
        # 의도 추적
        if "메뉴" in user_input or "뭐" in user_input and "있" in user_input:
            if "menu_inquiry" not in self.order_context["detected_intents"]:
                self.order_context["detected_intents"].append("menu_inquiry")
        
        # 메뉴 언급 추적
        menu_info = self._extract_menu_from_text(user_input)
        if menu_info["has_menu"]:
            self.order_context["last_mentioned_menu"] = menu_info["menu_name"]
            self.order_context["menu_count"] = menu_info["quantity"]
            
            if "order" not in self.order_context["detected_intents"]:
                self.order_context["detected_intents"].append("order")
        
        # 결제 의도 추적
        if "결제" in user_input or "카드" in user_input:
            if "payment" not in self.order_context["detected_intents"]:
                self.order_context["detected_intents"].append("payment")
        
        # 현재 상태에 따른 다음 단계 추천
        if current_state == "start" or current_state == "greeting":
            self.order_context["suggested_next"] = "메뉴 선택을 도와드릴까요?"
        elif current_state == "order_taking":
            self.order_context["suggested_next"] = "온도나 사이즈 옵션을 선택하실래요?"
        elif current_state == "option_select":
            self.order_context["suggested_next"] = "주문을 확인해 드릴까요?"
        elif current_state == "order_confirm":
            self.order_context["suggested_next"] = "결제 방법을 선택해주세요"
        elif current_state == "payment":
            self.order_context["suggested_next"] = "결제가 완료되었습니다"
    
    # 컨텍스트 기반 무음 메시지 생성
    def _generate_context_aware_silence_message(self) -> str:
        """컨텍스트 기반 무음 메시지 생성"""
        # 컨텍스트를 기반으로 더 적절한 메시지 생성
        state = self.kiosk_service.pipeline_service.current_state
        
        # 기본 메시지
        if state == "start" or state == "greeting":
            return "안녕하세요! 무엇을 도와드릴까요? 메뉴를 살펴보시거나 추천 메뉴를 물어보셔도 됩니다."
        elif state == "order_taking":
            if self.order_context["last_mentioned_menu"]:
                return f"{self.order_context['last_mentioned_menu']}를 주문하시겠어요? 몇 잔 필요하신가요?"
            else:
                return "어떤 음료를 주문하시겠어요? 아메리카노, 카페라떼, 카페모카 등 다양한 메뉴가 있습니다."
        elif state == "option_select":
            return "음료의 온도나 사이즈를 선택하실 수 있어요. 기본 옵션으로 진행할까요?"
        elif state == "order_confirm":
            return "주문하신 내용이 맞으면 '결제'라고 말씀해주세요. 수정이 필요하시면 알려주세요."
        elif state == "payment":
            return "카드로 결제하시겠어요? 결제가 완료되면 음료를 준비해 드리겠습니다."
        
        # 기본 메시지 반환
        return f"계속 진행하시려면 {self.order_context['suggested_next']}"
    
    async def start_dialog_session(self, 
                           on_session_start: Optional[Callable] = None,
                           on_session_end: Optional[Callable] = None,
                           on_speech_detected: Optional[Callable] = None,
                           on_response_start: Optional[Callable] = None,
                           on_response_end: Optional[Callable] = None) -> Dict[str, Any]:
        """
        향상된 대화 세션 시작 - 메뉴 먼저 로드
        """

        # 전역 인사말 플래그 참조
        global _greeting_shown

        # 처리 중인지 확인 코드 추가
        if self._processing:
            logger.info("이미 음성 처리가 진행 중입니다. 대기 중...")
            return {"success": False, "message": "이미 진행 중인 처리가 있습니다."}
        
        self._processing = True  # 처리 시작 플래그 설정

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
        self.silence_counter = 0
        
        # 세션 시작 콜백 호출
        if self.on_session_start:
            await self.on_session_start()
        
        # 메뉴 데이터 로드 및 전송 (먼저 실행)
        try:
            # 메뉴 데이터 가져오기
            menu_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "menu_data.json")
            menu_data = {}
            
            if os.path.exists(menu_path):
                with open(menu_path, 'r', encoding='utf-8') as f:
                    menu_data = json.load(f)
                    
            # WebSocket을 통해 메뉴 데이터 먼저 전송
            await notify_menu_loading(menu_data)
            
            # 메뉴 로딩 시간 확보를 위한 대기
            logger.info("메뉴 로딩을 위해 잠시 대기 중...")
            await asyncio.sleep(1.5)  # 메뉴 로딩 시간 확보
        except Exception as e:
            logger.error(f"메뉴 데이터 전송 실패: {str(e)}")

        # 나머지 초기화 작업
        await self.kiosk_service.reset_conversation()
        self.conversation_history = []
        self._last_processed_input = None
        self._processing = False

        # 주문 컨텍스트 초기화
        self.order_context = {
            "detected_intents": [],
            "suggested_next": "메뉴를 말씀해주세요",
            "frequent_menus": [],
            "last_mentioned_menu": "",
            "menu_count": 0
        }

        start_time = time.time()
        session_result = {
            "success": True,
            "completed": False,
            "duration": 0,
            "turns": [],
            "final_state": ""
        }

        # 인사말 생성 - 이 부분을 조건부로 변경
        greeting_result = {"text": "", "audio_path": ""}

        # 인사말을 아직 표시하지 않았다면
        if not _greeting_shown:
            greeting_result = await self.kiosk_service.greet_customer()
            
            # 첫 번째 턴 기록
            session_result["turns"].append({
                "speaker": "system",
                "text": greeting_result["text"],
                "audio_path": greeting_result["audio_path"]
            })
            
            # 대화 이력에 추가
            self._add_to_conversation_history("assistant", greeting_result["text"])
            
            # 응답 시작 콜백 호출
            if self.on_response_start:
                await self.on_response_start(greeting_result["text"])
            
            # 응답 종료 콜백 호출
            if self.on_response_end:
                await self.on_response_end(greeting_result["audio_path"])
                
            # 전역 인사말 플래그 설정
            _greeting_shown = True
            logger.info("인사말 표시 완료, 전역 플래그 설정됨")
        else:
            # 이미 인사말이 표시된 경우, 대화 세션 시작만 기록
            logger.info("이미 인사말이 표시되었습니다. 인사말 생성 건너뜀")
        
        # 주 대화 루프
        try:
            while self.is_listening:
                # 세션 타임아웃 확인 코드 유지
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
                user_speech = await self._listen_for_speech_with_vad(max_duration=5.0)
                
                # 음성이 감지되면 즉시 처리
                if user_speech:
                    # 이전 처리 진행 중이라면 중복 처리 방지
                    if self._processing:
                        logger.info("이미 처리 중인 입력이 있습니다. 대기 중...")
                        await asyncio.sleep(0.5)
                        continue
                        
                    self._processing = True
                    
                    try:
                        # 사용자 발화 로깅
                        logger.info(f"사용자 발화: '{user_speech}'")
                        print(f"사용자: '{user_speech}'")
                        # 장바구니 초기화 명령 확인
                        if self._is_cart_reset_command(user_speech) or user_speech in ["장바구니", "카트"]:
                            logger.info("장바구니 초기화 명령 감지")
                            
                            # 장바구니 초기화 알림 호출
                            await notify_cart_reset()
                            
                            # 사용자에게 응답
                            cart_reset_text = "장바구니가 초기화되었습니다. 새로운 주문을 말씀해주세요."
                            
                            # 응답 시작 콜백 호출
                            if self.on_response_start:
                                await self.on_response_start(cart_reset_text)
                            
                            # TTS 실행
                            cart_reset_result = await self.kiosk_service.tts_service.synthesize(
                                cart_reset_text,
                                play_audio=True
                            )
                            
                            # 응답 종료 콜백 호출
                            if self.on_response_end:
                                await self.on_response_end(cart_reset_result.get("audio_path", ""))
                            
                            # 턴 기록
                            session_result["turns"].append({
                                "speaker": "user",
                                "text": user_speech
                            })
                            
                            session_result["turns"].append({
                                "speaker": "system",
                                "text": cart_reset_text,
                                "audio_path": cart_reset_result.get("audio_path", "")
                            })
                            
                            # 대화 이력에 추가
                            self._add_to_conversation_history("user", user_speech)
                            self._add_to_conversation_history("assistant", cart_reset_text)
                            
                            # 다음 사용자 발화 대기를 위해 continue
                            continue

                        # 종료 요청 확인
                        if any(word in user_speech.lower() for word in ["종료", "그만", "취소", "나가기", "그만하기", "주문 취소"]):
                            farewell_text = "주문이 취소되었습니다. 이용해주셔서 감사합니다."
                            # 로깅
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
                            
                            # 대화 이력에 추가
                            self._add_to_conversation_history("user", user_speech)
                            self._add_to_conversation_history("assistant", farewell_text)
                            
                            session_result["completed"] = True
                            session_result["reason"] = "user_cancel"
                            break
                        
                        # 메뉴 직접 추출 - 전체 텍스트에서 모든 메뉴 찾기
                        menu_info = self._extract_menu_from_text(user_speech)
                        if menu_info["has_menu"]:
                            # 대화 이력에 사용자 발화 추가
                            self._add_to_conversation_history("user", user_speech)
                            
                            # 사용자 발화 기록 (결과에 저장)
                            session_result["turns"].append({
                                "speaker": "user",
                                "text": user_speech
                            })
                            
                            # 다중 메뉴 처리 개선
                            if menu_info["is_multi_menu"]:
                                logger.info(f"다중 메뉴 감지: {menu_info['menu_names']}")
                                
                                # 각 메뉴별 개별 처리를 위한 변수 초기화
                                cart_items = []
                                total_price = 0
                                all_responses = []
                                
                                # 모든 발견된 메뉴에 대해 처리
                                for i, menu_name in enumerate(menu_info["menu_names"]):
                                    # 메뉴 수량 가져오기
                                    quantity = menu_info["quantities"].get(menu_name, 1)
                                    
                                    # 해당 메뉴의 기본 주문 텍스트 생성
                                    menu_order_text = f"{menu_name} {quantity}잔 주문"
                                    logger.info(f"다중 메뉴 처리 {i+1}/{len(menu_info['menu_names'])}: '{menu_order_text}'")
                                    
                                    # 개별 메뉴 처리 - TTS 실행 없이 텍스트만 처리
                                    try:
                                        # 키오스크 서비스의 내부 로직을 사용하여 TTS 없이 처리
                                        menu_result = await self.kiosk_service.pipeline_service.process_input(
                                            menu_order_text, 
                                            skip_tts=True  # TTS 실행 건너뛰기
                                        )
                                        
                                        # 응답 메시지 수집
                                        all_responses.append(menu_result.get("response_text", ""))
                                        
                                        # 주문 정보 추출 (장바구니 업데이트 목적)
                                        order_info = extract_order_info(menu_result.get("response_text", ""))
                                        
                                        if order_info and order_info.get("items"):
                                            # 주문 항목 수집
                                            cart_items.extend(order_info.get("items", []))
                                            total_price += order_info.get("total", 0)
                                            
                                        # 처리 사이에 짧은 대기 (안정성 확보)
                                        await asyncio.sleep(0.3)
                                        
                                    except Exception as menu_error:
                                        logger.error(f"메뉴 '{menu_name}' 처리 중 오류: {str(menu_error)}")
                                
                                # 모든 메뉴에 대한 처리를 마친 후 통합 응답 생성
                                # 모든 메뉴 이름 결합
                                menu_names_text = ", ".join([f"{menu} {menu_info['quantities'].get(menu, 1)}잔" for menu in menu_info["menu_names"]])
                                combined_response = f"{menu_names_text} 추가되었습니다."
                                
                                # 통합 응답용 오디오 생성 - 여기서만 TTS 실행
                                audio_result = await self.kiosk_service.tts_service.synthesize(
                                    combined_response,
                                    play_audio=True
                                )
                                
                                # 최종 처리 결과
                                process_result = {
                                    "response_text": combined_response,
                                    "audio_path": audio_result.get("audio_path", "")
                                }
                                
                                # 시스템 응답 로깅
                                logger.info(f"통합 시스템 응답: '{combined_response}'")
                                print(f"시스템: '{combined_response}'")
                                
                                # 장바구니 업데이트 알림 (통합)
                                await notify_cart_update({
                                    "items": cart_items,
                                    "total": total_price,
                                    "is_multi_menu": True
                                })
                            else:
                                # 단일 메뉴 처리 (기존 로직)
                                direct_order_text = f"{menu_info['menu_name']} {menu_info['quantity']}잔 주문"
                                logger.info(f"단일 메뉴 직접 추출: '{user_speech}' -> '{direct_order_text}'")
                                
                                # 텍스트 처리 전달
                                process_result = await self.kiosk_service.process_text_input(direct_order_text)
                                
                                # 시스템 응답 로깅
                                logger.info(f"시스템 응답: '{process_result['response_text']}'")
                                print(f"시스템: '{process_result['response_text']}'")
                            
                            # 턴 기록 - 시스템 응답 추가
                            session_result["turns"].append({
                                "speaker": "system",
                                "text": process_result["response_text"],
                                "audio_path": process_result["audio_path"]
                            })
                            
                            # 대화 이력에 시스템 응답 추가
                            self._add_to_conversation_history("assistant", process_result["response_text"])
                            
                            # 응답 시작 콜백 호출
                            if self.on_response_start:
                                await self.on_response_start(process_result["response_text"])
                            
                            # 응답 종료 콜백 호출
                            if self.on_response_end:
                                await self.on_response_end(process_result["audio_path"])
                            
                            # 대화 상태 확인
                            current_state = self.kiosk_service.pipeline_service.current_state
                            session_result["final_state"] = current_state
                            
                            # 주문 상태 추적 및 다음 추천 행동 준비
                            self._update_order_context(current_state, user_speech, process_result["response_text"])
                            
                            # 다음 음성 감지로 이동
                            continue
                        
                        else:
                            # 단축 명령어 확인
                            if user_speech in self.command_shortcuts:
                                expanded_text = self.command_shortcuts[user_speech]
                                logger.info(f"단축 명령어 확장: '{user_speech}' -> '{expanded_text}'")
                                user_speech = expanded_text
                            
                            # 대화 이력에 사용자 발화 추가
                            self._add_to_conversation_history("user", user_speech)
                            
                            # 직접 텍스트 처리
                            process_result = await self.kiosk_service.process_text_input(user_speech)
                        
                        # 시스템 응답 로깅
                        logger.info(f"시스템 응답: '{process_result['response_text']}'")
                        print(f"시스템: '{process_result['response_text']}'")
                        
                        # 턴 기록
                        session_result["turns"].append({
                            "speaker": "user",
                            "text": user_speech  # 원본 발화 저장
                        })
                        
                        session_result["turns"].append({
                            "speaker": "system",
                            "text": process_result["response_text"],
                            "audio_path": process_result["audio_path"]
                        })
                        
                        # 대화 이력에 시스템 응답 추가
                        self._add_to_conversation_history("assistant", process_result["response_text"])
                        
                        # 응답 시작 콜백 호출
                        if self.on_response_start:
                            await self.on_response_start(process_result["response_text"])
                        
                        # 응답 종료 콜백 호출
                        if self.on_response_end:
                            await self.on_response_end(process_result["audio_path"])
                        
                        # 대화 상태 확인
                        current_state = self.kiosk_service.pipeline_service.current_state
                        session_result["final_state"] = current_state
                        
                        # 주문 완료 상태 확인
                        if current_state in ["farewell", "payment"]:
                            logger.info(f"주문 완료 감지: {current_state}")
                            completion_text = "주문이 완료되었습니다. 잠시만 기다려주시면 음료를 준비해 드리겠습니다. 감사합니다!"
                            
                            # 응답 시작 콜백 호출
                            if self.on_response_start:
                                await self.on_response_start(completion_text)
                            
                            # TTS 실행
                            completion_result = await self.kiosk_service.tts_service.synthesize(
                                completion_text,
                                play_audio=True
                            )
                            
                            # 응답 종료 콜백 호출
                            if self.on_response_end:
                                await self.on_response_end(completion_result.get("audio_path", ""))
                            
                            # 턴 기록
                            session_result["turns"].append({
                                "speaker": "system",
                                "text": completion_text,
                                "audio_path": completion_result.get("audio_path", "")
                            })
                            
                            # 대화 이력에 추가
                            self._add_to_conversation_history("assistant", completion_text)
                            
                            session_result["completed"] = True
                            session_result["reason"] = "order_completed"
                            break
                        
                        # 주문 상태 추적 및 다음 추천 행동 준비
                        self._update_order_context(current_state, user_speech, process_result["response_text"])
                    
                    finally:
                        self._processing = False
                    
                    # 잠시 대기 (과도한 CPU 사용 방지)
                    await asyncio.sleep(0.5)
                
                # 음성이 감지되지 않았으면 무음 처리
                else:
                    # 기존 무음 처리 로직 유지
                    if self.silence_counter == 0:
                        logger.info("첫 번째 무음 감지, 추가 대기 중...")
                        await asyncio.sleep(1.0)  # 3초 더 기다림
                        # 한 번 더 음성 감지 시도
                        user_speech = await self._listen_for_speech_with_vad(max_duration=5.0)
                        if user_speech:  # 음성 감지 성공
                            self.silence_counter = 0
                            # 음성 처리 계속 진행
                            logger.info(f"추가 대기 후 사용자 발화 감지: '{user_speech}'")
                            continue
                    
                    # 무음 카운터 증가
                    self.silence_counter += 1
                    
                    # 무음 응답 처리 (카운터에 따라 다른 응답)
                    if self.silence_counter >= self.max_silence_count:
                        # 주문 상태 체크 (결제 상태인 경우 주문 완료로 간주)
                        current_state = self.kiosk_service.pipeline_service.current_state
                        if current_state == "payment":
                            logger.info("결제 상태에서 무음 감지, 주문 완료로 간주")
                            session_result["completed"] = True
                            session_result["reason"] = "order_completed_silence"
                            break
                        
                        # 최대 무음 횟수 초과 로그만 출력하고 종료하지 않음
                        logger.info(f"무음 횟수 ({self.silence_counter}) - 계속 대기 중...")

                        if self.silence_counter >= self.max_silence_count + 5:
                            self.silence_counter = self.max_silence_count  # 계속 메시지는 표시하되 카운터가 무한정 증가하지 않도록
                        
                        # 무음 안내 메시지 준비 (컨텍스트 기반)
                        silence_message = self._generate_context_aware_silence_message()
                        
                        # 응답 시작 콜백 호출
                        if self.on_response_start:
                            await self.on_response_start(silence_message)
                        
                        # TTS 실행
                        silence_result = await self.kiosk_service.tts_service.synthesize(
                            silence_message,
                            play_audio=True
                        )
                        
                        # 응답 종료 콜백 호출
                        if self.on_response_end:
                            await self.on_response_end(silence_result.get("audio_path", ""))
                        
                        # 턴 기록
                        session_result["turns"].append({
                            "speaker": "system",
                            "text": silence_message,
                            "audio_path": silence_result.get("audio_path", "")
                        })
                        
                        # 대화 이력에 추가
                        self._add_to_conversation_history("assistant", silence_message)
                    
                    # 잠시 대기 후 다음 루프
                    await asyncio.sleep(0.5)
                    continue

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
           
            # 중복 처리 방지 변수 초기화
            self._last_processed_input = None
            self._processing = False
           
            logger.info(f"대화 세션 종료: {session_result['duration']:.1f}초, 턴 수: {len(session_result['turns'])//2}")
           
            # 세션 완료 후 잠시 대기
            await asyncio.sleep(1.0)
           
            if session_result["completed"] or session_result.get("reason") == "timeout":
                logger.info("주문 완료/취소 또는 타임아웃 감지, 새 대화 세션 자동 시작")
                # 짧은 대기 후 새 세션 시작 (사용자가 다음 주문을 준비할 시간)
                await asyncio.sleep(5.0)
                # 기존 콜백 함수를 그대로 사용하여 새 세션 시작
                asyncio.create_task(self.start_dialog_session(
                    self.on_session_start,
                    self.on_session_end,
                    self.on_speech_detected,
                    self.on_response_start,
                    self.on_response_end
                ))
                logger.info("새 대화 세션 자동 시작 요청 완료")

        return session_result 

    async def stop_dialog_session(self) -> bool:
        """진행 중인 대화 세션 중지"""
        if self.is_listening:
            self.is_listening = False
            logger.info("대화 세션 중지 요청")
            await asyncio.sleep(0.5)  # 대화 루프가 정상 종료될 시간 부여
            return True
        return False
        
    async def process_speech_for_cart(self, user_speech: str) -> Dict[str, Any]:
        """음성 인식 결과를 장바구니 추가 로직으로 처리"""
        try:
            # 로깅
            logger.info(f"장바구니 추가용 음성 처리: '{user_speech}'")
            
            # 메뉴 직접 추출 - 전체 텍스트에서 모든 메뉴 찾기
            menu_info = self._extract_menu_from_text(user_speech)
            
            if menu_info["has_menu"]:
                # 다중 메뉴 처리 개선
                if menu_info["is_multi_menu"]:
                    # 다중 메뉴 처리를 위한 주문 항목 생성
                    cart_items = []
                    total_price = 0
                    
                    # 모든 발견된 메뉴에 대해 처리
                    for menu_name in menu_info["menu_names"]:
                        # 메뉴 수량 가져오기
                        quantity = menu_info["quantities"].get(menu_name, 1)
                        
                        # 해당 메뉴의 기본 주문 텍스트 생성
                        menu_order_text = f"{menu_name} {quantity}잔 주문"
                        logger.info(f"다중 메뉴 중 개별 처리: '{menu_name}' {quantity}잔")
                        
                        # 키오스크 서비스를 통해 개별 메뉴 처리 (장바구니에는 추가하지 않고 정보만 가져옴)
                        menu_result = await self.kiosk_service.process_text_input(menu_order_text)
                        
                        # extract_order_info 함수를 통해 메뉴 정보 추출
                        order_info = extract_order_info(menu_result.get("response_text", ""))
                        
                        # 유효한 항목이 있으면 장바구니에 추가
                        if order_info and order_info.get("items"):
                            # 첫 번째 항목만 추가 (각 메뉴 처리에서는 하나만 나옴)
                            cart_items.extend(order_info.get("items", []))
                            total_price += order_info.get("total", 0)
                    
                    # 전체 메뉴에 대한 응답 메시지 생성
                    response_text = f"{menu_info['menu_text']} 추가."
                    
                    # 장바구니 업데이트 알림
                    from app.services.notification_service import notify_order_processed
                    await notify_order_processed({
                        "items": cart_items,
                        "total": total_price,
                        "response_text": response_text,
                        "audio_path": ""  # 오디오 경로는 나중에 생성됨
                    })
                    
                    # TTS로 응답 생성
                    audio_result = await self.kiosk_service.tts_service.synthesize(
                        response_text,
                        play_audio=True
                    )
                    
                    return {
                        "success": True,
                        "response_text": response_text,
                        "audio_path": audio_result.get("audio_path", ""),
                        "order_info": {
                            "items": cart_items,
                            "total": total_price,
                            "extraction_success": True
                        }
                    }
                else:
                    # 단일 메뉴 처리 (기존 로직)
                    direct_order_text = f"{menu_info['menu_name']} {menu_info['quantity']}잔 주문"
                    logger.info(f"단일 메뉴 직접 추출: '{user_speech}' -> '{direct_order_text}'")
                    
                    # 키오스크 서비스로 텍스트 처리
                    result = await self.kiosk_service.process_text_input(direct_order_text)
                    
                    # 메뉴와 수량 정보 추출
                    order_info = extract_order_info(result.get("response_text", ""))
                    
                    # 장바구니 업데이트 알림
                    from app.services.notification_service import notify_order_processed
                    await notify_order_processed({
                        "items": order_info.get("items", []),
                        "total": order_info.get("total", 0),
                        "response_text": result.get("response_text", ""),
                        "audio_path": result.get("audio_path", "")
                    })
                    
                    return {
                        "success": True,
                        "response_text": result.get("response_text", ""),
                        "audio_path": result.get("audio_path", ""),
                        "order_info": order_info
                    }
            else:
                # 메뉴가 없는 경우 기본 텍스트 처리
                result = await self.kiosk_service.process_text_input(user_speech)
                
                # 기본 처리 결과 반환
                order_info = extract_order_info(result.get("response_text", ""))
                
                return {
                    "success": True,
                    "response_text": result.get("response_text", ""),
                    "audio_path": result.get("audio_path", ""),
                    "order_info": order_info
                }
                
        except Exception as e:
            logger.error(f"장바구니 음성 처리 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "음성 주문 처리 중 오류가 발생했습니다."
            }
    
    async def _listen_for_speech_with_vad(self, wait_timeout: float = 1.0, max_duration: float = 7.0) -> Optional[str]:
        """
        VAD(음성 활동 감지)를 사용하여 음성 감지 및 인식
        
        Args:
            wait_timeout: 사용자 음성을 기다리는 최대 시간(초)
            max_duration: 녹음 최대 시간(초)
        
        Returns:
            인식된 텍스트 또는 None
        """
        try:
            import pyaudio
            import wave
            import time
            import numpy as np
            
            # webrtcvad 모듈 가져오기 시도
            try:
                import webrtcvad
                use_vad = True
                vad = webrtcvad.Vad(3)  # 민감도 조정 (0=덜 민감, 3=가장 민감)
                logger.info("VAD 활성화: webrtcvad 모듈 로드 성공")
            except ImportError:
                use_vad = False
                logger.error("webrtcvad 임포트 실패, 에너지 기반 VAD 사용")
            except Exception as e:
                use_vad = False
                logger.error(f"webrtcvad 초기화 오류: {str(e)}, 에너지 기반 VAD 사용")
            
            # 오디오 설정
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            CHUNK_DURATION_MS = 30
            CHUNK = int(RATE * CHUNK_DURATION_MS / 1000)
            
            # 무음 감지 관련 설정
            SILENCE_THRESHOLD = 3  # 무음 청크 수 감소
            SPEECH_THRESHOLD = 2   # 음성 청크 수 증가
            ENERGY_THRESHOLD = 300  # 에너지 임계값 약간 낮춤
            
            # 임시 파일 경로
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "audio_input")
            os.makedirs(temp_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            wav_path = os.path.join(temp_dir, f"vad_input_{timestamp}.wav")
            
            # PyAudio 스트림 설정
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
            voiced_frames = []
            is_recording = False
            is_speech_detected = False
            num_silent_chunks = 0
            num_speech_chunks = 0
            start_time = time.time()
            wait_end_time = start_time + wait_timeout  # 대기 종료 시간 계산
            speech_start_time = None
            waiting_indicator_time = start_time  # 대기 표시기 시간
            
            try:
                # 녹음 및 VAD 감지 루프
                while time.time() < wait_end_time + (max_duration if is_recording else 0):
                    # 현재 시간
                    current_time = time.time()
                    
                    # 대기 중 상태 표시 (1초마다)
                    if not is_recording and current_time - waiting_indicator_time >= 1.0:
                        remaining_wait = wait_end_time - current_time
                        if remaining_wait > 0:
                            logger.debug(f"음성 감지 대기 중... (남은 시간: {remaining_wait:.1f}초)")
                        waiting_indicator_time = current_time
                    
                    # 대기 시간이 지났고 음성이 감지되지 않았으면 종료
                    if not is_recording and current_time > wait_end_time:
                        logger.info(f"최대 대기 시간({wait_timeout:.1f}초) 초과, 음성 감지 종료")
                        break
                    
                    # 녹음 최대 시간 확인
                    if is_recording and current_time - speech_start_time >= max_duration:
                        logger.info(f"최대 녹음 시간({max_duration:.1f}초) 도달, 녹음 종료")
                        break
                    
                    # 마이크에서 데이터 읽기
                    frame = stream.read(CHUNK, exception_on_overflow=False)
                    
                    # 음성 감지 여부 확인
                    if use_vad:
                        try:
                            is_speech = vad.is_speech(frame, RATE)
                        except Exception as vad_error:
                            # VAD 오류 발생 시 에너지 기반 감지로 대체
                            data = np.frombuffer(frame, dtype=np.int16)
                            energy = np.sqrt(np.mean(data**2))
                            is_speech = energy > ENERGY_THRESHOLD
                            logger.debug(f"VAD 처리 오류, 에너지 기반 감지로 대체")
                    else:
                        # 에너지 기반 음성 감지 사용
                        data = np.frombuffer(frame, dtype=np.int16)
                        energy = np.sqrt(np.mean(data**2))
                        is_speech = energy > ENERGY_THRESHOLD
                    
                    # 음성이 감지되는 경우
                    if is_speech:
                        num_speech_chunks += 1
                        num_silent_chunks = 0
                        
                        # 일정 수 이상의 음성 청크가 감지되면 녹음 시작
                        if num_speech_chunks >= SPEECH_THRESHOLD and not is_recording:
                            is_recording = True
                            is_speech_detected = True
                            speech_start_time = time.time()
                            logger.info("음성 감지됨, 녹음 시작")
                            
                            # 이전 버퍼된 프레임 추가 (음성 시작 부분 보존)
                            if voiced_frames:
                                frames.extend(voiced_frames)
                                voiced_frames = []
                    # 무음이 감지되는 경우
                    else:
                        num_silent_chunks += 1
                        
                        # 녹음 중이 아니면 제한된 수의 프레임만 버퍼링
                        if not is_recording:
                            voiced_frames.append(frame)
                            if len(voiced_frames) > SPEECH_THRESHOLD * 3:
                                voiced_frames.pop(0)  # 오래된 프레임 제거
                        
                        # 녹음 중 충분한 무음이 감지되면 녹음 종료 여부 결정
                        if is_recording and num_silent_chunks >= SILENCE_THRESHOLD:
                            # 녹음 시작 후 경과 시간 계산
                            recording_duration = time.time() - speech_start_time
                            
                            # 최소 2초 이상 녹음된 경우에만 종료
                            if recording_duration >= 5.0:
                                logger.info(f"충분한 무음 감지, 녹음 종료 (녹음 시간: {recording_duration:.2f}초)")
                                break
                            else:
                                # 최소 시간이 지나지 않았으면 무음 카운터 리셋
                                num_silent_chunks = 0
                                logger.debug(f"무음 감지되었으나 최소 녹음 시간({recording_duration:.2f}/2.0초)이 지나지 않아 계속 녹음")
                    
                    # 녹음 중이면 프레임 저장
                    if is_recording:
                        frames.append(frame)
                    
                    # 짧은 대기 (CPU 부하 방지)
                    await asyncio.sleep(0.01)
                
            finally:
                # 스트림 정리
                stream.stop_stream()
                stream.close()
                p.terminate()
            
            # 음성이 감지되지 않은 경우
            if not is_speech_detected or len(frames) < RATE // CHUNK // 2:  # 0.5초 미만은 무시
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
            logger.info(f"음성 녹음 완료: {wav_path} ({recording_seconds:.2f}초)")
            
            # STT 처리
            with open(wav_path, 'rb') as audio_file:
                stt_result = await self.kiosk_service.stt_service.transcribe(audio_file)

            if not stt_result["success"] or not stt_result.get("text"):
                logger.info("음성 인식 결과 없음")
                return None
            
            # 인식된 텍스트 가져오기
            recognized_text = stt_result.get("text")

            # 종료/취소 명령어 확인
            termination_keywords = ["종료", "그만", "취소", "나가기", "그만하기", "주문 취소", "주문 종료"]
            is_termination_command = any(keyword in recognized_text.lower() for keyword in termination_keywords)
            
            # GPT로 음성 인식 결과 개선
            if self.openai_api_key and recognized_text and self.enable_gpt_correction:
                try:
                    # GPT를 사용하여 음성 인식 결과의 오류 수정 및 개선
                    response = await asyncio.to_thread(
                        self.openai_client.chat.completions.create,
                        model="gpt-3.5-turbo-1106",
                        messages=[
                            {"role": "system", "content": "당신은 음성 인식 결과를 개선하는 도우미입니다. "
                            "커피숍 키오스크에서 인식된 텍스트의 오류를 수정하고, 자연스러운 한국어로 변환하세요. "
                            "메뉴 주문, 수량, 옵션 등의 정보는 최대한 보존하세요."},
                            {"role": "user", "content": f"다음 음성 인식 결과를 개선해주세요: '{recognized_text}'"}
                        ]
                    )
                    
                    corrected_text = response.choices[0].message.content.strip()
                    logger.info(f"GPT 음성 인식 개선: '{recognized_text}' -> '{corrected_text}'")
                    recognized_text = corrected_text
                except Exception as e:
                    logger.error(f"GPT 음성 인식 개선 실패: {str(e)}")

            order_info = extract_order_info(recognized_text)

            # 종료 명령이 아닌 경우에만 장바구니 업데이트
            if order_info and not order_info.get("is_termination", False) and order_info.get("items"):
                try:
                    from app.services.notification_service import notify_cart_update
                    await notify_cart_update(order_info)
                    logger.info(f"장바구니 업데이트 알림 전송: {order_info}")
                except Exception as e:
                    logger.error(f"장바구니 업데이트 알림 실패: {str(e)}")
                    
             # 음성 인식 결과 처리 부분 수정
            order_info = extract_order_info(recognized_text)
            
            # 주문 정보 비교를 위한 함수 추가
            def is_same_order(order1, order2):
                """두 주문이 실질적으로 동일한지 비교 (ID 무시)"""
                if not order1 or not order2:
                    return False
                
                # items가 없으면 다른 주문으로 간주
                if not order1.get("items") or not order2.get("items"):
                    return False
                    
                # 아이템 수가 다르면 다른 주문으로 간주
                if len(order1["items"]) != len(order2["items"]):
                    return False
                    
                # 메뉴명과 수량만 비교
                items1 = sorted([(i["name"], i["quantity"]) for i in order1["items"]])
                items2 = sorted([(i["name"], i["quantity"]) for i in order2["items"]])
                
                return items1 == items2
            
            # 중복 주문 확인 (이전 주문과 완전히 동일한 경우만 중복으로 처리)
            if order_info and self._last_order_info and is_same_order(self._last_order_info, order_info):
                logger.info("중복 주문 감지, 알림 생략")
                
                # 메뉴명과 수량이 동일하더라도 ID는 다르게 생성
                for item in order_info.get("items", []):
                    item["id"] = str(uuid.uuid4())
            else:
                # 유효한 주문 정보가 있고 중복이 아닌 경우에만 장바구니 업데이트
                if order_info and order_info.get("items"):
                    # 이전 주문 정보 갱신
                    self._last_order_info = order_info.copy()
                    
                    # WebSocket 알림 전송
                    try:
                        from app.services.notification_service import notify_cart_update
                        await notify_cart_update(order_info)
                        logger.info(f"장바구니 업데이트 알림 전송: {order_info}")
                    except Exception as e:
                        logger.error(f"장바구니 업데이트 알림 실패: {str(e)}")

            # 단축 명령어 검사
            if recognized_text in self.command_shortcuts:
                expanded_text = self.command_shortcuts[recognized_text]
                logger.info(f"단축 명령어 확장: '{recognized_text}' -> '{expanded_text}'")
                recognized_text = expanded_text
            
            return recognized_text
            
        except Exception as e:
            logger.error(f"음성 감지 중 예외 발생: {str(e)}")
            return None