# app/models/fsm.py
import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from enum import Enum

import openai
        
logger = logging.getLogger(__name__)

_reset_in_progress = False

class State(Enum):
    START = "start"
    GREETING = "greeting"
    ORDER_TAKING = "order_taking"
    OPTION_SELECT = "option_select"
    ORDER_CONFIRM = "order_confirm"
    PAYMENT = "payment"
    FAREWELL = "farewell"

# 유사어 사전
synonym_dict = {
    # 감정 관련 유사어
    "슬픔": ["슬퍼", "슬프다", "우울하다", "기분이 안 좋다", "슬퍼요", "우울해", "기분이 우울하다"],
    "행복": ["행복하다", "기쁘다", "즐겁다", "행복해", "기분이 좋다"],
    "피곤": ["피곤하다", "힘들다", "지치다", "피곤해", "피곤한", "너무 피곤하다"],
   
    # 날씨 관련 유사어
    "비": ["비", "비가 오다", "비가 내리다", "비가 온다"],
    "더운": ["더운", "덥다", "뜨겁다"],
    "추운": ["추운", "차갑다", "춥다"],
   
    # 시간 관련 유사어
    "아침": ["아침", "오전", "아침시간"],
    "점심": ["점심", "점심시간"],
    "저녁": ["저녁", "저녁시간"],

    "1잔": ["한 잔", "1잔", "하나", "1개", "한 개"],
    "2잔": ["두 잔", "2잔", "둘", "2개", "두 개"],
    "3잔": ["세 잔", "3잔", "셋", "3개", "세 개"],
    "4잔": ["네 잔", "4잔", "넷", "4개", "네 개"],
    "5잔": ["다섯 잔", "5잔", "다섯", "5개", "다섯 개"],
    "6잔": ["여섯 잔", "6잔", "여섯", "6개", "여섯 개"],
    "7잔": ["일곱 잔", "7잔", "일곱", "7개", "일곱 개"],
    "8잔": ["여덟 잔", "8잔", "여덟", "8개", "여덟 개"],
    "9잔": ["아홉 잔", "9잔", "아홉", "9개", "아롭 개"],
    "10잔": ["열 잔", "10잔", "열", "10개", "열 개"],
   
    # 카페 메뉴 관련 유사어
    "아메리카노": ["아메리카노", "아메", "아메리까노", "블랙커피", "에스프레소 물탄거"],
    "카페라떼": ["카페라떼", "라떼", "카페 라떼", "우유 커피", "라테"],
    "바닐라라떼": ["바닐라라떼", "바닐라 라떼", "바닐라", "바닐라 넣은 라떼", "바닐라향 라떼"],
    "카페모카": ["카페모카", "모카", "초코 커피", "초코라떼", "모카라떼", "카페 모카"],
    "초콜릿라떼": ["초콜릿라떼", "초코 라떼", "초콜릿 라떼", "초코", "핫초코"],
    "카라멜마끼아또": ["카라멜마끼아또", "마끼아또", "카라멜 마끼아또", "카라멜 커피", "마키아또", "카라멜"],
    "녹차라떼": ["녹차라떼", "녹차 라떼", "그린티 라떼", "말차라떼", "녹차", "그린티", "말차"],
    "복숭아아이스티": ["복숭아아이스티", "아이스티", "아이스 티", "복숭아티", "복숭아차", "피치티", "피치 아이스티"],
    "레몬에이드": ["레몬에이드", "레몬 에이드", "레모네이드", "상큼한 레몬", "레몬 음료", "레몬소다", "레모네이드"],
    "허브티": ["허브티", "허브 티", "허브차", "캐모마일", "루이보스", "페퍼민트", "허브 차", "카모마일", "허브음료"],
   
    # 옵션 관련 유사어
    "따뜻한": ["따뜻한", "뜨거운", "핫", "hot", "따땃한", "따뜻하게"],
    "차가운": ["차가운", "시원한", "아이스", "ice", "찬", "차갑게"],
    "샷추가": ["샷추가", "샷 추가", "에스프레소 추가", "샷 넣어주세요", "진하게"],
    "시럽추가": ["시럽추가", "시럽 추가", "달게", "달달하게", "설탕 추가"],
    "휘핑추가": ["휘핑추가", "휘핑 추가", "크림 추가", "휘핑크림 추가"],
   
    # 사이즈 관련 유사어
    "스몰": ["스몰", "작은", "small", "s", "작게"],
    "미디엄": ["미디엄", "중간", "medium", "m", "레귤러", "보통"],
    "라지": ["라지", "큰", "large", "l", "크게", "빅"],
    "벤티": ["벤티", "엄청 큰", "venti", "가장 큰", "제일 큰"],
   
    # 주문 관련 유사어
    "주문": ["주문", "시킬게요", "주문할게요", "먹고싶어요", "마실게요", "주세요"],
    "취소": ["취소", "안할래요", "그만둘래요", "취소할게요", "안 마실래요", "장바구니 비워줘", "초기화", "장바구니 초기화", "전부 취소", "전체 취소"],
    "확인": ["확인", "네 맞아요", "좋아요", "그걸로 할게요", "결제할게요"],
   
    # 결제 관련 유사어
    "카드": ["카드", "신용카드", "체크카드", "카드로 결제"],
    "모바일결제": ["모바일결제", "삼성페이", "애플페이", "카카오페이", "네이버페이", "페이앱"]
}

