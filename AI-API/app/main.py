# main.py
from app.services.kiosk_service import KioskService
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from typing import List, Dict, Any
import json
import logging
import os
import sys
import threading
import importlib.util
import time
import asyncio
import uvicorn
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 이벤트 및 로거 설정
model_init_event = threading.Event()
greeting_complete_event = threading.Event()
logger = logging.getLogger(__name__)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# 필요한 디렉토리 생성
os.makedirs(settings.AUDIO_OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.MODEL_CACHE_DIR, exist_ok=True)

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="AI 통합 API", 
    description="STT -> NLP -> FSM -> RAG -> TTS 통합 파이프라인 API",
    debug=settings.DEBUG, 
    version="1.0.0"
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# WebSocket 관리자는 connection_manager로 분리됨

# 서비스 매니저 싱글톤 구현
class ServiceManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.services = {}
            self._initialized = True
    
    def register(self, name: str, service: Any) -> None:
        """서비스 등록"""
        self.services[name] = service
    
    def get(self, name: str) -> Any:
        """서비스 조회"""
        return self.services.get(name)
    
    async def initialize_all(self) -> None:
        """모든 서비스 초기화"""
        # 초기화 필요한 서비스만 선택적으로 초기화
        if "rag_service" in self.services:
            await self.services["rag_service"].initialize()

# 싱글톤 서비스 매니저 인스턴스
service_manager = ServiceManager()

# notify_clients 로직은 websocket_router에 있는 유틸리티 함수로 통합됨

vad_session_started = False

