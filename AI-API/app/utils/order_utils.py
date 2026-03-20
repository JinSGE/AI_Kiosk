"""
주문 정보 추출 및 메뉴 관련 유틸리티 함수들
"""
import re
import uuid
import logging
from typing import Dict, Any, List, Optional
from app.services.nlp_processor import MENU_DATA

logger = logging.getLogger(__name__)

def parse_quantity(text: str, menu_name: Optional[str] = None) -> int:
    """텍스트에서 메뉴의 수량 추출"""
    quantity = 1
    
    if menu_name:
        # "[메뉴] N잔" 같은 명시적 패턴 확인
        specific_pattern = rf'{menu_name}\s*(\d+)\s*잔'
        specific_match = re.search(specific_pattern, text)
        if specific_match:
            try:
                quantity = int(specific_match.group(1))
                return quantity
            except ValueError:
                pass
        
        # "메뉴 한 잔" 형태 처리
        if f"{menu_name} 한 잔" in text or f"{menu_name} 한잔" in text or f"{menu_name}한잔" in text:
            return 1

    # 수량 매핑 (한글 -> 숫자)
    quantity_mapping = {
        "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, 
        "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
        "하나": 1, "둘": 2, "셋": 3, "넷": 4
    }
    
    # "N잔" 형태 확인
    count_match = re.search(r'(\d+)\s*잔', text)
    if count_match:
        try:
            return int(count_match.group(1))
        except ValueError:
            pass
            
    # 한글 수량 확인
    for kor, num in quantity_mapping.items():
        if f"{kor} 잔" in text or f"{kor}잔" in text:
            return num
            
    return quantity

def extract_order_info(text: str, menu_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    응답 텍스트에서 주문 정보를 추출하여 장바구니 형태로 반환
    """
    if not menu_data:
        menu_data = MENU_DATA

    items = []
    total_price = 0
    
    # 메뉴 목록
    available_menus = [m["name"] for m in menu_data.get("menus", [])]
    
    # 텍스트에서 각 메뉴 찾기
    for menu_name in available_menus:
        if menu_name in text:
            quantity = parse_quantity(text, menu_name)
            
            # 메뉴 정보 찾기
            menu_info = next((m for m in menu_data.get("menus", []) if m["name"] == menu_name), None)
            price = menu_info.get("basePrice", 4500) if menu_info else 4500
            
            # 항목 추가
            item_total = price * quantity
            items.append({
                "id": str(uuid.uuid4()),
                "name": menu_name,
                "quantity": quantity,
                "price": price,
                "total": item_total,
                "options": ["Ice", "Small"], # 기본 옵션
                "optionsText": "Ice, Small"
            })
            total_price += item_total
            
    return {
        "items": items,
        "total": total_price,
        "text": text
    }

def update_cart_with_merge(existing_items: List[Dict], new_items: List[Dict]) -> tuple:
    """
    기존 장바구니에 새 아이템을 추가하되, 중복 메뉴는 수량 증가로 처리
    """
    import copy
    updated_items = copy.deepcopy(existing_items) if existing_items else []
    updated = False
    
    for new_item in new_items:
        menu_name = new_item['name']
        quantity = new_item['quantity']
        
        found = False
        for item in updated_items:
            if item['name'] == menu_name:
                item['quantity'] += quantity
                item['total'] = item['price'] * item['quantity']
                found = True
                updated = True
                break
        
        if not found:
            updated_items.append(copy.deepcopy(new_item))
            updated = True
    
    total = sum(item['total'] for item in updated_items)
    return updated_items, total, updated