class FSM:
    """대화 흐름을 제어하는 유한 상태 기계(Finite State Machine)"""
    
    def __init__(self):
        self.current_state = State.START
        
        # 상태 전이 테이블: {현재 상태: {인텐트: 다음 상태}}
        self.state_transitions = {
            State.START: {"greeting": State.GREETING, "order": State.ORDER_TAKING, "help": State.GREETING},
            State.GREETING: {"order": State.ORDER_TAKING, "help": State.GREETING, "menu": State.ORDER_TAKING},
            State.ORDER_TAKING: {"option": State.OPTION_SELECT, "confirm": State.ORDER_CONFIRM, "change": State.ORDER_TAKING, "cancel": State.GREETING},  
            State.OPTION_SELECT: {"confirm": State.ORDER_CONFIRM, "change": State.ORDER_TAKING, "option": State.OPTION_SELECT, "cancel": State.GREETING}, 
            State.ORDER_CONFIRM: {"payment": State.PAYMENT, "change": State.ORDER_TAKING, "cancel": State.GREETING}, 
            State.PAYMENT: {"complete": State.FAREWELL, "cancel": State.GREETING, "help": State.PAYMENT},
            State.FAREWELL: {"greeting": State.GREETING, "order": State.ORDER_TAKING, "exit": State.START}
        }
        
        # 기본 응답 템플릿
        self.response_templates = {
            State.START: "안녕하세요, 카페에 오신 것을 환영합니다. 무엇을 도와드릴까요?",
            State.GREETING: "안녕하세요! 무엇을 주문하시겠어요?",
            State.ORDER_TAKING: "네, {menu} 주문이시군요. 어떤 옵션을 선택하시겠어요?",
            State.OPTION_SELECT: "{option} 선택하셨습니다. 주문을 확정하시겠어요?",
            State.ORDER_CONFIRM: "주문 내역을 확인하겠습니다. {order_details} 총 {total_price}원입니다.",
            State.PAYMENT: "결제가 완료되었습니다. 감사합니다.",
            State.FAREWELL: "이용해주셔서 감사합니다. 좋은 하루 되세요!"
        }
        
        # 각 상태별 필수 슬롯
        self.required_slots = {
            State.ORDER_TAKING: ["menu"],
            State.OPTION_SELECT: ["option"],
            State.ORDER_CONFIRM: ["order_details", "total_price"],
            State.PAYMENT: []
        }
        
        # 유사어 사전 설정
        self.synonym_dict = synonym_dict
        
        logger.info("FSM 초기화 완료")
    
    def get_next_state(self, current_state: str, intent: str, slots: Dict[str, Any] = None) -> str:
        """현재 상태와 인텐트, 슬롯을 기반으로 다음 상태 결정"""
        try:
            # slots가 None이면 빈 딕셔너리로 초기화
            if slots is None:
                slots = {}
                
            # 상태가 문자열로 제공되면 Enum으로 변환
            current = State(current_state) if isinstance(current_state, str) else current_state
            
            # 결제 의도 처리 로직 추가 (어느 상태에서든 payment 의도와 결제 방법이 있으면 PAYMENT 상태로 전환)
            if intent == "payment" and "payment_method" in slots and "menu" in slots:
                logger.info(f"결제 의도 감지: {current.value} -> payment (결제 방법: {slots['payment_method']})")
                return State.PAYMENT.value

            # 주문 관련 상태 변환 로직 개선
            if current == State.ORDER_TAKING:
                # 메뉴가 선택되어 있고 수량이 명확하면 확인 상태로 전환 고려
                if "menu" in slots and "count" in slots:
                    # 여러 메뉴인 경우에도 처리
                    if "menu_quantities" in slots or slots["count"] > 1:
                        logger.info(f"메뉴와 수량/옵션 정보가 있어 ORDER_CONFIRM 상태로 전환합니다 (메뉴: {slots['menu']}, 수량: {slots.get('count', 1)})")
                        return State.ORDER_CONFIRM.value
                
            # 결제 정보 처리 로직 개선
            if current == State.ORDER_CONFIRM and "payment_method" in slots:
                logger.info(f"결제 정보 입력으로 PAYMENT 상태로 전환합니다")
                return State.PAYMENT.value
                
            # 기존 상태 전환 로직
            if current in self.state_transitions and intent in self.state_transitions[current]:
                next_state = self.state_transitions[current][intent]
                logger.info(f"상태 전환: {current.value} -> {next_state.value} (인텐트: {intent})")
                return next_state.value
            
            # 상태 전환이 없는 경우 현재 상태 유지하되 로그 강화
            logger.info(f"상태 유지: {current.value} (인텐트: {intent}, 슬롯: {slots})")
            return current.value
                
        except (ValueError, KeyError) as e:
            logger.warning(f"상태 전환 오류: {str(e)}, 시작 상태로 리셋")
            # 오류 발생 시 시작 상태로 리셋
            return State.START.value
    
    def get_response(self, state: str, slots: Dict[str, Any]) -> str:
        """현재 상태와 슬롯 정보를 기반으로 응답 생성"""
        try:
            # 상태가 문자열로 제공되면 Enum으로 변환
            current = State(state) if isinstance(state, str) else state
            
            # 특별한 인삿말 생성 로직 추가
            if current == State.START or current == State.GREETING:
                greetings = [
                    "안녕하세요! 카페에 오신 것을 환영합니다. 오늘 어떤 음료를 드시겠어요?",
                    "카페에 오신 걸 환영합니다. 오늘의 음료 추천해드릴까요?",
                    "안녕하세요! 저희 카페에 오신 것을 진심으로 환영합니다. 무엇을 도와드릴까요?",
                    "반갑습니다! 오늘도 맛있는 음료로 즐거운 시간 되세요. 어떤 메뉴가 좋으실까요?",
                    "어서오세요! 오늘 기분 좋은 음료 한 잔 어떠세요?"
                ]
                
                # 랜덤 인삿말 선택
                import random
                return random.choice(greetings)
            
            # 기존 응답 템플릿 가져오기
            template = self.response_templates.get(current, "죄송합니다, 다시 말씀해주시겠어요?")
            
            # 누락된 필수 슬롯 확인
            if current in self.required_slots:
                missing_slots = [slot for slot in self.required_slots[current] if slot not in slots]
                if missing_slots:
                    # 첫 번째 누락된 슬롯에 대한 프롬프트 반환
                    if missing_slots[0] == "menu":
                        return "오늘 어떤 음료를 마시고 싶으세요? 메뉴를 말씀해주세요."
                    elif missing_slots[0] == "option":
                        return "사이즈나 온도, 추가 옵션을 선택해주세요."
                    else:
                        return f"{missing_slots[0]}에 대한 정보가 필요합니다."
            
            # 슬롯 값으로 템플릿 채우기
            try:
                # slots에 있는 키만 형식화에 사용
                valid_slots = {k: v for k, v in slots.items() if k in template}
                if valid_slots:
                    return template.format(**valid_slots)
                return template
            except KeyError as e:
                logger.warning(f"응답 형식화 오류: {str(e)}, 기본 응답 사용")
                # 필요한 슬롯이 없는 경우 기본 응답
                return template
                
        except ValueError as e:
            logger.warning(f"응답 생성 오류: {str(e)}")
            return "죄송합니다, 다시 말씀해주시겠어요?"
    
    def find_canonical_term(self, text: str) -> Dict[str, str]:
        """사용자 입력에서 표준 용어(canonical term) 찾기"""
        result = {}
        
        # 모든 유사어 그룹에 대해 검사
        for canonical, synonyms in self.synonym_dict.items():
            for synonym in synonyms:
                if synonym in text:
                    # 카테고리 결정
                    if canonical in ["아메리카노", "카페 라떼", "바닐라 라떼", "카페 모카", "그린 라떼", "복숭아 아이스 티", "레몬 에이드", "허브 티","카라멜 마끼아또","초코 라떼"]:
                        result["menu"] = canonical
                    elif canonical in ["따뜻한", "차가운"]:
                        result["temperature"] = canonical
                    elif canonical in ["샷추가", "시럽추가", "휘핑추가"]:
                        result["addition"] = canonical
                    elif canonical in ["스몰", "레귤러", "라지"]:
                        result["size"] = canonical
                    elif canonical in ["주문", "취소", "확인"]:
                        result["action"] = canonical
                    elif canonical in ["카드", "모바일결제"]:
                        result["payment"] = canonical
                    else:
                        # 기타 분류되지 않은 용어
                        result[canonical] = synonym
                    break
        
        return result
    
    def reset(self):
        """FSM 상태 초기화"""
        global _reset_in_progress
        
        # 이미 리셋 중이면 중복 호출 방지
        if _reset_in_progress:
            return
        
        try:
            _reset_in_progress = True
            self.current_state = "start"
            # 기타 상태 초기화 로직...
            logger.info("FSM 상태 리셋됨")
        finally:
            _reset_in_progress = False
    
    def transition_to(self, new_state, **kwargs):
        # 이전 상태 저장
        previous_state = self.current_state
        
        # 기존 전환 로직 수행
        if not self.can_transition_to(new_state):
            logger.warning(f"Invalid transition from {previous_state} to {new_state}")
            return False

        # 상태 업데이트
        self.current_state = new_state

        # 상태 변경 시 추가 처리 함수 호출 (있으면)
        if hasattr(self, 'on_state_change'):
            self.on_state_change(previous_state, new_state, **kwargs)

        # 웹소켓으로 상태 변경 알림
        try:
            from app.services.notification_service import notify_state_update
            
            # 비동기로 상태 업데이트 알림 전송
            import asyncio
            asyncio.create_task(notify_state_update(
                new_state, 
                message=self.get_response(new_state, kwargs),
                context=kwargs
            ))
        except Exception as e:
            logger.error(f"WebSocket 알림 중 오류: {str(e)}")
        except Exception as e:
            logger.error(f"WebSocket 알림 중 오류: {str(e)}")
        
        # 결과 반환
        return True
    
