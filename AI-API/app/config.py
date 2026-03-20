# app/config.py - 노트북 최적화 버전
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os
import torch

class Settings(BaseSettings):
    """애플리케이션 설정 - 노트북 최적화 버전"""
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra='ignore'
    )
    
    # 디버그 모드 - 성능을 위해 False로 설정
    DEBUG: bool = False
    
    # CORS 설정 - 변경 없음
    CORS_ORIGINS: List[str] = json.loads(os.getenv('CORS_ORIGINS', '["http://localhost:3000", "http://localhost:5000"]'))
    
    # 모델 경로 - 변경 없음
    TEXT_MODEL_PATH: str = "EleutherAI/polyglot-ko-1.3b"
    TTS_MODEL_PATH: str = "gtts"
    STT_MODEL_PATH: str = "google"
    
    # 모델 캐시 경로 - 사용자 홈 디렉토리 아래에 캐시 (노트북 환경 권장)
    MODEL_CACHE_DIR: str = os.path.expanduser("~/.cache/polyglot-models")
    
    # 성능 최적화 설정 - 노트북 환경에 최적화
    USE_MODEL_CACHING: bool = True
    LAZY_LOADING: bool = True
    PARALLEL_INIT: bool = False  # 노트북에서는 병렬 초기화 끄기 (메모리 부담)
    
    # 메모리 관리 설정 - 노트북 환경에 최적화
    GPU_MEMORY_FRACTION: float = 0.5  # 더 낮은 GPU 메모리 사용 (0.7 -> 0.5)
    CLEAR_CUDA_CACHE: bool = True
    
    # 서비스 최적화 설정 - 더 적극적인 타임아웃
    REQUEST_TIMEOUT: int = 20  # 더 짧은 타임아웃 (30 -> 20)
    MAX_RETRIES: int = 2  # 재시도 횟수 감소 (3 -> 2)
    BATCH_SIZE: int = 8  # 더 작은 배치 사이즈 (16 -> 8)
    
    # 텍스트 처리 설정 - 더 적은 텍스트 길이
    MAX_TEXT_LENGTH: int = 512  # 최대 길이 감소 (1024 -> 512)
    MAX_RESPONSE_LENGTH: int = 150  # 응답 길이 제한 (새로 추가)
    
    # GPU 설정 - 노트북에 최적화
    USE_GPU: bool = torch.cuda.is_available()
    USE_8BIT_QUANTIZATION: bool = True  # 메모리 사용량 감소를 위해 8비트 양자화 활성화
    GPU_MEMORY_LIMIT: float = 0.7  # 메모리 제한 (0.9 -> 0.7)
    
    # NLP 최적화 설정 (새로 추가)
    NLP_SIMPLIFIED_PATTERNS: bool = True  # 간소화된 패턴 사용
    NLP_USE_STRING_MATCHING: bool = True  # 정규식 대신 문자열 검색 사용
    NLP_MAX_INTENT_PATTERNS: int = 5  # 의도당 최대 패턴 수
    
    # 텍스트 생성 최적화 (새로 추가)
    GEN_TEMPERATURE: float = 0.5  # 낮은 온도 값 (더 결정적인 생성)
    GEN_MAX_NEW_TOKENS: int = 40  # 생성 토큰 수 제한
    GEN_TOP_K: int = 20  # 더 낮은 top_k 값
    GEN_TOP_P: float = 0.75  # 더 낮은 top_p 값
    GEN_REPETITION_PENALTY: float = 1.2  # 낮은 반복 페널티
    GEN_NO_REPEAT_NGRAM_SIZE: int = 2  # ngram 크기 감소 (3 -> 2)
    GEN_EARLY_STOPPING: bool = True  # 조기 종료 활성화
    
    # TTS 설정 - 변경 없음
    TTS_ENGINE: str = "gtts"
    TTS_SAMPLING_RATE: int = 24000
    TTS_DEFAULT_SPEAKER: str = "default"
    TTS_DEFAULT_SPEED: float = 1.0
    
    # TTS 캐싱 (새로 추가)
    TTS_USE_CACHE: bool = True  # TTS 결과 캐싱
    TTS_CACHE_SIZE: int = 100  # 캐시 크기
    
    # STT 최적화 (새로 추가)
    STT_CHUNK_SIZE: int = 1024  # 오디오 청크 크기
    STT_SILENCE_THRESHOLD: int = 300  # 무음 감지 임계값
    STT_SILENCE_DURATION: float = 0.5  # 무음 지속 시간
    
    # 오디오 설정 - 더 짧은 오디오 길이
    MAX_AUDIO_LENGTH_SECONDS: int = 60  # 오디오 길이 제한 (300 -> 60)
    STT_SAMPLING_RATE: int = 16000
    
    # 시스템 프롬프트 - 더 짧은 프롬프트
    KIOSK_SYSTEM_PROMPT: str = "카페 키오스크입니다. 주문을 확인하고 간결하게 응답하세요."
    
    # 경로 설정 - 변경 없음
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 오디오 디렉토리 설정 - 변경 없음
    AUDIO_OUTPUT_DIR: str = os.path.join(BASE_DIR, "audio_output")
    AUDIO_INPUT_DIR: str = os.path.join(BASE_DIR, "audio_input")
    TEMP_DIR: str = os.path.join(BASE_DIR, "temp")
    
    # 로깅 설정 (새로 추가)
    LOG_LEVEL: str = "INFO"  # DEBUG -> INFO로 변경하여 로깅 부하 감소
    DISABLE_DETAILED_LOGGING: bool = True  # 상세 로깅 비활성화
    
    # 캐싱 정책 (새로 추가)
    ENABLE_RESPONSE_CACHING: bool = True  # 응답 캐싱 활성화
    RESPONSE_CACHE_SIZE: int = 20  # 응답 캐시 크기
    
    # 기타 설정
    CORS_ORIGINS_STR: str = "*"
    
    # 노트북 특화 설정 (새로 추가)
    NOTEBOOK_MODE: bool = True  # 노트북 모드 활성화
    LOW_MEMORY_MODE: bool = True  # 저메모리 모드
    
    # 디렉토리 생성
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        os.makedirs(self.AUDIO_OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.AUDIO_INPUT_DIR, exist_ok=True)
        os.makedirs(self.TEMP_DIR, exist_ok=True)
        os.makedirs(self.MODEL_CACHE_DIR, exist_ok=True)
        
        # 노트북 환경 감지 및 자동 설정
        try:
            import IPython
            self.NOTEBOOK_MODE = True
            # 노트북 환경에서는 더 보수적인 설정 적용
            if torch.cuda.is_available():
                gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB 단위
                # GPU 메모리가 4GB 이하면 더 강한 제한 적용
                if gpu_mem <= 4:
                    self.GPU_MEMORY_FRACTION = 0.4
                    self.BATCH_SIZE = 4
                    self.MAX_TEXT_LENGTH = 256
        except ImportError:
            self.NOTEBOOK_MODE = False

# 싱글톤 설정 인스턴스 생성
settings = Settings()

# 환경 변수 접근 도우미 함수
def get_env(key: str, default=None):
    return os.environ.get(key, default)