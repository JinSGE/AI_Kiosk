# app/utils/model_installer.py
import os
import sys
import subprocess
import logging
import tempfile
import shutil
import requests
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

def install_requirements():
    """필요한 패키지 설치"""
    requirements = [
        "torch",
        "numpy",
        "soundfile",
        "librosa",
        "SpeechRecognition",
        "pyaudio",
        "pydub",
        "gtts",
        "faster-whisper",
        "openai-whisper"
    ]
    
    logger.info("필요한 패키지 설치 중...")
    
    for package in requirements:
        try:
            logger.info(f"{package} 설치 중...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError:
            logger.error(f"{package} 설치 실패")
        except Exception as e:
            logger.error(f"{package} 설치 중 오류 발생: {str(e)}")
    
    logger.info("패키지 설치 완료")

def download_whisper_model(model_name: str = "small", force_download: bool = False) -> Optional[str]:
    """
    Whisper 모델 다운로드 또는 모델 경로 반환
    
    Args:
        model_name: 모델 이름 ("tiny", "base", "small", "medium", "large")
        force_download: 이미 존재하더라도 강제 다운로드 여부
        
    Returns:
        모델 경로 또는 None
    """
    try:
        # model_name이 미리 정의된 크기인지 확인
        predefined_sizes = ["tiny", "base", "small", "medium", "large"]
        if model_name in predefined_sizes:
            # openai-whisper 패키지 사용 시 모델 이름만 반환 (자동 다운로드됨)
            import whisper
            
            logger.info(f"Whisper {model_name} 모델을 사용합니다.")
            # 모델 사전 다운로드 (캐시)
            _ = whisper.load_model(model_name)
            return model_name
        
        # 이미 로컬에 있는지 확인
        model_path = os.path.join(settings.MODEL_CACHE_DIR, model_name)
        if os.path.exists(model_path) and not force_download:
            logger.info(f"이미 다운로드된 모델을 사용합니다: {model_path}")
            return model_path
        
        # Hugging Face에서 다운로드 시도
        if ":" in model_name:
            # repo_id:model_name 형식 (예: "openai/whisper-small")
            from huggingface_hub import snapshot_download
            repo_id = model_name.split(":")[0]
            try:
                path = snapshot_download(repo_id=repo_id)
                logger.info(f"Hugging Face에서 {repo_id} 모델 다운로드 완료: {path}")
                return path
            except Exception as e:
                logger.error(f"Hugging Face에서 모델 다운로드 실패: {str(e)}")
        
        logger.error(f"지원되지 않는 모델 이름: {model_name}")
        return None
        
    except Exception as e:
        logger.error(f"Whisper 모델 다운로드 실패: {str(e)}")
        return None

def download_mb_istft_vits(force_download: bool = False) -> Optional[str]:
    """
    MB-iSTFT-VITS 모델 다운로드
    
    Args:
        force_download: 이미 존재하더라도 강제 다운로드 여부
        
    Returns:
        모델 경로 또는 None
    """
    try:
        # 경로 설정
        model_dir = os.path.join(settings.MODEL_CACHE_DIR, "mb_istft_vits")
        os.makedirs(model_dir, exist_ok=True)
        
        # 모델 파일 목록
        model_files = {
            "모델 가중치": "model.pth",
            "설정 파일": "config.json",
            "음소 사전": "lexicon.txt"
        }
        
        # 모델 파일 존재 여부 확인
        if not force_download:
            all_exists = True
            for _, filename in model_files.items():
                file_path = os.path.join(model_dir, filename)
                if not os.path.exists(file_path):
                    all_exists = False
                    break
            
            if all_exists:
                logger.info(f"이미 모든 MB-iSTFT-VITS 모델 파일이 존재합니다: {model_dir}")
                return model_dir
        
        # 모델 파일 다운로드 (예시 URL, 실제 URL로 교체 필요)
        model_urls = {
            "model.pth": "https://example.com/mb_istft_vits/model.pth",
            "config.json": "https://example.com/mb_istft_vits/config.json",
            "lexicon.txt": "https://example.com/mb_istft_vits/lexicon.txt"
        }
        
        # 모델 소스 코드 다운로드 및 설치
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", 
                "git+https://github.com/AppleHolic/mb-istft-vits.git@main"
            ])
            logger.info("MB-iSTFT-VITS 패키지 설치 완료")
        except Exception as e:
            logger.error(f"MB-iSTFT-VITS 패키지 설치 실패: {str(e)}")
            # 중요한 패키지이므로 실패 시 None 반환
            return None
        
        for filename, url in model_urls.items():
            file_path = os.path.join(model_dir, filename)
            try:
                logger.info(f"{filename} 다운로드 중...")
                # 요청 및 저장
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                logger.info(f"{filename} 다운로드 완료")
            except Exception as e:
                logger.error(f"{filename} 다운로드 실패: {str(e)}")
                # 중요한 파일이므로 실패 시 None 반환
                return None
        
        logger.info(f"MB-iSTFT-VITS 모델 다운로드 완료: {model_dir}")
        return model_dir
        
    except Exception as e:
        logger.error(f"MB-iSTFT-VITS 모델 다운로드 실패: {str(e)}")
        return None

def setup_models():
    """모든 모델 설정"""
    # 모델 캐시 디렉토리 생성
    os.makedirs(settings.MODEL_CACHE_DIR, exist_ok=True)
    
    # 필요한 패키지 설치
    install_requirements()
    
    # STT 모델 다운로드
    stt_model_path = download_whisper_model(settings.STT_MODEL_PATH)
    if stt_model_path:
        logger.info(f"STT 모델 준비 완료: {stt_model_path}")
    else:
        logger.warning("STT 모델 다운로드 실패")
    
    # TTS 모델 다운로드
    tts_model_path = download_mb_istft_vits()
    if tts_model_path:
        logger.info(f"TTS 모델 준비 완료: {tts_model_path}")
    else:
        logger.warning("TTS 모델 다운로드 실패, gTTS 폴백을 사용합니다.")
    
    logger.info("모델 설정 완료")

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 모델 설정 실행
    setup_models()