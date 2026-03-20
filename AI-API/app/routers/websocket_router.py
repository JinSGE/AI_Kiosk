from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio
import uuid
import time
import copy  

# Connection Manager import
from app.services.connection_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket 의존성
async def get_active_connections():
    return manager.active_connections

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        # 초기 상태 정보 전송
        from app.models.fsm import fsm
        current_state = fsm.current_state
        await websocket.send_json({
            "type": "state_update",
            "state": str(current_state),
            "message": fsm.get_response(current_state, {}),
            "context": {}
        })
        
        # 클라이언트로부터 메시지 대기
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                logger.info(f"WebSocket 메시지 수신: {message}")
                
                # 메시지 유형에 따라 처리
                if message.get("action") == "change_state":
                    # FSM 상태 변경 요청
                    from app.models.fsm import fsm
                    
                    state = message.get("state", "")
                    slots = message.get("slots", {})
                    
                    if state:
                        try:
                            current_state = fsm.current_state
                            fsm.current_state = state
                            response = fsm.get_response(state, slots)
                            
                            # 상태 변경 알림
                            await notify_clients(str(state), response, slots)
                            logger.info(f"클라이언트 요청으로 상태 변경: {current_state} -> {state}")
                            
                            # 요청 성공 응답
                            await websocket.send_json({
                                "type": "state_changed",
                                "success": True,
                                "state": str(state),
                                "message": response
                            })
                        except Exception as e:
                            logger.error(f"상태 변경 중 오류: {str(e)}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"상태 변경 중 오류: {str(e)}"
                            })
                
                elif message.get("action") == "process_text":
                    # 텍스트 처리 요청
                    text = message.get("text", "")
                    
                    if text:
                        try:
                            from app.services.nlp_processor import extract_intent_and_slots
                            from app.models.fsm import fsm
                            
                            nlp_result = extract_intent_and_slots(text)
                            intent = nlp_result.get("intent", "unknown")
                            slots = nlp_result.get("slots", {})
                            
                            current_state = fsm.current_state
                            next_state = fsm.get_next_state(current_state, intent, slots)
                            fsm.current_state = next_state
                            
                            response_message = fsm.get_response(next_state, slots)
                            
                            await notify_clients(str(next_state), response_message, slots)
                            logger.info(f"텍스트 처리: '{text}' -> 의도: {intent}, 상태 변경: {current_state} -> {next_state}")
                            
                            await websocket.send_json({
                                "type": "text_processed",
                                "success": True,
                                "state": str(next_state),
                                "message": response_message,
                                "context": slots
                            })
                        except Exception as e:
                            logger.error(f"텍스트 처리 중 오류: {str(e)}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"텍스트 처리 중 오류: {str(e)}"
                            })
                
                elif message.get("action") == "payment_complete":
                    try:
                        logger.info("결제 완료 메시지 수신, 세션 초기화 시작")
                        
                        from app.main import get_kiosk_service
                        kiosk_service = get_kiosk_service()
                        
                        reset_result = await kiosk_service.reset_conversation(full_reset=True)
                        completion_message = "주문이 접수되었습니다. 잠시만 기다려주시면 음료를 준비해 드리겠습니다. 감사합니다."
                        
                        tts_result = await kiosk_service.tts_service.synthesize(
                            completion_message,
                            play_audio=True
                        )
                        
                        await notify_cart_reset()
                        
                        # 클라이언트에 결제 완료 알림
                        await notify_payment_completed(
                            message=completion_message,
                            audio_path=tts_result.get("audio_path", ""),
                            reset_success=reset_result.get("success", False)
                        )
                        
                        # 초기 상태로 변경 알림
                        await notify_clients("start", "안녕하세요, 새로운 주문을 시작하실 수 있습니다.", {})
                        
                        await websocket.send_json({
                            "type": "payment_completed",
                            "success": True,
                            "message": "결제가 완료되었습니다. 초기화되었습니다."
                        })
                    except Exception as e:
                        logger.error(f"결제 완료 처리 중 오류: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"결제 완료 처리 중 오류: {str(e)}"
                        })
                
            except json.JSONDecodeError:
                logger.error("유효하지 않은 JSON 메시지")
                await websocket.send_json({
                    "type": "error",
                    "message": "유효하지 않은 JSON 형식"
                })
            except Exception as e:
                logger.error(f"메시지 처리 중 오류: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"메시지 처리 중 오류: {str(e)}"
                })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 통신 중 오류: {str(e)}")
        manager.disconnect(websocket, "오류로 인한 연결 해제")

