# app/routers/kiosk_router.py
import time
import asyncio
import uuid
import json
import logging
import os
from datetime import datetime
import re
# 서비스 및 종속성 가져오기
from app.services.kiosk_service import KioskService
from app.services.continuous_dialog_service import GPTEnhancedContinuousDialogService as ContinuousDialogService
from app.services.audio_device import audio_device_service
from app.services.pipeline_service import PipelineService
from app.main import get_kiosk_service
from app.services.notification_service import notify_cart_update
from app.utils.order_utils import extract_order_info, update_cart_with_merge

from fastapi import APIRouter, Request, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, Dict, Any, List


# 전역 변수로 현재 장바구니 상태 저장
_current_cart_items = []
_current_cart_total = 0

# 현재 장바구니 항목 가져오기 함수
async def get_current_cart_items():
    """
    현재 장바구니 항목 반환
    
    Returns:
        현재 장바구니 항목 목록의 복사본
    """
    global _current_cart_items
    # 항목의 깊은 복사본 반환 (수정 방지)
    import copy
    return copy.deepcopy(_current_cart_items)

# 장바구니 항목 설정 함수
async def set_current_cart_items(items, total=None):
    """
    현재 장바구니 항목 설정
    
    Args:
        items: 설정할 장바구니 항목 목록
        total: 총액 (None인 경우 자동 계산)
    
    Returns:
        설정된 항목 목록과 총액
    """
    global _current_cart_items, _current_cart_total
    
    # 항목 목록 복사
    import copy
    _current_cart_items = copy.deepcopy(items)
    
    # 총액 계산 또는 설정
    if total is None:
        _current_cart_total = sum(item.get('total', 0) for item in _current_cart_items)
    else:
        _current_cart_total = total
    
    return _current_cart_items, _current_cart_total

# 장바구니 초기화 함수
async def clear_cart():
    """
    장바구니 초기화
    
    Returns:
        초기화 성공 여부
    """
    global _current_cart_items, _current_cart_total
    _current_cart_items = []
    _current_cart_total = 0
    return True

_last_extraction_text = None
_last_extraction_result = None

_last_order_info = None
_last_audio_hash = None
_processing_lock = False
_last_processing_time = 0

# 로깅 설정
logger = logging.getLogger(__name__)

# 라우터 선언
router = APIRouter(tags=["kiosk"])

