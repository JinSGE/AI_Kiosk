# app/routers/fsm_router.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.models.fsm import fsm as fsm_instance
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fsm",
    tags=["fsm"],
)

class StateUpdateRequest(BaseModel):
    state: str
    slots: Optional[Dict[str, Any]] = None

class ProcessInputRequest(BaseModel):
    text: str

class StateResponse(BaseModel):
    state: str
    message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

@router.get("/state")
async def get_state():
    """현재 FSM 상태 조회"""
    current_state = fsm_instance.current_state
    response = fsm_instance.get_response(current_state, {})
    
    return {
        "state": current_state,
        "message": response
    }

@router.post("/state")
async def set_state(request: StateUpdateRequest):
    """FSM 상태 수동 업데이트"""
    try:
        state_name = request.state
        current_state = fsm_instance.current_state
        
        # 상태 업데이트
        fsm_instance.current_state = state_name
        
        # 응답 메시지 생성
        response_message = fsm_instance.get_response(state_name, request.slots or {})
        
        # WebSocket으로 상태 변경 알림
        try:
            from app.services.notification_service import notify_state_update
            await notify_state_update(state_name, response_message, request.slots or {})
        except Exception as e:
            logger.error(f"WebSocket 알림 중 오류: {str(e)}")
        
        logger.info(f"FSM 상태 수동 업데이트: {current_state} -> {state_name}")
        
        return {
            "success": True, 
            "state": state_name,
            "message": response_message
        }
    except Exception as e:
        logger.error(f"상태 업데이트 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=400, detail=f"상태 업데이트 중 오류: {str(e)}")

@router.post("/process", response_model=StateResponse)
async def process_input(request: ProcessInputRequest):
    """사용자 입력 처리 및 FSM 상태 업데이트"""
    try:
        # 텍스트 처리 로직
        from app.services.nlp_processor import extract_intent_and_slots
        
        # 의도 및 슬롯 추출
        nlp_result = extract_intent_and_slots(request.text)
        intent = nlp_result.get("intent", "unknown")
        slots = nlp_result.get("slots", {})
        
        # 현재 상태
        current_state = fsm_instance.current_state
        
        # 다음 상태 결정
        next_state = fsm_instance.get_next_state(current_state, intent, slots)
        
        # FSM 상태 업데이트
        fsm_instance.current_state = next_state
        
        # 응답 메시지 생성
        response_message = fsm_instance.get_response(next_state, slots)
        
        # WebSocket으로 상태 변경 알림
        try:
            from app.services.notification_service import notify_state_update
            await notify_state_update(next_state, response_message, slots)
        except Exception as e:
            logger.error(f"WebSocket 알림 중 오류: {str(e)}")
        
        logger.info(f"텍스트 처리: '{request.text}' -> 의도: {intent}, 상태 변경: {current_state} -> {next_state}")
        
        return {
            "state": next_state,
            "message": response_message,
            "context": slots
        }
    except Exception as e:
        logger.error(f"입력 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_fsm():
    """FSM 상태 초기화"""
    try:
        # 초기 상태 저장
        initial_state = "start"
        
        # 상태 리셋
        fsm_instance.reset()
        
        # WebSocket으로 상태 변경 알림
        try:
            from app.services.notification_service import notify_state_update
            await notify_state_update(initial_state, '안녕하세요, 카페에 오신 것을 환영합니다. 무엇을 도와드릴까요?', {})
        except Exception as e:
            logger.error(f"WebSocket 알림 중 오류: {str(e)}")
        
        return {"status": "success", "message": "FSM이 초기화되었습니다."}
    except Exception as e:
        logger.error(f"FSM 초기화 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))