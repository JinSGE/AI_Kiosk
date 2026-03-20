
# app/utils/kb_manager.py
import os
import json
from typing import List, Dict, Any
import logging

from app.config import settings
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

class KnowledgeBaseManager:
    """RAG 지식 베이스 관리 유틸리티"""
    
    def __init__(self, rag_service: RAGService = None):
        self.rag_service = rag_service or RAGService()
        self.kb_path = os.path.join(settings.MODEL_CACHE_DIR, "knowledge_base.json")
    
    async def add_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """문서 추가"""
        try:
            # 기존 지식 베이스 로드
            kb = await self._load_kb()
            
            # 문서 ID 중복 확인 및 처리
            existing_ids = {doc["id"] for doc in kb if "id" in doc}
            new_docs = []
            
            for doc in documents:
                if "id" not in doc:
                    doc["id"] = f"doc_{len(kb) + len(new_docs)}"
                
                if doc["id"] in existing_ids:
                    logger.warning(f"문서 ID가 중복됩니다: {doc['id']}, 건너뜁니다.")
                    continue
                
                new_docs.append(doc)
                existing_ids.add(doc["id"])
            
            # 문서 추가
            kb.extend(new_docs)
            
            # 저장
            await self._save_kb(kb)
            
            # RAG 서비스 재초기화
            await self.rag_service.initialize()
            
            return True
        except Exception as e:
            logger.error(f"문서 추가 실패: {str(e)}")
            return False
    
    async def remove_document(self, doc_id: str) -> bool:
        """문서 삭제"""
        try:
            # 기존 지식 베이스 로드
            kb = await self._load_kb()
            
            # 문서 필터링
            kb_filtered = [doc for doc in kb if doc.get("id") != doc_id]
            
            # 변경사항 확인
            if len(kb_filtered) == len(kb):
                logger.warning(f"삭제할 문서를 찾을 수 없습니다: {doc_id}")
                return False
            
            # 저장
            await self._save_kb(kb_filtered)
            
            # RAG 서비스 재초기화
            await self.rag_service.initialize()
            
            return True
        except Exception as e:
            logger.error(f"문서 삭제 실패: {str(e)}")
            return False
    
    async def update_document(self, doc_id: str, new_content: str) -> bool:
        """문서 업데이트"""
        try:
            # 기존 지식 베이스 로드
            kb = await self._load_kb()
            
            # 문서 업데이트
            updated = False
            for doc in kb:
                if doc.get("id") == doc_id:
                    doc["content"] = new_content
                    updated = True
                    break
            
            if not updated:
                logger.warning(f"업데이트할 문서를 찾을 수 없습니다: {doc_id}")
                return False
            
            # 저장
            await self._save_kb(kb)
            
            # RAG 서비스 재초기화
            await self.rag_service.initialize()
            
            return True
        except Exception as e:
            logger.error(f"문서 업데이트 실패: {str(e)}")
            return False
    
    async def _load_kb(self) -> List[Dict[str, Any]]:
        """지식 베이스 로드"""
        if os.path.exists(self.kb_path):
            try:
                with open(self.kb_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"지식 베이스 로드 실패: {str(e)}")
        
        return []
    
    async def _save_kb(self, kb: List[Dict[str, Any]]) -> bool:
        """지식 베이스 저장"""
        try:
            # 디렉토리 생성
            os.makedirs(os.path.dirname(self.kb_path), exist_ok=True)
            
            # 저장
            with open(self.kb_path, 'w', encoding='utf-8') as f:
                json.dump(kb, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"지식 베이스 저장 실패: {str(e)}")
            return False