# 텍스트 입력 처리 엔드포인트
@router.post("/text-input")
async def process_text_input(
    request: Request,
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """텍스트 입력 처리 및 응답 생성"""
    try:
        body = await request.body()
        text = json.loads(body).get("text", "") if body else ""
        result         = await kiosk_service.process_text_input(text)
        return {
            "response_text": result.get("response_text", ""),
            "audio_path": result.get("audio_path", "")
        }
    except Exception as e:
        logger.error(f"텍스트 처리 실패: {str(e)}")
        return {"response_text": "텍스트 처리 중 오류가 발생했습니다.", "audio_path": None}
    
# extract_menu_from_part, update_cart_with_merge 는 order_utils로 이동됨 또는 대체됨



@router.get("/cart")
async def get_cart() -> Dict[str, Any]:
    """현재 장바구니 상태 조회"""
    try:
        items = await get_current_cart_items()
        total = sum(item.get('total', 0) for item in items)
        
        return {
            "success": True,
            "items": items,
            "total": total
        }
    except Exception as e:
        logger.error(f"장바구니 조회 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/cart/clear")
async def clear_cart_endpoint() -> Dict[str, Any]:
    """장바구니 초기화"""
    try:
        success = await clear_cart()
        
        # WebSocket 알림 전송
        if success:
            await notify_cart_update({"items": [], "total": 0, "cleared": True})
        
        return {
            "success": success,
            "message": "장바구니가 초기화되었습니다."
        }
    except Exception as e:
        logger.error(f"장바구니 초기화 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
    
@router.post("/process-audio")
async def process_audio_for_cart(
    file: Optional[UploadFile] = File(None),
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """오디오 파일 처리 및 장바구니에 추가"""
    try:
        if not file:
            return {"success": False, "message": "오디오 파일이 없습니다."}

        # 오디오 데이터 읽기
        audio_data = await file.read()
        
        # 임시 파일 생성
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(audio_data)

        try:
            # 오디오 처리
            result = await kiosk_service.process_order_from_audio(temp_path)
            
            # 메뉴 및 수량 정보 추출
            order_info = extract_order_info(result.get("response_text", ""))
            response_text = result.get("response_text", "")
            
            # WebSocket으로 장바구니 업데이트 알림


            global _last_order_info

            # "추가" 키워드 처리
            if "추가" in response_text.lower():
                # 기존 장바구니 항목 가져오기
                existing_items = await get_current_cart_items()
                
                # 장바구니 병합
                updated_items, updated_total, was_updated = update_cart_with_merge(
                    existing_items, 
                    order_info.get("items", [])
                )
                
                if was_updated:
                    # 업데이트된 장바구니 저장
                    await set_current_cart_items(updated_items, updated_total)
                    
                    # 병합된 주문 정보로 알림
                    await notify_cart_update({
                        "items": updated_items,
                        "total": updated_total,
                        "is_additional": True
                    })
            else:
                # 일반 주문 (교체) - 장바구니 설정 및 알림
                await set_current_cart_items(order_info.get("items", []), order_info.get("total", 0))
                await notify_cart_update(order_info)

            # 주문 정보 캐싱
            if _last_order_info != order_info:
                _last_order_info = order_info

            return {
                "success": True,
                "response_text": result.get("response_text", ""),
                "audio_path": result.get("audio_path", ""),
                "order_info": order_info
            }
        finally:
            # 임시 파일 삭제
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        logger.error(f"오디오 처리 실패: {str(e)}")
        return {"success": False, "message": f"오디오 처리 중 오류가 발생했습니다: {str(e)}"}
    
# 오디오 처리 엔드포인트 수정
@router.post("/audio")
async def process_audio_for_cart(
    file: Optional[UploadFile] = File(None),
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """오디오 파일 처리 및 장바구니에 추가"""
    global _last_order_info, _last_audio_hash, _processing_lock, _last_processing_time
    
    try:
        if not file:
            return {"success": False, "message": "오디오 파일이 없습니다."}

        # 현재 시간 체크 - 너무 빠른 연속 요청 방지
        current_time = time.time()
        if current_time - _last_processing_time < 3.0:  # 3초 이내 요청은 무시
            logger.info("너무 빠른 연속 요청 감지, 처리 무시")
            return {"success": False, "message": "잠시 후 다시 시도해주세요."}
            
        # 이미 처리 중인지 확인
        if _processing_lock:
            logger.info("이미 오디오 처리가 진행 중입니다.")
            return {"success": False, "message": "이미 처리 중입니다. 잠시 후 다시 시도해주세요."}

        # 처리 시작 표시
        _processing_lock = True
        _last_processing_time = current_time

        try:
            # 오디오 데이터 읽기
            audio_data = await file.read()
            
            # 오디오 해시 생성 (중복 체크용)
            import hashlib
            audio_hash = hashlib.md5(audio_data).hexdigest()
            
            # 동일 오디오 체크
            if audio_hash == _last_audio_hash:
                logger.info("동일한 오디오 파일 감지, 중복 처리 방지")
                return {"success": False, "message": "동일한 요청이 이미 처리되었습니다."}
                
            _last_audio_hash = audio_hash
            
            # 임시 파일 생성
            temp_path = f"temp_{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(audio_data)

            # 오디오 처리
            result = await kiosk_service.process_order_from_audio(temp_path)
            
            # 메뉴와 수량 정보 추출
            order_info = extract_order_info(result.get("response_text", ""))    

            # 중복 주문 체크
            if _last_order_info == order_info:
                logger.info("중복 주문 감지, 알림 생략")
                return {
                    "success": True,
                    "response_text": result.get("response_text", ""),
                    "audio_path": result.get("audio_path", ""),
                    "order_info": order_info,
                    "duplicate": True
                }

            # 주문 정보 업데이트 및 WebSocket 알림
            _last_order_info = order_info
            
            # WebSocket을 통해 장바구니 업데이트 알림
            from app.services.notification_service import notify_order_processed
            await notify_order_processed({
                "items": order_info.get("items", []),
                "total": order_info.get("total", 0),
                "response_text": result.get("response_text", ""),
                "audio_path": result.get("audio_path", "")
            })
            
            return {
                "success": True,
                "response_text": result.get("response_text", ""),
                "audio_path": result.get("audio_path", ""),
                "order_info": order_info
            }
        finally:
            # 처리 완료 표시
            _processing_lock = False
            
            # 임시 파일 삭제
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        _processing_lock = False  # 에러 발생 시에도 락 해제
        logger.error(f"오디오 처리 실패: {str(e)}")
        return {"success": False, "message": f"오디오 처리 중 오류가 발생했습니다: {str(e)}"}

def extract_options(text: str, menu_name: str, menu_options: Dict) -> List[str]:
    """
    텍스트에서 메뉴 옵션을 추출하여 배열로 반환
    
    Args:
        text: 입력 텍스트
        menu_name: 메뉴명
        menu_options: 메뉴 옵션 정보 (기본값: None 처리 추가)
    
    Returns:
        추출된 옵션 정보 (문자열 배열)
    """
    # 예외 처리 추가
    if menu_options is None:
        menu_options = {}
        
    options = []
    
    try:
        # 기본 옵션 - 온도
        if "아이스" in text.lower() or "차가운" in text.lower() or "시원한" in text.lower():
            options.append("Ice")
        elif "핫" in text.lower() or "따뜻한" in text.lower() or "뜨거운" in text.lower():
            options.append("Hot")
        else:
            # 기본 옵션으로 Ice 추가 (아무것도 지정하지 않은 경우)
            options.append("Ice")  # 기본값

        # 사이즈 옵션
        if "라지" in text.lower() or "큰" in text.lower() or "large" in text.lower():
            options.append("Large")
        elif "레귤러" in text.lower() or "보통" in text.lower() or "regular" in text.lower():
            options.append("Regular")
        else:
            # 기본 옵션으로 Small 추가
            options.append("Small")  # 기본값
        
        # 샷 추가 옵션 (사용자가 명시적으로 요청한 경우만)
        if "2샷" in text.lower() or "투샷" in text.lower() or "샷 2번" in text.lower():
            options.append("샷 추가")
        elif "1샷" in text.lower() or "원샷" in text.lower() or "샷 추가" in text.lower():
            options.append("샷 추가")
        
        # 시럽 추가 옵션 (사용자가 명시적으로 요청한 경우만)
        if "바닐라" in text.lower() and "시럽" in text.lower():
            options.append("바닐라 시럽 추가")
        elif "헤이즐넛" in text.lower() and "시럽" in text.lower():
            options.append("헤이즐넛 시럽 추가")
        elif "카라멜" in text.lower() and "시럽" in text.lower():
            options.append("카라멜 시럽 추가")
        
    except Exception as e:
        # 오류 발생 시 로깅하고 기본 옵션만 반환
        logger.error(f"옵션 추출 중 오류 발생: {str(e)}")
        # 오류 발생 시 기본 옵션으로 Small과 Ice 추가
        if not any(opt in ["Small", "Regular", "Large"] for opt in options):
            options.append("Small")
        if not any(opt in ["Ice", "Hot"] for opt in options):
            options.append("Ice")
    
    return options

def find_closest_menu(input_menu: str, menu_list: List[str]) -> str:
    """
    입력된 메뉴와 가장 유사한 메뉴를 찾음
    
    Args:
        input_menu: 입력된 메뉴명
        menu_list: 메뉴 목록
    
    Returns:
        가장 유사한 메뉴명 또는 빈 문자열
    """
    # 메뉴 목록이 비어있거나 입력 메뉴가 빈 문자열인 경우 처리
    if not menu_list or not input_menu:
        return ""
    
    try:
        # 정확히 일치하면 바로 반환
        if input_menu in menu_list:
            return input_menu
        
        # 특수 케이스 처리: 일반적으로 혼동되는 메뉴명 매핑
        special_case_map = {
            # 아메리카노 계열
            "아아": "아메리카노",
            "아이스아메리카노": "아메리카노",
            "아아메": "아메리카노",
            "아메": "아메리카노",
            "아메리까노": "아메리카노",
            "아이스메리카노": "아메리카노",
            "아이스아메": "아메리카노",
            
            # 카페라떼 계열
            "카페라테": "카페라떼",
            "라테": "카페라떼",
            "라떼": "카페라떼",
            "까페라떼": "카페라떼",
            "까페라테": "카페라떼",
            
            # 카페모카 계열
            "카페목화": "카페모카",
            "카페못화": "카페모카",
            "카페모까": "카페모카",
            "카페목카": "카페모카",
            "까페모카": "카페모카",
            "모카": "카페모카",
            "목카": "카페모카",
            "목화": "카페모카",
            "모까": "카페모카",
            "못화": "카페모카",
            
            # 초코라떼 계열
            "핫초코": "초코라떼",
            "초코": "초코라떼",
            "아이스초코": "초코라떼",
            "초코렛": "초코라떼",
            "초콜렛": "초코라떼",
            "초코라테": "초코라떼",
            "초코릿": "초코라떼",
            "초코렛라떼": "초코라떼",
            "초콜렛라떼": "초코라떼",
            
            # 바닐라라떼 계열
            "바닐라": "바닐라라떼",
            "바닐라라테": "바닐라라떼",
            "바닐라아떼": "바닐라라떼",
            "바닐라아테": "바닐라라떼",
            "바닐라레떼": "바닐라라떼",
            
            # 카라멜마끼아또 계열
            "카라멜": "카라멜마끼아또",
            "카라멜마키아또": "카라멜마끼아또",
            "카라멜마키아토": "카라멜마끼아또",
            "카라멜마끼아토": "카라멜마끼아또",
            "카라멜마치아또": "카라멜마끼아또",
            "까라멜마끼아또": "카라멜마끼아또",
            "카라멜마끼야또": "카라멜마끼아또",
            "카라멜마끼야토": "카라멜마끼아또",
            "마끼아또": "카라멜마끼아또",
            "마키아또": "카라멜마끼아또",
            "마키아토": "카라멜마끼아또",
            
            # 그린라떼(녹차라떼) 계열
            "그린티": "그린라떼",
            "녹차": "그린라떼",
            "녹차라떼": "그린라떼",
            "녹차라테": "그린라떼",
            "그린티라떼": "그린라떼",
            "그린티라테": "그린라떼",
            "그린라테": "그린라떼",
            
            # 아이스티 계열
            "아이스티": "복숭아아이스티",
            "아스티": "복숭아아이스티",
            "복숭아티": "복숭아아이스티",
            "복숭아아스티": "복숭아아이스티",
            "복숭아아이스트": "복숭아아이스티",
            "복티": "복숭아아이스티",
            "복숭티": "복숭아아이스티",
            "아이스복숭아티": "복숭아아이스티",
            
            # 레몬에이드 계열
            "레몬": "레몬에이드",
            "레모네이드": "레몬에이드",
            "레몬네이드": "레몬에이드",
            "레모나데": "레몬에이드",
            "레몬아데": "레몬에이드",
            "레몬에이뜨": "레몬에이드",
            "레몬에이뜨": "레몬에이드",
            "래몬에이드": "레몬에이드",
            "래몬": "레몬에이드",

            # 허브티 기본
            "허브티": "허브티",
            "허브차": "허브티",
            "허브": "허브티",
            "헙티": "허브티",
            "허브떼": "허브티",
            "허브데": "허브티",
            "허브째": "허브티",
            "허브치": "허브티",
            "허브탸": "허브티"
    }
        
        # 특수 케이스 확인
        for case, menu in special_case_map.items():
            if case in input_menu:
                if menu in menu_list:  # 메뉴 목록에 있는지 확인
                    return menu
        
        # 부분 일치 확인 (입력 메뉴가 메뉴 이름의 일부인 경우)
        for menu in menu_list:
            if input_menu in menu or menu in input_menu:
                return menu
                
        # 단어 간 유사도 검사
        max_similarity = 0
        closest_menu = ""
        
        for menu in menu_list:
            # 간단한 유사도 계산
            try:
                # 글자 단위 일치 개수 계산 (보다 안정적인 방식)
                common_chars = set(menu.lower()) & set(input_menu.lower())
                similarity = len(common_chars) / max(len(set(menu)), len(set(input_menu)))
                
                if similarity > max_similarity:
                    max_similarity = similarity
                    closest_menu = menu
            except Exception as sim_error:
                # 유사도 계산 중 오류 발생 시 로깅하고 계속 진행
                logger.error(f"유사도 계산 중 오류: {str(sim_error)}")
                continue
        
        # 유사도가 임계값 이상인 경우만 반환
        if max_similarity > 0.4:  # 임계값을 0.5에서 0.4로 낮춤 (더 넓은 범위의 매칭 허용)
            return closest_menu
        
        # 유사도가 충분히 높지 않으면 가장 유사한 메뉴 목록에서 찾기
        for menu in menu_list:
            # 각 메뉴에 대해 입력 메뉴의 절반 이상의 글자가 일치하는지 확인
            overlap_count = sum(1 for c in input_menu.lower() if c in menu.lower())
            if overlap_count >= len(input_menu) // 2:
                return menu
        
        # 마지막 시도: 음소 유사도 기반 (한글 특성 고려)
        # 첫 글자와 마지막 글자가 일치하는 메뉴 찾기
        if len(input_menu) >= 2:
            first_char = input_menu[0]
            last_char = input_menu[-1]
            
            for menu in menu_list:
                if len(menu) >= 2 and menu[0] == first_char and menu[-1] == last_char:
                    return menu
                    
        # 어떤 방법으로도 찾지 못한 경우 빈 문자열 반환
        return ""
        
    except Exception as e:
        # 전체 함수에 대한 예외 처리
        logger.error(f"메뉴 유사도 검색 중 오류 발생: {str(e)}")
        # 안전하게 빈 문자열 반환
        return ""

def calculate_option_price(options: List[str]) -> int:
    """
    선택된 옵션에 따른 추가 가격 계산
    
    Args:
        options: 선택된 옵션 (문자열 배열)
    
    Returns:
        추가 가격
    """
    # 옵션 가격 테이블
    option_prices = {
        "Ice": 0,     # 아이스 옵션 가격 0원으로 변경
        "Hot": 0,
        "Small": 0,
        "Regular": 500,
        "Large": 1000,
        "샷 추가": 500,
        "바닐라 시럽 추가": 500,
        "헤이즐넛 시럽 추가": 500,
        "카라멜 시럽 추가": 500
    }
    
    total_option_price = 0
    
    # 옵션 배열을 순회하며 가격 합산
    for option in options:
        total_option_price += option_prices.get(option, 0)
    
    return total_option_price

def extract_order_info(text: str, menu_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    응답 텍스트에서 주문 정보를 추출하여 장바구니 형태로 반환
    
    Args:
        text: 응답 텍스트
        menu_data: 메뉴 데이터 (기본값: None, 없을 경우 내부에서 로드)
    
    Returns:
        장바구니 정보 (items, total)
    """
    import uuid
    import os
    import json
    from typing import Dict, Any, List, Optional
    import logging
    import re

    global _last_extraction_text, _last_extraction_result

    # 수량 매핑 (한글 -> 숫자)
    quantity_mapping = {
        "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, 
        "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
        "하나": 1, "둘": 2, "셋": 3, "넷": 4
    }
    
    # 수량 추출 함수 - 함수 외부나 호출 후가 아닌 함수 내부 시작 부분에 정의
    def parse_quantity(text, menu_name=None):
        """메뉴의 수량 추출"""
        # 기본 수량은 1
        quantity = 1
        
        if menu_name:
            # "[메뉴] N잔" 같은 명시적 패턴 확인
            specific_pattern = rf'{menu_name}\s*(\d+)\s*잔'
            specific_match = re.search(specific_pattern, text)
            if specific_match:
                try:
                    quantity = int(specific_match.group(1))
                    logger.info(f"명시적 수량 감지: {menu_name} {quantity}잔 (숫자)")
                    return quantity
                except ValueError:
                    pass  # 변환 오류 시 다음 패턴 확인
            
            # "메뉴 한 잔" 형태 처리
            if f"{menu_name} 한 잔" in text or f"{menu_name} 한잔" in text or f"{menu_name}한잔" in text:
                logger.info(f"명시적 수량 감지: {menu_name} 1잔 (한 잔)")
                return 1
            
            # 한글 수량 표현 처리
            for num_word, value in quantity_mapping.items():
                pattern = rf'{menu_name}\s*{num_word}\s*잔'
                if re.search(pattern, text):
                    logger.info(f"한글 수량 감지: {menu_name} {value}잔 (한글)")
                    return value
                
                # 공백 없는 형태도 처리 ("아메리카노두잔")
                if f"{menu_name}{num_word}잔" in text:
                    logger.info(f"공백 없는 한글 수량 감지: {menu_name} {value}잔")
                    return value
            
            # 메뉴 반복 확인 (메뉴가 여러 번 언급되면 그 횟수를 수량으로)
            menu_count = len(re.findall(rf'\b{re.escape(menu_name)}\b', text))
            if menu_count > 1:
                logger.info(f"메뉴 반복 패턴 감지: {menu_name} {menu_count}잔")
                return menu_count
        
        # 일반 "N잔" 패턴 (메뉴와 무관하게)
        number_pattern = r'(\d+)\s*잔'
        number_match = re.search(number_pattern, text)
        if number_match:
            try:
                quantity = int(number_match.group(1))
                logger.info(f"일반 수량 감지: {quantity}잔")
                return quantity
            except ValueError:
                pass
        
        logger.info(f"기본 수량 적용: {menu_name if menu_name else '메뉴'} 1잔 (명시적 수량 없음)")
        return quantity

    # 캐싱: 동일한 텍스트에 대한 반복 호출 감지
    if text == _last_extraction_text and _last_extraction_result is not None:
        result_copy = _last_extraction_result.copy()
        
        # ID값 제거하고 비교 (항상 다른 UUID가 생성되는 문제 해결)
        for item in result_copy.get("items", []):
            if "id" in item:
                item["id"] = str(uuid.uuid4())  # 새 ID 생성하여 반환
                
        logger.info(f"주문 정보 캐시 사용: '{text}'")
        return result_copy
    
    termination_keywords = ["종료", "그만", "취소", "나가기", "그만하기", "주문 취소", "주문 종료"]
    if any(keyword in text.lower() for keyword in termination_keywords):
        logger.info(f"종료/취소 명령 감지: '{text}' - 메뉴 추출 건너뜀")
        return {"items": [], "total": 0, "extraction_success": False, "is_termination": True}
    
    # 음성 인식 오류 교정
    correction_map = {
        "허벅지": "허브티",
        "레모네이드": "레몬에이드",
        "안전": "한잔",
        "완전": "한잔"       
    }
    
    for wrong, correct in correction_map.items():
        if wrong in text:
            text = text.replace(wrong, correct)
            logger.info(f"텍스트 교정: '{wrong}' -> '{correct}'")
    
    # 메뉴 데이터 로드
    if menu_data is None:
        try:
            # 메뉴 데이터 파일 경로
            menu_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "menu_data.json")
            if os.path.exists(menu_path):
                with open(menu_path, 'r', encoding='utf-8') as f:
                    menu_data = json.load(f)
            else:
                logger.warning(f"메뉴 데이터 파일을 찾을 수 없습니다: {menu_path}")
                menu_data = {}
        except Exception as e:
            logger.error(f"메뉴 데이터 로드 실패: {str(e)}")
            menu_data = {}
    
    # 메뉴 목록 및 가격 정보 초기화
    menu_list = []
    menu_prices = {}
    menu_options = {}
    
    # 메뉴 데이터에서 메뉴 목록 및 가격 정보 추출
    if menu_data and "menus" in menu_data:
        for menu_item in menu_data["menus"]:
            name = menu_item.get("name", "")
            if name:
                menu_list.append(name)
                menu_prices[name] = menu_item.get("basePrice", 4500)
                menu_options[name] = menu_item.get("options", {})
    
    # 메뉴 목록이 비어있는 경우 기본값 설정
    if not menu_list:
        menu_list = ["아메리카노", "카페 라떼", "카페 모카", "바닐라 라떼", "카라멜 마끼아또", "초코 라떼", "그린 라떼", 
                    "복숭아아이스티", "허브티", "레몬에이드"]
        menu_prices = {
            "아메리카노": 4500,
            "카페라떼": 5000,
            "카페모카": 5500,
            "바닐라라떼": 5500,
            "카라멜마끼아또": 5800,
            "초코라떼": 5000,
            "그린라떼": 5000,
            "복숭아아이스티": 5200,
            "허브티": 5000,
            "레몬에이드": 5500
        }
    
    # 결과 초기화
    items = []
    total = 0
    
    # 수량 매핑 (한글 -> 숫자)
    quantity_mapping = {
        "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, 
        "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
        "하나": 1, "둘": 2, "셋": 3, "넷": 4
    }
    
    # 수량 추출 함수
    def parse_quantity(text, menu_name=None):
        """메뉴의 수량 추출"""
        # 기본 수량은 1
        quantity = 1
        
        if menu_name:
            # "[메뉴] N잔" 같은 명시적 패턴 확인
            specific_pattern = rf'{menu_name}\s*(\d+)\s*잔'
            specific_match = re.search(specific_pattern, text)
            if specific_match:
                try:
                    quantity = int(specific_match.group(1))
                    logger.info(f"명시적 수량 감지: {menu_name} {quantity}잔 (숫자)")
                    return quantity
                except ValueError:
                    pass  # 변환 오류 시 다음 패턴 확인
            
            # "메뉴 한 잔" 형태 처리
            if f"{menu_name} 한 잔" in text or f"{menu_name} 한잔" in text or f"{menu_name}한잔" in text:
                logger.info(f"명시적 수량 감지: {menu_name} 1잔 (한 잔)")
                return 1
            
            # 한글 수량 표현 처리
            for num_word, value in quantity_mapping.items():
                pattern = rf'{menu_name}\s*{num_word}\s*잔'
                if re.search(pattern, text):
                    logger.info(f"한글 수량 감지: {menu_name} {value}잔 (한글)")
                    return value
                
                # 공백 없는 형태도 처리 ("아메리카노두잔")
                if f"{menu_name}{num_word}잔" in text:
                    logger.info(f"공백 없는 한글 수량 감지: {menu_name} {value}잔")
                    return value
            
            # 메뉴 반복 확인 (메뉴가 여러 번 언급되면 그 횟수를 수량으로)
            menu_count = len(re.findall(rf'\b{re.escape(menu_name)}\b', text))
            if menu_count > 1:
                logger.info(f"메뉴 반복 패턴 감지: {menu_name} {menu_count}잔")
                return menu_count
        
        # 일반 "N잔" 패턴 (메뉴와 무관하게)
        number_pattern = r'(\d+)\s*잔'
        number_match = re.search(number_pattern, text)
        if number_match:
            try:
                quantity = int(number_match.group(1))
                logger.info(f"일반 수량 감지: {quantity}잔")
                return quantity
            except ValueError:
                pass
        
        logger.info(f"기본 수량 적용: {menu_name if menu_name else '메뉴'} 1잔 (명시적 수량 없음)")
        return quantity
    
    # 모든 메뉴를 한 번에 찾기 (전체 텍스트에서 추출)
    # 메뉴 목록을 길이순으로 정렬 (긴 메뉴명 우선 매칭)
    sorted_menu_list = sorted(menu_list, key=len, reverse=True)
    
    # 모든 메뉴에 대해 검색
    for menu_name in sorted_menu_list:
        if menu_name in text:
            # 메뉴가 텍스트에 있으면 수량 추출
            quantity = parse_quantity(text, menu_name)
            
            # 아이스 옵션 확인
            is_ice = "아이스" in text.lower() or "ice" in text.lower()
            
            # 기본 가격
            base_price = menu_prices.get(menu_name, 4500)
            
            # 옵션 추출
            options = extract_options(text, menu_name, menu_options.get(menu_name, {}))
            
            # 옵션 가격 계산 - 아이스 옵션에 대한 추가 금액 제거
            option_price = calculate_option_price(options)
            # ICE 옵션 가격 제거 (있는 경우)
            if "Ice" in options:
                option_price = max(0, option_price - 500)  # 만약 ICE 옵션이 500원으로 계산되었다면 제거
            
            # 총 가격 계산
            item_price = base_price + option_price
            item_total = item_price * quantity
            
            # 장바구니 아이템 생성
            item = {
                "id": str(uuid.uuid4()),
                "name": menu_name,
                "quantity": quantity,
                "price": item_price,
                "base_price": base_price,
                "option_price": option_price,
                "options": options,
                "optionsText": ", ".join(options) if options else "",
                "total": item_total
            }
            
            # 장바구니에 추가
            items.append(item)
            total += item_total
            
            logger.info(f"텍스트에서 메뉴 '{menu_name}' 발견, 수량: {quantity}, 옵션: {options}")
    
    # 메뉴 추출 실패 시 패턴 매칭 시도 (기존 코드 유지)
    if not items:
        # 각 패턴에 대해 매칭 시도
        menu_quantity_patterns = [
            # "아메리카노 2잔" 패턴
            r'([가-힣]+(?:\s[가-힣]+)*)\s*(\d+)잔',
            # "2잔의 아메리카노" 패턴
            r'(\d+)잔의?\s*([가-힣]+(?:\s[가-힣]+)*)',
            # "아메리카노 두 잔" 패턴
            r'([가-힣]+(?:\s[가-힣]+)*)\s*([한두세네다섯여섯일곱여덟아홉열])\s*잔',
            # "두 잔의 아메리카노" 패턴
            r'([한두세네다섯여섯일곱여덟아홉열])\s*잔의?\s*([가-힣]+(?:\s[가-힣]+)*)'
        ]
        
        matched_menus = []
        
        for pattern in menu_quantity_patterns:
            matches = re.findall(pattern, text)
            if matches:
                for match in matches:
                    menu_name = ""
                    quantity = 1
                    
                    # 패턴에 따라 메뉴명과 수량 추출
                    if match[0].isdigit():
                        # "2잔의 아메리카노" 패턴
                        quantity = int(match[0])
                        menu_raw = match[1]
                    elif match[0] in quantity_mapping:
                        # "두 잔의 아메리카노" 패턴
                        quantity = quantity_mapping.get(match[0], 1)
                        menu_raw = match[1]
                    elif match[1].isdigit():
                        # "아메리카노 2잔" 패턴
                        menu_raw = match[0]
                        quantity = int(match[1])
                    else:
                        # "아메리카노 두 잔" 패턴
                        menu_raw = match[0]
                        quantity = quantity_mapping.get(match[1], 1)
                    
                    # 메뉴명 정규화
                    menu_name = find_closest_menu(menu_raw, menu_list)
                    
                    if menu_name and menu_name not in matched_menus:
                        matched_menus.append(menu_name)
                        
                        # 기본 가격
                        price = menu_prices.get(menu_name, 4500)
                        
                        # 옵션 추출
                        options = extract_options(text, menu_name, menu_options.get(menu_name, {}))
                        
                        # 옵션 가격 계산
                        option_price = calculate_option_price(options)
                        
                        # 총 가격 계산
                        item_price = price + option_price
                        item_total = item_price * quantity
                        
                        # 장바구니 아이템 생성
                        item = {
                            "id": str(uuid.uuid4()),
                            "name": menu_name,
                            "quantity": quantity,
                            "price": item_price,
                            "base_price": price,
                            "option_price": option_price,
                            "options": options,
                            "optionsText": ", ".join(options) if options else "",
                            "total": item_total
                        }
                        
                        items.append(item)
                        total += item_total
    
    logger.info(f"추출된 주문: {items}, 총액: {total}원")

    result = {
        "items": items,
        "total": total,
        "extraction_success": len(items) > 0
    }
    
    # 결과 캐싱
    _last_extraction_text = text
    _last_extraction_result = result
    
    return result

@router.get("/start-continuous-dialog")
async def start_continuous_dialog_get(
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """웹 브라우저에서 연속 대화 세션 시작 (GET 메서드)"""
    return await start_continuous_dialog(kiosk_service)

# 연속 대화 세션 시작 엔드포인트
@router.post("/start-continuous-dialog")
async def start_continuous_dialog(
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """연속 대화 세션 시작"""
    try:
        logger.info("연속 대화 세션 시작 요청 수신")
        
        # 대화 서비스가 없는 경우 초기화
        if not hasattr(kiosk_service, 'dialog_service') or kiosk_service.dialog_service is None:
            logger.warning("대화 서비스가 초기화되지 않았습니다. 새로 초기화합니다.")
            # 적절한 대화 서비스 초기화 코드
            from app.services.enhanced_continuous_dialog_service import EnhancedContinuousDialogService
            kiosk_service.dialog_service = EnhancedContinuousDialogService(
                kiosk_service=kiosk_service,
                openai_api_key=kiosk_service.openai_api_key
            )
        
        # 세션 시작 콜백 정의
        async def on_session_start():
            logger.info("대화 세션이 시작되었습니다.")
            
        # 세션 종료 콜백 정의
        async def on_session_end(result):
            logger.info(f"대화 세션이 종료되었습니다. 결과: {result.get('success', False)}")
            
        # 음성 감지 콜백 정의
        async def on_speech_detected():
            logger.info("음성이 감지되었습니다.")
            
        # 응답 시작 콜백 정의
        async def on_response_start(text):
            logger.info(f"응답 시작: '{text}'")
            
        # 응답 종료 콜백 정의
        async def on_response_end(audio_path):
            logger.info(f"응답 종료: {audio_path}")
        
        # 콜백 함수를 전달하여 대화 세션 시작
        session_result = await kiosk_service.dialog_service.start_dialog_session(
            on_session_start=on_session_start,
            on_session_end=on_session_end,
            on_speech_detected=on_speech_detected,
            on_response_start=on_response_start,
            on_response_end=on_response_end
        )
        
        return {
            "success": session_result.get("success", False),
            "message": "연속 대화 세션이 시작되었습니다.",
            "conversation_id": kiosk_service.conversation_id,
            "session_details": session_result
        }
    except Exception as e:
        logger.error(f"연속 대화 세션 시작 실패: {str(e)}", exc_info=True)
        return {
            "success": False, 
            "message": f"연속 대화 세션 시작 중 오류 발생: {str(e)}",
            "conversation_id": None
        }

# 연속 대화 세션 중지 엔드포인트
@router.post("/stop-continuous-dialog")
async def stop_continuous_dialog(
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """연속 대화 세션 중지"""
    try:
        # 현재 대화 세션 중지
        result = await kiosk_service.stop_continuous_dialog()
        
        return {
            "success": result,
            "message": "연속 대화 세션이 중지되었습니다." if result else "활성화된 세션이 없습니다."
        }
    except Exception as e:
        logger.error(f"대화 세션 중지 실패: {str(e)}")
        return {
            "success": False, 
            "message": f"대화 세션 중지 중 오류 발생: {str(e)}"
        }

# 대화 상태 확인 엔드포인트
@router.get("/state")
async def get_conversation_state(
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """현재 대화 상태 정보 반환"""
    try:
        return {
            "success": True,
            "current_state": kiosk_service.pipeline_service.current_state
        }
    except Exception as e:
        logger.error(f"대화 상태 조회 실패: {str(e)}")
        return {
            "success": False, 
            "current_state": None,
            "error": str(e)
        }

# 키오스크 초기화 엔드포인트
@router.post("/initialize")
async def initialize_kiosk(
    request: Request,
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """키오스크 초기화"""
    try:
        # 요청 본문 파싱
        body_bytes = await request.body()
        body_dict = json.loads(body_bytes) if body_bytes else {}
        
        # 선택적 파라미터 추출
        device_id = body_dict.get("device_id")
        location = body_dict.get("location")
        force_reinitialize = body_dict.get("force_reinitialize", False)
        
        # 키오스크 서비스를 통한 초기화
        result = await kiosk_service.initialize(
            device_id=device_id, 
            location=location, 
            force_reinitialize=force_reinitialize
        )
        
        # 표준화된 응답 구조
        return {
            "success": True,
            "device_id": result.get("device_id") or str(uuid.uuid4()),
            "conversation_id": result.get("device_id") or str(uuid.uuid4()),
            "status": result.get("status", "success"),
            "ready": result.get("ready", True),
            "greeting_text": "안녕하세요, 카페에 오신 것을 환영합니다. 무엇을 도와드릴까요?"
        }
    
    except Exception as e:
        logger.error(f"키오스크 초기화 실패: {str(e)}")
        
        # 실패 시 폴백 응답
        fallback_id = str(uuid.uuid4())
        return {
            "success": False,
            "device_id": fallback_id,
            "conversation_id": fallback_id,
            "status": "error",
            "ready": False,
            "error_message": str(e)
        }

# 인사말 생성 및 재생 엔드포인트
@router.post("/greet")
async def greet_customer(
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """고객 인사말 생성 및 재생"""
    try:
        result = await kiosk_service.greet_customer()
        return {
            "success": True,
            "text": result.get("text", ""),
            "audio_path": result.get("audio_path", "")
        }
    except Exception as e:
        logger.error(f"인사말 생성 실패: {str(e)}")
        return {
            "success": False,
            "text": "안녕하세요. 어서오세요.",
            "audio_path": None,
            "error": str(e)
        }


# 오디오 장치 관련 엔드포인트
@router.get("/audio-devices")
async def list_audio_devices() -> Dict[str, Any]:
    """사용 가능한 오디오 장치 목록 조회"""
    try:
        devices = audio_device_service.list_devices()
        return {
            "success": True,
            "devices": devices
        }
    except Exception as e:
        logger.error(f"오디오 장치 목록 조회 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# 진단 엔드포인트
@router.get("/diagnostic")
async def diagnostic_check(
    kiosk_service: KioskService = Depends(get_kiosk_service)
) -> Dict[str, Any]:
    """시스템 진단 정보 제공"""
    try:
        # 현재 서비스 상태 확인
        pipeline_service = kiosk_service.pipeline_service
        
        return {
            "status": "running",
            "conversation_id": kiosk_service.conversation_id,
            "current_state": pipeline_service.current_state,
            "services": {
                "stt": kiosk_service.stt_service is not None,
                "tts": kiosk_service.tts_service is not None,
                "rag": kiosk_service.rag_service is not None and kiosk_service.rag_service.is_initialized,
                "gpt": kiosk_service.openai_api_key is not None
            },
            "audio_devices": audio_device_service.list_devices()
        }
    except Exception as e:
        logger.error(f"진단 정보 조회 실패: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }