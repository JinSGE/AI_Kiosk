# app/services/__init__.py
#
# 서비스 패키지 초기화 파일
# 실제 서비스 인스턴스는 app/main.py의 ServiceManager에서 관리됩니다.
# 외부에서 서비스가 필요한 경우 app.main의 get_*_service() 함수를 통해 의존성 주입을 받으세요.
#
# 예시:
#   from app.main import get_kiosk_service
#   @router.post("/endpoint")
#   async def my_endpoint(kiosk_service: KioskService = Depends(get_kiosk_service)):
#       ...

import logging

logger = logging.getLogger(__name__)

__all__ = []