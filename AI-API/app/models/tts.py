import os
import sys
import json
import logging
import asyncio
import tempfile
import uuid
import datetime

import torch
import numpy as np
import soundfile as sf
import openai
import subprocess

from typing import Tuple, Optional, Dict, Any, List

from app.config import settings

os.environ["PATH"] += os.pathsep + r"C:/ffmpeg-2025-05-05-git-f4e72eb5a3-full_build/bin"

logger = logging.getLogger(__name__)

class GPTEmotionalTTSEnhancer:
    """GPT 기반 감정 및 억양 분석기"""
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    async def analyze_emotional_tone(self, text: str) -> Dict[str, float]:
        """
        텍스트의 감정적 뉘앙스를 분석하여 TTS 파라미터 조정
        """
        try:
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        텍스트의 감정적 뉘앙스를 분석하고 
                        pitch, speed, energy 파라미터를 0~2 사이 실수로 제안해.
                        """
                    },
                    {
                        "role": "user", 
                        "content": f"다음 문장의 감정적 톤을 분석해: {text}"
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            params = json.loads(response.choices[0].message.content)
            return {
                "pitch": max(0.5, min(params.get("pitch", 1.0), 1.5)),
                "speed": max(0.8, min(params.get("speed", 1.0), 1.2)),
                "energy": max(0.7, min(params.get("energy", 1.0), 1.3))
            }
        
        except Exception as e:
            logger.error(f"감정 분석 실패: {str(e)}")
            return {"pitch": 1.0, "speed": 1.2, "energy": 1.0}

class TTSModel:
    """gTTS 기반 TTS 모델 래퍼 클래스"""
    
    def __init__(self):
        self.is_ready = False
        self.device = "cpu"  # gTTS는 클라우드 서비스므로 디바이스 설정 불필요
        
        # 출력 디렉토리 설정
        self.output_dir = os.path.join(settings.AUDIO_OUTPUT_DIR)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 화자 정보 (gTTS는 단일 화자만 제공)
        self.available_speakers = [
            {"id": 0, "name": "기본 화자 (여성)", "language": "ko"}
        ]
        
        # 기본 설정
        self.config = {
            'sample_rate': settings.TTS_SAMPLING_RATE or 24000,
            'language': 'ko'
        }
        self.AUDIO_OUTPUT_DIR = settings.AUDIO_OUTPUT_DIR
        
        # 필요한 패키지 자동 설치
        self._ensure_packages_installed()
    
    def _ensure_packages_installed(self):
        """필요한 패키지가 설치되어 있는지 확인하고 없으면 설치"""
        try:
            # gTTS 패키지 확인
            try:
                from gtts import gTTS
            except ImportError:
                logger.info("gTTS 패키지 설치 중...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "gtts"])
            
            # pydub 패키지 확인
            try:
                from pydub import AudioSegment
            except ImportError:
                logger.info("pydub 패키지 설치 중...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pydub"])
                # ffmpeg 설치 안내 메시지
                logger.info("pydub 사용을 위해 ffmpeg가 설치되어 있어야 합니다.")
                logger.info("Windows: choco install ffmpeg")
                logger.info("macOS: brew install ffmpeg")
                logger.info("Ubuntu: sudo apt install ffmpeg")
            
            logger.info("패키지 설치 확인 완료")
        except Exception as e:
            logger.error(f"패키지 설치 확인 중 오류: {str(e)}")
    
    def load_model(self):
        """필요한 패키지 로드 및 상태 준비"""
        try:
            # 패키지 임포트 확인
            from gtts import gTTS
            from pydub import AudioSegment
            
            self.is_ready = True
            logger.info("gTTS 시스템 준비 완료")
            return True
        except Exception as e:
            logger.error(f"gTTS 준비 실패: {str(e)}")
            raise
    
    def generate_speech(
        self, 
        text: str,
        speed: float = 1.2,
        save_path: Optional[str] = None,
        speaker_id: int = 0,  # 무시됨
        pitch_adjustment: float = 1.0,  # 제한적 지원
        energy_adjustment: float = 1.0  # 볼륨으로 구현
    ) -> Tuple[np.ndarray, int, str]:
        """텍스트를 음성으로 변환"""
        if not self.is_ready:
            self.load_model()
        
        try:
            # 입력 길이 제한
            if hasattr(settings, 'MAX_TEXT_LENGTH') and len(text) > settings.MAX_TEXT_LENGTH:
                # 문장 중간에 자르지 않고 마지막 완전한 문장까지만 유지
                text_parts = text[:settings.MAX_TEXT_LENGTH].rsplit('.', 1)
                if len(text_parts) > 1:
                    text = text_parts[0] + '.'
                else:
                    text = text[:settings.MAX_TEXT_LENGTH]
            
            # 파일 저장 경로 설정
            if save_path is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = uuid.uuid4().hex[:8]
                save_path = os.path.join(self.output_dir, f"{timestamp}_{unique_id}.wav")
            
            # gTTS를 사용하여 음성 생성
            from gtts import gTTS
            from pydub import AudioSegment
            
            # slow 옵션은 속도를 0.7배로 느리게 함, 속도 조절이 제한적이므로 참고용 조건 추가
            slow_option = False
            if speed <= 0.8:
                slow_option = True
                logger.info("gTTS의 속도 제어는 제한적입니다. slow 옵션을 활성화합니다.")
            
            # gTTS로 MP3 생성
            tts = gTTS(text=text, lang=self.config['language'], slow=slow_option)
            
            # 임시 파일로 저장 (gTTS는 파일로만 저장 가능)
            temp_mp3 = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            temp_mp3.close()
            tts.save(temp_mp3.name)
            
            # MP3를 로드하여 처리
            audio = AudioSegment.from_mp3(temp_mp3.name)
            
            # 속도 조절 (pydub의 speedup 기능 사용, 단 버전에 따라 기능이 없을 수 있음)
            if speed > 1.0:
                try:
                    # pydub 1.0.0 이상에서는 speedup 함수 사용 가능
                    if hasattr(audio, 'speedup'):
                        audio = audio.speedup(playback_speed=speed)
                    else:
                        # 속도 조절 기능이 없는 경우 경고 로그 출력
                        logger.warning("pydub 버전이 speedup을 지원하지 않습니다. 속도 조절을 건너뜁니다.")
                except Exception as speed_err:
                    logger.warning(f"속도 조절 실패: {str(speed_err)}")
            
            # 볼륨 조절 (에너지 조정)
            if energy_adjustment != 1.0:
                try:
                    # dB 단위로 변환하여 볼륨 조절
                    gain_db = 20 * np.log10(energy_adjustment)
                    audio = audio.apply_gain(gain_db)
                except Exception as vol_err:
                    logger.warning(f"볼륨 조절 실패: {str(vol_err)}")
            
            # WAV 파일로 저장
            audio.export(save_path, format="wav")
            
            # NumPy 배열로 변환 (필요한 경우)
            try:
                sample_array = np.array(audio.get_array_of_samples())
                sample_rate = audio.frame_rate
            except Exception as arr_err:
                logger.warning(f"오디오 데이터 배열 변환 실패: {str(arr_err)}")
                # 기본값으로 대체
                sample_array = np.zeros(1000)
                sample_rate = 24000
            
            # 임시 파일 삭제
            try:
                os.unlink(temp_mp3.name)
            except Exception:
                pass
            
            logger.info(f"gTTS 음성 생성 완료: {save_path}")
            return sample_array, sample_rate, save_path
            
        except Exception as e:
            logger.error(f"음성 생성 실패: {str(e)}")
            
            # 오류 발생 시 무음 생성 (대체 방안)
            sample_rate = self.config['sample_rate']
            duration = len(text) * 0.1  # 텍스트 길이에 비례한 오디오 길이
            audio = np.zeros(int(duration * sample_rate))
            audio = audio.astype(np.int16)
            
            try:
                sf.write(save_path, audio, sample_rate)
                logger.warning(f"오류로 인해 무음 오디오를 생성했습니다: {save_path}")
            except Exception as sf_err:
                logger.error(f"무음 오디오 저장 실패: {str(sf_err)}")
            
            return audio, sample_rate, save_path
    
    def get_available_speakers(self) -> List[Dict[str, Any]]:
        """사용 가능한 화자 목록 반환"""
        if not self.is_ready:
            self.load_model()
            
        return self.available_speakers

# 싱글톤 인스턴스 생성
tts_model = TTSModel()