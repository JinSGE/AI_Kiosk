# app/services/rag_service.py
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
import os
import json
import asyncio
from typing import List, Dict, Any, Optional

from app.config import settings
from app.models.rag_models import Document, RAGResponse
from app.models.text_generation import text_model

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.retriever = None
        self.generator = None
        self.is_initialized = False
        self.knowledge_base = []
        self.faiss_retriever = None
        logger.info("RAG 서비스 초기화 중...")

    async def initialize(self) -> bool:
        """RAG 서비스 초기화"""
        if self.is_initialized:
            logger.info("RAG 서비스가 이미 초기화되어 있습니다.")
            return True
        
        try:
            # 검색기 초기화
            logger.info("FAISS 검색기 초기화 중...")
            self.retriever = FAISS_Retriever()
            
            # 생성기 초기화
            logger.info("LLM 생성기 초기화 완료")
            self.generator = LLMGenerator(text_model)
            
            # 메뉴 데이터 로드 및 저장
            menu_data_path = os.path.join(settings.MODEL_CACHE_DIR, "menu_data.json")
            menu_knowledge = []
            
            try:
                # 메뉴 데이터 로드 또는 기본값 생성
                if os.path.exists(menu_data_path):
                    with open(menu_data_path, 'r', encoding='utf-8') as f:
                        menu_data = json.load(f)
                else:
                    menu_data = self._get_default_menu_data()
                    
                    # 파일 저장
                    os.makedirs(os.path.dirname(menu_data_path), exist_ok=True)
                    with open(menu_data_path, 'w', encoding='utf-8') as f:
                        json.dump(menu_data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"기본 메뉴 데이터 파일 생성: {menu_data_path}")
                
                # 메뉴 정보를 지식 베이스로 변환
                menu_knowledge = self._convert_menu_to_knowledge(menu_data)
                logger.info(f"메뉴 지식 베이스 생성: {len(menu_knowledge)}개 항목")
                
            except Exception as e:
                logger.warning(f"메뉴 데이터 처리 실패: {str(e)}")
            
            # 지식 베이스 로드
            kb_path = os.path.join(settings.MODEL_CACHE_DIR, "knowledge_base.json")
            try:
                if os.path.exists(kb_path):
                    logger.info(f"지식 베이스 로드 중: {kb_path}")
                    with open(kb_path, 'r', encoding='utf-8') as f:
                        self.knowledge_base = json.load(f)
                    logger.info(f"지식 베이스 로드 완료: {len(self.knowledge_base)} 문서")
                else:
                    logger.info("지식 베이스 파일이 없어 기본 지식 베이스를 생성합니다.")
                    self.knowledge_base = self._create_default_knowledge_base()
            except Exception as e:
                logger.warning(f"지식 베이스 로드 실패: {str(e)}")
                self.knowledge_base = self._create_default_knowledge_base()
            
            # 메뉴 지식 베이스 추가
            if menu_knowledge:
                self.knowledge_base.extend(menu_knowledge)
                logger.info(f"메뉴 지식 베이스 추가: {len(menu_knowledge)}개 항목")
            
            # FAISS 검색기 준비
            self._prepare_faiss_retriever()
            
            self.is_initialized = True
            logger.info("RAG 서비스 초기화 완료")
            return True
        
        except Exception as e:
            logger.error(f"RAG 서비스 초기화 실패: {str(e)}")
            return False
        
    async def query_knowledge_base(self, query_text: str) -> str:
        """
        지식 베이스에 쿼리를 실행하고 결과 문자열 반환
        파이프라인 서비스에서 호출하는 인터페이스 메소드
        """
        if not self.is_initialized:
            await self.initialize()
        
        try:
            # RAG 응답 생성
            rag_response = await self.process_query(query_text)
            
            # 생성된 응답 반환
            return rag_response.generated_text
        
        except Exception as e:
            logger.error(f"지식 베이스 쿼리 실패: {str(e)}")
            return f"죄송합니다. 요청을 처리하는 중에 오류가 발생했습니다: {str(e)}"
        
    def _prepare_faiss_retriever(self):
            """
            FAISS 검색기 준비 및 지식 베이스 임베딩
            """
            try:
                # FAISS 검색기 초기화 (이미 존재하지 않는 경우)
                if self.faiss_retriever is None:
                    self.faiss_retriever = FAISS_Retriever()
                
                # 지식 베이스 임베딩 및 인덱싱
                self.faiss_retriever.add_documents(self.knowledge_base)
                logger.info(f"FAISS 검색기에 {len(self.knowledge_base)}개의 지식 베이스 문서 추가")
            
            except Exception as e:
                logger.warning(f"FAISS 검색기 문서 추가 실패: {str(e)}")
    def _get_default_menu_data(self) -> Dict[str, Any]:
            """기본 메뉴 데이터 반환"""
            return {
        "menus": [
        {
            "name": "아메리카노",
            "categories": ["커피"],
            "basePrice": 4500,
            "description": "깊고 진한 에스프레소에 물을 더해 깔끔한 맛의 스탠다드 커피",
            "imageUrl": "/images/menu/americano.jpg",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            },
            "temperature": {
                "핫": 0,
                "아이스": 500
            },
            "shots": {
                "1샷 추가": 500,
                "2샷 추가": 1000
            },
            "syrup": {
                "바닐라 시럽 추가": 500,
                "헤이즐넛 시럽 추가": 500,
                "카라멜 시럽 추가": 500
            }
            }
        },
        {
            "name": "카페 라떼",
            "categories": ["커피"],
            "basePrice": 5000,  
            "imageUrl": "/images/cafelatte.jpg",
            "description": "진한 에스프레소와 부드러운 우유가 조화를 이루는 대표적인 라떼",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            },
            "temperature": {
                "핫": 0,
                "아이스": 500
            },
            "shots": {
                "1샷 추가": 500,
                "2샷 추가": 1000
            },
            "syrup": {
                "바닐라 시럽 추가": 500,
                "헤이즐넛 시럽 추가": 500,
                "카라멜 시럽 추가": 500
            }
            }
        },
        {
            "name": "카페 모카",
            "categories": ["커피"],
            "basePrice": 5500,
            "imageUrl": "/images/cafemocha.jpg",
            "description": "진한 초콜릿과 에스프레소의 완벽한 조화, 달콤 쌉싸름한 맛",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            },
            "temperature": {
                "핫": 0,
                "아이스": 500
            },
            "shots": {
                "1샷 추가": 500,
                "2샷 추가": 1000
            },
            "syrup": {
                "바닐라 시럽 추가": 500,
                "헤이즐넛 시럽 추가": 500,
                "카라멜 시럽 추가": 500
            }
            }
        },
        {
            "name": "바닐라 라떼",
            "categories": ["커피"],
            "basePrice": 5500,
            "imageUrl": "/images/vanillalatte.jpg",
            "description": "달콤한 바닐라 시럽이 추가된 크리미한 라떼",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            },
            "temperature": {
                "핫": 0,
                "아이스": 500
            },
            "shots": {
                "1샷 추가": 500,
                "2샷 추가": 1000
            },
            "syrup": {
                "바닐라 시럽 추가": 500,
                "헤이즐넛 시럽 추가": 500,
                "카라멜 시럽 추가": 500
            }
            }
        },
        {
            "name": "카라멜 마끼아또",
            "categories": ["커피"],
            "imageUrl": "/images/caramelmacchiato.jpg",
            "description": "바닐라 시럽과 카라멜 소스가 어우러진 달콤한 에스프레소 음료",
            "basePrice": 5800,
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            },
            "temperature": {
                "핫": 0,
                "아이스": 500
            },
            "shots": {
                "1샷 추가": 500,
                "2샷 추가": 1000
            },
            "syrup": {
                "바닐라 시럽 추가": 500,
                "헤이즐넛 시럽 추가": 500,
                "카라멜 시럽 추가": 500
            }
            }
        },
        {
            "name": "초코 라떼",
            "categories": ["커피"],
            "imageUrl": "/images/chocolatte.jpg",
            "description": "진한 초콜릿과 부드러운 우유가 만나 달콤한 맛의 음료",
            "basePrice": 5000,
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            },
            "temperature": {
                "핫": 0,
                "아이스": 500
            },
            "shots": {
                "1샷 추가": 500,
                "2샷 추가": 1000
            },
            "syrup": {
                "바닐라 시럽 추가": 500,
                "헤이즐넛 시럽 추가": 500,
                "카라멜 시럽 추가": 500
            }
            }
        },
        {
            "name": "그린 라떼",
            "categories": ["커피"],
            "basePrice": 5000,
            "imageUrl": "/images/greentealatte.jpg",
            "description": "은은한 녹차 향과 부드러운 우유의 조화로운 맛",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            },
            "temperature": {
                "핫": 0,
                "아이스": 500
            },
            "shots": {
                "1샷 추가": 500,
                "2샷 추가": 1000
            },
            "syrup": {
                "바닐라 시럽 추가": 500,
                "헤이즐넛 시럽 추가": 500,
                "카라멜 시럽 추가": 500
            }
            }
        },
        {
            "name": "복숭아 아이스 티",
            "categories": ["티"],
            "basePrice": 5200,
            "imageUrl": "/images/peachicedtea.jpg",
            "description": "향긋한 복숭아 향이 가득한 시원한 아이스티",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            }
            }
        },
        {
            "name": "허브 티",
            "categories": ["티"],
            "basePrice": 5000,
            "imageUrl": "/images/herbtea.jpg",
            "description": "다양한 허브의 은은한 향과 맛을 즐길 수 있는 전통 차",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            }
            }
        },
        {
            "name": "레몬 에이드",
            "categories": ["에이드/주스"],
            "basePrice": 5500,
            "imageUrl": "/images/lemonade.jpg",
            "description": "상큼한 레몬과 탄산의 청량함이 가득한 시원한 음료",
            "options": {
            "size": {
                "레귤러": 0,
                "라지": 500
            }
            }
        }
        ],
        "quantities": {
        "한 잔": 1,
        "두 잔": 2,
        "세 잔": 3,
        "네 잔": 4,
        "다섯 잔": 5,
        "여섯 잔": 6,
        "일곱 잔": 7,
        "여덟 잔": 8,
        "아홉 잔": 9,
        "열 잔": 10
        },
        "categories": {
        "커피": ["아메리카노", "카페라떼", "카페모카", "바닐라 라떼", "카라멜 마끼아토", "초코라떼", "녹차라떼"],
        "티": ["복숭아 아이스 티", "허브 티"],
        "에이드/주스": ["레몬 에이드"]
        },
        "option_types": {
        "커피": ["size", "temperature", "shots", "syrup"],
        "티": ["size"],
        "에이드/주스": ["size"]
        }
    }
    def _convert_menu_to_knowledge(self, menu_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """메뉴 데이터를 지식 베이스로 변환"""
        menu_knowledge = []
        
        for menu in menu_data.get('menus', []):
            # 기본 메뉴 정보 추가
            menu_knowledge.append({
                "id": f"menu_{menu['name']}",
                "content": f"{menu['name']}는 {menu['basePrice']}원입니다.",
                "category": "menu"
            })
            
            # 옵션 정보 추가
            if 'options' in menu:
                for option_type, options in menu['options'].items():
                    option_text = f"{menu['name']}의 {option_type} 옵션: "
                    option_details = []
                    
                    for option_name, price in options.items():
                        option_details.append(f"{option_name}{'' if price == 0 else f'(+{price}원)'}")
                    
                    option_text += ", ".join(option_details)
                    menu_knowledge.append({
                        "id": f"option_{menu['name']}_{option_type}",
                        "content": option_text,
                        "category": "option"
                    })
        
        return menu_knowledge

    def _create_default_knowledge_base(self) -> List[Dict[str, Any]]:
        """기본 지식 베이스 생성"""
        return [
            {
                "id": "menu_1",
                "content": "아메리카노는 4,500원, 카페라떼는 5,000원, 카페모카는 5,500원, 그린 라떼는 5,000원, 초코 라떼는 5000원입니다.",
                "category": "menu"
            },
            {
                "id": "menu_2",
                "content": "카라멜 마끼아또는 5,800원, 허브 티는 5000원, 레몬 에이드는 5,500원, 복숭아 아이스 티는 5,200원, 바닐라 라떼는 5,500원입니다.",
                "category": "menu"
            },
            {
                "id": "option_1",
                "content": "모든 음료는 따뜻한(핫) 또는 차가운(아이스) 옵션을 선택할 수 있습니다.",
                "category": "option"
            },
            {
                "id": "payment_1",
                "content": "결제는 카드, 삼성페이, 애플페이, 카카오페이, 네이버페이를 지원합니다.",
                "category": "payment"
            }
        ]

    async def process_query(self, query_text: str, top_k: int = 3) -> RAGResponse:
        """쿼리 처리 및 응답 생성"""
        if not self.is_initialized:
            await self.initialize()
        
        try:
            # FAISS 검색기 준비 확인
            if self.faiss_retriever is None:
                self._prepare_faiss_retriever()
            
            # 문서 검색
            retrieved_docs = self.faiss_retriever.search(query_text, top_k)
            
            # 검색 결과 없을 경우 기본 문서 추가
            if not retrieved_docs:
                retrieved_docs.append({
                    "id": "default_query",
                    "content": "죄송합니다. 요청하신 내용에 대한 정보를 찾을 수 없습니다. 다른 방식으로 질문해 주시겠어요?",
                    "category": "default",
                    "score": 0.5
                })
            
            # 컨텍스트 구성
            context = "\n".join([doc['content'] for doc in retrieved_docs])
            
            # 응답 생성
            generated_text = await self.generator.generate(query_text, context) if self.generator else context
            
            # 검색된 문서를 Document 객체로 변환
            retrieved_document_objs = [
                Document(
                    id=doc.get('id', ''),
                    content=doc.get('content', ''),
                    metadata={"category": doc.get('category', 'general')},
                    score=doc.get('score', 0.0)
                ) for doc in retrieved_docs
            ]
            
            return RAGResponse(
                query=query_text,
                generated_text=generated_text,
                retrieved_documents=retrieved_document_objs,
                metadata={
                    "top_k": top_k,
                    "retrieved_count": len(retrieved_docs)
                }
            )
        
        except Exception as e:
            logger.error(f"쿼리 처리 실패: {str(e)}")
            return RAGResponse(
                query=query_text,
                generated_text="죄송합니다. 요청을 처리하는 중에 오류가 발생했습니다.",
                retrieved_documents=[],
                metadata={"error": str(e)}
            )

class FAISS_Retriever:
    """FAISS 기반 문서 검색 클래스"""
    
    def __init__(self, model_name: str = 'distiluse-base-multilingual-cased-v2'):
        """
        FAISS 검색기 초기화
        
        :param model_name: 임베딩 모델 이름
        """
        try:
            # 임베딩 모델 로드
            self.embedding_model = SentenceTransformer(model_name)
            
            # FAISS 인덱스 초기화 (L2 거리 기반)
            self.dimension = self.embedding_model.get_sentence_embedding_dimension()
            self.index = faiss.IndexFlatL2(self.dimension)
            
            # 문서 메타데이터 저장용 리스트
            self.documents = []
            self.embeddings = []
            
            logger.info(f"FAISS 검색기 초기화 완료 (임베딩 차원: {self.dimension})")
        
        except Exception as e:
            logger.error(f"FAISS 검색기 초기화 실패: {str(e)}")
            raise
    
    def add_documents(self, documents: List[Dict[str, Any]]):
            """
            문서 임베딩 및 FAISS 인덱스에 추가
            
            :param documents: 문서 목록 (각 문서는 id, content 등의 키를 포함)
            """
            try:
                # 문서 내용 임베딩
                texts = [doc['content'] for doc in documents]
                embeddings = self.embedding_model.encode(texts)
                
                # FAISS 인덱스에 임베딩 추가
                self.index.add(embeddings)
                
                # 메타데이터 저장
                self.documents.extend(documents)
                self.embeddings.extend(embeddings)
                
                logger.info(f"{len(documents)}개의 문서 임베딩 및 인덱스 추가 완료")
            
            except Exception as e:
                logger.error(f"문서 추가 실패: {str(e)}")
                raise
    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        쿼리에 대한 유사 문서 검색
        
        :param query: 검색 쿼리 문자열
        :param top_k: 반환할 상위 문서 수
        :return: 유사 문서 목록
        """
        try:
            # 쿼리 임베딩
            query_embedding = self.embedding_model.encode([query])[0]
            
            # FAISS를 통한 유사도 검색
            distances, indices = self.index.search(
                np.array([query_embedding]), 
                k=top_k
            )
            
            # 검색 결과 변환
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < len(self.documents):
                    doc = self.documents[idx].copy()
                    doc['score'] = 1 / (1 + dist)  # 유사도 점수 변환
                    results.append(doc)
            
            return results
        
        except Exception as e:
            logger.error(f"문서 검색 실패: {str(e)}")
            return []
        

class LLMGenerator:
    """LLM 기반 텍스트 생성 클래스"""
    
    def __init__(self, text_model):
        self.text_model = text_model
    
    async def generate(self, query: str, context: str) -> str:
        """컨텍스트와 쿼리를 기반으로 응답 생성"""
        try:
            # 프롬프트 구성
            prompt = f"""다음 정보를 참고하여 카페 키오스크 직원처럼 친절하게 답변해주세요:

정보:
{context}

고객 질문: {query}

응답:"""
            
            # 동기 함수를 비동기로 실행
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.text_model.generate_text(
                    prompt=prompt,
                    max_length=512,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.1,
                    use_dialog=True
                )
            )
            
            # 리스트 또는 단일 문자열 확인
            if isinstance(response, list):
                return response[0] if response else "죄송합니다. 응답을 생성할 수 없습니다."
            return response
            
        except Exception as e:
            logger.error(f"응답 생성 실패: {str(e)}")
            return f"죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다."

rag_service = RAGService()