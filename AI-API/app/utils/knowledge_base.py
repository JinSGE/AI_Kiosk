# utils/knowledge_base.py
import os
from typing import List, Dict, Any, Optional
import pickle
from app.models.rag_models import Document
from app.services.retrieval_service import KoAlpacaVectorStore

class KnowledgeBase:
    """RAG 시스템 지식 베이스 관리"""
    
    def __init__(self, vector_store: Optional[KoAlpacaVectorStore] = None):
        self.vector_store = vector_store or KoAlpacaVectorStore()
    
    def add_documents(self, documents: List[Document]) -> None:
        """문서를 지식 베이스에 추가"""
        self.vector_store.add_documents(documents)
    
    def save(self, file_path: str) -> None:
        """지식 베이스 저장"""
        with open(file_path, "wb") as f:
            pickle.dump(self.vector_store, f)
    
    @classmethod
    def load(cls, file_path: str) -> 'KnowledgeBase':
        """저장된 지식 베이스 로드"""
        with open(file_path, "rb") as f:
            vector_store = pickle.load(f)
        
        return cls(vector_store=vector_store)