# setup_knowledge_base.py
import os
import json
import argparse
import asyncio
import logging
from typing import List, Dict, Any

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_CACHE_DIR = os.path.join(BASE_DIR, "model_cache")
KB_PATH = os.path.join(MODEL_CACHE_DIR, "knowledge_base.json")

# 기본 지식 베이스 데이터
DEFAULT_KNOWLEDGE_BASE = [
    {
        "id": "menu_1",
        "content": "아메리카노는 4,500원, 카페 라떼는 5,000원, 카페 모카는 5,500원, 카라멜 마끼아또는 5,800원, 레몬 에이드는 5,500원입니다.",
        "category": "menu"
    },
    {
        "id": "menu_2",
        "content": "초코 라떼는 5,500원, 녹차 라떼는 5,300원, 바닐라 라떼는 5,500원, 허브 티는 5,000원, 복숭아 아이스 티는 5,200원입니다.",
        "category": "menu"
    },
     {
      "id": "option_1",
      "content": "모든 음료는 따뜻한(핫) 또는 차가운(아이스) 옵션을 선택할 수 있습니다. 아이스는 추가 요금이 없습니다.",
      "category": "option"
    },
    {
      "id": "option_2",
      "content": "샷 추가는 500원, 시럽 추가는 300원, 휘핑 추가는 500원입니다.",
      "category": "option"
    },
    {
      "id": "size_1",
      "content": "음료 사이즈는 스몰(S), 미디엄(M), 라지(L)가 있습니다. 미디엄은 500원, 라지는 1,000원 추가됩니다.",
      "category": "size"
    },
    {
      "id": "payment_1",
      "content": "결제는 카드, 현금, 삼성페이, 애플페이, 카카오페이, 네이버페이를 지원합니다.",
      "category": "payment"
    },
    {
        "id": "faq_1",
        "content": "음료는 매장 이용과 포장 모두 가능합니다. 포장시 테이크아웃 컵으로 제공됩니다.",
        "category": "faq"
    },
    {
        "id": "greeting_1",
        "content": "안녕하세요! 저희 카페에 오신 것을 환영합니다. 어떤 메뉴를 도와드릴까요?",
        "category": "greeting"
    },
    {
        "id": "recommend_1",
        "content": "오늘의 추천 메뉴는 바닐라라떼입니다. 부드러운 우유와 달콤한 바닐라가 조화롭게 어우러진 음료입니다.",
        "category": "recommend"
    }
]

async def setup_knowledge_base(kb_data: List[Dict[str, Any]], output_path: str, force: bool = False):
    """지식 베이스 설정"""
    try:
        # 디렉토리 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 기존 파일 확인
        if os.path.exists(output_path) and not force:
            logger.info(f"지식 베이스 파일이 이미 존재합니다: {output_path}")
            logger.info("기존 파일을 덮어쓰려면 --force 옵션을 사용하세요.")
            return False
        
        # 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(kb_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"지식 베이스 설정 완료: {output_path} ({len(kb_data)} 문서)")
        return True
    except Exception as e:
        logger.error(f"지식 베이스 설정 실패: {str(e)}")
        return False

if __name__ == "__main__":
    # 커맨드 라인 인자 파싱
    parser = argparse.ArgumentParser(description="지식 베이스 초기 설정")
    parser.add_argument("--force", action="store_true", help="기존 파일 덮어쓰기")
    parser.add_argument("--input", help="입력 JSON 파일 경로 (지정하지 않으면 기본 데이터 사용)")
    parser.add_argument("--output", default=KB_PATH, help="출력 JSON 파일 경로")
    args = parser.parse_args()
    
    # 입력 데이터 결정
    kb_data = DEFAULT_KNOWLEDGE_BASE
    if args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
            logger.info(f"입력 파일 로드: {args.input} ({len(kb_data)} 문서)")
        except Exception as e:
            logger.error(f"입력 파일 로드 실패: {str(e)}")
            logger.info("기본 데이터를 사용합니다.")
    
    # 비동기 함수 실행
    asyncio.run(setup_knowledge_base(kb_data, args.output, args.force))