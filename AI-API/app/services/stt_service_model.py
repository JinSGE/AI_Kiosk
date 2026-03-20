# app/services/stt_service.py
import logging
import os
import tempfile
import asyncio
import time
from typing import Dict, Any, Optional, BinaryIO
import io

from app.models.stt import stt_model
from app.config import settings

logger = logging.getLogger(__name__)

class STTService:
    """STT(Speech-to-Text) 서비스 클래스"""
    
    def __init__(self, model=None):
        """
        STT 서비스 초기화
        
        Args:
            model: 사용할 STT 모델 인스턴스 (기본값: 글로벌 싱글톤 인스턴스)
        """
        self.model = model or stt_model
        logger.info("STT 서비스 초기화 완료")
    
    async def transcribe(self, audio_data) -> Dict[str, Any]:
        """
        오디오 데이터를 텍스트로 변환
        
        Args:
            audio_data: 오디오 데이터 (바이트 또는 파일 객체)
            
        Returns:
            Dict: 변환 결과 (success, text, duration, language 등)
        """
        try:
            # 다양한 입력 형식 처리
            temp_file_path = None
            
            # 바이트 객체인 경우
            if isinstance(audio_data, bytes):
                logger.info(f"바이트 데이터를 임시 파일로 변환 중: {len(audio_data)} 바이트")
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_file_path = temp_file.name
                    temp_file.write(audio_data)
            
            # 파일 객체인 경우
            elif hasattr(audio_data, 'read'):
                audio_content = audio_data.read()
                if isinstance(audio_content, bytes):
                    logger.info(f"파일 객체에서 바이트 데이터 읽는 중: {len(audio_content)} 바이트")
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                        temp_file_path = temp_file.name
                        temp_file.write(audio_content)
            
            # 문자열 경로인 경우 (이미 파일이 존재하는 경우)
            elif isinstance(audio_data, str) and os.path.exists(audio_data):
                logger.info(f"기존 파일 경로 사용: {audio_data}")
                temp_file_path = audio_data
            
            else:
                raise ValueError("지원되지 않는 오디오 데이터 형식입니다.")
            
            logger.info(f"임시 파일 생성: {temp_file_path}")
            
            # 모델 로드 확인
            if not hasattr(self.model, 'model') or (self.model.model is None and self.model.model_type != "speech_recognition"):
                logger.info("STT 모델 로드 중...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.model.load_model)
            
            # 음성 인식 실행 (비동기 처리)
            loop = asyncio.get_event_loop()
            transcribe_result = await loop.run_in_executor(
                None, 
                lambda: self.model.transcribe_audio(temp_file_path)
            )
            
            # 임시 파일 삭제 (경로를 직접 제공한 경우 제외)
            if temp_file_path != audio_data and isinstance(audio_data, (bytes, BinaryIO)):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"임시 파일 삭제 실패: {str(e)}")
            
            # 결과 반환
            logger.info(f"음성 인식 완료: '{transcribe_result.get('text', '')[:50]}...'")
            
            return {
                "success": True,
                "text": transcribe_result.get("text", ""),
                "duration": transcribe_result.get("duration", 0.0),
                "language": transcribe_result.get("language", "ko"),
                "confidence": transcribe_result.get("confidence", 1.0)
            }
        except Exception as e:
            logger.error(f"음성 인식 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "duration": 0.0,
                "language": "ko"
            }
    
    async def record_and_transcribe(self, duration: int = 5) -> Dict[str, Any]:
        """
        마이크에서 음성 녹음 후 텍스트로 변환
        
        Args:
            duration: 녹음 시간(초)
            
        Returns:
            Dict: 변환 결과
        """
        try:
            logger.info(f"마이크 녹음 시작: {duration}초")
            
            # 모델 로드 확인
            if hasattr(self.model, 'model') and self.model.model is None and self.model.model_type != "speech_recognition":
                logger.info("STT 모델 로드 중...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.model.load_model)
            
            # 마이크 녹음 실행 (비동기 처리)
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(
                None, 
                lambda: self.model.record_from_microphone(duration=duration)
            )
            
            # 텍스트 변환 실행
            result = await self.transcribe(audio_path)
            
            # 임시 파일 삭제
            try:
                os.unlink(audio_path)
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {str(e)}")
            
            logger.info(f"마이크 녹음 및 인식 완료: '{result.get('text', '')[:50]}...'")
            
            return result
        except Exception as e:
            logger.error(f"마이크 녹음 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "duration": 0.0,
                "language": "ko"
            }