# 애플리케이션 시작 시 실행되는 이벤트 핸들러
@app.on_event("startup")
async def startup_event():
    # 환경 변수에서 OpenAI API 키 읽기
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    
    # API 키 유효성 확인
    use_enhanced_services = bool(openai_api_key)
    
    # 서비스 초기화
    try:
        from app.services.pipeline_service import PipelineService
        from app.services.kiosk_service import KioskService
        from app.services.rag_service import RAGService
        from app.services.stt_service_model import STTService
        from app.services.tts_service_model import TTSService
        
        # 공통 필수 서비스 초기화
        stt_service = STTService()
        tts_service = TTSService()
        rag_service = RAGService()
        
        # 서비스 매니저에 등록
        service_manager.register("stt_service", stt_service)
        service_manager.register("tts_service", tts_service)
        service_manager.register("rag_service", rag_service)
        
        # OpenAI 클라이언트 초기화 시도
        if use_enhanced_services:
            import openai
            try:
                openai_client = openai.OpenAI(api_key=openai_api_key)
                service_manager.register("openai_client", openai_client)
                
                # 개선된 파이프라인 서비스 비동기 생성
                from app.services.enhanced_pipeline_service import EnhancedPipelineService
                pipeline_service = await EnhancedPipelineService.create(
                    stt_service,
                    rag_service,
                    tts_service,
                    openai_api_key
                )
                service_manager.register("pipeline_service", pipeline_service)
                
                logging.info("개선된 서비스 활성화 (GPT 통합)")
            except Exception as e:
                logging.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
                use_enhanced_services = False
        
        # 기본 서비스 사용 (개선된 서비스 초기화 실패 시)
        if not use_enhanced_services:
            pipeline_service = PipelineService(stt_service, rag_service, tts_service)
            service_manager.register("pipeline_service", pipeline_service)
            logging.info("기본 서비스 활성화")
        
        # 키오스크 서비스 초기화
        kiosk_service = KioskService(
            stt_service,
            tts_service,
            rag_service,
            openai_api_key,
            use_enhanced_services,
            pipeline_service=pipeline_service  # 기존 인스턴스 전달
        )
        service_manager.register("kiosk_service", kiosk_service)
        
        # VAD 모듈 초기화
        try:
            import webrtcvad
            logger.info("webrtcvad 모듈 로드 성공")
        except ImportError:
            logger.warning("webrtcvad 모듈을 찾을 수 없습니다. VAD 기능이 제한될 수 있습니다.")
            try:
                # 자동 설치 시도
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "webrtcvad"])
                import webrtcvad
                logger.info("webrtcvad 모듈 설치 및 로드 성공")
            except Exception as vad_install_error:
                logger.error(f"webrtcvad 모듈 설치 실패: {str(vad_install_error)}")
        
        # 비동기 서비스 초기화 시작
        asyncio.create_task(service_manager.initialize_all())
        
        # FSM과 WebSocket 서비스 초기화
        try:
            # FSM 모델 초기화
            from app.models.fsm import fsm as fsm_instance
            
            # 서비스 매니저에 등록
            service_manager.register("fsm_instance", fsm_instance)
            from app.services.connection_manager import manager
            service_manager.register("active_connections", manager.active_connections)
            
            logger.info("FSM 및 WebSocket 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"FSM/WebSocket 초기화 실패: {str(e)}")
        
        # 서버 시작 시 자동으로 VAD 세션 시작 (수정)
        try:
            global vad_session_started
            # 이미 시작된 경우 중복 실행 방지
            if vad_session_started:
                logger.info("VAD 세션이 이미 실행 중입니다.")
                return
                
            # 비동기 초기화 작업 완료 대기
            await asyncio.sleep(2)
            
            # 대화 서비스 초기화 및 세션 시작
            from app.services.enhanced_continuous_dialog_service import EnhancedContinuousDialogService
            
            # 로그 메시지 추가
            logger.info("서버 시작 시 자동 VAD 세션 초기화 중...")
            
            # 대화 서비스가 없는 경우 초기화
            if not hasattr(kiosk_service, 'dialog_service') or kiosk_service.dialog_service is None:
                kiosk_service.dialog_service = EnhancedContinuousDialogService(
                    kiosk_service=kiosk_service,
                    openai_api_key=kiosk_service.openai_api_key
                )
                logger.info("대화 서비스 초기화 완료")
            
            # 메뉴 데이터 먼저 전송 (새로 추가)
            try:
                # 메뉴 데이터 경로
                menu_path = os.path.join(os.path.dirname(__file__), "data", "menu_data.json")
                menu_data = {}
                
                # 메뉴 데이터 로드
                if os.path.exists(menu_path):
                    with open(menu_path, 'r', encoding='utf-8') as f:
                        menu_data = json.load(f)
                
                # 웹소켓을 통해 메뉴 데이터 전송
                from app.services.notification_service import notify_menu_loading
                asyncio.create_task(notify_menu_loading(menu_data))  # menu_data 직접 전달
                
                logger.info("메뉴 데이터 전송 요청 완료")
                
                # 메뉴 로딩을 위한 짧은 대기
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"메뉴 데이터 전송 실패: {str(e)}")
            
            # 콜백 함수 정의
            async def on_session_start():
                logger.info("자동 대화 세션이 시작되었습니다.")
                
            async def on_session_end(result):
                logger.info(f"대화 세션이 종료되었습니다. 결과: {result.get('success', False)}")
                
            async def on_speech_detected():
                logger.info("음성이 감지되었습니다.")
                
            async def on_response_start(text):
                pass
                
            async def on_response_end(audio_path):
                logger.info(f"응답 종료: {audio_path}")
            
            # 비동기 태스크로 세션 시작 (메인 스레드 차단 방지)
            asyncio.create_task(kiosk_service.dialog_service.start_dialog_session(
                on_session_start=on_session_start,
                on_session_end=on_session_end,
                on_speech_detected=on_speech_detected,
                on_response_start=on_response_start,
                on_response_end=on_response_end
            ))
            logger.info("VAD 세션 자동 시작 요청 완료")
            
        except Exception as e:
            logger.error(f"자동 VAD 세션 시작 실패: {str(e)}", exc_info=True)
        
        logging.info("서비스 초기화 완료")
        
    except Exception as e:
        logging.error(f"서비스 초기화 중 오류 발생: {str(e)}")

# 의존성 주입 함수들
def get_kiosk_service() -> KioskService:
    return service_manager.get("kiosk_service")

def get_pipeline_service():
    return service_manager.get("pipeline_service")

def get_rag_service():
    return service_manager.get("rag_service")

def get_stt_service():
    return service_manager.get("stt_service")

def get_tts_service():
    return service_manager.get("tts_service")

def get_fsm_instance():
    return service_manager.get("fsm_instance")

# get_active_connections() 의존성 함수는 connection_manager로 이전됨

