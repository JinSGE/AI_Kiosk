# app/services/enhanced_pipeline_service.py
import re
import logging
import os
import json
import asyncio
import time
import random
from typing import Dict, Any, Optional, BinaryIO, List, Callable

import openai
from datetime import datetime

from app.services.nlp_processor import extract_intent_and_slots, MENU_DATA
from app.services.stt_service_model import STTService
from app.services.rag_service import RAGService
from app.services.tts_service_model import TTSService
from app.models.fsm import fsm, State, GPTEnhancedFSM

logger = logging.getLogger(__name__)

import random

# 전역 변수를 파일 최상단에 정의
_greeting_shown = False

class MenuRecommendationService:
    def __init__(self, menu_list=None):
        # 메뉴 리스트가 제공되지 않으면 기본 메뉴 사용
        self.menu_list = menu_list or [
            "아메리카노", "카페라떼", "카페모카", "바닐라라떼", 
            "카라멜마끼아또", "초코라떼", "그린라떼", 
            "복숭아아이스티", "레몬에이드"
        ]
        
        # 시간대별 맞춤 멘트
        self.time_based_responses = {
            "아침": [
                "상쾌한 아침을 위한 음료를 골라봤어요.",
                "아침을 깨우는 특별한 음료예요.",
                "좋은 아침! 오늘의 아침 음료를 추천해드려요."
            ],
            "점심": [
                "활력 넘치는 점심 시간 음료예요.",
                "점심 휴식에 딱 맞는 음료를 골랐어요.",
                "바쁜 점심 시간, 잠시 휴식을 취해보세요."
            ],
            "저녁": [
                "하루를 마무리하는 아늑한 음료예요.",
                "편안한 저녁 시간을 위한 음료입니다.",
                "하루의 피로를 풀어줄 음료를 추천해드려요."
            ]
        }
        
        # 감정별 맞춤 멘트
        self.emotion_based_responses = {
            "행복": [
                "오늘 기분 좋은 날이네요! 더 즐겁게 만들어줄 음료예요.",
                "행복한 하루를 더욱 특별하게 만들어줄 음료입니다.",
                "당신의 미소를 더 밝게 만들어줄 음료를 골랐어요!"
            ],
            "슬픔": [
                "작은 위로가 될 수 있는 음료를 추천해드려요.",
                "힘든 하루, 잠시 위로받으세요.",
                "따뜻한 마음을 전해드리고 싶어요."
            ],
            "스트레스": [
                "잠시 숨을 고르게 해줄 음료예요.",
                "스트레스 해소에 도움되는 음료를 골랐어요.",
                "마음의 평화를 찾아줄 음료입니다."
            ],
            "피곤": [
                "에너지를 충전해줄 음료예요.",
                "활력을 되찾게 해줄 음료를 추천해드려요.",
                "잠시 휴식과 함께 힘을 내보세요."
            ]
        }

    def recommend_menu(self, context: Dict[str, Any]) -> str:
        """
        대화 컨텍스트를 기반으로 메뉴 추천
        시간대와 감정에 따른 맞춤 멘트 우선적으로 선택
        """
        query_text = context.get('query_text', '').lower()
        
        # 시간대 감지
        time_keywords = {
            "아침": ["아침", "morning", "브렉퍼스트", "오전"],
            "점심": ["점심", "런치", "midday", "오후"],
            "저녁": ["저녁", "디너", "evening", "night"]
        }
        
        # 감정 키워드 감지
        emotion_keywords = {
            "행복": ["행복", "기쁘", "좋은", "즐겁"],
            "슬픔": ["슬픕", "우울", "힘들", "외롭", "안 좋은", "안좋은"],
            "스트레스": ["스트레스", "짜증", "화", "스트"],
            "피곤": ["피곤", "지침", "졸림", "힘들"]
        }
        
        # 시간대 및 감정 감지
        detected_time = next(
            (time for time, keywords in time_keywords.items() 
             if any(keyword in query_text for keyword in keywords)), 
            None
        )
        
        detected_emotion = next(
            (emotion for emotion, keywords in emotion_keywords.items() 
             if any(keyword in query_text for keyword in keywords)), 
            None
        )
        
        # 랜덤 추천 (3개)
        recommended_menus = random.sample(self.menu_list, min(3, len(self.menu_list)))
        menu_str = ', '.join(recommended_menus)
        
        # 맞춤형 멘트 선택 로직 완전 변경
        selected_response = None
        
        # 1순위: 시간대 맞춤 멘트 + 시간대 메뉴 추천
        if detected_time and detected_time in self.time_based_responses:
            time_specific_responses = self.time_based_responses[detected_time]
            selected_response = (
                f"{random.choice(time_specific_responses)} "
                f"{menu_str}를 추천해드려요!"
            )
        
        # 2순위: 감정 맞춤 멘트 + 감정 기반 메뉴 추천
        if not selected_response and detected_emotion and detected_emotion in self.emotion_based_responses:
            emotion_specific_responses = self.emotion_based_responses[detected_emotion]
            selected_response = (
                f"{random.choice(emotion_specific_responses)} "
                f"{menu_str}로 기분 전환 어떠세요?"
            )
        
        # 3순위: 기본 추천 멘트
        if not selected_response:
            recommendation_responses = [
                f"오늘의 추천 음료는 {menu_str}예요. 어때요?",
                f"오늘의 특별한 음료를 추천해드려요: {menu_str}예요. 어떠세요?",
                f"제가 오늘의 음료를 골라봤어요: {menu_str}예요. 어떠세요?",
                f"이 음료들이 맛있을거같아요! {menu_str}예요. 좋은가요?",
                f"추천 음료는 {menu_str}예요. 어때요?"
            ]
            selected_response = random.choice(recommendation_responses)
        
        return selected_response

