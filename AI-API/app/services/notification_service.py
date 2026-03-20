"""
WebSocket을 통한 클라이언트 알림 서비스
"""
import logging
import time
import copy
from typing import Dict, Any, Optional
from app.services.connection_manager import manager

logger = logging.getLogger(__name__)

async def notify_order_processed(order_data: Dict[str, Any]):
    """음성 주문 처리 결과 알림"""
    notification = {
        "type": "order_processed",
        "data": order_data
    }
    logger.info(f"음성 주문 처리 결과 알림: {order_data}")
    await manager.broadcast(notification)

async def notify_cart_update(order_data: Dict[str, Any]):
    """장바구니 업데이트 알림 (중복 방지 포함)"""
    current_time = time.time()
    
    def _is_same_cart_content(cart1, cart2):
        if not cart1 or not cart2: return False
        if cart1.get("total") != cart2.get("total"): return False
        items1 = cart1.get("items", [])
        items2 = cart2.get("items", [])
        if len(items1) != len(items2): return False
        menu_counts1 = {item["name"]: item["quantity"] for item in items1}
        menu_counts2 = {item["name"]: item["quantity"] for item in items2}
        return menu_counts1 == menu_counts2

    if isinstance(order_data, list):
        items = order_data
        total = sum(item.get("total", 0) for item in items)
        order_data = {"items": items, "total": total}
    
    if (manager._last_cart_update_content and 
        current_time - manager._last_cart_update_time < 3.0 and
        _is_same_cart_content(manager._last_cart_update_content, order_data)):
        logger.info("중복 장바구니 업데이트 감지, 알림 생략")
        return
        
    manager._last_cart_update_time = current_time
    manager._last_cart_update_content = copy.deepcopy(order_data)

    notification = {
        "type": "cart_update",
        "operation": "add",
        "items": order_data.get("items", []),
        "total": order_data.get("total", 0)
    }
    
    # 추가 필드 (is_additional, is_multi_menu 등) 포함
    for key in ["is_additional", "is_multi_menu", "cleared"]:
        if key in order_data:
            notification[key] = order_data[key]
            
    logger.info(f"장바구니 업데이트 알림: {notification}")
    await manager.broadcast(notification)

async def notify_menu_loading(menu_data: Dict[str, Any]):
    """메뉴 로딩 알림"""
    notification = {
        "type": "load_menu",
        "message": "메뉴를 먼저 불러옵니다",
        "menu_data": menu_data
    }
    logger.info("모든 클라이언트에 메뉴 로딩 알림")
    await manager.broadcast(notification)

async def notify_cart_reset():
    """장바구니 초기화 알림"""
    notification = {
        "type": "cart_update",
        "operation": "reset",
        "items": [],
        "total": 0
    }
    logger.info("장바구니 초기화 알림")
    await manager.broadcast(notification)

async def notify_state_update(state: str, message: str, context: Dict[str, Any] = None):
    """FSM 상태 변경 알림"""
    if context is None:
        context = {}
    notification = {
        "type": "state_update",
        "state": str(state),
        "message": message,
        "context": context
    }
    logger.info(f"상태 변경 알림: {state}, 메시지: {message}")
    await manager.broadcast(notification)

async def notify_payment_completed(message: str, audio_path: str = "", reset_success: Optional[bool] = None):
    """결제 완료 알림"""
    notification = {
        "type": "payment_completed",
        "message": message,
        "audio_path": audio_path
    }
    if reset_success is not None:
        notification["reset_success"] = reset_success
    logger.info("결제 완료 알림")
    await manager.broadcast(notification)
