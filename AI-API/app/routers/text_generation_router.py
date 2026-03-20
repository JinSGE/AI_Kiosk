from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Dict, Any
import logging

from app.models.text_generation import TextGenerationModel, text_model 
from app.services.text_generation_service import TextGenerationService

logger = logging.getLogger(__name__)

router = APIRouter()

# ChatMessage 클래스 정의
class ChatMessage(BaseModel):
    role: str = Field(..., description="메시지 작성자 역할 (system, user, assistant)")
    content: str = Field(..., description="메시지 내용")

# TextGenerationResponse 클래스 정의
class TextGenerationResponse(BaseModel):
    generated_texts: List[str] = Field(..., description="생성된 텍스트 목록")
    prompt: str = Field(..., description="원본 프롬프트")
    is_order_mode: bool = Field(False, description="주문 처리 모드 사용 여부")

# ChatResponse 클래스 정의
class ChatResponse(BaseModel):
    response: str = Field(..., description="AI 응답 메시지")
    conversation_id: Optional[str] = Field(None, description="대화 세션 ID (옵션)")

# 서비스 의존성 주입 함수
def get_text_generation_service():
    return TextGenerationService(text_model)

# 요청 모델 (max_length 상한선 증가)
class TextGenerationRequest(BaseModel):
    prompt: str = Field(..., description="생성할 텍스트의 프롬프트")
    max_length: Optional[int] = Field(1024, description="생성할 최대 토큰 수", ge=1, le=4096)  # 상한선 대폭 증가
    temperature: Optional[float] = Field(0.7, description="생성 다양성 (0.0-1.0)", ge=0.0, le=1.0)
    top_p: Optional[float] = Field(0.95, description="Nucleus 샘플링 파라미터", ge=0.0, le=1.0)  # 약간 조정
    top_k: Optional[int] = Field(100, description="상위 k개 토큰 선택", ge=1, le=200)  # 상한선 증가
    repetition_penalty: Optional[float] = Field(1.1, description="반복 페널티", ge=1.0, le=2.0)  # 약간 완화
    num_return_sequences: Optional[int] = Field(1, description="반환할 생성 결과 수", ge=1, le=5)
    is_order: Optional[bool] = Field(True, description="카페 주문 처리 모드 활성화")
    
    @validator('prompt')
    def prompt_not_empty(cls, v):
        if not v.strip():
            raise ValueError('프롬프트는 비어있을 수 없습니다')
        return v

# 채팅 요청 모델 (max_length 상한선 증가)
class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="대화 메시지 목록")
    temperature: Optional[float] = Field(0.7, description="생성 다양성 (0.0-1.0)", ge=0.0, le=1.0)
    max_length: Optional[int] = Field(1024, description="생성할 최대 토큰 수", ge=1, le=4096)  # 상한선 대폭 증가
    
    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "system", "content": "당신은 카페 키오스크 시스템입니다."},
                    {"role": "user", "content": "아메리카노 한 잔이랑 카페라떼 한 잔 주세요"}
                ],
                "temperature": 0.7
            }
        }

