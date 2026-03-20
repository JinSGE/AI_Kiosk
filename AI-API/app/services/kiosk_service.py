# app/services/kiosk_service.py
import logging
from typing import Dict, Any, Optional
import os
import tempfile
import uuid
import asyncio
import json
import time  # 시간 측정을 위해 추가

from app.services.stt_service_model import STTService
from app.services.enhanced_pipeline_service import EnhancedPipelineService
from app.services.enhanced_continuous_dialog_service import EnhancedContinuousDialogService
from app.services.tts_service_model import TTSService
from app.services.rag_service import RAGService
from app.services.notification_service import notify_cart_update, notify_order_processed
from app.utils.order_utils import extract_order_info
from app.models.fsm import fsm

logger = logging.getLogger(__name__)

# 전역 인사말 플래그 추가
_greeting_shown = False

class KioskService:
    """통합 키오스크 서비스 클래스"""
    def __init__(
        self,
        stt_service,
        tts_service,
        rag_service,
        openai_api_key=None,
        use_enhanced_services=False,
        pipeline_service=None  # 수정된 부분
    ):
        # 파이프라인 서비스 초기화 로직 개선
        if pipeline_service is not None:
            # 전달받은 파이프라인 서비스 직접 사용
            self.pipeline_service = pipeline_service
        elif use_enhanced_services:
            try:
                # 비동기 생성 메서드 사용
                from app.services.enhanced_pipeline_service import EnhancedPipelineService
                
                # 동기 컨텍스트에서 비동기 메서드 호출을 위한 asyncio.run() 사용
                self.pipeline_service = asyncio.run(
                    EnhancedPipelineService.create(
                        stt_service, 
                        rag_service, 
                        tts_service, 
                        openai_api_key
                    )
                )
                
                logger.info("개선된 파이프라인 서비스 초기화 완료")
            except Exception as e:
                logger.error(f"파이프라인 서비스 초기화 실패: {str(e)}")
                # 기본 파이프라인 서비스로 폴백
                from app.services.pipeline_service import PipelineService
                self.pipeline_service = PipelineService(
                    stt_service, 
                    rag_service, 
                    tts_service
                )
        else:
            # 기본 파이프라인 서비스 사용
            from app.services.pipeline_service import PipelineService
            self.pipeline_service = PipelineService(
                stt_service, 
                rag_service, 
                tts_service
            )
        
        # 기존 초기화 로직 유지
        self.stt_service = stt_service or STTService()
        self.tts_service = tts_service or TTSService()
        self.rag_service = rag_service or RAGService()
        
        # 인사말 플래그 추가
        global _greeting_shown
        self._greeting_shown = _greeting_shown

        # OpenAI API 키 설정
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.use_enhanced_services = use_enhanced_services and bool(self.openai_api_key)
        
        # 개선된 연속 대화 서비스 초기화
        if self.use_enhanced_services:
            from app.services.enhanced_continuous_dialog_service import EnhancedContinuousDialogService
            self.dialog_service = EnhancedContinuousDialogService(
                self,
                self.openai_api_key
            )
            logger.info("개선된 파이프라인 및 대화 서비스 활성화 (GPT 통합)")
        else:
            # 기존 연속 대화 서비스
            from app.services.continuous_dialog_service import GPTEnhancedContinuousDialogService
            self.dialog_service = GPTEnhancedContinuousDialogService(self)
            logger.info("기본 파이프라인 및 대화 서비스 활성화")
        
        # 대화 관리
        self.conversation_id = None
        self.menu_data = self._load_menu_data()
        
        # 초기화 상태 관리 변수 추가
        self._initializing = False
        self._last_init_time = 0
        self._init_cooldown = 5  # 초기화 사이의 최소 시간(초)
        
        logger.info("키오스크 서비스 초기화 완료")
    
    def _load_menu_data(self) -> Dict[str, Any]:
        """메뉴 데이터 로드"""
        try:
            menu_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "menu_data.json")
            if os.path.exists(menu_path):
                with open(menu_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            logger.warning(f"메뉴 데이터 파일을 찾을 수 없습니다: {menu_path}")
            return {}
        except Exception as e:
            logger.error(f"메뉴 데이터 로드 실패: {str(e)}")
            return {}

    async def initialize(self, device_id: str = None, location: str = None, force_reinitialize: bool = False):
        """모든 모델 로드 및 초기화"""
        # 중복 초기화 방지 로직 수정
        current_time = time.time()
        
        # 이미 초기화 중인 경우
        if self._initializing:
            logger.warning("이미 초기화 진행 중입니다. 중복 요청 무시됨")
            return {
                "status": "already_initializing",
                "device_id": self.conversation_id or device_id or f"kiosk-{str(uuid.uuid4())}",
                "models_loaded": True,
                "ready": True,
                "location": location
            }
        
        # 짧은 시간 내 중복 요청 방지 (강제 재초기화가 아닌 경우)
        if not force_reinitialize and self.conversation_id and (current_time - self._last_init_time) < self._init_cooldown:
            logger.warning(f"초기화 요청이 너무 빈번합니다. {self._init_cooldown}초 내 중복 요청 무시됨")
            return {
                "status": "success",
                "device_id": self.conversation_id,
                "models_loaded": True,
                "ready": True,
                "location": location
            }
        
        # 이미 초기화가 완료되었고 대화 ID가 있는 경우 - 강제 재초기화가 아니면 그냥 성공 반환
        if not force_reinitialize and self.conversation_id:
            logger.info(f"이미 초기화 완료됨. 기존 대화 ID 사용: {self.conversation_id}")
            return {
                "status": "success",
                "device_id": self.conversation_id,
                "models_loaded": True,
                "ready": True,
                "location": location
            }
        
        try:
            self._initializing = True
            self._last_init_time = time.time()
        
            logger.info("키오스크 서비스 초기화 중...")
            
            # RAG 서비스 초기화
            await self.rag_service.initialize()
            
            # 파이프라인 초기화
            if hasattr(self.pipeline_service, 'initialize'):
                await self.pipeline_service.initialize()
            
            # 오래된 오디오 파일 정리 (3분 이상된 파일)
            await self.cleanup_old_audio_files(0.0625)
            
            # 대화 초기화
            await self.reset_conversation()
            
            # 새 대화 ID 생성
            self.conversation_id = device_id or f"kiosk-{str(uuid.uuid4())}"
            
            # 성공 메시지 명확하게
            logger.info(f"키오스크 서비스 초기화 완료 (대화 ID: {self.conversation_id})")
            return {
                "status": "success",
                "device_id": self.conversation_id,
                "models_loaded": True,
                "ready": True,
                "location": location
            }
        except Exception as e:
            logger.error(f"키오스크 서비스 초기화 실패: {str(e)}")
            # 실패해도 기본 기능은 동작하도록
            self.conversation_id = device_id or f"kiosk-{str(uuid.uuid4())}"
            return {
                "status": "partial_success",
                "device_id": self.conversation_id,
                "models_loaded": False,
                "ready": True,  # 기본 기능은 사용 가능
                "location": location,
                "error": str(e)
            }
        finally:
            self._initializing = False
        
    async def cleanup_old_audio_files(self, max_age_hours=24):
        """오래된 오디오 파일 정리"""
        try:
            # 하드코딩된 경로 대신 설정에서 경로 가져오기
            audio_dir = self.tts_service.audio_dir
            
            # 디렉토리 존재 여부 확인
            if not os.path.exists(audio_dir):
                logger.warning(f"오디오 디렉토리가 존재하지 않습니다: {audio_dir}")
                return {
                    "success": False,
                    "error": f"오디오 디렉토리가 존재하지 않습니다: {audio_dir}"
                }
                
            current_time = time.time()
            removed_count = 0
            
            for filename in os.listdir(audio_dir):
                if not filename.endswith('.wav'):
                    continue
                    
                file_path = os.path.join(audio_dir, filename)
                file_age = current_time - os.path.getmtime(file_path)
                
                # 파일이 지정된 시간보다 오래된 경우 삭제 (3600초 = 1시간)
                if file_age > (max_age_hours * 3600):
                    os.remove(file_path)
                    removed_count += 1
                    
            logger.info(f"오래된 오디오 파일 {removed_count}개를 정리했습니다.")
            return {
                "success": True, 
                "removed_count": removed_count
            }
        except Exception as e:
            logger.error(f"오디오 파일 정리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def greet_customer(self, force_new=False) -> Dict[str, Any]:
        """
        인사말 생성 및 음성 합성 - 메뉴 확인 후 인사말 재생
        
        Args:
            force_new: 강제로 새 인사말 생성 (결제 후 세션 초기화 시)
        
        Returns:
            인사말 정보
        """
        # 전역 인사말 플래그 사용
        global _greeting_shown

        try:
            # 인사말이 이미 표시된 경우 빈 응답 반환 (강제 플래그가 없는 경우)
            if _greeting_shown and not force_new:
                logger.info("인사말이 이미 표시되었습니다. 인사말 생성 건너뜀")
                return {
                    "text": "",
                    "audio_path": "",
                    "audio_base64": ""
                }
            
            # 대화 ID가 없는 경우 생성
            if not self.conversation_id:
                self.conversation_id = f"kiosk-{str(uuid.uuid4())}"
            
            # 메뉴 데이터 확인 (이미 로드되어 있다고 가정)
            menu_data = self._load_menu_data()
            
            # UI가 준비되었는지 확인하는 로직 (간단하게 시간 지연으로 처리)
            try:
                # WebSocket 연결이 활성화되어 있는지 확인
                from app.services.connection_manager import manager
                if not manager.active_connections:
                    logger.warning("웹소켓 연결이 없습니다. UI 준비 신호를 받을 수 없습니다.")
                    # 짧은 시간 대기 (UI 준비를 위한 최소 시간)
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"WebSocket 연결 확인 실패: {str(e)}")
            
            # 이제 메뉴가 로드되었다고 가정하고 인사말 생성 및 TTS 실행
            if self.use_enhanced_services:
                # EnhancedPipelineService의 reset_conversation 사용 (인사말 포함)
                result = await self.pipeline_service.reset_conversation()

                # 전역 플래그 설정
                _greeting_shown = True
                logger.info("인사말 표시 완료, 전역 플래그 설정됨")

                return {
                    "text": result.get("response_text", "안녕하세요, 카페에 오신 것을 환영합니다."),
                    "audio_path": result.get("audio_path", ""),
                    "audio_base64": result.get("audio_base64", "")
                }
            else:
                # 기존 방식: FSM 사용 인사말 생성
                greeting = fsm.get_response("greeting", {})
                
                # 인사말 음성 생성
                tts_result = await self.tts_service.synthesize(greeting)
                
                if not tts_result["success"]:
                    return {
                        "text": greeting,
                        "audio_path": None
                    }
                
                # 플래그 설정
                _greeting_shown = True
                logger.info("인사말 표시 완료, 전역 플래그 설정됨")
                
                # 간소화된 응답
                return {
                    "text": greeting,
                    "audio_path": tts_result["audio_path"],
                    "audio_base64": tts_result.get("audio_base64", "")
                }
        except Exception as e:
            logger.error(f"인사말 생성 실패: {str(e)}")
            raise RuntimeError(f"인사말 생성 실패: {str(e)}")
    
    # 음성 주문 처리 메서드 개선
    async def process_order_from_audio(self, audio_path: str) -> Dict[str, Any]:
        """오디오 파일에서 주문 처리"""
        try:
            # 대화 ID가 없는 경우 생성
            if not self.conversation_id:
                self.conversation_id = f"kiosk-{str(uuid.uuid4())}"
            
            # 파일 읽기
            with open(audio_path, 'rb') as audio_file:
                # 파이프라인 서비스 호출
                result = await self.pipeline_service.process_audio_query(audio_file)
            
            if not result["success"]:
                return await self._handle_empty_input()
            
            # JSON 형태로 분석 결과 추가
            response_text = result["response_text"]
            slots = result.get("_meta", {}).get("slots", {})
            
            # 장바구니 정보 추출
            cart_items = []
            total_price = 0
            
            # 메뉴와 수량 정보 처리
            if "menu" in slots:
                menu = slots["menu"]
                count = slots.get("count", 1)
                
                # 가격 정보
                price_per_item = 4500  # 기본 가격
                
                # 장바구니 아이템 만들기
                if isinstance(menu, list):
                    for m in menu:
                        cart_items.append({
                            "id": str(uuid.uuid4()),
                            "name": m,
                            "quantity": count,
                            "price": price_per_item,
                            "total": price_per_item * count
                        })
                        total_price += price_per_item * count
                else:
                    cart_items.append({
                        "id": str(uuid.uuid4()),
                        "name": menu,
                        "quantity": count,
                        "price": price_per_item,
                        "total": price_per_item * count
                    })
                    total_price = price_per_item * count
            
            # 결과 강화
            enhanced_result = {
                **result,
                "cart_items": cart_items,
                "total_price": total_price
            }
            
            return enhanced_result
        
        except Exception as e:
            logger.error(f"주문 처리 실패: {str(e)}")
            raise RuntimeError(f"주문 처리 실패: {str(e)}")
    
    async def process_order_from_microphone(self, duration: int = 5) -> Dict[str, Any]:
        """마이크에서 주문 처리"""
        try:
            # 대화 ID가 없는 경우 생성
            if not self.conversation_id:
                self.conversation_id = f"kiosk-{str(uuid.uuid4())}"
            
            logger.info(f"마이크 녹음 시작: {duration}초")
            
            # 마이크에서 STT로 변환
            stt_result = await self.stt_service.record_and_transcribe(duration)
            
            logger.info(f"STT 결과: {stt_result}")
            
            # STT 실패 처리
            if not stt_result["success"]:
                logger.error(f"STT 실패: {stt_result.get('error', 'Unknown error')}")
                return await self._handle_empty_input()
            
            user_text = stt_result["text"]
            logger.info(f"인식된 텍스트: '{user_text}'")
            
            if not user_text:
                logger.warning("빈 텍스트 인식됨")
                return await self._handle_empty_input()
            
            # 파이프라인으로 텍스트 처리
            logger.info(f"텍스트 처리 시작: '{user_text}'")
            result = await self.pipeline_service.process_text_query(user_text)
            
            if not result["success"]:
                logger.error(f"파이프라인 처리 실패: {result.get('error', 'Unknown error')}")
                return await self._handle_empty_response()
            
            logger.info(f"처리 결과: {result['response_text']}")
            
            # 간소화된 응답
            return {
                "response_text": result["response_text"],
                "audio_path": result["audio_path"],
                "audio_base64": result.get("audio_base64", "")
            }
        except Exception as e:
            logger.error(f"마이크 주문 처리 실패: {str(e)}", exc_info=True)
            raise RuntimeError(f"마이크 주문 처리 실패: {str(e)}")
    
    async def process_text_input(self, text: str) -> Dict[str, Any]:
        """텍스트 입력 처리"""
        try:
            # text가 dict인 경우 처리
            if isinstance(text, dict):
                text = text.get('text', '')

            # 빈 문자열 처리
            if not text or not isinstance(text, str):
                return {"error": "유효한 텍스트가 없습니다."}
            
            # 대화 ID가 없는 경우 생성
            if not self.conversation_id:
                self.conversation_id = f"kiosk-{str(uuid.uuid4())}"
            
            if not text.strip():
                return await self._handle_empty_input()
            # 중복 처리 방지 로직 추가 (현재 처리 중인지 확인)
            if hasattr(self.pipeline_service, '_processing') and self.pipeline_service._processing:
                logger.info("이미 처리 중인 입력이 있습니다. 중복 처리 방지.")
                return {
                    "response_text": "잠시만 기다려주세요, 이전 요청을 처리 중입니다.",
                    "audio_path": None
                }
            
            # 파이프라인으로 텍스트 처리
            result = await self.pipeline_service.process_text_query(text)
            
            if not result["success"]:
                return await self._handle_empty_response()
            
            # 간소화된 응답
            return {
                "response_text": result["response_text"],
                "audio_path": result["audio_path"],
                "audio_base64": result.get("audio_base64", "")
            }
        except Exception as e:
            logger.error(f"텍스트 주문 처리 실패: {str(e)}")
            # 예외를 발생시키는 대신 에러 정보를 포함한 응답 반환
            return {
                "success": False,
                "error": str(e),
                "response_text": "주문 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
                "audio_path": None
            }
    
    async def reset_conversation(self, full_reset=False) -> Dict[str, Any]:
        """
        대화 세션 초기화
        
        Args:
            full_reset: 인사말 상태까지 모두 초기화 여부
        
        Returns:
            초기화 결과
        """
        try:
            # 파이프라인 대화 상태 초기화
            result = await self.pipeline_service.reset_conversation()
            
            # 새 대화 ID 생성
            self.conversation_id = f"kiosk-{str(uuid.uuid4())}"
            
            # 완전 초기화가 요청된 경우 인사말 플래그도 초기화
            global _greeting_shown
            if full_reset:
                _greeting_shown = False  # 인사말 표시 플래그 초기화
                logger.info("인사말 플래그 초기화 완료")
            
            if not result.get("success", False):
                return {
                    "success": False,
                    "message": "대화 초기화 실패"
                }
            
            # 인사말 텍스트와 오디오를 제거하여 인사말이 반복되지 않도록 함
            return {
                "success": True,
                "message": "대화가 초기화되었습니다.",
                "audio_path": None,  # 인사말 오디오 경로 제거
                "response_text": ""  # 인사말 텍스트 제거
            }
        except Exception as e:
            logger.error(f"대화 초기화 실패: {str(e)}")
            raise RuntimeError(f"대화 초기화 실패: {str(e)}")
    
    async def start_continuous_dialog(self):
        """연속 대화 세션 시작"""
        return await self.dialog_service.start_dialog_session()
    
    async def stop_continuous_dialog(self):
        """연속 대화 세션 중지"""
        return await self.dialog_service.stop_dialog_session()
    
    async def _handle_empty_input(self) -> Dict[str, Any]:
        """입력이 비어있는 경우 처리"""
        # 대화 ID가 없는 경우 생성
        if not self.conversation_id:
            self.conversation_id = f"kiosk-{str(uuid.uuid4())}"
            
        response_text = "죄송합니다. 말씀을 이해하지 못했어요. 다시 말씀해 주시겠어요?"
        
        # TTS로 응답 음성 생성
        tts_result = await self.tts_service.synthesize(response_text)
        
        if not tts_result["success"]:
            return {
                "response_text": response_text,
                "audio_path": None
            }
        
        # 간소화된 응답
        return {
            "response_text": response_text,
            "audio_path": tts_result["audio_path"],
            "audio_base64": tts_result.get("audio_base64", "")
        }
    
    async def _handle_empty_response(self) -> Dict[str, Any]:
        """응답 생성 실패 처리"""
        # 대화 ID가 없는 경우 생성
        if not self.conversation_id:
            self.conversation_id = f"kiosk-{str(uuid.uuid4())}"
            
        response_text = "주문을 처리하는데 문제가 발생했습니다. 다시 말씀해 주시겠어요?"
        
        # TTS로 응답 음성 생성
        tts_result = await self.tts_service.synthesize(response_text)
        
        if not tts_result["success"]:
            return {
                "response_text": response_text,
                "audio_path": None
            }
        
        # 간소화된 응답
        return {
            "response_text": response_text,
            "audio_path": tts_result["audio_path"],
            "audio_base64": tts_result.get("audio_base64", "")
        }