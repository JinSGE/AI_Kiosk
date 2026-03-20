# app/__init__.py # 패키지 초기화 파일
import os
import sys
import logging
import io

# Windows 콘솔에서 유니코드 출력 문제 해결
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf8')

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
   sys.path.append(parent_dir)

# 로깅 설정
logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
   handlers=[
       logging.StreamHandler(),  # 콘솔 출력
       logging.FileHandler(os.path.join(parent_dir, "app.log"))  # 파일 출력
   ]
)

logger = logging.getLogger(__name__)

# 필요한 디렉토리 목록 정의
required_dirs = [
   os.path.join(parent_dir, "data", "documents"),
   os.path.join(parent_dir, "data", "knowledge_base"),
   os.path.join(parent_dir, "model_cache"),
   os.path.join(parent_dir, "audio_output"),  # 오디오 출력 디렉토리 추가
   os.path.join(parent_dir, "audio_input"),   # 오디오 입력 디렉토리 추가
   os.path.join(parent_dir, "temp")           # 임시 디렉토리 추가
]

# 필요한 디렉토리 생성
for directory in required_dirs:
   try:
       os.makedirs(directory, exist_ok=True)
       logger.info(f"디렉토리 확인/생성 완료: {directory}")
   except Exception as e:
       logger.error(f"디렉토리 생성 중 오류 발생: {directory}, 오류: {str(e)}")

# 경로 정보 로깅
logger.info(f"BASE_DIR: {parent_dir}")
logger.info(f"AUDIO_OUTPUT_DIR: {os.path.join(parent_dir, 'audio_output')}")
logger.info(f"AUDIO_INPUT_DIR: {os.path.join(parent_dir, 'audio_input')}")