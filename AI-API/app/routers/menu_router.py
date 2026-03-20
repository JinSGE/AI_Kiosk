from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
import os
import json
import logging

from app.config import settings
from app.main import get_rag_service

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter()

# 메뉴 데이터 경로 수동 지정
MENU_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
    'app', 'data', 'menu_data.json'
)

# 캐싱된 메뉴 데이터를 저장할 변수들
_cached_menu_data = None
_cached_menu_items = None
_cached_categories = None

def load_menu_data():
    """
    메뉴 데이터 안전하게 로드하는 함수
    캐싱된 데이터가 있으면 캐시에서 반환
    
    :return: 메뉴 데이터 딕셔너리
    """
    global _cached_menu_data
    
    # 캐시된 데이터가 있으면 바로 반환
    if _cached_menu_data is not None:
        return _cached_menu_data
    
    try:
        # 파일 존재 여부 확인
        if not os.path.exists(MENU_DATA_PATH):
            logger.error(f"메뉴 데이터 파일을 찾을 수 없습니다: {MENU_DATA_PATH}")
            raise FileNotFoundError(f"메뉴 데이터 파일이 존재하지 않습니다: {MENU_DATA_PATH}")
        
        # 파일 읽기
        with open(MENU_DATA_PATH, 'r', encoding='utf-8') as f:
            menu_data = json.load(f)
        
        # 데이터 구조 검증
        if not menu_data or 'menus' not in menu_data:
            logger.error("메뉴 데이터 형식이 올바르지 않습니다.")
            raise ValueError("메뉴 데이터가 비어있거나 형식이 잘못되었습니다.")
        
        # 캐시에 저장
        _cached_menu_data = menu_data
        
        return menu_data
    
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as e:
        logger.error(f"메뉴 데이터 로딩 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메뉴 데이터를 로드할 수 없습니다: {str(e)}")

@router.get("", response_model=List[Dict])
async def get_menu_items(
    category: Optional[str] = None
):
    """
    메뉴 아이템 조회 API
    - 전체 메뉴 조회
    - 카테고리별 필터링
    """
    global _cached_menu_items
    
    try:
        # 카테고리가 없고 캐시가 있으면 바로 반환
        if category is None and _cached_menu_items is not None:
            return _cached_menu_items
        
        # RAG 서비스는 처음 한 번만 초기화
        await initialize_rag_service_once()
        
        # 메뉴 데이터 로드 (캐시 활용)
        menu_data = load_menu_data()
        
        # 전체 메뉴 추출
        menus = menu_data.get('menus', [])
        
        # 전체 메뉴 캐싱
        if category is None:
            _cached_menu_items = menus
        
        # 카테고리 필터링
        if category:
            menus = [
                menu for menu in menus 
                if category.lower() in [cat.lower() for cat in menu.get('categories', [])]
            ]
        
        return menus
    
    except HTTPException:
        # 이미 HTTPException인 경우 그대로 다시 발생
        raise
    except Exception as e:
        logger.error(f"메뉴 조회 중 예상치 못한 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"메뉴 조회 중 오류 발생: {str(e)}"
        )

@router.get("/categories", response_model=List[str])
async def get_menu_categories():
    """
    사용 가능한 메뉴 카테고리 목록 조회
    """
    global _cached_categories
    
    # 캐시된 카테고리가 있으면 바로 반환
    if _cached_categories is not None:
        return _cached_categories
    
    try:
        # RAG 서비스는 처음 한 번만 초기화
        await initialize_rag_service_once()
        
        # 메뉴 데이터 로드 (캐시 활용)
        menu_data = load_menu_data()
        
        # 카테고리 추출
        categories = list(menu_data.get('categories', {}).keys())
        
        # 캐시에 저장
        _cached_categories = categories
        
        return categories
    
    except HTTPException:
        # 이미 HTTPException인 경우 그대로 다시 발생
        raise
    except Exception as e:
        logger.error(f"카테고리 조회 중 예상치 못한 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"카테고리 조회 중 오류 발생: {str(e)}"
        )

@router.get("/{menu_name}", response_model=Dict)
async def get_menu_item_by_name(menu_name: str):
    """
    특정 메뉴 아이템 상세 조회
    """
    try:
        # RAG 서비스는 처음 한 번만 초기화
        await initialize_rag_service_once()
        
        # 메뉴 데이터 로드 (캐시 활용)
        menu_data = load_menu_data()
        
        # 메뉴 찾기 (대소문자 구분 없이)
        menu_item = next(
            (menu for menu in menu_data.get('menus', []) 
             if menu['name'].lower() == menu_name.lower()), 
            None
        )
        
        if not menu_item:
            raise HTTPException(status_code=404, detail="메뉴 아이템을 찾을 수 없습니다.")
        
        return menu_item
    
    except HTTPException:
        # 이미 HTTPException인 경우 그대로 다시 발생
        raise
    except Exception as e:
        logger.error(f"메뉴 아이템 조회 중 예상치 못한 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"메뉴 아이템 조회 중 오류 발생: {str(e)}"
        )

# RAG 서비스 초기화 상태를 추적하는 변수
_rag_initialized = False

async def initialize_rag_service_once():
    """RAG 서비스를 한 번만 초기화하는 함수"""
    global _rag_initialized
    
    if not _rag_initialized:
        # RAG 서비스 안전하게 가져오기
        rag_service = get_rag_service()
        
        # RAG 서비스 초기화 확인
        if rag_service and not rag_service.is_initialized:
            await rag_service.initialize()
            logger.info("RAG 서비스 초기화 완료")
        
        _rag_initialized = True

# 디버깅용 라우트 - 메뉴 파일 경로 확인
@router.get("/debug/menu-path")
async def debug_menu_path():
    """
    메뉴 데이터 파일 경로 디버깅
    """
    return {
        "menu_data_path": MENU_DATA_PATH,
        "file_exists": os.path.exists(MENU_DATA_PATH),
        "cached_data_exists": _cached_menu_data is not None
    }

# 캐시 수동 갱신을 위한 엔드포인트 (관리용)
@router.post("/refresh-cache")
async def refresh_menu_cache():
    """메뉴 데이터 캐시를 수동으로 갱신"""
    global _cached_menu_data, _cached_menu_items, _cached_categories
    
    try:
        # 캐시 초기화
        _cached_menu_data = None
        _cached_menu_items = None
        _cached_categories = None
        
        # 데이터 다시 로드
        menu_data = load_menu_data()
        _cached_menu_items = menu_data.get('menus', [])
        _cached_categories = list(menu_data.get('categories', {}).keys())
        
        return {
            "success": True,
            "message": "메뉴 데이터 캐시가 갱신되었습니다.",
            "cache_status": {
                "menu_data": _cached_menu_data is not None,
                "menu_items": _cached_menu_items is not None,
                "categories": _cached_categories is not None
            }
        }
    except Exception as e:
        logger.error(f"캐시 갱신 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"캐시 갱신 중 오류 발생: {str(e)}"
        )