# 장바구니 데이터 추가
@router.websocket("/ws/cart")
async def cart_websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket, "새로운 장바구니 WebSocket 연결 추가")
    
    try:
        await websocket.send_json({
            "type": "cart_update",
            "items": [],
            "total": 0
        })
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                logger.info(f"장바구니 WebSocket 메시지 수신: {message}")
                
                if message.get("action") == "add_to_cart":
                    item = message.get("item", {})
                    await manager.broadcast({
                        "type": "cart_update",
                        "operation": "add",
                        "item": item
                    })
                
                elif message.get("action") == "remove_from_cart":
                    item_id = message.get("item_id")
                    await manager.broadcast({
                        "type": "cart_update",
                        "operation": "remove",
                        "item_id": item_id
                    })
                
                elif message.get("action") == "payment_complete":
                    try:
                        logger.info("장바구니 결제 완료 메시지 수신, 세션 초기화 시작")
                        
                        from app.main import get_kiosk_service
                        kiosk_service = get_kiosk_service()
                        
                        if hasattr(kiosk_service, 'dialog_service') and kiosk_service.dialog_service:
                            await kiosk_service.dialog_service.stop_dialog_session()
                            logger.info("결제 완료 후 기존 대화 세션 강제 종료 완료")
                        
                        await kiosk_service.reset_conversation(full_reset=True)
                        logger.info("대화 컨텍스트 및 인사말 플래그 초기화 완료")
                        
                        await notify_cart_reset()
                        logger.info("클라이언트에 장바구니 초기화 신호 전송 완료")
                        
                        complete_message = "주문이 완료되었습니다. 음료가 준비되면 호출해 드리겠습니다."
                        
                        tts_result = await kiosk_service.tts_service.synthesize(
                            complete_message,
                            play_audio=True
                        )
                        
                        await notify_payment_completed(
                            message=complete_message,
                            audio_path=tts_result.get("audio_path", "")
                        )
                        
                        await asyncio.sleep(1.0)
                        
                        asyncio.create_task(start_new_dialog_session(kiosk_service))
                        
                        await websocket.send_json({
                            "type": "payment_completed",
                            "success": True,
                            "message": "결제가 완료되었습니다. 시스템이 초기화되었습니다."
                        })
                    except Exception as e:
                        logger.error(f"결제 완료 처리 중 오류: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"결제 완료 처리 중 오류: {str(e)}"
                        })

                elif message.get("action") == "reset_session":
                    try:
                        logger.info("세션 완전 초기화 요청")
                        
                        from app.main import get_kiosk_service
                        kiosk_service = get_kiosk_service()
                        
                        full_reset = message.get("full_reset", False)
                        reset_result = await kiosk_service.reset_conversation(full_reset=full_reset)
                        
                        await websocket.send_json({
                            "type": "session_reset",
                            "success": reset_result.get("success", False)
                        })
                    except Exception as e:
                        logger.error(f"세션 초기화 중 오류: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"세션 초기화 중 오류: {str(e)}"
                        })

                elif message.get("action") == "request_greeting":
                    try:
                        logger.info("인사말 요청")
                        
                        from app.main import get_kiosk_service
                        kiosk_service = get_kiosk_service()
                        
                        force_new = message.get("force_new", False)
                        greeting_result = await kiosk_service.greet_customer(force_new=force_new)
                        
                        await websocket.send_json({
                            "type": "greeting_response",
                            "success": True,
                            "text": greeting_result.get("text", ""),
                            "audio_path": greeting_result.get("audio_path", "")
                        })
                    except Exception as e:
                        logger.error(f"인사말 생성 중 오류: {str(e)}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"인사말 생성 중 오류: {str(e)}"
                        })
                        
            except json.JSONDecodeError:
                logger.error("유효하지 않은 JSON 메시지")
            except Exception as e:
                logger.error(f"메시지 처리 중 오류: {str(e)}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, "장바구니 WebSocket 연결 해제")

# 유틸리티 함수들
# 알림 기능은 app.services.notification_service로 이전됨
from app.services.notification_service import (
    notify_order_processed,
    notify_cart_update,
    notify_menu_loading,
    notify_cart_reset,
    notify_clients,
    notify_payment_completed
)


async def start_new_dialog_session(kiosk_service):
    try:
        await asyncio.sleep(2.0)
        async def on_session_start(): logger.info("결제 후 새 대화 세션이 시작되었습니다.")
        async def on_session_end(result): logger.info(f"대화 세션이 종료되었습니다. 결과: {result.get('success', False)}")
        async def on_speech_detected(): logger.info("음성이 감지되었습니다.")
        async def on_response_start(text): pass
        async def on_response_end(audio_path): logger.info(f"응답 종료: {audio_path}")
        
        await kiosk_service.dialog_service.start_dialog_session(
            on_session_start=on_session_start,
            on_session_end=on_session_end,
            on_speech_detected=on_speech_detected,
            on_response_start=on_response_start,
            on_response_end=on_response_end
        )
        logger.info("결제 완료 후 새 대화 세션 시작 완료")
    except Exception as e:
        logger.error(f"새 대화 세션 시작 중 오류 발생: {str(e)}")