# app/services/pipeline_service.py
import logging
import os
import json
import asyncio
import time
import openai

from typing import Dict, Any, Optional, BinaryIO, List

from app.services.nlp_processor import extract_intent_and_slots, MENU_DATA
from app.services.stt_service_model import STTService
from app.services.rag_service import RAGService
from app.services.tts_service_model import TTSService
from app.models.rag_models import Query, GPTQueryEnhancer, GPTEnhancedRAGResponse
from app.models.fsm import fsm, GPTEnhancedFSM, State

logger = logging.getLogger(__name__)

# OpenAI API 키 설정
openai_api_key = os.getenv("OPENAI_API_KEY")
use_gpt = openai_api_key is not None
if use_gpt:
    try:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        logger.info("OpenAI 클라이언트 초기화 완료, GPT 기능 활성화")
    except Exception as e:
        logger.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
        use_gpt = False
else:
    logger.warning("OPENAI_API_KEY가 설정되지 않았습니다. GPT 기능이 비활성화됩니다.")

async def initialize_pipeline():
    """파이프라인 초기화 함수"""
    logger.info("파이프라인 초기화 시작")
    
    # 필요한 초기화 작업 수행
    # 예: 모델 로드, API 키 확인 등
    
    logger.info("파이프라인 초기화 완료")
    return True