class EnhancedPipelineService:
    """
    파이프라인 서비스의 개선된 버전 
    - 싱글톤 패턴 적용
    - 안전한 초기화 로직
    - 오류 처리 강화
    """
    _instance = None
    _initialization_lock = asyncio.Lock()
    _is_initialized = False

    # 전역 변수를 파일 최상단에 정의
    _greeting_shown = False

    def __new__(cls, *args, **kwargs):
        """싱글톤 패턴 구현"""
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        stt_service: Optional[STTService] = None,
        rag_service: Optional[RAGService] = None,
        tts_service: Optional[TTSService] = None,
        openai_api_key: Optional[str] = None
    ):
        """
        안전한 초기화 메서드
        - 중복 초기화 방지
        - 락(Lock) 사용으로 스레드 안전성 확보
        """
        # 이미 초기화된 경우 건너뛰기
        if getattr(self, '_already_initialized', False):
            return

        # 인사말 상태 관리
        if not hasattr(self, '_initialized_greeting'):
            self._initialized_greeting = False

        # 초기화 시작
        try:
            # 서비스 인스턴스 설정 (기본값 사용)
            self.stt_service = stt_service or STTService()
            self.rag_service = rag_service or RAGService()
            self.tts_service = tts_service or TTSService()
            
            # OpenAI API 키 설정
            self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
            
             # 중복 처리 설정 추가 (환경 변수나 기본값 사용)
            self.enable_duplicate_checking = os.environ.get("ENABLE_DUPLICATE_CHECKING", "True").lower() == "true"
            self.enable_gpt_correction = os.environ.get("GPT_CORRECTION_ENABLED", "True").lower() == "true"
            self.enable_performance_logging = os.environ.get("ENABLE_PERFORMANCE_LOGGING", "True").lower() == "true"

            # OpenAI 클라이언트 초기화
            self.openai_client = None
            if self.openai_api_key:
                try:
                    self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
                    logger.info("OpenAI 클라이언트 초기화 완료")
                except Exception as e:
                    logger.warning(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
            
            # 캐시 및 상태 관리
            self._response_cache = {}
            self._rag_cache = {}
            self._tts_cache = {}
            self._cache_timestamps = {}

            # 캐시 설정
            self._cache_ttl = 3600  # 캐시 만료 시간(초)
            self._response_cache_max_size = 100
            self._rag_cache_max_size = 50
            self._tts_cache_max_size = 50

            # 대화 상태 관리
            self.current_state = "start"
            self.current_slots = {}
            self.conversation_history = []
            self.max_history_length = 10

            # 고우선순위 문구 추가
            self._high_priority_phrases = [
                "아메리카노", "카페라떼", "카페모카", "바닐라라떼", "카라멜마끼아또",
                "초코라떼", "그린라떼", "복숭아아이스티", "아이스티", "레몬에이드", "허브티"
                "주문 확인"
            ]

            # 처리 관련 변수
            self._last_processed_input = None
            self._last_result = None
            self._processing = False
            
            # 초기화 플래그 설정
            self._already_initialized = True
            
            logger.info("EnhancedPipelineService 초기화 완료")
        
        except Exception as e:
            logger.error(f"EnhancedPipelineService 초기화 중 오류 발생: {str(e)}")
            # 오류 발생 시 초기화 상태 재설정
            self._already_initialized = False
            raise

    @classmethod
    async def create(
        cls,
        stt_service: Optional[STTService] = None,
        rag_service: Optional[RAGService] = None,
        tts_service: Optional[TTSService] = None,
        openai_api_key: Optional[str] = None
    ):
        """
        비동기 팩토리 메서드
        - 스레드로부터 안전한 인스턴스 생성
        """
        async with cls._initialization_lock:
            if not cls._instance:
                cls._instance = cls(
                    stt_service, 
                    rag_service, 
                    tts_service, 
                    openai_api_key
                )
            
            # 초기화 메서드 호출
            if not cls._is_initialized:
                try:
                    await cls._instance.initialize()
                    cls._is_initialized = True
                except Exception as e:
                    logger.error(f"EnhancedPipelineService 초기화 실패: {str(e)}")
                    cls._is_initialized = False
            
            return cls._instance
          
    async def initialize(self):
        """
        서비스 초기화 메서드
        - 캐시 초기화
        - 공통 응답 미리 생성
        - 서비스 의존성 준비
        """
        try:
            logger.info("EnhancedPipelineService 초기화 시작")
            
            # 캐시 초기화
            self._response_cache.clear()
            self._rag_cache.clear()
            self._tts_cache.clear()
            self._cache_timestamps.clear()
            
            # RAG 서비스 초기화 (필요한 경우)
            if not self.rag_service.is_initialized:
                await asyncio.wait_for(self.rag_service.initialize(), timeout=5.0)

        
            # 2. 자주 사용되는 응답들 목록
            common_responses = [
                # 인사 및 시작
                "안녕하세요, 어서오세요. 무엇을 도와드릴까요?",
                "메뉴를 선택해주세요.",
                
                # 메뉴 주문 확인
                "아메리카노 1잔 주문 확인했습니다.",
                "카페라떼 1잔 주문 확인했습니다.",
                "카페모카 1잔 주문 확인했습니다.",
                "바닐라라떼 1잔 주문 확인했습니다.",
                "카라멜마끼아또 1잔 주문 확인했습니다.",
                "초코라떼 1잔 주문 확인했습니다.",
                "그린라떼 1잔 주문 확인했습니다.",
                "복숭아아이스티 1잔 주문 확인했습니다.",
                "아이스티 1잔 주문 확인했습니다.",
                "허브티 1잔 주문 확인했습니다.",
                "레몬에이드 1잔 주문 확인했습니다."

            ]
            
            # 3. 일반적인 메뉴와 옵션 조합 미리 생성
            menu_options = [
                "따뜻하게",
                "차갑게",
                "라지 사이즈",
                "레귤러 사이즈",
                "스몰 사이즈",
                "샷추가"
            ]
            
            common_responses.extend([f"{opt} 준비해드리겠습니다." for opt in menu_options])
            
            # 병렬 TTS 처리
            async def _pregenerate_tts(responses):
                tasks = []
                for response in responses:
                    tasks.append(
                        asyncio.create_task(
                            self.tts_service.synthesize(response, play_audio=False)
                        )
                    )
                return await asyncio.gather(*tasks)
            
            # 5. RAG 서비스 초기화 (필요한 경우)
            if not self.rag_service.is_initialized:
                try:
                    rag_init_task = asyncio.create_task(self.rag_service.initialize())
                    await asyncio.wait_for(rag_init_task, timeout=5.0)
                    logger.info("RAG 서비스 초기화 완료")
                except asyncio.TimeoutError:
                    logger.warning("RAG 서비스 초기화 시간 초과, 백그라운드로 계속 진행")
                    # 백그라운드에서 계속 초기화
                    asyncio.create_task(self.rag_service.initialize())
                except Exception as e:
                    logger.error(f"RAG 서비스 초기화 실패: {str(e)}")
            
            # 6. 메뉴 데이터 미리 로드
            try:
                menu_count = len(MENU_DATA.get("menus", []))
                logger.info(f"메뉴 데이터 로드 완료: {menu_count}개 메뉴")
            except Exception as e:
                logger.error(f"메뉴 데이터 로드 실패: {str(e)}")
            
            # TTS 미리 생성
            await _pregenerate_tts(common_responses)
            
            # 7. 백그라운드에서 TTS 미리 생성 (서비스 시작 지연 방지)
            asyncio.create_task(_pregenerate_tts(common_responses))
            
            self.__class__._initialization_complete = True
            logger.info("파이프라인 서비스 초기화 및 응답 최적화 완료")
        
        except asyncio.TimeoutError:
            logger.warning("서비스 초기화 시간 초과")
        except Exception as e:
            logger.error(f"초기화 중 오류 발생: {str(e)}")
            raise

        
        # 5. RAG 서비스 초기화 (필요한 경우)
        if not self.rag_service.is_initialized:
            try:
                rag_init_task = asyncio.create_task(self.rag_service.initialize())
                await asyncio.wait_for(rag_init_task, timeout=5.0)
                logger.info("RAG 서비스 초기화 완료")
            except asyncio.TimeoutError:
                logger.warning("RAG 서비스 초기화 시간 초과, 백그라운드로 계속 진행")
                # 백그라운드에서 계속 초기화
                asyncio.create_task(self.rag_service.initialize())
            except Exception as e:
                logger.error(f"RAG 서비스 초기화 실패: {str(e)}")
        
        # 6. 메뉴 데이터 미리 로드
        try:
            menu_count = len(MENU_DATA.get("menus", []))
            logger.info(f"메뉴 데이터 로드 완료: {menu_count}개 메뉴")
        except Exception as e:
            logger.error(f"메뉴 데이터 로드 실패: {str(e)}")
        
        # 7. 백그라운드에서 TTS 미리 생성 (서비스 시작 지연 방지)
        asyncio.create_task(_pregenerate_tts())
        
        self.__class__._initialization_complete = True
        logger.info("파이프라인 서비스 초기화 및 응답 최적화 완료")
        
    def _add_to_conversation_history(self, role: str, content: str) -> None:
        """대화 이력에 메시지 추가"""
        self.conversation_history.append({"role": role, "content": content})
        
        # 최대 길이 제한
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def _extract_menu_info(self, text: str) -> Dict[str, Any]:
        """텍스트에서 메뉴 정보 추출 (간소화 버전)"""
        # 메뉴와 수량 추출 로직
        result = {
            "has_menu": False,
            "menu_name": "",
            "count": 1
        }
        
        # 메뉴 목록
        menu_list = ["아메리카노", "카페라떼", "카페모카", "바닐라라떼", "카라멜마끼아또", 
                    "초코라떼", "그린라떼", "아이스티", "허브티", "레몬에이드"]
        
        # 길이 순으로 정렬 (긴 이름부터 검색)
        menu_list.sort(key=len, reverse=True)
        
        # 메뉴 검색
        for menu in menu_list:
            if menu in text:
                result["has_menu"] = True
                result["menu_name"] = menu
                
                # 수량 추출
                count_match = re.search(rf'{menu}\s*(\d+)\s*잔', text)
                if count_match:
                    try:
                        result["count"] = int(count_match.group(1))
                    except ValueError:
                        pass
                elif f"{menu} 한 잔" in text or f"{menu} 한잔" in text or f"{menu}한잔" in text:
                    result["count"] = 1
                    
                break
        
        return result
    
    def _is_duplicate_order(self, current_query: str, previous_query: str) -> bool:
        """동일한 메뉴의 중복 주문인지 확인"""
        # 이전 쿼리와 현재 쿼리 비교
        if not previous_query or not current_query:
            return False
            
        # 주요 메뉴 키워드 추출
        menu_keywords = [m["name"] for m in MENU_DATA.get("menus", [])]
        
        # 각 쿼리에서 메뉴 키워드 찾기
        current_menus = [menu for menu in menu_keywords if menu in current_query]
        previous_menus = [menu for menu in menu_keywords if menu in previous_query]
        
        # 동일 메뉴가 있으면 중복으로 간주
        return bool(set(current_menus) & set(previous_menus))
    
    def _is_similar_order(self, text1: str, text2: str) -> bool:
        """두 텍스트가 유사한 주문인지 확인 (동일 메뉴와 수량)"""
        try:
            # 주요 메뉴 키워드 추출
            menu_keywords = [m["name"] for m in MENU_DATA.get("menus", [])]
            
            # 숫자 패턴 (수량)
            number_pattern = r'(\d+)\s*잔'
            
            # 각 텍스트에서 메뉴와 수량 추출
            menu_counts1 = {}
            menu_counts2 = {}
            
            for menu in menu_keywords:
                if menu in text1:
                    # 수량 추출
                    match = re.search(rf'{menu}\s*(\d+)\s*잔', text1)
                    if match:
                        menu_counts1[menu] = int(match.group(1))
                    elif f"{menu} 한 잔" in text1 or f"{menu} 한잔" in text1 or f"{menu}한잔" in text1:
                        menu_counts1[menu] = 1
                    else:
                        menu_counts1[menu] = 1  # 기본값
                
                if menu in text2:
                    # 수량 추출
                    match = re.search(rf'{menu}\s*(\d+)\s*잔', text2)
                    if match:
                        menu_counts2[menu] = int(match.group(1))
                    elif f"{menu} 한 잔" in text2 or f"{menu} 한잔" in text2 or f"{menu}한잔" in text2:
                        menu_counts2[menu] = 1
                    else:
                        menu_counts2[menu] = 1  # 기본값
            
            # 메뉴와 수량이 동일한지 확인
            return menu_counts1 == menu_counts2 and bool(menu_counts1)
            
        except Exception as e:
            logger.error(f"유사 주문 확인 중 오류 발생: {str(e)}")
            return False
    
    async def _process_nlp(self, text: str) -> Dict[str, Any]:
        """NLP 처리 메서드"""
        return extract_intent_and_slots(text)
    
    def _should_use_rag(self, intent: str, query_text: str, slots: Dict[str, Any]) -> bool:
        """RAG 사용 필요성 판단"""
        # 메뉴 관련 기본 질문은 RAG 생략 (빠른 경로)
        if intent == "order" and "menu" in slots:
            return False
        
        # 간단한 옵션 선택도 RAG 생략
        if intent == "option" and any(opt in slots for opt in ["temperature", "size"]):
            return False
        
        # 결제 관련도 RAG 생략
        if intent == "payment" or "payment_method" in slots:
            return False
        
        # 메뉴 추천, 복잡한 질문에만 RAG 사용
        return (
            "추천" in query_text or
            "어떤" in query_text and "메뉴" in query_text or
            "메뉴" in query_text and "뭐" in query_text or
            intent == "help"
        )
    
    async def _process_rag_with_timeout(self, query_text: str) -> str:
        """제한 시간 내 RAG 처리"""
        try:
            if not self.rag_service.is_initialized:
                await asyncio.wait_for(self.rag_service.initialize(), timeout=1.0)
            
            rag_response = await asyncio.wait_for(
                self.rag_service.query_knowledge_base(query_text),
                timeout=2.0
            )
            return rag_response
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"RAG 처리 실패 또는 타임아웃: {str(e)}")
            return ""
    
    def _get_from_cache(self, key: str, cache_dict: Dict[str, Any]) -> Any:
        """캐시에서 값 가져오기"""
        if key in cache_dict:
            # 캐시 타임스탬프 확인
            timestamp = self._cache_timestamps.get(key, 0)
            # 캐시 TTL 내 항목만 사용
            if time.time() - timestamp < self._cache_ttl:
                return cache_dict[key]
        
        return None
    
    def _add_to_cache(self, key: str, value: Any, cache_dict: Dict[str, Any], max_size: int = 100):
        # 메뉴별로 고유한 캐시 키 생성
        menu_list = ["아메리카노", "카페라떼", "카페모카", "바닐라라떼", 
                    "카라멜마끼아또", "초코라떼", "그린라떼", 
                    "복숭아아이스티", "아이스티", "허브티", "레몬에이드"]
        
        # 메뉴가 포함된 경우 해당 메뉴로 키 생성
        for menu in menu_list:
            if menu in key:
                key = f"{menu}_cache_{hash(key)}"
                break

        # 캐시 크기 제한
        if len(cache_dict) >= max_size:
            # 가장 오래된 항목 제거
            oldest_key = None
            oldest_time = float('inf')
            
            for k in cache_dict.keys():
                timestamp = self._cache_timestamps.get(k, 0)
                if timestamp < oldest_time:
                    oldest_time = timestamp
                    oldest_key = k
            
            if oldest_key:
                if oldest_key in cache_dict:
                    del cache_dict[oldest_key]
                if oldest_key in self._cache_timestamps:
                    del self._cache_timestamps[oldest_key]
        
        # 값과 타임스탬프 저장
        cache_dict[key] = value
        self._cache_timestamps[key] = time.time()
    
    def _get_cached_tts(self, text: str) -> Optional[Dict[str, Any]]:
        # 정확한 메뉴 이름 매칭
        for cached_text, cached_result in self._tts_cache.items():
            # 메뉴 이름 정확히 매칭
            if any(menu in text and menu in cached_text for menu in [
                "아메리카노", "카페라떼", "카페모카", "바닐라라떼", 
                "카라멜마끼아또", "초코라떼", "그린라떼", 
                "복숭아아이스티", "아이스티", "허브티", "레몬에이드"
            ]):
                return cached_result
        
        return None 
    
    async def _process_tts(self, text: str, play_audio: bool = True) -> Dict[str, Any]:
        """최적화된 TTS 처리"""
        # 1. 캐시 확인
        cached_result = self._get_cached_tts(text)
        if cached_result:
            # 캐시된 결과 사용
            if play_audio:
                # 오디오 재생만 수행
                try:
                    await self.tts_service.play_audio(cached_result["audio_path"])
                    logger.info(f"캐시된 오디오 재생: {cached_result['audio_path']}")
                except Exception as e:
                    logger.error(f"캐시된 오디오 재생 실패: {str(e)}")
            
            return cached_result
        
        # 2. 새 TTS 생성
        start_time = time.time()
        tts_result = await self.tts_service.synthesize(text, play_audio=play_audio)
        duration = time.time() - start_time
        
        # 생성 시간 기록
        logger.info(f"TTS 생성 시간: {duration:.2f}초")
        
        # 3. 결과 캐싱 (성공한 경우만)
        if tts_result["success"]:
            # 문구에 우선순위 키워드가 포함되어 있거나 짧은 문구면 캐싱
            if len(text) < 100 or any(phrase in text for phrase in self._high_priority_phrases):
                self._add_to_cache(text, tts_result, self._tts_cache, self._tts_cache_max_size)
        
        return tts_result
    
    async def process_text_query(self, query_text: str) -> Dict[str, Any]:
        """최적화된 텍스트 쿼리 처리: NLP -> FSM -> RAG -> GPT -> TTS 파이프라인"""
        # 성능 측정 시작
        start_time = time.time()
        
        # 중복 처리 방지 개선
        if self.enable_duplicate_checking:
            # 완전히 동일한 쿼리 중복 체크
            if query_text == self._last_processed_input and self._last_result:
                logger.info(f"중복 입력 감지, 기존 결과 반환: '{query_text}'")
                return self._last_result
                
            # 유사 주문 중복 체크
            if self._last_processed_input and self._is_similar_order(query_text, self._last_processed_input):
                logger.info(f"유사 주문 감지, 중복 처리 방지: '{query_text}' vs '{self._last_processed_input}'")
                
                if self._last_result:
                    # 기존 결과의 사본을 반환하되, 중복 플래그 추가
                    result = self._last_result.copy()
                    result["duplicate_detected"] = True
                    return result
        
        # 처리 중 플래그 확인
        if self._processing:
            logger.info("이미 처리 중인 입력이 있습니다. 중복 처리 방지.")
            return {
                "success": False,
                "error": "이미 처리 중인 요청이 있습니다.",
                "stage": "duplicate",
                "response_text": "잠시만 기다려주세요."
            }
        
        # 처리 플래그 설정
        self._processing = True
        
        try:
            # 병렬 처리를 위한 작업 모음
            tasks = []
            
            # 로그 추가
            logger.info(f"텍스트 쿼리 처리 시작: '{query_text}'")
            
            # 대화 이력에 사용자 입력 추가
            self._add_to_conversation_history("user", query_text)
            
            # 메뉴 정보 빠른 추출 (우선 순위 경로)
            menu_info = self._extract_menu_info(query_text)
            has_menu = menu_info["has_menu"]
            menu_name = menu_info["menu_name"]
            menu_count = menu_info["count"]
            
            # 빠른 경로 판단 (메뉴 주문)
            use_fast_path = False
            predicted_response = None
            
            if has_menu:
                # 예측 응답 준비
                predicted_response = f"{menu_name} {menu_count}잔 주문 확인했습니다."
                # TTS 미리 준비 시작 (병렬)
                if predicted_response not in self._tts_cache:
                    tts_task = asyncio.create_task(self._process_tts(predicted_response, play_audio=False))
                    tasks.append(tts_task)
            
            # 1. NLP로 의도와 슬롯 추출
            nlp_task = asyncio.create_task(self._process_nlp(query_text))
            tasks.append(nlp_task)
            
            # NLP 결과 가져오기
            nlp_result = await nlp_task
            intent = nlp_result["intent"]
            slots = nlp_result["slots"]
            
            # 로그 추가
            logger.info(f"NLP 결과: 의도={intent}, 슬롯={slots}")
            
            # 메뉴 주문 확인 (빠른 경로)
            if intent == "order" and has_menu:
                use_fast_path = True
                logger.info(f"빠른 경로 사용: 메뉴 '{menu_name}' 주문 감지")
            
            # 결제 관련 키워드 확인 (빠른 경로)
            is_payment = any(word in query_text.lower() for word in ["결제", "카드", "계산", "페이"])
            if is_payment:
                use_fast_path = True
                predicted_response = "결제가 완료되었습니다. 이용해주셔서 감사합니다."
                logger.info("빠른 경로 사용: 결제 관련 키워드 감지")
                
                # TTS 미리 준비 시작 (병렬)
                if predicted_response not in self._tts_cache:
                    tts_task = asyncio.create_task(self._process_tts(predicted_response, play_audio=False))
                    tasks.append(tts_task)
            
            # 이전 슬롯 백업 및 새 슬롯 병합
            self.previous_slots = self.current_slots.copy()

            # "추가" 주문 처리 - "is_additional_order" 플래그 확인
            if "is_additional_order" in slots and slots["is_additional_order"] and "menu_quantities" in slots:
                # 현재 슬롯에서 기존 주문 정보 가져오기
                current_quantities = self.current_slots.get("menu_quantities", {}).copy()
                
                # 새 주문 정보 병합 (새 메뉴는 추가, 기존 메뉴는 수량 증가)
                for menu, quantity in slots["menu_quantities"].items():
                    if menu in current_quantities:
                        # 기존에 있던 메뉴는 새로 주문한 quantity만큼만 정확히 더함
                        current_quantities[menu] += quantity
                        logger.info(f"기존 메뉴 수량 증가: {menu} +{quantity}잔 = {current_quantities[menu]}잔")
                    else:
                        # 새 메뉴는 그대로 추가
                        current_quantities[menu] = quantity
                        logger.info(f"새 메뉴 추가: {menu} {quantity}잔")
                
                # 업데이트된 수량 정보를 슬롯에 저장 (기존 슬롯 덮어쓰기)
                slots["menu_quantities"] = current_quantities
                
                # 총 수량 업데이트 (현재 메뉴 수량의 합계)
                total_count = sum(current_quantities.values())
                slots["count"] = total_count
                logger.info(f"총 주문 수량: {total_count}잔")
                
                # 주문 상세 내역 업데이트
                order_details = []
                for menu, quantity in current_quantities.items():
                    order_details.append(f"{menu} {quantity}잔")
                slots["order_details"] = ", ".join(order_details)

            # remove 의도 처리 로직 - 메뉴 삭제 또는 수량 감소
            if intent == "remove" and "menu" in slots:
                menu_name = slots["menu"]
                # 현재 슬롯의 메뉴 수량 복사본 생성
                current_quantities = self.current_slots.get("menu_quantities", {}).copy()
                
                if menu_name in current_quantities:
                    # 메뉴가 존재하면 수량 감소
                    current_quantities[menu_name] -= 1
                    
                    # 수량이 0 이하면 메뉴 삭제
                    if current_quantities[menu_name] <= 0:
                        del current_quantities[menu_name]
                        logger.info(f"메뉴 삭제: {menu_name}")
                    else:
                        logger.info(f"메뉴 수량 감소: {menu_name}, 남은 수량: {current_quantities[menu_name]}잔")
                    
                    # 총 가격 재계산
                    total_price = 0
                    for menu, quantity in current_quantities.items():
                        menu_info = next((m for m in MENU_DATA.get("menus", []) if m["name"] == menu), None)
                        if menu_info:
                            base_price = menu_info.get("basePrice", 4500)
                            total_price += base_price * quantity
                        else:
                            # 기본 가격 (메뉴 정보가 없는 경우)
                            total_price += 4500 * quantity
                    slots["total_price"] = f"{total_price:,}"
                    
                    # 로그 추가
                    logger.info(f"추가 주문 병합 완료: {slots['menu_quantities']}, 총 {slots['count']}잔, {slots['total_price']}원")
                    
                    # 플래그 제거 (처리 완료)
                    del slots["is_additional_order"]
                    
                    # 수정된 정보를 slots에 업데이트
                    slots["menu_quantities"] = current_quantities
                    slots["count"] = sum(current_quantities.values()) if current_quantities else 0
                    
                    if order_details:
                        slots["order_details"] = ", ".join(order_details)
                        slots["total_price"] = f"{total_price:,}"
                    else:
                        # 모든 메뉴가 제거된 경우
                        slots["order_details"] = "주문 없음"
                        slots["total_price"] = "0"
                        
                        # 메뉴 필드 비워주기
                        if "menu" in slots:
                            del slots["menu"]
                        if "menu_list" in slots:
                            del slots["menu_list"]
                            
                    # 현재 슬롯에 업데이트된 정보 즉시 반영 (중요!)
                    self.current_slots.update(slots)
                    logger.info(f"업데이트된 주문 내역: {slots.get('order_details', '없음')}, 총 가격: {slots.get('total_price', '0')}원")

                else:
                    logger.info(f"제거할 메뉴가 없음: {menu_name}")
                    # 사용자에게 알림
                    slots["error_message"] = f"{menu_name}은(는) 현재 주문 내역에 없습니다."

            elif "menu" in slots:
                # 기존 메뉴 처리 로직 (변경없음)
                if "menu_list" in slots and isinstance(slots["menu_list"], list) and len(slots["menu_list"]) > 1:
                    # 다중 메뉴 정보 보존
                    logger.info(f"여러 메뉴 감지: {slots['menu_list']}")
                    
                    # menu_quantities 정보 처리
                    if "menu_quantities" in slots and isinstance(slots["menu_quantities"], dict):
                        # 새 주문으로 처리 (이전 주문 정보 대체)
                        new_quantities = slots["menu_quantities"]
                        
                        # 수량 정보 그대로 사용
                        slots["menu_quantities"] = new_quantities
                        slots["count"] = sum(new_quantities.values())
                        
                        # 주문 내역 업데이트
                        order_details = []
                        total_price = 0
                        
                        for menu, count in new_quantities.items():
                            # 주문 내역에 추가
                            order_details.append(f"{menu} {count}잔")
                            
                            # 해당 메뉴의 가격 계산
                            menu_info = next((m for m in MENU_DATA.get("menus", []) if m["name"] == menu), None)
                            if menu_info:
                                base_price = menu_info.get("basePrice", 4500)
                                total_price += base_price * count
                            else:
                                # 기본 가격 (메뉴 정보가 없는 경우)
                                total_price += 4500 * count
                        
                        # 총 주문 정보 업데이트
                        slots["order_details"] = ", ".join(order_details)
                        slots["total_price"] = f"{total_price:,}"
                        
                        # 현재 슬롯 업데이트 (새 주문으로 설정)
                        self.current_slots = slots
                        logger.info(f"다중 메뉴 처리 완료: {new_quantities}, 총 {slots['count']}잔, {slots['total_price']}원")
                
                # 단일 메뉴인 경우 기존 로직 유지
                elif isinstance(slots["menu"], str):
                    menu_name = slots["menu"]
                    
                    # 중요: 수량 정보를 이미 NLP에서 추출한 경우 해당 값을 우선 사용
                    if "menu_quantities" in slots and menu_name in slots["menu_quantities"]:
                        count = slots["menu_quantities"][menu_name]
                    else:
                        # 수량 정보가 없는 경우에만 기본값 사용
                        count = slots.get("count", 1)
                    
                    logger.info(f"단일 메뉴 처리: {menu_name}, 수량: {count}잔")

                    # 새 주문으로 처리 (기존 주문을 대체하지 않고 새로 설정)
                    menu_quantities = {menu_name: count}
                    slots["menu_quantities"] = menu_quantities
                    slots["count"] = count
                    
                    # 총 가격 계산
                    total_price = 0
                    menu_info = next((m for m in MENU_DATA.get("menus", []) if m["name"] == menu_name), None)
                    if menu_info:
                        base_price = menu_info.get("basePrice", 4500)
                        total_price = base_price * count
                    else:
                        # 기본 가격 (메뉴 정보가 없는 경우)
                        total_price = 4500 * count
                    
                    slots["total_price"] = f"{total_price:,}"
                    slots["order_details"] = f"{menu_name} {count}잔"
                    
                    # 현재 슬롯 업데이트 (새 주문으로 설정)
                    self.current_slots = slots
                    logger.info(f"단일 메뉴 주문 처리 완료: {menu_name} {count}잔, {total_price}원")
            else:
                # 메뉴가 없는 경우는 슬롯 전체 업데이트
                self.current_slots = {**slots}
                
                # 2. FSM으로 상태 전이
            try:
                current_state = self.current_state
                
                # 결제 관련 인텐트 및 키워드가 있을 때 바로 payment 상태로 전환
                if (intent == "payment" or is_payment) and "menu" in self.current_slots:
                    next_state = "payment"
                    logger.info(f"결제 의도 감지: {current_state} -> {next_state}")
                    
                    # 결제 방법이 명시되지 않은 경우 기본값 설정
                    if "payment_method" not in slots and "카드" in query_text:
                        slots["payment_method"] = "카드"
                    elif "payment_method" not in slots:
                        slots["payment_method"] = "결제"
                else:
                    next_state = fsm.get_next_state(current_state, intent, self.current_slots)
                
                # 로그 추가
                logger.info(f"상태 전이: {current_state} -> {next_state}")
                self.current_state = next_state
            except Exception as fsm_error:
                logger.error(f"FSM 상태 전이 중 오류 발생: {str(fsm_error)}")
                # 오류 발생 시 현재 상태 유지
                next_state = self.current_state
            
            # 3. 기본 FSM 응답 생성 
            base_response = fsm.get_response(next_state, self.current_slots)
            
            # 4. RAG 서비스 호출 - 필요한 경우만 & 병렬 처리
            rag_response = ""
            rag_task = None
            
            if self._should_use_rag(intent, query_text, slots):
                # 캐시 확인
                rag_cache_key = f"rag_{query_text.lower().strip()}"
                cached_rag = self._get_from_cache(rag_cache_key, self._rag_cache)
                
                if cached_rag:
                    rag_response = cached_rag
                    logger.info(f"RAG 캐시 사용: '{rag_cache_key}'")
                else:
                    # RAG 비동기 처리 시작
                    rag_task = asyncio.create_task(self._process_rag_with_timeout(query_text))
                    tasks.append(rag_task)
            
            # 5. 최종 응답 생성
            final_response = ""
            
            # 빠른 경로 사용 시 (메뉴 주문 또는 결제)
            if use_fast_path and predicted_response:
                final_response = predicted_response
                logger.info(f"빠른 경로 응답 사용: '{final_response}'")
            else:
                # RAG 결과 확인 (병렬 처리 대기)
                if rag_task:
                    try:
                        rag_response = await asyncio.wait_for(rag_task, timeout=2.0)
                        logger.info(f"RAG 응답: {rag_response}")
                        
                        # 결과 캐싱
                        self._add_to_cache(f"rag_{query_text.lower().strip()}", 
                                          rag_response, self._rag_cache, self._rag_cache_max_size)
                    except asyncio.TimeoutError:
                        logger.warning("RAG 처리 시간 초과, 기본 응답 사용")
                    except Exception as e:
                        logger.error(f"RAG 처리 오류: {str(e)}")
                
                # GPT로 최종 통합 응답 생성 (타임아웃 설정)
                try:
                    gpt_task = asyncio.create_task(
                        self._generate_unified_response(
                            query_text, intent, self.current_slots, 
                            current_state, next_state, base_response, rag_response
                        )
                    )
                    tasks.append(gpt_task)
                    
                    final_response = await asyncio.wait_for(gpt_task, timeout=2.0)
                    logger.info(f"GPT 통합 응답: '{final_response}'")
                except asyncio.TimeoutError:
                    logger.warning("GPT 응답 생성 시간 초과, 기본 응답 사용")
                    # 시간 초과 시 기본 응답 사용
                    final_response = base_response
                except Exception as e:
                    logger.error(f"GPT 응답 생성 실패: {str(e)}")
                    # 오류 시 기본 응답 사용
                    final_response = base_response
            
            # 응답 로그 추가
            logger.info(f"최종 응답: '{final_response}'")
            
            # 대화 이력에 시스템 응답 추가
            self._add_to_conversation_history("assistant", final_response)
            
            # 6. TTS로 음성 합성 - 최적화된 버전 사용
            tts_start_time = time.time()
            tts_result = await self._process_tts(final_response, play_audio=True)
            tts_duration = time.time() - tts_start_time
            
            if self.enable_performance_logging:
                logger.info(f"TTS 처리 시간: {tts_duration:.3f}초")
            
            if not tts_result["success"]:
                return {
                    "success": False,
                    "error": tts_result.get("error", "음성 합성 실패"),
                    "stage": "tts",
                    "response_text": final_response
                }
            
            # 7. WebSocket 알림 (선택적)
            try:
                from app.services.connection_manager import manager
                await manager.notify_clients(next_state, final_response, self.current_slots)
            except (ImportError, Exception) as e:
                # 웹소켓 오류는 무시 (TTS 결과는 이미 생성됨)
                logger.debug(f"WebSocket 알림 실패 (무시): {str(e)}")
            
            # 8. 처리 시간 계산 및 로깅
            total_duration = time.time() - start_time
            if self.enable_performance_logging:
                logger.info(f"총 처리 시간: {total_duration:.3f}초")
            
            # 9. 결과 준비 및 저장
            result = {
                "success": True,
                "audio": tts_result["audio"],
                "audio_path": tts_result["audio_path"],
                "audio_base64": tts_result.get("audio_base64", ""),
                "response_text": final_response,
                "current_state": next_state,
                "processing_time": total_duration,
                "_meta": {
                    "query": query_text,
                    "intent": intent,
                    "slots": self.current_slots,
                    "rag_used": bool(rag_response),
                    "fast_path": use_fast_path
                }
            }
            
            # 처리 결과 저장
            self._last_processed_input = query_text
            self._last_result = result
            
            return result
                
        except Exception as e:
            self._processing = False  # 오류 발생 시에도 플래그 초기화
            logger.error(f"텍스트 쿼리 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "pipeline",
                "response_text": "주문을 처리하는데 문제가 발생했습니다. 다시 말씀해 주시겠어요?"
            }
        finally:
            # 처리 완료 플래그 설정
            self._processing = False
    
    async def _generate_unified_response(
    self, query_text: str, intent: str, slots: Dict[str, Any],
    current_state: str, next_state: str, 
    base_response: str, rag_response: str
    ) -> str:

        # 직접 메뉴 이름 추출
        menu_list = ["아메리카노", "카페라떼", "카페모카", "바닐라라떼", 
                    "카라멜마끼아또", "초코라떼", "그린라떼", 
                    "복숭아아이스티", "아이스티", "허브티", "레몬에이드"]
        
        detected_menu = next((menu for menu in menu_list if menu in query_text), None)
        
        # 메뉴가 감지된 경우 해당 메뉴로 응답 생성
        if detected_menu:
            count = slots.get("count", 1)
            return f"{detected_menu} {count}잔 주문 확인했습니다."
        
        # 메뉴 추천 의도 확인
        if intent == "recommend":
            menu_recommender = MenuRecommendationService()
            recommendation = menu_recommender.recommend_menu({
                'query_text': query_text,
                'intent': intent,
                'slots': slots,
                'current_state': current_state
            })
            return recommendation

        # OpenAI API가 설정되지 않았으면 기본 응답 조합
        if not self.openai_client:
            # 기본 응답과 RAG 응답 결합
            if rag_response:
                # 중복 내용 제거
                if base_response in rag_response:
                    return rag_response
                else:
                    return f"{base_response} {rag_response}"
            return base_response
        
        try:
            # 1. 응답 패턴 확인 - 자주 사용되는 패턴은 바로 반환
            # 메뉴 주문에 대한 빠른 응답
            if intent == "order" and "menu" in slots:
                menu_name = slots["menu"] if isinstance(slots["menu"], str) else slots["menu"][0]
                count = slots.get("count", 1)
                # 아주 자주 사용되는 응답 패턴
                return f"{menu_name} {count}잔 주문 확인했습니다."
            
            # 결제 관련 빠른 응답
            if next_state == "payment" or "payment" in intent:
                return "결제가 완료되었습니다. 곧 음료 준비해드리겠습니다."
            
            # 2. 캐시 확인 - 이전에 처리한 유사 쿼리 활용
            cache_key = f"{intent}_{next_state}_{hash(str(slots))}"
            cached_response = self._get_from_cache(cache_key, self._response_cache)
            if cached_response:
                logger.info(f"GPT 응답 캐시 사용: {cache_key}")
                return cached_response
                
            # 3. GPT 요청 최적화 - 더 작은 프롬프트, 더 적은 토큰
            system_message = {
                "role": "system",
                "content": f"""
                카페 키오스크 직원으로서 간결하게 응답하세요. 현재 대화 상태: {next_state}
                1. 응답은 반드시 30자 이내로 짧게 작성
                2. 핵심 정보만 정확히 전달
                3. 자연스러운 대화체 사용
                """
            }
            
            # 더 작은 컨텍스트 메시지
            context_message = {
                "role": "user",
                "content": f"주문: {query_text}\n상태: {next_state}\n기본응답: {base_response}"
            }
            
            # 4. GPT API 호출
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[system_message, context_message],
                temperature=0.5,  # 낮은 온도로 더 결정적인 생성
                max_tokens=30,    # 적은 토큰으로 제한
                top_p=0.8         # 샘플링 조정
            )
            
            unified_response = response.choices[0].message.content.strip()
            
            # 5. 캐시 업데이트
            self._add_to_cache(cache_key, unified_response, self._response_cache, self._response_cache_max_size)
            
            return unified_response
                
        except Exception as e:
            logger.error(f"GPT 응답 생성 실패: {str(e)}")
            # 오류 시 기본 응답 조합으로 폴백
            if rag_response:
                if base_response in rag_response:
                    return rag_response
                else:
                    return f"{base_response} {rag_response}"
            return base_response
    
    def _format_menu_info(self, slots: Dict[str, Any]) -> str:
        """메뉴와 수량 정보를 깔끔한 형식으로 포맷팅"""
        if "menu" not in slots:
            return "없음"
            
        # 여러 메뉴가 있는 경우
        if "menu_quantities" in slots and isinstance(slots["menu_quantities"], dict) and len(slots["menu_quantities"]) > 0:
            menu_details = []
            for menu, qty in slots["menu_quantities"].items():
                menu_details.append(f"{menu} {qty}잔")
            return ", ".join(menu_details)
        
        # 단일 메뉴인 경우
        elif isinstance(slots["menu"], str):
            menu_name = slots["menu"]
            count = slots.get("count", 1)
            return f"{menu_name} {count}잔"
        
        # 메뉴가 리스트인 경우
        elif isinstance(slots["menu"], list) and len(slots["menu"]) > 0:
            if len(slots["menu"]) == 1:
                # 단일 메뉴 리스트
                menu_name = slots["menu"][0]
                count = slots.get("count", 1)
                return f"{menu_name} {count}잔"
            else:
                # 다중 메뉴 리스트
                menu_details = []
                for menu in slots["menu"]:
                    # 메뉴별 수량 정보 확인
                    qty = 1  # 기본값
                    if "menu_quantities" in slots and menu in slots["menu_quantities"]:
                        qty = slots["menu_quantities"][menu]
                    menu_details.append(f"{menu} {qty}잔")
                return ", ".join(menu_details)
        
        return "메뉴 정보 없음"

    def _summarize_conversation_history(self) -> str:
        """대화 이력 요약 - 마지막 몇 턴의 대화만 제공"""
        if not self.conversation_history:
            return "초기 대화"
            
        # 최근 3턴의 대화만 요약
        recent_history = self.conversation_history[-3:]
        summary = []
        
        for entry in recent_history:
            role = "사용자" if entry["role"] == "user" else "시스템"
            # 내용이 너무 길면 줄임
            content = entry["content"]
            if len(content) > 30:
                content = content[:27] + "..."
            summary.append(f"{role}: {content}")
        
        return " | ".join(summary)

    def _get_response_strategy_for_state(self, state: str) -> str:
        """각 상태별 최적의 응답 전략 제공"""
        strategies = {
            "start": "간단한 인사말과 함께 주문을 안내하세요.",
            "greeting": "따뜻한 인사와 함께 메뉴 주문을 유도하세요.",
            "order_taking": "메뉴 주문을 명확히 확인하고 필요한 옵션(온도, 사이즈)을 물어보세요.",
            "option_select": "선택된 옵션을 확인하고 주문 확정을 자연스럽게 유도하세요.",
            "order_confirm": "전체 주문 내역을 간결하게 요약하고 결제 방법을 안내하세요.",
            "payment": "결제 완료를 확인하고 준비 시간과 함께 따뜻한 인사를 전하세요.",
            "farewell": "감사 인사와 함께 다음 방문을 기대하는 따뜻한 마무리를 하세요."
        }
        
        return strategies.get(state, "자연스러운 대화를 이어가세요.")
    
    def _get_system_message_for_state(self, state: str) -> Dict[str, str]:
        """현재 대화 상태에 맞는 시스템 메시지 생성"""
        
        base_instruction = """
        당신은 카페 키오스크의 친절한 AI 직원입니다. 
        사용자의 요청을 이해하고 자연스럽게 응답하세요.
        
        다음 원칙을 항상 따르세요:
        1. "최대 30자"로 답변하세요. 대신 중간에 끊기는것처럼 답변이 나오면 안됩니다.
        2. 사용자에게 공감하고 전문적인 서비스를 제공하세요.
        3. 핵심 정보(메뉴, 가격, 옵션 등)는 정확히 유지하세요.
        4. 응답은 자연스러운 간결한 대화체로 작성하세요.
        5. 주어진 상태에 맞는 응답을 생성하세요.
        6. 최대 2문장 정도의 간결한 응답을 생성하세요.
        7. 한국어로 응답하세요.
        """
        
        state_instructions = {
            "start": "손님을 반갑게 맞이하고 주문을 도와줄 준비가 되어 있음을 알리세요.",
            "greeting": "인사에 응답하고 메뉴 주문을 유도하세요.",
            "order_taking": "메뉴 주문을 받고, 필요한 경우 옵션(온도, 사이즈 등)을 물어보세요.",
            "option_select": "선택한 옵션을 확인하고, 추가 옵션이 필요한지 물어보세요.",
            "order_confirm": "주문 내역을 확인하고 총 가격을 알려준 후, 결제 방법을 안내하세요.",
            "payment": "결제 완료를 알리고 감사 인사를 전하세요.",
            "farewell": "따뜻한 작별 인사와 함께 즐거운 시간을 기원하세요."
        }
        
        instruction = base_instruction + "\n\n" + state_instructions.get(state, "자연스러운 대화를 이어가세요.")
        
        return {
            "role": "system",
            "content": instruction
        }
        
    async def process_audio_query(self, audio_data: BinaryIO) -> Dict[str, Any]:
        """음성 쿼리 처리: STT -> NLP -> FSM -> RAG -> GPT -> TTS 파이프라인"""
        try:
            # 처리 중 플래그 확인
            if self._processing:
                logger.info("이미 처리 중인 입력이 있습니다. 중복 처리 방지.")
                return {
                    "success": False,
                    "error": "이미 처리 중인 요청이 있습니다.",
                    "stage": "duplicate",
                    "response_text": "잠시만 기다려주세요."
                }
            
            self._processing = True
            start_time = time.time()
            
            try:
                # 1. 음성을 텍스트로 변환 (STT)
                stt_result = await self.stt_service.transcribe(audio_data)
                
                if not stt_result["success"]:
                    return {
                        "success": False,
                        "error": stt_result.get("error", "음성인식 실패"),
                        "stage": "stt"
                    }
                
                query_text = stt_result["text"]
                logger.info(f"STT 결과: '{query_text}'")
                
                # 중복 입력 확인
                if self.enable_duplicate_checking and query_text == self._last_processed_input and self._last_result:
                    logger.info(f"중복 입력 감지 (음성): '{query_text}'")
                    return self._last_result
                
                # GPT를 사용하여 음성 인식 결과 개선 (활성화된 경우)
                if self.openai_client and query_text and self.enable_gpt_correction:
                    try:
                        # GPT로 STT 결과 개선
                        response = await asyncio.to_thread(
                            self.openai_client.chat.completions.create,
                            model="gpt-3.5-turbo-1106",
                            messages=[
                                {
                                    "role": "system", 
                                    "content": """
                                    당신은 음성 인식 결과를 교정하는 AI입니다. 
                                    STT 시스템이 오인식한 단어나 구문을 카페 키오스크 맥락에 맞게 
                                    수정해주세요. 다음 정보를 참고하세요:
                                    
                                    카페 메뉴: 아메리카노, 카페라떼, 카페모카, 바닐라라떼, 
                                    카라멜마끼아또, 초코라떼, 그린라떼, 복숭아아이스티, 허브티, 레몬에이드
                                    
                                    관련 단어: 아이스, 핫, 따뜻한, 차가운, 샷추가, 시럽, 휘핑, 레귤러, 
                                    라지, 포장, 매장, 카드, 결제
                                    
                                    중요: 원본 인식 결과를 카페 주문 맥락에 맞게 자연스럽게 수정하되,
                                    1. 발화를 질문형으로 바꾸지 마세요
                                    2. 원래 의미를 유지하세요 
                                    3. 완전히 다른 내용으로 대체하지 마세요
                                    """
                                },
                                {
                                    "role": "user", 
                                    "content": f"음성 인식 결과: {query_text}"
                                }
                            ],
                            timeout=1.5  # 1.5초 타임아웃
                        )
                        
                        corrected_text = response.choices[0].message.content.strip()
                        logger.info(f"GPT 음성 인식 개선: '{query_text}' -> '{corrected_text}'")
                        query_text = corrected_text
                    except Exception as e:
                        logger.warning(f"GPT 음성 인식 개선 실패 (무시): {str(e)}")
                
                # 텍스트 쿼리 처리로 전달
                return await self.process_text_query(query_text)
                
            finally:
                # 처리 시간 로깅
                if self.enable_performance_logging:
                    duration = time.time() - start_time
                    logger.info(f"음성 쿼리 총 처리 시간: {duration:.3f}초")
                
                self._processing = False
                
        except Exception as e:
            self._processing = False  # 오류 발생 시에도 플래그 초기화
            logger.error(f"오디오 쿼리 처리 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stage": "pipeline"
            }
   
    async def process_text_input(self, text: str) -> Dict[str, Any]:
        """텍스트 입력 처리 (키오스크 전용)"""
        # 텍스트 형식 확인
        if isinstance(text, dict) and "text" in text:
            text = text["text"]
            
        # 빈 텍스트 확인
        if not text or not isinstance(text, str) or not text.strip():
            return {
                "success": False,
                "error": "유효한 텍스트가 아닙니다.",
                "response_text": "다시 말씀해 주시겠어요?"
            }
            
        # 중복 입력 확인
        if self.enable_duplicate_checking and text == self._last_processed_input and self._last_result:
            logger.info(f"중복 입력 감지 (텍스트 입력): '{text}'")
            return self._last_result
            
        return await self.process_text_query(text)
    
    async def reset_conversation(self) -> Dict[str, Any]:
        try:

            # FSM 상태 초기화
            reset_already_called = getattr(self, "_reset_already_called", False)
            if not reset_already_called:
                fsm.reset()
                self._reset_already_called = True

            self.current_state = "start"
            self.current_slots = {}
            self.previous_slots = {}
            self.conversation_history = []
            
            # 중복 처리 방지 변수 초기화
            self._last_processed_input = None
            self._last_result = None
            self._processing = False
            
             # 인사말 상태 확인
            if not self.__class__._greeting_shown:
                # 인사말 생성 로직 (기존과 동일)
                greeting = "안녕하세요, 환영합니다!"

                if self.openai_client:
                    try:
                        # 캐시 확인
                        greeting_key = "greeting_message"
                        cached_greeting = self._get_from_cache(greeting_key, self._response_cache)
                        
                        if cached_greeting:
                            greeting = cached_greeting
                            logger.info(f"캐시된 인사말 사용: '{greeting}'")
                        else:
                            response = await asyncio.wait_for(
                                asyncio.to_thread(
                                    self.openai_client.chat.completions.create,
                                    model="gpt-3.5-turbo-1106",
                                    messages=[
                                        {
                                            "role": "system", 
                                            "content": """
                                            당신은 카페 키오스크 AI입니다. 매우 짧고 간결하고 친절하고 따뜻한 인사말을 생성해주세요.
                                            15자를 넘지 마세요.
                                            """
                                        },
                                        {
                                            "role": "user", 
                                            "content": "카페에 방문한 고객을 위한 인사말을 생성해주세요."
                                        }
                                    ]
                                ),
                                timeout=1.5  # 1.5초 타임아웃
                            )
                            
                            #인사말 표시 후 클래스 변수 업데이트
                            self.__class__._greeting_shown = True
                            logger.info("인사말 표시 완료, 클래스 플래그 설정됨")

                            greeting = response.choices[0].message.content.strip()
                            # 캐시에 저장
                            self._add_to_cache(greeting_key, greeting, self._response_cache)
                            logger.info(f"GPT 인사말 생성: '{greeting}'")
                    except Exception as e:
                        logger.error(f"GPT 인사말 생성 실패: {str(e)}")
                        greeting = "안녕하세요, 어서오세요."
                
                # 대화 이력에 시스템 인사말 추가
                self._add_to_conversation_history("assistant", greeting)
                
                # TTS 캐시 확인
                cached_tts = self._get_cached_tts(greeting)
                if cached_tts:
                    tts_result = cached_tts
                    # 오디오 재생
                    await self.tts_service.play_audio(tts_result["audio_path"])
                else:
                    # TTS로 음성 합성 (오디오 자동 재생 활성화)
                    tts_result = await self.tts_service.synthesize(greeting, play_audio=True)
                    # 결과 캐싱
                    self._add_to_cache(greeting, tts_result, self._tts_cache, self._tts_cache_max_size)
            
            else:
                # 이미 인사말이 표시된 경우 로그만 남김
                logger.info("이미 인사말이 표시되었습니다. 인사말 생성 건너뜀")
                
                # 빈 응답 반환을 위한 기본값 설정
                tts_result = {
                    "success": True,
                    "audio": b"",
                    "audio_path": "",
                    "audio_base64": "",
                }
            # 인사말 포함한 응답 반환
            if tts_result and tts_result.get("success", False):
                return {
                    "success": True,
                    "message": "대화가 초기화되었습니다.",
                    "audio": tts_result.get("audio", b""),
                    "audio_path": tts_result.get("audio_path", ""),
                    "audio_base64": tts_result.get("audio_base64", ""),
                    "response_text": greeting if not _greeting_shown else "",
                    "current_state": "start"
                }
            else:
                # TTS 실패 시 기본 응답
                return {
                    "success": False,
                    "error": tts_result.get("error", "음성 합성 실패") if tts_result else "음성 합성 실패",
                    "message": "대화 초기화 실패"
                }
                
        except Exception as e:
            logger.error(f"대화 초기화 중 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "대화 초기화 실패"
            }