# app/models/rag_models.py
import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

import openai
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class Document(BaseModel):
    """검색 결과로 반환되는 문서를 나타내는 클래스"""
    id: str
    content: str
    metadata: Dict[str, Any] = {}
    score: float = 0.0

class Query(BaseModel):
    """사용자 쿼리를 나타내는 클래스"""
    text: str
    metadata: Dict[str, Any] = {}

class RAGResponse(BaseModel):
    """RAG 시스템의 응답을 나타내는 클래스"""
    query: str
    generated_text: str
    retrieved_documents: List[Document] = []
    metadata: Dict[str, Any] = {}

from typing import Optional, List
from pydantic import BaseModel, Field

class GPTEnhancedDocument(Document):
    """GPT로 강화된 문서 모델"""
    semantic_summary: Optional[str] = None
    key_insights: List[str] = []
    gpt_enhanced: bool = False
    
    async def gpt_enhance(
        self, 
        model_name: str = "gpt-3.5-turbo-1106", 
        temperature: float = 0.7,
        max_tokens: int = 512
    ) -> 'GPTEnhancedDocument':
        """GPT를 사용하여 문서 강화"""
        try:
            client = openai.OpenAI()
            
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "문서의 심층 분석 및 요약을 수행하세요."
                    },
                    {
                        "role": "user", 
                        "content": self.content
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            enhanced_text = response.choices[0].message.content
            
            return GPTEnhancedDocument(
                **self.dict(),
                semantic_summary=enhanced_text,
                gpt_enhanced=True
            )
        except Exception as e:
            logger.error(f"문서 강화 실패: {str(e)}")
            return self

class GPTQueryEnhancer(Query):
    """GPT로 강화된 쿼리 모델"""
    intent: Optional[str] = None  # 쿼리의 의도
    emotional_context: Optional[str] = None  # 감정적 컨텍스트
    query_complexity: Optional[float] = None  # 쿼리 복잡성
    
    @classmethod
    async def enhance_query(
        cls, 
        query: Query, 
        api_key: Optional[str] = None
    ) -> 'GPTQueryEnhancer':
        """
        GPT를 활용하여 쿼리 메타데이터 강화
        
        Args:
            query: 원본 쿼리
            api_key: OpenAI API 키
        
        Returns:
            강화된 쿼리 모델
        """
        try:
            client = openai.OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
            
            # 쿼리 강화 요청
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        사용자 쿼리의 심층 분석을 JSON으로 제공:
                        - 쿼리의 정확한 의도
                        - 감정적 컨텍스트
                        - 쿼리 복잡성 점수 (0-1 사이)
                        """
                    },
                    {
                        "role": "user", 
                        "content": query.text
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            # JSON 파싱
            enhanced_data = json.loads(response.choices[0].message.content)
            
            return cls(
                text=query.text,
                metadata=query.metadata,
                intent=enhanced_data.get('intent'),
                emotional_context=enhanced_data.get('emotional_context'),
                query_complexity=enhanced_data.get('query_complexity')
            )
        
        except Exception as e:
            logger.error(f"쿼리 강화 실패: {str(e)}")
            # 오류 시 원본 쿼리 그대로 반환
            return cls(**query.dict())

class GPTEnhancedRAGResponse(RAGResponse):
    """GPT로 강화된 RAG 응답 모델"""
    generated_insights: List[str] = []  # GPT 기반 추가 인사이트
    confidence_score: Optional[float] = None  # 응답 신뢰도
    alternative_responses: List[str] = []  # 대체 가능한 응답들
    
    @classmethod
    async def enhance_response(
        cls, 
        rag_response: RAGResponse, 
        api_key: Optional[str] = None
    ) -> 'GPTEnhancedRAGResponse':
        """
        GPT를 활용하여 RAG 응답 강화
        
        Args:
            rag_response: 원본 RAG 응답
            api_key: OpenAI API 키
        
        Returns:
            강화된 RAG 응답 모델
        """
        try:
            client = openai.OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
            
            # 컨텍스트 준비 (검색된 문서들)
            context_docs = " ".join([doc.content for doc in rag_response.retrieved_documents])
            
            # 응답 강화 요청
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        다음 컨텍스트와 생성된 응답을 분석:
                        - 추가적인 인사이트 추출
                        - 응답의 신뢰도 점수 계산 (0-1 사이)
                        - 대체 가능한 응답들 제안
                        """
                    },
                    {
                        "role": "user", 
                        "content": json.dumps({
                            "query": rag_response.query,
                            "generated_text": rag_response.generated_text,
                            "context": context_docs
                        })
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            # JSON 파싱
            enhanced_data = json.loads(response.choices[0].message.content)
            
            return cls(
                query=rag_response.query,
                generated_text=rag_response.generated_text,
                retrieved_documents=rag_response.retrieved_documents,
                metadata=rag_response.metadata,
                generated_insights=enhanced_data.get('insights', []),
                confidence_score=enhanced_data.get('confidence_score'),
                alternative_responses=enhanced_data.get('alternative_responses', [])
            )
        
        except Exception as e:
            logger.error(f"RAG 응답 강화 실패: {str(e)}")
            # 오류 시 원본 응답 그대로 반환
            return cls(**rag_response.dict())