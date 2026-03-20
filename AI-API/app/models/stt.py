import os
import json
import logging
import asyncio
import tempfile
import subprocess
import sys
import wave

import torch
import librosa
import numpy as np
import openai

from typing import Dict, List, Optional, Union, Tuple, Any

from app.config import settings

logger = logging.getLogger(__name__)

_last_audio_md5 = None
_last_transcribe_result = None
_last_transcribe_time = 0.0

class GPTAudioContextualizer:
    """GPT를 활용한 음성 인식 컨텍스트 개선"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    async def enhance_transcription(
        self, 
        transcribed_text: str, 
        audio_context: Dict[str, Any]
    ) -> str:
        """
        음성 인식 결과를 주변 컨텍스트로 개선
        """
        try:
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        음성 인식 결과를 주변 컨텍스트로 보정하고 
                        가장 가능성 높은 텍스트를 제안해.
                        """
                    },
                    {
                        "role": "user", 
                        "content": json.dumps({
                            "transcription": transcribed_text,
                            "context": audio_context
                        })
                    }
                ]
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"음성 인식 개선 실패: {str(e)}")
            return transcribed_text
        
class STTModel:
    """Speech-to-Text 모델 래퍼 클래스 - Google Speech Recognition 사용"""
    
    def __init__(self):
        # CUDA 사용 가능성 확인
        cuda_available = torch.cuda.is_available()
        logger.info(f"CUDA 사용 가능 여부: {cuda_available}")
        self.is_ready = False  # 초기화 플래그 추가
        # GPU 설정
        if cuda_available and settings.USE_GPU:
            try:
                torch.cuda.empty_cache()  # GPU 메모리 캐시 초기화
                self.device = "cuda"
                logger.info(f"CUDA 디바이스 이름: {torch.cuda.get_device_name(0)}")
            except Exception as e:
                logger.warning(f"CUDA 초기화 실패: {str(e)}. CPU로 폴백됩니다.")
                self.device = "cpu"
        else:
            self.device = "cpu"
        
        self.model = None
        self.processor = None
        self.model_type = "speech_recognition"  # Google Speech Recognition 사용
        logger.info(f"STT 모델 초기화 중: Google Speech Recognition (device: {self.device})")
        
    def load_model(self):
        """모델과 프로세서 로드"""
        try:
            # SpeechRecognition과 PyAudio 패키지 확인 및 설치
            try:
                import speech_recognition as sr
                self.is_ready = True  # 초기화 성공 시 플래그 설정
                logger.info("Google Speech Recognition 설정 완료")
                return True
            except ImportError:
                logger.info("speech_recognition 설치 중...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "SpeechRecognition"]
                )
                import speech_recognition as sr
            
            try:
                import pyaudio
            except ImportError:
                logger.info("PyAudio 설치 중...")
                if sys.platform == 'win32':
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "pyaudio"]
                    )
                else:
                    # Linux나 macOS에서는 시스템 라이브러리 설치 필요 메시지
                    logger.warning("PyAudio 설치에는 시스템 라이브러리가 필요할 수 있습니다.")
                    logger.warning("Linux: sudo apt-get install python3-pyaudio")
                    logger.warning("macOS: brew install portaudio && pip install pyaudio")
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "pyaudio"]
                    )
                import pyaudio
            
            # pydub 설치 확인
            try:
                from pydub import AudioSegment
            except ImportError:
                logger.info("pydub 설치 중...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "pydub"]
                )
            
            self.model_type = "speech_recognition"
            logger.info("Google Speech Recognition 설정 완료")
            return True
        
        except Exception as e:
            logger.error(f"STT 모델 로드 실패: {str(e)}")
            self.is_ready = False
            raise RuntimeError(f"STT 모델 로드 실패: {str(e)}")
    
    def record_from_microphone(self, duration=5, sample_rate=16000):
        """
        마이크에서 오디오를 녹음하여 임시 파일로 저장하고 파일 경로를 반환합니다.
        
        Args:
            duration: 녹음 시간(초)
            sample_rate: 샘플링 레이트
            
        Returns:
            임시 오디오 파일 경로
        """
        try:
            # SpeechRecognition 설치 확인 및 설치
            try:
                import speech_recognition as sr
            except ImportError:
                logger.info("speech_recognition 설치 중...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "SpeechRecognition"]
                )
                import speech_recognition as sr
            
            # PyAudio 설치 확인 및 설치 (SpeechRecognition 마이크 입력에 필요)
            try:
                import pyaudio
            except ImportError:
                logger.info("PyAudio 설치 중...")
                if sys.platform == 'win32':
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "pyaudio"]
                    )
                else:
                    # Linux나 macOS에서는 시스템 라이브러리 설치 필요 메시지
                    logger.warning("PyAudio 설치에는 시스템 라이브러리가 필요할 수 있습니다.")
                    logger.warning("Linux: sudo apt-get install python3-pyaudio")
                    logger.warning("macOS: brew install portaudio && pip install pyaudio")
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "pyaudio"]
                    )
                import pyaudio
            
            # 임시 파일 생성
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_file.close()
            temp_file_path = temp_file.name
            
            # 녹음 객체 생성
            recognizer = sr.Recognizer()
            
            logger.info(f"마이크 녹음 시작 ({duration}초)...")
            
            with sr.Microphone() as source:
                # 배경 소음 조정
                recognizer.adjust_for_ambient_noise(source)
                
                # 녹음
                audio_data = recognizer.listen(source, timeout=duration)
                
                # 오디오 데이터를 WAV 파일로 저장
                with open(temp_file_path, "wb") as f:
                    f.write(audio_data.get_wav_data())
                
                logger.info(f"녹음 완료, 파일 저장됨: {temp_file_path}")
                
                return temp_file_path
                
        except Exception as e:
            logger.error(f"마이크 녹음 실패: {str(e)}")
            raise RuntimeError(f"마이크 녹음 실패: {str(e)}")
    
    def transcribe_from_microphone(self, duration=5):
        """
        마이크에서 음성을 녹음하고 텍스트로 변환합니다.
        
        Args:
            duration: 녹음 시간(초)
            
        Returns:
            Dict: 변환 결과
        """
        try:
            # 마이크 녹음
            audio_path = self.record_from_microphone(duration=duration)
            
            # 녹음된 오디오를 텍스트로 변환
            result = self.transcribe_audio(audio_path)
            
            # 임시 파일 정리
            try:
                os.unlink(audio_path)
            except Exception:
                pass
                
            return result
            
        except Exception as e:
            logger.error(f"마이크 음성 인식 실패: {str(e)}")
            raise RuntimeError(f"마이크 음성 인식 실패: {str(e)}")
    
    def transcribe_audio(
        self, 
        audio_path: str,
        return_timestamps: bool = False
    ) -> Dict:
        """오디오 파일을 텍스트로 변환하는 함수"""
        # 직접 Google Speech API 사용
        return self.transcribe_audio_fallback(audio_path)
    
    def transcribe_audio_fallback(self, audio_path: str) -> Dict:
        """SpeechRecognition을 사용한 대체 음성 인식 메서드"""
        global _last_audio_md5, _last_transcribe_result, _last_transcribe_time
        
        try:
            import speech_recognition as sr
        except ImportError:
            logger.info("speech_recognition 설치 중...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "SpeechRecognition"])
            import speech_recognition as sr
        
        logger.info(f"SpeechRecognition 사용 중: {audio_path}")
        
        try:
            # 오디오 파일 길이 계산
            try:
                with wave.open(audio_path, 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration = frames / float(rate)
            except Exception:
                # WAV가 아닌 경우 librosa 사용
                try:
                    audio_data, sample_rate = librosa.load(audio_path)
                    duration = len(audio_data) / sample_rate
                except Exception:
                    duration = 0.0
            
            # 오디오 파일의 확장자 확인
            file_ext = os.path.splitext(audio_path)[1].lower()
            
            # 만약 wav 파일이 아니라면 변환 시도
            temp_wav_file = None
            if file_ext != '.wav':
                import tempfile
                from pydub import AudioSegment
                
                temp_wav_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
                logger.info(f"{file_ext} 파일을 WAV로 변환: {temp_wav_file}")
                
                try:
                    # pydub을 사용한 변환 시도
                    AudioSegment.from_file(audio_path).export(temp_wav_file, format="wav")
                    audio_path = temp_wav_file
                except Exception as conv_error:
                    logger.error(f"오디오 변환 실패: {str(conv_error)}")
                    # 변환 실패 시 원본 파일 계속 사용
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
            
            # Google Speech Recognition 사용 (인터넷 연결 필요)
            text = recognizer.recognize_google(audio_data, language="ko-KR")
            
            # 임시 파일 삭제
            if temp_wav_file and os.path.exists(temp_wav_file):
                os.unlink(temp_wav_file)
            
            return {
                "success": True,
                "text": text,
                "duration": duration,
                "language": "ko"
            }
        except sr.UnknownValueError:
            logger.warning("Google Speech Recognition이 오디오를 인식하지 못했습니다.")
            return {"success": False, "text": "", "duration": 0.0, "language": "ko", "error": "UnknownValue"}
        except sr.RequestError as e:
            logger.error(f"Google Speech API 요청 오류: {str(e)}")
            return {"success": False, "text": "", "duration": 0.0, "language": "ko", "error": f"RequestError: {str(e)}"}
        except Exception as e:
            logger.error(f"SpeechRecognition 오류: {str(e)}")
            return {"success": False, "text": "", "duration": 0.0, "language": "ko", "error": str(e)}
        finally:
            # 임시 파일 정리
            if temp_wav_file and os.path.exists(temp_wav_file):
                try:
                    os.unlink(temp_wav_file)
                except Exception:
                    pass



# 싱글톤 인스턴스 생성
stt_model = STTModel()