# 라우터 등록
def register_routers():
    # 기존 라우터 등록
    from app.routers.rag_router import router as rag_router
    from app.routers.stt_router import router as stt_router
    from app.routers.tts_router import router as tts_router
    from app.routers.pipeline_router import router as pipeline_router
    from app.routers.kiosk_router import router as kiosk_router
    from app.routers.menu_router import router as menu_router
    from app.routers.order_router import router as order_router
    
    # FSM 상태 관리 및 WebSocket 라우터 추가
    from app.routers.fsm_router import router as fsm_router
    from app.routers.websocket_router import router as websocket_router

    # 라우터 등록 로직
    routers_to_check = {
        "RAG": rag_router,
        "STT": stt_router,
        "TTS": tts_router,
        "Pipeline": pipeline_router,
        "Kiosk": kiosk_router,
        "FSM": fsm_router,
        "WebSocket": websocket_router
    }
    
    for name, router in routers_to_check.items():
        if router is None:
            logger.warning(f"{name} 라우터가 None입니다. 해당 기능은 비활성화됩니다.")
            continue
    
    # 각 라우터 등록
    if 'rag_router' in locals():
        app.include_router(rag_router, prefix="/api/rag", tags=["rag"])
    
    if 'stt_router' in locals():
        app.include_router(stt_router, prefix="/api/stt", tags=["stt"])
    
    if 'tts_router' in locals():
        app.include_router(tts_router, prefix="/api/tts", tags=["tts"])
    
    if 'pipeline_router' in locals():
        app.include_router(pipeline_router, prefix="/api/pipeline", tags=["pipeline"])
    
    if 'menu_router' in locals():
        app.include_router(menu_router, prefix="/api/v1/menu", tags=["menu"])
    
    if 'order_router' in locals():
        app.include_router(order_router, prefix="/api/v1/orders", tags=["orders"])

    if 'kiosk_router' in locals():
        app.include_router(
            kiosk_router, 
            prefix="/api/v1/kiosk",
            tags=["kiosk"]
        )
    
    # FSM 및 WebSocket 라우터 등록
    if 'fsm_router' in locals():
        app.include_router(fsm_router, prefix="/fsm", tags=["fsm"])
    
    if 'websocket_router' in locals():
        app.include_router(websocket_router, tags=["websocket"])
    
    logger.info("라우터 등록 완료")