class GPTEnhancedFSM(FSM):
    """GPT API를 활용하여 대화 흐름을 더욱 지능적으로 관리"""
    
    def __init__(self):
        super().__init__()
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    async def analyze_dialog_intent(self, text: str) -> Dict[str, Any]:
        """
        GPT를 활용한 의도 및 슬롯 심층 분석
        기존 NLP 방식을 보완하고 더 정교한 의도 파악
        """
        try:
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo-1106",
                messages=[
                    {
                        "role": "system", 
                        "content": """
                        너는 카페 키오스크의 대화 의도 분석기야. 
                        사용자 입력의 숨겨진 의도와 감정을 정확히 파악해.
                        의도, 감정, 주요 키워드를 JSON 형식으로 반환해.
                        """
                    },
                    {
                        "role": "user", 
                        "content": f"다음 문장의 의도를 분석해: {text}"
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            # JSON 파싱
            analysis = json.loads(response.choices[0].message.content)
            return {
                "intent": analysis.get("intent", ""),
                "emotion": analysis.get("emotion", "neutral"),
                "keywords": analysis.get("keywords", [])
            }
        
        except Exception as e:
            logger.error(f"GPT 의도 분석 실패: {str(e)}")
            return {"intent": "unknown", "emotion": "neutral", "keywords": []}
        
# 싱글톤 인스턴스
fsm = FSM()