# 텍스트 생성 엔드포인트 수정
@router.post("/generate-text", response_model=TextGenerationResponse, tags=["Text Generation"])
async def generate_text(
    request: TextGenerationRequest,
    service: TextGenerationService = Depends(get_text_generation_service)
):
    try:
        logger.info(f"텍스트 생성 요청 수신: {request.prompt[:50]}... (주문 모드: {request.is_order})")
        
        # 카페 주문 감지 패턴
        order_patterns = ["주세요", "주문", "메뉴", "커피", "아메리카노", "라떼", "카페","티","마끼아또","에이드"]
        detected_as_order = any(pattern in request.prompt for pattern in order_patterns)
        
        # 명시적 설정 또는 자동 감지 기반 주문 모드 사용
        use_order_mode = request.is_order or detected_as_order
        
        # 주문 모드일 경우 파라미터 조정
        if use_order_mode:
            temperature = min(request.temperature, 0.6)  # 약간 완화
        else:
            temperature = request.temperature
        
        generated_texts = service.generate_text(
            prompt=request.prompt,
            max_length=request.max_length,
            temperature=temperature,
            top_p=0.95,  # 고정된 높은 top_p
            top_k=100,  # 토큰 선택 범위 확대
            repetition_penalty=1.1,  # 반복 페널티 완화
            num_return_sequences=request.num_return_sequences,
            is_order=use_order_mode,
            use_dialog=False  # 단일 응답 모드 사용
        )
        
        return TextGenerationResponse(
            generated_texts=generated_texts,
            prompt=request.prompt,
            is_order_mode=use_order_mode
        )
        
    except Exception as e:
        logger.error(f"텍스트 생성 처리 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"텍스트 생성 처리 중 오류 발생: {str(e)}")

# 카페 주문 전용 엔드포인트 수정
@router.post("/cafe-order", response_model=TextGenerationResponse, tags=["Cafe Ordering"])
async def process_cafe_order(
    request: TextGenerationRequest,
    service: TextGenerationService = Depends(get_text_generation_service)
):
    try:
        logger.info(f"카페 주문 요청 수신: {request.prompt[:50]}...")
        
        # 카페 주문에 최적화된 파라미터 사용
        generated_texts = service.generate_text(
            prompt=request.prompt,
            max_length=512,  # 최대 길이 대폭 증가
            temperature=0.6,  # 약간 높은 다양성 유지
            top_p=0.95,
            top_k=100,
            repetition_penalty=1.1,
            num_return_sequences=1,
            is_order=True,  # 명시적으로 주문 모드 활성화
            use_dialog=False  # 단일 응답 모드
        )
        
        return TextGenerationResponse(
            generated_texts=generated_texts,
            prompt=request.prompt,
            is_order_mode=True
        )
        
    except Exception as e:
        logger.error(f"카페 주문 처리 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"카페 주문 처리 중 오류 발생: {str(e)}")

# 대화형 채팅 엔드포인트 수정
@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    request: ChatRequest,
    service: TextGenerationService = Depends(get_text_generation_service)
):
    try:
        logger.info(f"대화 요청 수신: {len(request.messages)} 메시지")
        
        # 대화 메시지에서 마지막 사용자 메시지 추출
        last_user_message = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                last_user_message = msg.content
                break
        
        if not last_user_message:
            raise HTTPException(status_code=400, detail="사용자 메시지가 없습니다")
        
        # 대화 이력 설정 (서비스에서 관리)
        if hasattr(service.model, 'conversation_history'):
            # 모델의 대화 이력 초기화
            service.model.conversation_history = []
            
            # 시스템 메시지 추가
            system_messages = [msg for msg in request.messages if msg.role == "system"]
            if system_messages:
                for system_msg in system_messages:
                    service.model.conversation_history.append({
                        "role": "system", 
                        "content": system_msg.content
                    })
            else:
                # 기본 시스템 메시지 추가
                service.model.conversation_history.append({
                    "role": "system", 
                    "content": "당신은 카페 키오스크 시스템입니다. 고객의 주문을 정확히 확인하고 응답하세요."
                })
            
            # 사용자 및 어시스턴트 메시지 추가 (마지막 사용자 메시지 제외)
            for i, msg in enumerate(request.messages):
                if msg.role in ["user", "assistant"]:
                    if msg.role == "user" and i == len(request.messages) - 1:
                        continue  # 마지막 사용자 메시지는 제외 (새 입력으로 처리)
                    service.model.conversation_history.append({
                        "role": msg.role, 
                        "content": msg.content
                    })
        
        # 대화형 모드로 응답 생성 (KoAlpaca 모델에 맞게 파라미터 조정)
        responses = service.generate_text(
            prompt=last_user_message,
            max_length=request.max_length or 512,  # 최대 길이 증가
            temperature=request.temperature or 0.7,
            top_p=0.95,
            top_k=100,
            repetition_penalty=1.1,
            is_order=True,
            use_dialog=True  # 대화형 모드 사용
        )
        
        if not responses:
            raise HTTPException(status_code=500, detail="응답 생성에 실패했습니다")
        
        return ChatResponse(
            response=responses[0],
            conversation_id="session-1"  # 실제 구현에서는 고유 ID 생성
        )
    
    except Exception as e:
        logger.error(f"챗 응답 생성 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"챗 응답 생성 중 오류 발생: {str(e)}")

# 카페 대화 엔드포인트 수정
@router.post("/cafe-chat", response_model=ChatResponse, tags=["Cafe Ordering"])
async def cafe_chat(
    request: ChatRequest,
    service: TextGenerationService = Depends(get_text_generation_service)
):
    try:
        logger.info(f"카페 대화 요청 수신: {len(request.messages)} 메시지")
        
        # 대화 메시지에서 마지막 사용자 메시지 추출
        last_user_message = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                last_user_message = msg.content
                break
        
        if not last_user_message:
            raise HTTPException(status_code=400, detail="사용자 메시지가 없습니다")
        
        # 대화 이력 설정 (서비스에서 관리)
        if hasattr(service.model, 'conversation_history'):
            # 모델의 대화 이력 초기화
            service.model.conversation_history = []
            
            # 시스템 메시지 추가
            system_messages = [msg for msg in request.messages if msg.role == "system"]
            if not system_messages:
                # 기본 카페 키오스크 시스템 메시지 추가
                service.model.conversation_history.append({
                    "role": "system", 
                    "content": "당신은 카페 키오스크 시스템입니다. 고객의 주문을 정확히 확인하고 응답하세요."
                })
            else:
                for system_msg in system_messages:
                    service.model.conversation_history.append({
                        "role": "system", 
                        "content": system_msg.content
                    })
            
            # 사용자 및 어시스턴트 메시지 추가 (마지막 사용자 메시지 제외)
            for i, msg in enumerate(request.messages):
                if msg.role in ["user", "assistant"]:
                    if msg.role == "user" and i == len(request.messages) - 1:
                        continue  # 마지막 사용자 메시지는 제외 (새 입력으로 처리)
                    service.model.conversation_history.append({
                        "role": msg.role, 
                        "content": msg.content
                    })
        
        # 카페 주문에 최적화된 대화형 모드 응답 생성
        responses = service.generate_text(
            prompt=last_user_message,
            max_length=256,  # 최대 길이 대폭 증가
            temperature=0.5,  # 다양성 유지
            top_p=0.95,
            top_k=50,
            repetition_penalty=1.3,
            is_order=True,
            use_dialog=True  # 대화형 모드 사용
        )
        
        if not responses:
            raise HTTPException(status_code=500, detail="응답 생성에 실패했습니다")
        
        return ChatResponse(
            response=responses[0],
            conversation_id="cafe-session-1"  # 실제 구현에서는 고유 ID 생성
        )
    
    except Exception as e:
        logger.error(f"카페 챗 응답 생성 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"카페 챗 응답 생성 중 오류 발생: {str(e)}")