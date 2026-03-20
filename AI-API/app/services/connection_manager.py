import logging
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket
import copy
import time

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._last_cart_update_time = 0
        self._last_cart_update_content = None

    async def connect(self, websocket: WebSocket, log_message: str = "새로운 WebSocket 연결 추가"):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"{log_message}. 현재 총 {len(self.active_connections)}개 연결")

    def disconnect(self, websocket: WebSocket, log_message: str = "WebSocket 연결 해제"):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"{log_message}. 남은 연결: {len(self.active_connections)}개")

    async def broadcast(self, message: dict):
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"클라이언트 알림 중 오류: {str(e)}")
                disconnected_clients.append(connection)

        for client in disconnected_clients:
            self.disconnect(client, "오류로 인한 연결 해제")

manager = ConnectionManager()
