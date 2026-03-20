from fastapi import APIRouter, Depends, HTTPException, Query as FastAPIQuery
from typing import List, Optional, Union
from app.models.rag_models import Query as QueryModel, RAGResponse, GPTEnhancedDocument
from app.services.rag_service import RAGService
import os
from pydantic import BaseModel

router = APIRouter()
rag_service = RAGService()

class RAGQueryConfig(BaseModel):
    """RAG 쿼리 설정"""
    top_k: int = 3
    use_gpt_enhancement: bool = True
    model_name: str = "gpt-3.5-turbo-1106"
    temperature: float = 0.7

class RAGQueryRequest(BaseModel):
    """RAG 쿼리 요청"""
    text: str
    config: Optional[RAGQueryConfig] = RAGQueryConfig()

@router.post("/enhanced-query", response_model=Union[RAGResponse, GPTEnhancedDocument])
async def process_rag_query(
    request: RAGQueryRequest,
    api_key: Optional[str] = FastAPIQuery(None, description="OpenAI API 키")
):
    """RAG 쿼리 처리 엔드포인트"""
    try:
        # API 키 설정 (선택적)
        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key
        
        # GPT 강화 쿼리 처리
        response = await rag_service.process_query_with_gpt(
            query_text=request.text,
            top_k=request.config.top_k,
            use_gpt_enhancement=request.config.use_gpt_enhancement,
            model_name=request.config.model_name,
            temperature=request.config.temperature
        )
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def list_gpt_models():
    """사용 가능한 GPT 모델 목록"""
    models = [
        {
            "name": "gpt-3.5-turbo-1106", 
            "description": "빠르고 경제적인 모델",
            "max_tokens": 4096
        },
        {
            "name": "gpt-4", 
            "description": "고성능 고급 모델",
            "max_tokens": 8192
        }
    ]
    return {"models": models}

@router.post("/query", response_model=RAGResponse)
async def process_query(query: QueryModel, top_k: Optional[int] = 5):
    """RAG 쿼리 처리 API 엔드포인트"""
    try:
        response = await rag_service.process_query(query.text, top_k=top_k)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """상태 확인 엔드포인트"""
    return {"status": "ok"}