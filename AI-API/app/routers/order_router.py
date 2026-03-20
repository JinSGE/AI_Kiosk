from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime
import uuid

router = APIRouter()

# 임시 주문 저장소 (실제 프로덕션에서는 데이터베이스 사용)
orders_db = {}

@router.post("")
async def create_order(order_data: Dict[str, Any]):
    """
    주문 생성 엔드포인트
    """
    try:
        # 주문 번호 생성 (UUID 사용)
        order_id = str(uuid.uuid4())
        
        # 주문 데이터 저장
        order = {
            "_id": order_id,
            **order_data,
            "created_at": datetime.now().isoformat(),
            "status": order_data.get('status', '접수')
        }
        
        # 주문 저장
        orders_db[order_id] = order
        
        return {
            "_id": order_id,
            "status": "success",
            "message": "주문이 성공적으로 접수되었습니다."
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"주문 생성 중 오류 발생: {str(e)}"
        )

@router.post("/{order_id}/payment")
async def process_payment(
    order_id: str, 
    payment_method: Dict[str, str]
):
    """
    결제 처리 엔드포인트
    """
    try:
        # 주문 존재 여부 확인
        if order_id not in orders_db:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
        # 주문 상태 업데이트
        order = orders_db[order_id]
        order['payment_method'] = payment_method.get('method', '')
        order['payment_status'] = '완료'
        
        return {
            "status": "success",
            "message": "결제가 성공적으로 처리되었습니다.",
            "order_id": order_id
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"결제 처리 중 오류 발생: {str(e)}"
        )

@router.get("/{order_id}")
async def get_order_details(order_id: str):
    """
    주문 상세 정보 조회
    """
    try:
        if order_id not in orders_db:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
        return orders_db[order_id]
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"주문 정보 조회 중 오류 발생: {str(e)}"
        )