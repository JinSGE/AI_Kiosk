import os
import base64
import logging
import asyncio
import inspect
from typing import Dict, Any, Optional, Union, Tuple
import uuid
from datetime import datetime

from app.models.tts import tts_model
from app.config import settings
from app.services.audio_device import audio_device_service

logger = logging.getLogger(__name__)

class TTSService:
    """TTS 서비스 클래스"""
    
    def __init__(self, model=None):
        """TTS 서비스 초기화"""
        self.model = model or tts_model
        
        # 오디오 저장 디렉토리 설정 및 생성
        self.audio_dir = settings.AUDIO_OUTPUT_DIR
        os.makedirs(self.audio_dir, exist_ok=True)
        
        logger.info(f"오디오 출력 디렉토리 설정: {self.audio_dir}")
    
    async def synthesize(
    self,
    text: str,
    speed: float = 1.2,
    pitch_adjustment: float = 0.0,
    energy_adjustment: float = 1.0,
    output_format: str = "wav",
    play_audio: bool = True  # 추가된 매개변수
    ) -> Dict[str, Any]:
        """
        텍스트를 음성으로 변환
        
        Args:
            text: 변환할 텍스트
            speed: 음성 속도
            pitch_adjustment: 피치 조정
            energy_adjustment: 에너지 조정
            output_format: 출력 포맷
            play_audio: 오디오 자동 재생 여부
            
        Returns:
            음성 합성 결과
        """
        try:
            # 모델 준비 확인
            if not hasattr(self.model, 'is_ready') or not self.model.is_ready:
                logger.info("TTS 모델 로드 중...")
                await self._load_model()
            
            # 파일명 생성 
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{uuid.uuid4().hex[:8]}.{output_format}"
            output_path = os.path.join(self.audio_dir, filename)
            
            # 음성 생성 메서드 호출을 위한 키워드 인자 준비
            synthesis_kwargs = {
                'text': text,
                'save_path': output_path
            }
            
            # 선택적 인자 처리 
            # speed, pitch_adjustment, energy_adjustment 등 
            # 모델의 generate_speech 메서드 시그니처에 맞춰 동적으로 전달
            try:
                # 비동기/동기 메서드 처리
                generate_method = self.model.generate_speech
                
                # 비동기 메서드인 경우
                if asyncio.iscoroutinefunction(generate_method):
                    audio_result = await generate_method(**synthesis_kwargs)
                else:
                    # 동기 메서드
                    audio_result = generate_method(**synthesis_kwargs)
                
                # 결과 언패킹 (다양한 반환 형식 대응)
                audio = audio_result[0] if isinstance(audio_result, tuple) else audio_result
                sample_rate = audio_result[1] if isinstance(audio_result, tuple) else 44100
            
            except TypeError:
                # 저장 경로 인자 없이 호출 시도
                if asyncio.iscoroutinefunction(self.model.generate_speech):
                    audio_result = await self.model.generate_speech(text)
                else:
                    audio_result = self.model.generate_speech(text)
                
                # 결과 언패킹
                audio = audio_result[0] if isinstance(audio_result, tuple) else audio_result
                sample_rate = audio_result[1] if isinstance(audio_result, tuple) else 44100
                
                # 수동으로 파일 저장
                from scipy.io import wavfile
                wavfile.write(output_path, sample_rate, audio)
            
            # 오디오 파일 읽기
            with open(output_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            
            # base64 인코딩
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            
            # 오디오 재생 (play_audio가 True인 경우)
            if play_audio:
                try:
                    # 오디오 재생은 별도 스레드에서 처리
                    asyncio.create_task(self._play_audio(output_path))
                except Exception as e:
                    logger.warning(f"오디오 재생 실패: {str(e)}")
            
            # 결과 반환
            return {
                "success": True,
                "audio": audio_bytes,
                "audio_path": output_path,
                "audio_base64": audio_base64,
                "sample_rate": sample_rate,
                "duration": len(audio) / sample_rate,
                "format": output_format
            }
            
        except Exception as e:
            logger.error(f"음성 합성 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_model(self):
        """
        모델 로드를 위한 안전한 비동기 메서드
        """
        # 모델의 load_model 메서드가 비동기인지 동기인지 확인
        if asyncio.iscoroutinefunction(self.model.load_model):
            await self.model.load_model()
        else:
            self.model.load_model()
        
        # is_ready 플래그 설정
        self.model.is_ready = True
    
    async def _play_audio(self, audio_path: str):
        """
        오디오 재생을 위한 비동기 메서드 (내부 사용)
        
        :param audio_path: 재생할 오디오 파일 경로
        """
        try:
            audio_device_service.play_audio(audio_path)
            logger.info(f"오디오 재생 시작: {audio_path}")
        except Exception as e:
            logger.warning(f"오디오 재생 실패: {str(e)}")
    
    # 새로 추가된 public play_audio 메서드
    async def play_audio(self, audio_path: str):
        """
        오디오 파일 재생을 위한 public 메서드
        
        :param audio_path: 재생할 오디오 파일 경로
        """
        return await self._play_audio(audio_path)
    
    async def get_available_speakers(self) -> Dict[str, Any]:
        """사용 가능한 화자 목록 반환"""
        try:
            # 모델 준비 확인
            if not hasattr(self.model, 'is_ready') or not self.model.is_ready:
                await self._load_model()
            
            # 화자 목록 가져오기 (존재하는 경우)
            speakers_method = getattr(self.model, 'get_available_speakers', None)
            
            if asyncio.iscoroutinefunction(speakers_method):
                speakers = await speakers_method()
            elif speakers_method:
                speakers = speakers_method()
            else:
                speakers = [{"id": 0, "name": "기본 화자", "language": "ko"}]
            
            return {
                "success": True,
                "speakers": speakers
            }
        except Exception as e:
            logger.error(f"화자 목록 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "speakers": [{"id": 0, "name": "기본 화자", "language": "ko"}]
            }
    
    async def get_model_info(self) -> Dict[str, Any]:
        """TTS 모델 정보 반환"""
        try:
            # 모델 준비 확인
            if not hasattr(self.model, 'is_ready') or not self.model.is_ready:
                await self._load_model()
            
            # 모델 정보 구성
            info = {
                "engine": "MB-iSTFT-VITS",
                "device": getattr(self.model, 'device', 'Unknown'),
                "is_ready": hasattr(self.model, 'is_ready') and self.model.is_ready,
                "model_path": getattr(settings, 'TTS_MODEL_PATH', 'Unknown'),
                "sampling_rate": getattr(settings, 'TTS_SAMPLING_RATE', 'Unknown'),
                "audio_output_dir": self.audio_dir
            }
            
            # 화자 정보 추가 (존재하는 경우)
            speakers_method = getattr(self.model, 'get_available_speakers', None)
            
            if asyncio.iscoroutinefunction(speakers_method):
                info["available_speakers"] = await speakers_method()
            elif speakers_method:
                info["available_speakers"] = speakers_method()
            
            return {
                "success": True,
                "info": info
            }
        except Exception as e:
            logger.error(f"모델 정보 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "info": {
                    "engine": "MB-iSTFT-VITS",
                    "is_ready": False
                }
            }