# 모델 초기화 함수
def initialize_models():
    """STT, TTS, NLP, RAG, FSM 모델 초기화 및 설치"""
    try:
        logger.info("모든 모델 초기화 중...")
        
        # STT 모델 초기화
        try:
            from app.models.stt import stt_model
            result = stt_model.load_model()
            stt_model.is_ready = True
            logger.info(f"STT 모델 초기화 완료 (is_ready={stt_model.is_ready})")
        except Exception as e:
            logger.error(f"STT 모델 초기화 실패: {str(e)}")
        
        # TTS 모델 초기화
        try:
            from app.models.tts import tts_model
            tts_model.load_model()
            logger.info("TTS 모델 초기화 완료")
        except Exception as e:
            logger.error(f"TTS 모델 초기화 실패: {str(e)}")
            
        # NLP 및 FSM 모델 초기화
        try:
            from app.services.nlp_processor import extract_intent_and_slots
            test_result = extract_intent_and_slots("테스트 문장입니다")
            logger.info("NLP 처리기 초기화 완료")
            
            from app.models.fsm import fsm
            logger.info("FSM 초기화 완료")
        except Exception as e:
            logger.error(f"NLP/FSM 초기화 실패: {str(e)}")
        
        # RAG 서비스 초기화
        try:
            from app.services.rag_service import rag_service
            asyncio.run(rag_service.initialize())
            logger.info("RAG 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"RAG 서비스 초기화 실패: {str(e)}")
            
        # 필요한 패키지 자동 설치
        try:
            import importlib
            
            packages_to_install = []
            
            # 필요한 패키지 확인 및 설치 리스트 추가
            if importlib.util.find_spec("whisper") is None:
                packages_to_install.append("openai-whisper")
            
            if importlib.util.find_spec("pyaudio") is None:
                packages_to_install.append("pyaudio")
            
            if importlib.util.find_spec("speech_recognition") is None:
                packages_to_install.append("SpeechRecognition")
            
            if importlib.util.find_spec("gtts") is None:
                packages_to_install.append("gtts")
                
            if importlib.util.find_spec("pydub") is None:
                packages_to_install.append("pydub")
            
            # 필요한 패키지 설치
            if packages_to_install:
                logger.info(f"필요한 패키지 설치 중: {', '.join(packages_to_install)}")
                import subprocess
                for package in packages_to_install:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                logger.info("패키지 설치 완료")
        except Exception as e:
            logger.error(f"패키지 설치 중 오류 발생: {str(e)}")
        
        # 모든 초기화가 완료되면 이벤트 설정
        model_init_event.set()
        logger.info("모델 초기화 완료, 초기화 이벤트 설정")
    except Exception as e:
        logger.error(f"모델 초기화 중 오류 발생: {str(e)}")
        model_init_event.set()

# 모델 상태 확인 엔드포인트
@app.get("/models/status")
async def model_status():
    """모델 상태 확인"""
    try:
        # 모델 상태 정보 딕셔너리
        status = {
            "stt": {"loaded": False, "type": None},
            "tts": {"loaded": False, "type": None},
            "nlp": {"loaded": False},
            "fsm": {"loaded": False},
            "rag": {"loaded": False}
        }
        
        # STT 모델 상태 확인
        try:
            from app.models.stt import stt_model
            status["stt"] = {
                "loaded": hasattr(stt_model, 'is_ready') and stt_model.is_ready,
                "type": stt_model.model_type if hasattr(stt_model, 'model_type') else None,
                "device": stt_model.device if hasattr(stt_model, 'device') else None
            }
        except Exception as e:
            logger.error(f"STT 모델 상태 확인 실패: {str(e)}")
        
        # TTS 모델 상태 확인
        try:
            from app.models.tts import tts_model
            status["tts"] = {
                "loaded": hasattr(tts_model, 'is_ready') and tts_model.is_ready,
                "type": getattr(tts_model, '_tts_engine', None),
                "speakers": tts_model.get_available_speakers() if hasattr(tts_model, 'get_available_speakers') else []
            }
        except Exception as e:
            logger.error(f"TTS 모델 상태 확인 실패: {str(e)}")
            
        # NLP 모델 상태 확인
        try:
            from app.services.nlp_processor import extract_intent_and_slots
            test_result = extract_intent_and_slots("테스트")
            status["nlp"] = {
                "loaded": True,
                "intent_count": len(test_result.get("intent", "").strip()) > 0
            }
        except Exception as e:
            logger.error(f"NLP 모델 상태 확인 실패: {str(e)}")
            
        # FSM 상태 확인
        try:
            from app.models.fsm import fsm
            status["fsm"] = {
                "loaded": hasattr(fsm, 'current_state'),
                "current_state": fsm.current_state if hasattr(fsm, 'current_state') else None
            }
        except Exception as e:
            logger.error(f"FSM 상태 확인 실패: {str(e)}")
            
        # RAG 상태 확인
        try:
            from app.services.rag_service import rag_service
            status["rag"] = {
                "loaded": rag_service.is_initialized,
                "doc_count": rag_service.get_document_count() if hasattr(rag_service, 'get_document_count') else 0
            }
        except Exception as e:
            logger.error(f"RAG 상태 확인 실패: {str(e)}")
        
        return status
        
    except Exception as e:
        logger.error(f"모델 상태 확인 중 오류 발생: {str(e)}")
        return {"error": str(e)}

# FSM 상태 관련 엔드포인트 추가
@app.get("/fsm/status")
async def fsm_status():
    """FSM 상태 확인"""
    try:
        from app.models.fsm import fsm
        return {
            "current_state": fsm.current_state,
            "is_initialized": hasattr(fsm, 'current_state')
        }
    except Exception as e:
        logger.error(f"FSM 상태 확인 중 오류 발생: {str(e)}")
        return {"error": str(e)}

# 정적 파일 서빙 설정 (public 디렉토리)
if os.path.exists("public"):
    app.mount("/static", StaticFiles(directory="public"), name="static")
    logger.info("정적 파일 서빙 설정 완료 (public)")
elif os.path.exists("frontend/build"):
    app.mount("/static", StaticFiles(directory="frontend/build/static"), name="static")
    logger.info("정적 파일 서빙 설정 완료 (frontend/build)")

# 라우터 등록 실행
register_routers()

# 루트 엔드포인트
@app.get("/")
async def root():
    """API 루트 정보 제공"""
    try:
        routes = [f"{route.path} [{', '.join(route.methods)}]" for route in app.routes if hasattr(route, 'methods')]
    except:
        routes = [f"{route.path}" for route in app.routes]
        
    # 프론트엔드 빌드 확인 및 반환
    if os.path.exists("frontend/build/index.html"):
        return FileResponse("frontend/build/index.html")
    
    return {
        "message": "STT -> NLP -> FSM -> RAG -> TTS 통합 파이프라인 API에 오신 것을 환영합니다.",
        "routes": routes,
        "version": "1.0.0",
        "docs_url": "/docs"
    }

# 상태 확인 엔드포인트
@app.get("/api/v1/health")
async def health():
    """서비스 건강 상태 확인"""
    return {"status": "ok"}

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    import sys
    import fastapi
    
    # 서버 실행 전 환경 정보 출력
    print("Python 버전:", sys.version)
    print("FastAPI 버전:", fastapi.__version__)
    print("Uvicorn 버전:", uvicorn.__version__)
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True, log_level="info", access_log=False)