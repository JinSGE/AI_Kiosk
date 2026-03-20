# app/services/retrieval_service.py
import logging
import os
import numpy as np
from typing import List, Dict, Any, Optional, Union
import torch
from transformers import AutoModel, AutoTokenizer

from app.config import settings
from app.models.rag_models import Document

logger = logging.getLogger(__name__)

class KoAlpacaVectorStore:
    """KoAlpaca 모델용 벡터 스토어 클래스"""
    
    def __init__(self, embedding_size=768, model_path=None):
        """
        KoAlpaca 모델로 생성된 임베딩을 저장하고 검색하는 벡터 스토어
        
        Args:
            embedding_size: 임베딩 벡터 크기
            model_path: 사용할 모델 경로 (기본값: settings에서 가져옴)
        """
        self.documents = []  # 문서 텍스트 저장
        self.document_ids = []  # 문서 ID 저장
        self.document_embeddings = []  # 문서 임베딩 저장
        self.metadata = []  # 문서 메타데이터 저장
        self.embedding_size = embedding_size
        self.model_path = model_path or r"C:/User/ssunge/OneDrive/바탕 화면/SE/AI-API/model_cache/models--EleutherAI--polyglot-ko-1.3b"
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() and settings.USE_GPU else "cpu"
        logger.info(f"벡터 스토어 초기화: {self.model_path} (device: {self.device})")
    
    def load_embedding_model(self):
        """임베딩 모델 로드"""
        try:
            logger.info(f"임베딩 모델 로드 중: {self.model_path}")
            
            # 토크나이저 로드
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                cache_dir=settings.MODEL_CACHE_DIR
            )
            
            # 모델 로드
            self.model = AutoModel.from_pretrained(
                self.model_path,
                cache_dir=settings.MODEL_CACHE_DIR
            )
            
            # GPU로 이동
            self.model.to(self.device)
            if self.device == "cuda":
                self.model = self.model.half()  # 메모리 최적화
                
            logger.info("임베딩 모델 로드 완료")
            return True
        except Exception as e:
            logger.error(f"임베딩 모델 로드 실패: {str(e)}")
            raise RuntimeError(f"임베딩 모델 로드 실패: {str(e)}")
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """텍스트에서 임베딩 생성"""
        if not self.model or not self.tokenizer:
            self.load_embedding_model()
            
        try:
            # 토큰화
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                max_length=512, 
                padding=True
            )
            
            # token_type_ids 제거 (필요한 경우)
            if 'token_type_ids' in inputs:
                del inputs['token_type_ids']
                
            # 디바이스로 이동
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # 임베딩 생성
            with torch.no_grad():
                outputs = self.model(**inputs)
                
            # [CLS] 토큰의 마지막 은닉 상태 사용
            embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            
            return embeddings[0]  # 첫 번째 문장의 임베딩 반환
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            # 오류 발생 시 0으로 채워진 임베딩 반환
            return np.zeros(self.embedding_size)
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        문서를 벡터 스토어에 추가
        
        Args:
            documents: 문서 목록. 각 문서는 딕셔너리로 'id', 'content', 'metadata' 키를 포함
            
        Returns:
            추가된 문서 수
        """
        if not self.model or not self.tokenizer:
            self.load_embedding_model()
            
        added_count = 0
        
        for doc in documents:
            doc_id = doc.get('id', str(len(self.documents)))
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            if not content:
                logger.warning(f"빈 콘텐츠의 문서 건너뜀: {doc_id}")
                continue
                
            # 임베딩 생성
            embedding = self._get_embedding(content)
            
            # 문서 저장
            self.documents.append(content)
            self.document_ids.append(doc_id)
            self.document_embeddings.append(embedding)
            self.metadata.append(metadata)
            
            added_count += 1
            
        logger.info(f"문서 {added_count}개 추가됨. 총 {len(self.documents)}개 문서")
        return added_count
    
    def similarity_search(self, query: str, top_k: int = 5) -> List[Document]:
        """
        쿼리와 가장 유사한 문서 검색
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 문서 수
            
        Returns:
            유사도 점수로 정렬된 문서 목록
        """
        if not self.documents:
            logger.warning("문서가 없습니다.")
            return []
            
        # 쿼리 임베딩 생성
        query_embedding = self._get_embedding(query)
        
        # 문서 임베딩이 하나도 없을 경우
        if not self.document_embeddings:
            logger.warning("문서 임베딩이 없습니다.")
            return []
            
        # 문서 임베딩을 numpy 배열로 변환
        doc_embeddings = np.array(self.document_embeddings)
        
        # 정규화
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        doc_embeddings = doc_embeddings / np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
        
        # 코사인 유사도 계산
        similarities = np.dot(doc_embeddings, query_embedding)
        
        # 상위 k개 인덱스
        if len(similarities) <= top_k:
            top_indices = np.argsort(similarities)[::-1]
        else:
            top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # 결과 생성
        results = []
        for i in top_indices:
            doc = Document(
                id=self.document_ids[i],
                content=self.documents[i],
                metadata=self.metadata[i],
                score=float(similarities[i])
            )
            results.append(doc)
            
        return results
    
    def save(self, file_path: str) -> bool:
        """
        벡터 스토어 저장
        
        Args:
            file_path: 저장할 파일 경로
            
        Returns:
            성공 여부
        """
        try:
            data = {
                "documents": self.documents,
                "document_ids": self.document_ids,
                "document_embeddings": self.document_embeddings,
                "metadata": self.metadata,
                "embedding_size": self.embedding_size,
                "model_path": self.model_path
            }
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 저장
            np.save(file_path, data, allow_pickle=True)
            logger.info(f"벡터 스토어 저장 완료: {file_path}")
            return True
        except Exception as e:
            logger.error(f"벡터 스토어 저장 실패: {str(e)}")
            return False
    
    def load(self, file_path: str) -> bool:
        """
        벡터 스토어 로드
        
        Args:
            file_path: 로드할 파일 경로
            
        Returns:
            성공 여부
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"파일이 존재하지 않음: {file_path}")
                return False
                
            # 로드
            data = np.load(file_path, allow_pickle=True).item()
            
            self.documents = data["documents"]
            self.document_ids = data["document_ids"]
            self.document_embeddings = data["document_embeddings"]
            self.metadata = data["metadata"]
            self.embedding_size = data["embedding_size"]
            self.model_path = data["model_path"]
            
            logger.info(f"벡터 스토어 로드 완료: {file_path}, {len(self.documents)}개 문서")
            return True
        except Exception as e:
            logger.error(f"벡터 스토어 로드 실패: {str(e)}")
            return False