class PipelineService:
    """STT -> NLP -> FSM -> RAG -> TTS 통합 파이프라인 서비스"""
    
    def __init__(
        self,
        stt_service: Optional[STTService] = None,
        rag_service: Optional[RAGService] = None,
        tts_service: Optional[TTSService] = None
    ):
        self.stt_service = stt_service or STTService()
        self.rag_service = rag_service or RAGService()
        self.tts_service = tts_service or TTSService()
        
        # 대화 상태 관리
        self.current_state = "start"
        self.current_slots = {}
        
        logger.info("파이프라인 서비스 초기화 완료")
    
    async def generate_natural_response(self, base_response: str, query: str, state: str) -> str:
        """더 자연스러운 응답 생성"""
        
        # OpenAI API 키가 없으면 기본 응답 반환
        if not os.getenv("OPENAI_API_KEY"):
            return base_response
            
        try:
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # GPT에게 적절한 응답 생성 요청
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": f"""
                        당신은 카페 키오스크입니다. 현재 '{state}' 상태에서 고객 질문에 대한 응답을 자연스럽게 만들어주세요.
                        단, 다음 사항을 지켜주세요:
                        
                        1. 원본 응답의 핵심 정보(메뉴명, 가격, 옵션 등)는 반드시 유지할 것
                        2. 블로그나 나무위키 같은 형식이 아닌 일상적인 대화체로 작성할 것
                        3. 응답을 필요 이상으로 짧게 자르지 말 것
                        4. 불필요한 정보는 제거하되, 필요한 정보는 자연스럽게 유지할 것
                        5. 고객을 존중하는 친절한 어투를 사용할 것
                        """
                    },
                    {
                        "role": "user", 
                        "content": f"고객 질문: {query}\n\n원본 응답: {base_response}"
                    }
                ],
                temperature=0.7
            )
            
            natural_response = response.choices[0].message.content.strip()
            return natural_response
            
        except Exception as e:
            logger.error(f"자연스러운 응답 생성 실패: {str(e)}")
            return base_response  # 오류 시 기본 응답 반환
        
    async def process_audio_query(self, audio_data: BinaryIO) -> Dict[str, Any]:
        """음성 쿼리 처리: STT -> NLP -> FSM -> RAG -> TTS 파이프라인"""
        try:
            # 1. 음성을 텍스트로 변환 (STT)
            stt_result = await self.stt_service.transcribe(audio_data)
            
            if not stt_result["success"]:
                return {
                    "success": False,
                    "error": stt_result.get("error", "음성인식 실패"),
                    "stage": "stt"
                }
            
            query_text = stt_result["text"]
            
            # 텍스트 쿼리 처리로 전달   
            return await self.process_text_query(query_text)
            
        except Exception as e:
            logger.error(f"오디오 쿼리 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "pipeline"
            }
    
    async def process_text_input(self, text: str) -> Dict[str, Any]:
        """텍스트 입력 처리 및 응답 생성 (키오스크 전용)"""
        try:
            # 로그 추가
            logger.info(f"텍스트 쿼리 처리 시작: '{text}'")
            
            # NLP 처리
            nlp_result = extract_intent_and_slots(text)
            intent = nlp_result["intent"]
            slots = nlp_result["slots"]
            
            logger.info(f"NLP 결과: 의도={intent}, 슬롯={slots}")
            
            # 현재 상태 가져오기
            current_state = self.current_state
            
            # 메뉴 항목 처리 개선 - 여러 메뉴 처리
            if "menu" in slots:
                # 메뉴가 문자열인 경우 리스트로 변환
                if isinstance(slots["menu"], str):
                    # 여러 메뉴 인식 - 메뉴와 메뉴 사이에 '랑', '와', '하고', ',' 등이 있는지 확인
                    menu_text = slots["menu"]
                    if any(sep in menu_text for sep in ['랑', '와', '하고', ',', '그리고']):
                        # 구분자로 분리
                        import re
                        menu_parts = re.split(r'[,\s]*(랑|와|하고|,|그리고)[,\s]*', menu_text)
                        # 빈 문자열 제거하고 리스트로 만들기
                        menu_list = [part.strip() for part in menu_parts if part.strip() and part.strip() not in ['랑', '와', '하고', ',', '그리고']]
                        slots["menu"] = menu_list
                    else:
                        slots["menu"] = [menu_text]
                
                # 여러 메뉴의 총 가격 계산
                if isinstance(slots["menu"], list) and len(slots["menu"]) > 1:
                    # 주문 상세 정보와 총 가격 재구성
                    menu_details = []
                    total_amount = 0
                    
                    for menu_item in slots["menu"]:
                        # 메뉴별 가격 찾기 (extract_intent_and_slots 함수의 논리와 유사)
                        menu_info = next((menu for menu in MENU_DATA.get("menus", []) if menu["name"] == menu_item), None)
                        
                        if menu_info:
                            base_price = menu_info.get("basePrice", 4500)
                        else:
                            # 임시 가격표 (메뉴 데이터에 없는 경우)
                            price_table = {
                                "아메리카노": 4500, "카페라떼": 5000, "카페모카": 5500, "바닐라 라떼": 5500,
                                "카라멜 마끼아또": 5800, "초코 라떼": 5000, "그린 라떼": 5000,
                                "복숭아 아이스 티": 5200, "허브 티": 5000, "레몬 에이드": 5500
                            }
                            base_price = price_table.get(menu_item, 4500)
                        
                        # 옵션 추가 가격 (모든 메뉴에 동일 옵션 적용)
                        option_price = 0
                        size_price = 0
                        
                        if "temperature" in slots and slots["temperature"] == "아이스":
                            option_price += 0
                        
                        if "shot" in slots:
                            if "1샷" in slots["shot"] or "샷 추가" in slots["shot"]:
                                option_price += 500
                            elif "2샷" in slots["shot"]:
                                option_price += 1000
                        
                        if "size" in slots:
                            size = slots["size"].lower()
                            if size in ["라지", "점보", "벤티", "large", "l", "트렌타"]:
                                size_price += 1000
                        
                        # 메뉴별 상세 정보
                        item_price = base_price + option_price + size_price
                        total_amount += item_price
                        
                        # 옵션 정보
                        option_text = ""
                        if "temperature" in slots:
                            option_text += f" {slots['temperature']}"
                        if "size" in slots:
                            option_text += f" {slots['size']}"
                        if "shot" in slots:
                            option_text += f" {slots['shot']}"
                        
                        menu_details.append(f"{menu_item}{option_text} ({item_price:,}원)")
                    
                    # 수량
                    count = slots.get("count", 1)
                    total_amount *= count
                    
                    # 주문 상세 정보 구성
                    order_details = ", ".join(menu_details)
                    if count > 1:
                        order_details += f" 각 {count}잔씩"
                    
                    # 포장/매장 정보 추가
                    if "takeout" in slots:
                        order_details += " 포장" if slots["takeout"] else " 매장"
                    
                    # 슬롯 업데이트
                    slots["order_details"] = order_details
                    slots["total_price"] = f"{total_amount:,}"
            
            # 온도, 사이즈, 샷 등의 개별 옵션을 options 배열로 통합
            if "menu" in slots:
                # 옵션 정보 배열 초기화
                if "options" not in slots:
                    slots["options"] = []
                elif not isinstance(slots["options"], list):
                    slots["options"] = [slots["options"]]
                
                # 온도 옵션 추가
                if "temperature" in slots:
                    slots["options"].append(slots["temperature"])
                
                # 사이즈 옵션 추가
                if "size" in slots:
                    slots["options"].append(slots["size"])
                
                # 샷 옵션 추가
                if "shot" in slots:
                    slots["options"].append(slots["shot"])
                
                # 시럽 옵션 추가
                if "syrup" in slots:
                    slots["options"].append(slots["syrup"])
                
                logger.info(f"통합된 옵션 정보: {slots['options']}")
            # 한번에 여러 정보 처리: 메뉴, 온도, 추가옵션, 결제 방법 확인
            has_menu = "menu" in slots
            has_temperature = "temperature" in slots
            has_option = "options" in slots or "shot" in slots or "syrup" in slots or "size" in slots
            has_payment = "payment_method" in slots or "카드" in text.lower() or "결제" in text.lower()
            
            # 전체 정보 한번에 입력된 경우 결제로 바로 진행
            if has_menu and (has_temperature or has_option) and has_payment:
                logger.info(f"모든 정보 한번에 입력됨: 메뉴, 옵션, 결제방법 감지")
                self.current_state = "payment"
                
                # 결제 방법 설정 (명시적으로 없는 경우)
                if "payment_method" not in slots:
                    if "카드" in text.lower():
                        slots["payment_method"] = "카드"
                    else:
                        slots["payment_method"] = "카드"  # 기본값
                
                payment_method = slots.get('payment_method', '카드')
                order_details = slots.get("order_details", "")
                total_price = slots.get("total_price", "")
                
                response_text = f"{order_details} 주문 받았습니다. 총 {total_price}원, {payment_method}로 결제 진행하겠습니다. 결제가 완료되었습니다. 잠시만 기다려주시면 음료 준비해드리겠습니다."
            
            # 기존 키워드 기반 상태 변경 로직
            elif "결제" in text.lower() or "카드" in text.lower() :
                self.current_state = "payment"
                logger.info(f"키워드 기반 상태 전환: {current_state} -> payment")
                
                # FSM 기반 상태 전환 (슬롯 정보도 전달)
                next_state = fsm.get_next_state(current_state, intent, slots)
                
                # 상태 변경 여부 확인 및 로깅
                if next_state != current_state and self.current_state != "payment":
                    logger.info(f"상태 전이: {current_state} -> {next_state}")
                    self.current_state = next_state
                
                # 결제 방법이 입력된 경우
                payment_method = slots.get('payment_method', '카드')
                self.current_state = "payment"
                response_text = f"{payment_method}로 결제 진행하겠습니다. 결제가 완료되었습니다. 잠시만 기다려주시면 음료 준비해드리겠습니다."
            
            else:
                # 기존 로직: FSM 기반 상태 전환
                next_state = fsm.get_next_state(current_state, intent, slots)
                
                if next_state != current_state:
                    logger.info(f"상태 전이: {current_state} -> {next_state}")
                    self.current_state = next_state
                
                # 응답 생성 - 상태에 따른 차별화된 응답
                if "menu" in slots and self.current_state == "order_taking":
                    # 메뉴만 입력된 경우 옵션 안내 - 여러 메뉴 대응
                    menus = slots["menu"]
                    if isinstance(menus, list) and len(menus) > 1:
                        menu_text = ", ".join(menus[:-1]) + " 그리고 " + menus[-1]
                        response_text = f"네, {menu_text} 주문하셨습니다. 어떤 옵션으로 준비해 드릴까요? 따뜻하게 드실지, 차갑게 드실지, 사이즈는 어떻게 하실지 알려주세요."
                    else:
                        menu_name = menus[0] if isinstance(menus, list) else menus
                        response_text = f"네, {menu_name} 주문하셨습니다. 어떤 옵션으로 준비해 드릴까요? 따뜻하게 드실지, 차갑게 드실지, 사이즈는 어떻게 하실지 알려주세요."
                
                elif self.current_state == "order_confirm" or ("option" in slots and self.current_state == "order_taking"):
                    # 옵션이 입력된 경우 주문 확인
                    order_details = slots.get("order_details", "")
                    total_price = slots.get("total_price", "")
                    
                    # 상태를 order_confirm으로 변경 (자동 진행)
                    self.current_state = "order_confirm"
                    logger.info(f"옵션 입력 감지로 상태 전환: order_taking -> order_confirm")
                    
                    response_text = f"{order_details} 주문 맞으시죠? 총 {total_price}원입니다. 결제는 어떻게 하시겠어요?"
                
                elif "payment_method" in slots or self.current_state == "payment":
                    # 결제 방법이 입력된 경우
                    payment_method = slots.get('payment_method', '카드')
                    self.current_state = "payment"
                    response_text = f"{payment_method}로 결제 진행하겠습니다. 결제가 완료되었습니다. 잠시만 기다려주시면 음료 준비해드리겠습니다."
                else:
                    # 그 외의 경우 FSM 기본 응답 사용
                    response_text = fsm.get_response(self.current_state, slots)
            
            # 최종 응답 로그 추가
            logger.info(f"최종 응답: '{response_text}'")

            # TTS 처리
            tts_result = await self.tts_service.synthesize(
                response_text,
                play_audio=True
            )
            # WebSocket으로 상태 변경 알림 (여기에 추가)
            try:
                from app.services.notification_service import notify_state_update
                await notify_state_update(self.current_state, response_text, slots)
            except Exception as e:
                logger.error(f"WebSocket 알림 중 오류: {str(e)}")
                
            # 결과 반환
            return {
                "success": True,
                "intent": intent,
                "slots": slots,
                "current_state": self.current_state,
                "response_text": response_text,
                "audio_path": tts_result.get("audio_path", "")
            }
        except Exception as e:
            logger.error(f"텍스트 입력 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response_text": "처리 중 오류가 발생했습니다."
            }
        
    async def process_text_query(self, query_text: str) -> Dict[str, Any]:
        """텍스트 쿼리 처리: NLP -> FSM -> RAG -> GPT -> TTS 파이프라인"""
        # 중복 처리 방지를 위한 타임스탬프 확인
        current_time = time.time()
        
        # 동일 입력에 대해 일정 시간(1초) 이내 재요청은 이전 결과 반환
        if (
            self.enable_duplicate_checking 
            and query_text == self._last_processed_input 
            and self._last_result 
            and hasattr(self, '_last_processing_time') 
            and current_time - self._last_processing_time < 1.0
        ):
            logger.info(f"중복 입력 감지, 기존 결과 반환: '{query_text}'")
            return self._last_result
            
        # 처리 중 플래그 확인
        if self._processing:
            logger.info("이미 처리 중인 입력이 있습니다. 중복 처리 방지.")
            return {
                "success": False,
                "error": "이미 처리 중인 요청이 있습니다.",
                "stage": "duplicate",
                "response_text": "잠시만 기다려주세요."
            }
        
        self._processing = True
        self._last_processing_time = current_time

        try:
            # 로그 추가
            logger.info(f"텍스트 쿼리 처리 시작: '{query_text}'")
            
            # 1. NLP로 의도와 슬롯 추출
            nlp_result = extract_intent_and_slots(query_text)
            intent = nlp_result["intent"]
            slots = nlp_result["slots"]
            
            # 로그 추가
            logger.info(f"NLP 결과: 의도={intent}, 슬롯={slots}")
            
            # 장바구니 초기화 명령 감지 및 처리
            if intent == "cancel" or intent == "remove" or ("취소" in query_text.lower() and "장바구니" in query_text.lower()):
                logger.info("장바구니 초기화 의도 감지")
                
                # 장바구니 초기화 메시지 생성
                final_response = "장바구니가 초기화되었습니다. 다시 주문해주세요."
                
                # 장바구니 초기화 이벤트 발생
                try:
                    from app.services.notification_service import notify_cart_update
                    await notify_cart_update({"items": [], "total": 0, "operation": "reset"})
                    logger.info("장바구니 초기화 이벤트 전송 완료")
                except Exception as e:
                    logger.error(f"장바구니 초기화 이벤트 전송 실패: {str(e)}")
                
                # 상태 초기화 (그리팅 상태로)
                self.current_state = "greeting"
                next_state = "greeting"
                
                # TTS로 음성 합성
                tts_result = await self.tts_service.synthesize(
                    final_response,
                    play_audio=True  # 오디오 자동 재생 활성화
                )
                
                if not tts_result["success"]:
                    return {
                        "success": False,
                        "error": tts_result.get("error", "음성 합성 실패"),
                        "stage": "tts",
                        "response_text": final_response
                    }
                
                # WebSocket으로 상태 변경 알림
                try:
                    from app.services.connection_manager import manager
                    await manager.notify_clients(next_state, final_response, self.current_slots)
                except ImportError:
                    logger.warning("WebSocket 모듈을 불러올 수 없습니다.")
                except Exception as e:
                    logger.error(f"WebSocket 알림 중 오류: {str(e)}")
                
                # 결과 반환
                return {
                    "success": True,
                    "audio": tts_result["audio"],
                    "audio_path": tts_result["audio_path"],
                    "audio_base64": tts_result.get("audio_base64", ""),
                    "response_text": final_response,
                    "current_state": next_state,
                    "_meta": {
                        "query": query_text,
                        "intent": intent,
                        "slots": self.current_slots,
                        "rag_used": False
                    }
                }

            # 기존 슬롯 정보와 병합
            merged_slots = {**self.current_slots, **slots}
            self.current_slots = merged_slots

            # 옵션 통합 코드 추가 (여기에 삽입)
            # 온도, 사이즈, 샷 등의 개별 옵션을 options 배열로 통합
            if "menu" in merged_slots:
                # 옵션 정보 배열 초기화
                if "options" not in merged_slots:
                    merged_slots["options"] = []
                elif not isinstance(merged_slots["options"], list):
                    merged_slots["options"] = [merged_slots["options"]]
                
                # 온도 옵션 추가
                if "temperature" in merged_slots:
                    merged_slots["options"].append(merged_slots["temperature"])
                
                # 사이즈 옵션 추가
                if "size" in merged_slots:
                    merged_slots["options"].append(merged_slots["size"])
                
                # 샷 옵션 추가
                if "shot" in merged_slots:
                    merged_slots["options"].append(merged_slots["shot"])
                
                # 시럽 옵션 추가
                if "syrup" in merged_slots:
                    merged_slots["options"].append(merged_slots["syrup"])
                
                logger.info(f"통합된 옵션 정보: {merged_slots['options']}")
            # 2. FSM으로 상태 전이 및 기본 응답 생성
            next_state = fsm.get_next_state(self.current_state, intent)
            
            # 로그 추가
            logger.info(f"상태 전이: {self.current_state} -> {next_state}")
            
            self.current_state = next_state
            
            base_response = fsm.get_response(next_state, merged_slots)
            
            # 3. 상태에 따라 RAG 사용 결정
            use_rag = (
                "menu" in intent or 
                "option" in intent or 
                next_state in ["order_taking", "option_select", "order_confirm"] or
                "help" in intent or
                "추천" in query_text
            )
            
            if use_rag:
                # RAG 서비스 초기화 확인
                if not self.rag_service.is_initialized:
                    await self.rag_service.initialize()
                
                # RAG 서비스 호출
                rag_response = await self.rag_service.process_query(query_text)
                rag_text = rag_response.generated_text
                
                # FSM 기본 응답과 RAG 응답 결합 결정
                if next_state == "greeting" or "help" in intent:
                    # 인사나 도움 요청은 RAG 응답 우선
                    final_response = rag_text
                elif "menu" in intent or "order" in intent:
                    # 메뉴/주문은 둘 다 포함
                    final_response = f"{base_response} {rag_text}"
                else:
                    # 그 외에는 상황에 따라 결합
                    if base_response in rag_text:
                        final_response = rag_text
                    else:
                        final_response = f"{base_response} {rag_text}"
            else:
                # RAG 없이 FSM 응답만 사용
                final_response = base_response
            
            # 4. 응답이 비어있거나 짧은 경우 처리
            if not final_response or len(final_response) < 5:
                final_response = "죄송합니다, 다시 말씀해주시겠어요?"
            
            # 최종 응답 로그 추가
            logger.info(f"최종 응답: '{final_response}'")

            # 5. TTS로 음성 합성
            tts_result = await self.tts_service.synthesize(
                final_response,
                play_audio=True  # 오디오 자동 재생 활성화
            )
            
            if not tts_result["success"]:
                return {
                    "success": False,
                    "error": tts_result.get("error", "음성 합성 실패"),
                    "stage": "tts",
                    "response_text": final_response
                }
            
            # 6. WebSocket으로 상태 변경 알림
            try:
                from app.services.connection_manager import manager
                await manager.notify_clients(next_state, final_response, merged_slots)
            except ImportError:
                logger.warning("WebSocket 모듈을 불러올 수 없습니다.")
            except Exception as e:
                logger.error(f"WebSocket 알림 중 오류: {str(e)}")
            
            # 7. 결과 반환 (간소화된 버전)
            return {
                "success": True,
                "audio": tts_result["audio"],
                "audio_path": tts_result["audio_path"],
                "audio_base64": tts_result.get("audio_base64", ""),
                "response_text": final_response,
                "current_state": next_state,
                "_meta": {
                    "query": query_text,
                    "intent": intent,
                    "slots": merged_slots,
                    "rag_used": use_rag
                }
            }
        except Exception as e:
            logger.error(f"텍스트 쿼리 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "pipeline",
                "response_text": "처리 중 오류가 발생했습니다."
            }
    
    def analyze_options(self, text: str) -> None:
        """
        텍스트에서 옵션을 분석하고 상태를 업데이트
        """
        # 온도 옵션 감지
        if any(word in text.lower() for word in ["아이스", "차가운", "시원한", "콜드", "ice"]):
            logger.info("텍스트 분석: 아이스 옵션 감지")
            # 현재 상태가 order_taking이면 order_confirm으로 자동 진행 고려
            if self.current_state == "order_taking":
                self.current_state = "order_confirm"
                logger.info("온도 옵션 감지로 상태 전환: order_taking -> order_confirm")
        
        # 샷 옵션 감지
        if any(word in text.lower() for word in ["샷", "shot", "에스프레소", "진하게"]):
            logger.info("텍스트 분석: 샷 옵션 감지")
            # 슬롯에 샷 옵션 추가 (현재 슬롯 구조에 따라 조정 필요)
            self.current_slots["shot"] = "샷 추가"
        
        # 결제 관련 키워드 감지
        if any(word in text.lower() for word in ["결제", "카드", "지불", "계산"]):
            logger.info("텍스트 분석: 결제 키워드 감지")
            self.current_state = "payment"
            logger.info("결제 키워드 감지로 상태 전환: -> payment")
        
        # 주문 확인 키워드 감지
        if any(word in text.lower() for word in ["확인", "맞아", "그거", "주문할게", "좋아"]):
            logger.info("텍스트 분석: 주문 확인 키워드 감지")
            if self.current_state in ["order_taking", "option_select"]:
                self.current_state = "order_confirm"
                logger.info("주문 확인 키워드 감지로 상태 전환: -> order_confirm")

    async def reset_conversation(self) -> Dict[str, Any]:
        """대화 상태 초기화"""
        try:
            # FSM 상태 초기화
            fsm.reset()
            self.current_state = "start"
            self.current_slots = {}
            
            # 초기 인사말 생성
            greeting = "안녕하세요, 어서오세요."
            
            # TTS로 음성 합성
            tts_result = await self.tts_service.synthesize(greeting)
            
            if not tts_result["success"]:
                return {
                    "success": False,
                    "error": tts_result.get("error", "음성 합성 실패"),
                    "message": "대화 초기화 실패"
                }
            
            return {
                "success": True,
                "message": "대화가 초기화되었습니다.",
                "audio": tts_result["audio"],
                "audio_path": tts_result["audio_path"],
                "audio_base64": tts_result.get("audio_base64", ""),
                "response_text": greeting
            }
        except Exception as e:
            logger.error(f"대화 초기화 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "대화 초기화 실패"
            }

    async def update_state(self, state_name: str) -> Dict[str, Any]:
        """
        수동으로 FSM 상태 업데이트
        
        Args:
            state_name: 설정할 상태 이름
        
        Returns:
            업데이트 결과
        """
        try:
            current_state = self.current_state
            self.current_state = state_name
            
            # 응답 메시지 생성
            response_message = fsm.get_response(state_name, self.current_slots)
            
            # WebSocket 클라이언트 업데이트
            try:
                from app.services.connection_manager import manager
                await manager.notify_clients(state_name, response_message, self.current_slots)
            except ImportError:
                logger.warning("WebSocket 알림 기능을 불러올 수 없습니다.")
            except Exception as e:
                logger.error(f"WebSocket 알림 중 오류: {str(e)}")
            
            logger.info(f"수동 상태 업데이트: {current_state} -> {state_name}")
            
            return {
                "success": True,
                "state": state_name,
                "message": response_message
            }
        except Exception as e:
            logger.error(f"상태 업데이트 중 오류: {str(e)}")
            return {
                "success": False,
                "error": f"상태 업데이트 실패: {str(e)}"
            }

class GPTEnhancedPipelineService(PipelineService):
    """GPT API로 강화된 STT -> NLP -> FSM -> RAG -> TTS 통합 파이프라인 서비스"""
    
    def __init__(
        self,
        stt_service: Optional[STTService] = None,
        rag_service: Optional[RAGService] = None,
        tts_service: Optional[TTSService] = None,
        openai_api_key: Optional[str] = None
    ):
        # 부모 클래스 초기화
        super().__init__(stt_service, rag_service, tts_service)
        
        # GPT 관련 설정
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            logger.warning("OpenAI API 키가 설정되지 않았습니다. GPT 기능이 제한됩니다.")
        else:
            # OpenAI 클라이언트 초기화
            self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
        
        # FSM을 GPT 강화 버전으로 교체 (가능한 경우)
        try:
            self.gpt_fsm = GPTEnhancedFSM()
        except Exception as e:
            logger.warning(f"GPT 강화 FSM 초기화 실패, 기본 FSM 사용: {str(e)}")
            self.gpt_fsm = None
        
        # 대화 이력 관리
        self.conversation_history = []
        self.max_history_length = 10
        
        logger.info("GPT 강화 파이프라인 서비스 초기화 완료")
    
    def _add_to_conversation_history(self, speaker: str, text: str) -> None:
        """대화 이력에 새 메시지 추가 및 길이 관리"""
        self.conversation_history.append({"speaker": speaker, "text": text})
        
        # 최대 길이 제한
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    async def gpt_analyze_text(self, text: str) -> Dict[str, Any]:
        """
        GPT를 사용하여 텍스트 분석 (의도, 슬롯, 감정, 맥락 등)
        """
        try:
            if not self.openai_api_key:
                logger.warning("OpenAI API 키가 없어 GPT 분석을 건너뜁니다.")
                return {}
            
            # GPT API 호출
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        당신은 카페 키오스크 주문 분석기입니다. 사용자의 발화를 분석하여:
                        1. 의도(intent): greeting, order, option, confirm, payment, help, exit 중 하나
                        2. 슬롯(slots): 메뉴(menu), 수량(count), 온도(temperature), 크기(size), 추가 옵션(option),
                           결제 방법(payment_method), 포장/매장(takeout) 등 주문 관련 정보
                        3. 감정(emotion): 사용자의 감정 상태 (positive, neutral, negative)
                        4. 우선순위(priority): 발화에서 가장 중요한 정보
                        5. 다음 상태(next_state): 적절한 다음 상태 제안
                        
                        다음 JSON 형식으로 반환하세요:
                        {
                            "intent": "의도",
                            "emotion": "감정",
                            "priority": "우선순위",
                            "next_state": "다음 상태",
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
            logger.info(f"GPT 분석 결과: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"GPT 분석 실패: {str(e)}")
            return {}
    
    async def gpt_enhance_response(self, original_response: str, context: Dict[str, Any], user_message: str = "", make_conversational: bool = False) -> str:
        """
        GPT를 사용하여 응답 개선
        """
        try:
            if not self.openai_api_key:
                logger.warning("OpenAI API 키가 없어 기본 응답을 그대로 사용합니다.")
                return original_response
            
            # 대화 맥락 구성
            context_history = self.conversation_history[-5:] if self.conversation_history else []
            
            # GPT API 호출
            system_content = f"""
                당신은 카페 키오스크 응답 개선기입니다. 다음 맥락을 고려하여 응답을 개선하세요:
                1. 현재 상태: {context.get('current_state', '알 수 없음')}
                2. 사용자의 의도: {context.get('intent', '알 수 없음')}
                3. 사용자의 감정: {context.get('emotion', 'neutral')}
                
                다음 원칙을 따라 응답을 개선하세요:
                - 간결하고 직관적인 표현 사용 (2-3문장 이내)
                - 사용자의 감정에 공감하되 전문적인 톤 유지
                - 주문 정보(메뉴, 가격, 옵션 등)는 정확히 유지
                - 카페 키오스크답게 친절하고 명확한 표현 사용
            """
            
            if make_conversational:
                system_content += """
                - 고객이 실제 대화하는 사람과 대화하는 느낌이 들도록 자연스러운 어투 사용
                - 기계적이고 딱딱한 응답보다는 친근하고 따뜻한 표현 사용
                """
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": system_content
                    },
                    {
                        "role": "user", 
                        "content": json.dumps({
                            "original_response": original_response,
                            "conversation_history": context_history,
                            "user_message": user_message,
                            "context": context
                        })
                    }
                ]
            )
            
            enhanced_response = response.choices[0].message.content.strip()
            logger.info(f"GPT 응답 개선: '{original_response}' -> '{enhanced_response}'")
            return enhanced_response
            
        except Exception as e:
            logger.error(f"GPT 응답 개선 실패: {str(e)}")
            return original_response
    
    async def process_text_query(self, query_text: str) -> Dict[str, Any]:
        """
        텍스트 쿼리 처리: NLP -> FSM -> RAG -> TTS 파이프라인
        GPT 강화 버전
        """
        try:
            # 로그 추가
            logger.info(f"텍스트 쿼리 처리 시작: '{query_text}'")
            
            # 대화 이력에 사용자 입력 추가
            self._add_to_conversation_history("user", query_text)
            
            # GPT 분석 (비동기로 병렬 처리)
            gpt_analysis_task = None
            if self.openai_api_key:
                gpt_analysis_task = asyncio.create_task(self.gpt_analyze_text(query_text))
            
            # 1. NLP로 의도와 슬롯 추출 (기존 방식)
            nlp_result = extract_intent_and_slots(query_text)
            intent = nlp_result["intent"]
            slots = nlp_result["slots"]
            
            # 로그 추가
            logger.info(f"NLP 결과: 의도={intent}, 슬롯={slots}")
            
            # GPT 분석 결과 가져오기 (완료된 경우)
            gpt_analysis = {}
            if gpt_analysis_task:
                try:
                    gpt_analysis = await asyncio.wait_for(gpt_analysis_task, timeout=1.0)
                    
                    # GPT 분석 결과로 NLP 결과 보강
                    if "intent" in gpt_analysis and gpt_analysis["intent"]:
                        # 전통적 NLP가 greeting/unknown인 경우 GPT 결과 우선 적용
                        if intent in ["greeting", "unknown"] or not intent:
                            intent = gpt_analysis["intent"]
                    
                    # 슬롯 정보 병합 (GPT가 인식한 추가 슬롯 적용)
                    if "slots" in gpt_analysis and isinstance(gpt_analysis["slots"], dict):
                        for key, value in gpt_analysis["slots"].items():
                            # 기존 슬롯에 없거나 값이 없는 경우 GPT 값 사용
                            if key not in slots or not slots.get(key):
                                slots[key] = value
                    
                    logger.info(f"NLP+GPT 통합 결과: 의도={intent}, 슬롯={slots}")
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(f"GPT 분석 적용 실패: {str(e)}")
            
            # 기존 슬롯 정보와 병합
            merged_slots = {**self.current_slots, **slots}
            self.current_slots = merged_slots
            
            # 2. FSM으로 상태 전이 및 기본 응답 생성
            # GPT 강화 FSM 사용 (가능한 경우)
            if self.gpt_fsm and self.openai_api_key:
                try:
                    # GPT 강화 의도 분석 사용
                    gpt_intent_analysis = await self.gpt_fsm.analyze_dialog_intent(query_text)
                    
                    # 감정 및 맥락 고려한 상태 전이
                    next_state = self.gpt_fsm.get_next_state(self.current_state, intent, merged_slots)
                    
                    logger.info(f"GPT FSM 분석: {gpt_intent_analysis}")
                    logger.info(f"상태 전이: {self.current_state} -> {next_state} (GPT 강화)")
                except Exception as e:
                    logger.error(f"GPT FSM 처리 실패, 기본 FSM으로 폴백: {str(e)}")
                    next_state = fsm.get_next_state(self.current_state, intent)
                    logger.info(f"상태 전이: {self.current_state} -> {next_state} (기본)")
            else:
                # 기본 FSM 사용
                next_state = fsm.get_next_state(self.current_state, intent)
                logger.info(f"상태 전이: {self.current_state} -> {next_state} (기본)")
            
            self.current_state = next_state
            
            # 상태별 응답 생성 전략
            # GPT가 제안한 다음 상태가 있으면 적용
            if gpt_analysis and "next_state" in gpt_analysis and gpt_analysis["next_state"]:
                # GPT 제안 상태가 현재와 다르면 로그
                if gpt_analysis["next_state"] != self.current_state:
                    logger.info(f"GPT 제안 상태: {gpt_analysis['next_state']} (현재: {self.current_state})")
                
                # 결제 관련 상태는 GPT 제안 우선 적용
                if gpt_analysis["next_state"] == "payment":
                    self.current_state = "payment"
                    logger.info(f"GPT 제안으로 상태 변경: {self.current_state} -> payment")
            
            # 기본 응답 생성
            base_response = fsm.get_response(self.current_state, merged_slots)
            
            # 3. 상태에 따라 RAG 사용 결정
            use_rag = (
                "menu" in intent or 
                "option" in intent or 
                self.current_state in ["order_taking", "option_select", "order_confirm"] or
                "help" in intent or
                "추천" in query_text
            )
            
            if use_rag:
                # RAG 서비스 초기화 확인
                if not self.rag_service.is_initialized:
                    await self.rag_service.initialize()
                
                # RAG 쿼리 강화 (GPT 기능 활성화된 경우)
                enhanced_query = None
                if self.openai_api_key:
                    try:
                        # 쿼리 객체 생성
                        query_obj = Query(text=query_text, metadata={"intent": intent, "state": self.current_state})
                        
                        # GPT로 쿼리 강화
                        enhanced_query = await GPTQueryEnhancer.enhance_query(query_obj, self.openai_api_key)
                        logger.info(f"GPT 쿼리 강화: {enhanced_query.intent}, 복잡도: {enhanced_query.query_complexity}")
                        
                        # 강화된 쿼리 사용
                        rag_response = await self.rag_service.process_query(enhanced_query.text)
                    except Exception as e:
                        logger.error(f"GPT 쿼리 강화 실패: {str(e)}")
                        # 원본 쿼리로 폴백
                        rag_response = await self.rag_service.process_query(query_text)
                else:
                    # 기본 RAG 사용
                    rag_response = await self.rag_service.process_query(query_text)
                
                # RAG 응답 강화 (GPT 기능 활성화된 경우)
                if self.openai_api_key:
                    try:
                        # GPT로 RAG 응답 강화
                        enhanced_rag_response = await GPTEnhancedRAGResponse.enhance_response(
                            rag_response, self.openai_api_key)
                        
                        # 강화된 RAG 응답 적용
                        rag_text = enhanced_rag_response.generated_text
                        
                        # 추가 인사이트 로깅
                        if enhanced_rag_response.generated_insights:
                            logger.info(f"GPT 추가 인사이트: {enhanced_rag_response.generated_insights}")
                    except Exception as e:
                        logger.error(f"GPT RAG 응답 강화 실패: {str(e)}")
                        rag_text = rag_response.generated_text
                else:
                    rag_text = rag_response.generated_text
                
                # FSM 기본 응답과 RAG 응답 결합 결정
                if self.current_state == "greeting" or "help" in intent:
                    # 인사나 도움 요청은 RAG 응답 우선
                    final_response = rag_text
                elif "menu" in intent or "order" in intent:
                    # 메뉴/주문은 둘 다 포함
                    final_response = f"{base_response} {rag_text}"
                else:
                    # 그 외에는 상황에 따라 결합
                    if base_response in rag_text:
                        final_response = rag_text
                    else:
                        final_response = f"{base_response} {rag_text}"
            else:
                # RAG 없이 FSM 응답만 사용
                final_response = base_response
            
            # 4. GPT로 최종 응답 개선 (활성화된 경우)
            if self.openai_api_key:
                try:
                    # 응답 개선 맥락 구성
                    context = {
                        "current_state": self.current_state,
                        "intent": intent,
                        "emotion": gpt_analysis.get("emotion", "neutral") if gpt_analysis else "neutral"
                    }
                    
                    # GPT로 응답 개선
                    improved_response = await self.gpt_enhance_response(
                        final_response, 
                        context,
                        user_message=query_text,
                        make_conversational=True
                    )
                    final_response = improved_response
                except Exception as e:
                    logger.error(f"GPT 응답 개선 실패: {str(e)}")
            
            # 응답이 비어있거나 짧은 경우 처리
            if not final_response or len(final_response) < 5:
                final_response = "죄송합니다, 다시 말씀해주시겠어요?"
            
            # 대화 이력에 시스템 응답 추가
            self._add_to_conversation_history("system", final_response)
            
            # 최종 응답 로그 추가
            logger.info(f"최종 응답: '{final_response}'")

            # 5. TTS로 음성 합성
            tts_result = await self.tts_service.synthesize(
                final_response,
                play_audio=True  # 오디오 자동 재생 활성화
            )
            
            if not tts_result["success"]:
                return {
                    "success": False,
                    "error": tts_result.get("error", "음성 합성 실패"),
                    "stage": "tts",
                    "response_text": final_response
                }
            
            # 6. WebSocket으로 상태 변경 알림
            try:
                from app.services.connection_manager import manager
                await manager.notify_clients(next_state, final_response, merged_slots)
            except ImportError:
                logger.warning("WebSocket 모듈을 불러올 수 없습니다.")
            except Exception as e:
                logger.error(f"WebSocket 알림 중 오류: {str(e)}")
            
            # 7. 결과 반환
            return {
                "success": True,
                "audio": tts_result["audio"],
                "audio_path": tts_result["audio_path"],
                "audio_base64": tts_result.get("audio_base64", ""),
                "response_text": final_response,
                "current_state": self.current_state,
                "_meta": {
                    "query": query_text,
                    "intent": intent,
                    "slots": merged_slots,
                    "rag_used": use_rag,
                    "gpt_enhanced": self.openai_api_key is not None
                }
            }
        except Exception as e:
            logger.error(f"텍스트 쿼리 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "pipeline",
                "response_text": "처리 중 오류가 발생했습니다."
            }
    
    async def process_audio_query(self, audio_data: BinaryIO) -> Dict[str, Any]:
        """
        음성 쿼리 처리: STT -> NLP -> FSM -> RAG -> TTS 파이프라인
        GPT 강화 버전
        """
        try:
            # 1. 음성을 텍스트로 변환 (STT)
            stt_result = await self.stt_service.transcribe(audio_data)
            
            if not stt_result["success"]:
                return {
                    "success": False,
                    "error": stt_result.get("error", "음성인식 실패"),
                    "stage": "stt"
                }
            
            query_text = stt_result["text"]
            
            # GPT를 사용하여 음성 인식 결과 개선 (활성화된 경우)
            if self.openai_api_key and query_text:
                try:
                    # GPT를 사용하여 음성 인식 결과의 오류 수정 및 개선
                    response = await asyncio.to_thread(
                        self.openai_client.chat.completions.create,
                        model="gpt-3.5-turbo-1106",
                        messages=[
                            {
                                "role": "system", 
                                "content": """
                                당신은 음성 인식 결과를 교정하는 AI입니다. 
                                STT 시스템이 오인식한 단어나 구문을 카페 키오스크 맥락에 맞게 
                                수정해주세요. 다음 정보를 참고하세요:
                                
                                카페 메뉴: 아메리카노, 카페라떼, 카페모카, 바닐라라떼, 
                                카라멜마끼아또, 초코라떼, 그린라떼, 아이스티, 허브티, 레몬에이드
                                
                                관련 단어: 아이스, 핫, 따뜻한, 차가운, 샷추가, 시럽, 휘핑, 레귤러, 
                                라지, 포장, 매장, 카드, 결제
                                
                                원본 인식 결과를 카페 주문 맥락에 맞게 자연스럽게 수정하되, 
                                완전히 다른 내용으로 바꾸지 말고 원문의 의미를 유지하세요.
                                """
                            },
                            {
                                "role": "user", 
                                "content": f"음성 인식 결과: {query_text}"
                            }
                        ]
                    )
                    
                    corrected_text = response.choices[0].message.content.strip()
                    logger.info(f"GPT 음성 인식 개선: '{query_text}' -> '{corrected_text}'")
                    query_text = corrected_text
                except Exception as e:
                    logger.error(f"GPT 음성 인식 개선 실패: {str(e)}")
            
            # 텍스트 쿼리 처리로 전달
            return await self.process_text_query(query_text)
            
        except Exception as e:
            logger.error(f"오디오 쿼리 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "pipeline"
            }
    
    async def reset_conversation(self) -> Dict[str, Any]:
        """대화 상태 초기화 - GPT 강화 버전"""
        try:
            # 부모 클래스의 초기화 메서드 호출
            result = await super().reset_conversation()
            
            # 대화 이력 초기화
            self.conversation_history = []
            
            # GPT 강화된 인사말 생성 (가능한 경우)
            if self.openai_api_key:
                try:
                    response = await asyncio.to_thread(
                        self.openai_client.chat.completions.create,
                        model="gpt-3.5-turbo-1106",
                        messages=[
                            {
                                "role": "system", 
                                "content": """
                                당신은 카페 키오스크 AI입니다. 절대 3문장을 넘지 않고, 간결하고 친절하고 따뜻한 인사말을 생성해주세요.
                                """
                            },
                            {
                                "role": "user", 
                                "content": "카페에 방문한 고객을 위한 인사말을 생성해주세요."
                            }
                        ]
                    )
                    
                    greeting = response.choices[0].message.content.strip()
                    logger.info(f"GPT 인사말 생성: '{greeting}'")
                    
                    # 기본 인사말 대체
                    result["response_text"] = greeting
                    
                    # TTS로 음성 합성
                    tts_result = await self.tts_service.synthesize(greeting)
                    if tts_result["success"]:
                        result["audio_path"] = tts_result["audio_path"]
                        result["audio_base64"] = tts_result.get("audio_base64", "")
                        result["audio"] = tts_result["audio"]
                except Exception as e:
                    logger.error(f"GPT 인사말 생성 실패: {str(e)}")
            
            return result
        except Exception as e:
            logger.error(f"대화 초기화 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "대화 초기화 실패"
            }