# app/services/nlp_processor.py
import re
import openai
import asyncio
import logging  
import os
import json
from typing import Dict, Any, List, Optional
from app.config import settings
from app.models.fsm import fsm

logger = logging.getLogger(__name__)

# 로깅은 app/__init__.py에서 전역으로 설정됨

# 메뉴 데이터 로드 - 캐싱 최적화
def load_menu_data():
    try:
        # 메뉴 데이터 파일 경로
        menu_data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "menu_data.json")
        
        # 메뉴 데이터 파일이 없으면 기본 데이터 사용
        if not os.path.exists(menu_data_path):
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
                "name": "카페라떼",
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
                "name": "카페모카",
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
                "name": "바닐라라떼",
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
                "name": "카라멜마끼아또",
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
                "name": "초코라떼",
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
                "name": "그린라떼",
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
                "name": "복숭아아이스티",
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
                "name": "허브티",
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
                "name": "레몬에이드",
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
            "커피": ["아메리카노", "카페라떼", "카페모카", "바닐라라떼", "카라멜마끼아또", "초코라떼", "그린라떼"],
            "티": ["복숭아아이스티", "허브티"],
            "에이드/주스": ["레몬에이드"]
            },
            "option_types": {
            "커피": ["size", "temperature", "shots", "syrup"],
            "티": ["size"],
            "에이드/주스": ["size"]
            }
        }
        
        # 메뉴 데이터 로드
        with open(menu_data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"메뉴 데이터 로드 실패: {str(e)}")
        return {"menus": [], "quantities": {}}

# 메뉴 데이터 로드 - 최초 한 번만 실행 (캐싱)
MENU_DATA = load_menu_data()

# 메뉴 이름과 가격 미리 캐싱하여 반복 lookup 최소화
MENU_NAMES = [menu["name"] for menu in MENU_DATA.get("menus", [])]
MENU_PRICES = {menu["name"]: menu.get("basePrice", 4500) for menu in MENU_DATA.get("menus", [])}

# 의도 분류를 위한 패턴
intent_patterns = {
    "greeting": [r"안녕", r"반가워", r"하이", r"헬로", r"시작", r"처음"],
    "order": [r"주문", r"먹고싶", r"마시고싶", r"주세요", r"시킬게요", r"메뉴"],
    "option": [r"옵션", r"사이즈", r"크기", r"샷 추가", r"시럽", r"얼음", r"따뜻한", r"아이스"],
    "confirm": [r"확인", r"맞아요", r"네 좋아요", r"주문할게요", r"그걸로 할게요"],
    "change": [r"변경", r"바꿀게요", r"다른", r"취소하고", r"다시"],
    "remove": [r"빼", r"취소", r"삭제", r"제거", r"지워", r"없애", r"줄여"],
    "payment": [r"결제", r"지불", r"카드", r"계산"],
    "complete": [r"완료", r"감사", r"고마워", r"됐어요"],
    "help": [r"도움", r"추천", r"어떤", r"알려줘", r"뭐가 있"],
    "exit": [r"종료", r"그만", r"나갈게", r"끝내"]
}

# 슬롯 추출을 위한 패턴 - 핵심 패턴만 유지
slot_patterns = {
    "menu": [
        # 메뉴 항목과 가능한 수량 접미사 캡처 (가장 일반적인 패턴)
        r"(아메리카노|카페라떼|카페모카|바닐라라떼|카라멜마끼아또|초코라떼|그린라떼|복숭아아이스티|허브티|레몬에이드)(?:.*?)(하나|한 ?잔|두 ?잔|세 ?잔|네 ?잔|다섯 ?잔|\\d+잔)?",
    ],
    
    "option": [
        # 핵심 옵션 패턴만 유지
        r"(따뜻한|아이스|핫|콜드|샷 ?추가|시럽 ?추가|휘핑 ?추가|얼음 ?많이|얼음 ?적게|얼음 ?없이)",
        r"(1샷|2샷|3샷|샷|시럽) ?(추가)?",
    ],
    
    "size": [
        r"(스몰|미디엄|라지|레귤러|점보|싱글|더블)"
    ],
    
    "count": [
        # 숫자 기반 수량 표현만 유지
        r"(\d+)? ?(잔|개|하나|둘|셋|넷|다섯|한 ?잔|두 ?잔|세 ?잔|네 ?잔|다섯 ?잔)",
        r"(\d+)잔",
    ],
    
    "payment_method": [
        # 간소화된 결제 방법 패턴
        r"(신용카드|체크카드|카드)",
        r"(삼성페이|애플페이|카카오페이|네이버페이|토스)",
        r"(결제)"
    ],
    
    "takeout_option": [
        r"(포장|테이크아웃|매장|드시고가실|먹고 ?갈|마시고 ?갈)"
    ],
}

# 최적화된 수량 추출 함수 - 더 적은 패턴 검사로 성능 향상
def parse_quantity(text: str, menu_name: str = None) -> int:
    """
    특정 메뉴의 수량 추출 - 노트북 최적화 버전
    
    Args:
        text: 입력 텍스트
        menu_name: 메뉴명 (기본값: None)
            
    Returns:
        추출된 수량 (기본값: 1)
    """
    # 기본 수량은 1
    quantity = 1
    
    if menu_name:
        # "[메뉴] N잔" 패턴 확인 (가장 일반적인 패턴만 체크)
        match = re.search(rf'{menu_name}\s*(\d+)\s*잔', text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        
        # "메뉴 한 잔" 형태 간소화
        if f"{menu_name} 한 잔" in text or f"{menu_name} 한잔" in text:
            return 1
        
        # 한글 수량 표현 처리 - 가장 자주 사용되는 것만 체크
        korean_nums = {"한": 1, "두": 2, "세": 3}
        for num_word, value in korean_nums.items():
            if f"{menu_name} {num_word}잔" in text:
                return value
    
    # 일반 "N잔" 패턴 (메뉴와 무관하게)
    match = re.search(r'(\d+)\s*잔', text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    
    return quantity

# 더 빠른 의도 및 슬롯 추출
def extract_intent_and_slots(text: str) -> Dict[str, Any]:
    """
    텍스트에서 의도와 슬롯 정보를 추출하는 함수 - 노트북 최적화 버전
    
    Args:
        text: 입력 텍스트
    
    Returns:
        추출된 의도와 슬롯 정보를 담은 사전
    """
    # 텍스트 전처리 - 소문자 변환만 수행
    text = text.lower()

    # 1. 슬롯 초기화
    slots = {}

    # 2. 메뉴 목록에서 직접 일치 항목 찾기 (정규식보다 빠름)
    # 정렬된 메뉴 목록 (긴 메뉴 이름부터 검색)
    sorted_menu_list = sorted(MENU_NAMES, key=len, reverse=True)
    
    # 발견된 메뉴 목록과 수량
    discovered_menus = []
    menu_quantities = {}
    
    # 각 메뉴 확인 - 정규식 없이 직접 문자열 검색
    for menu in sorted_menu_list:
        if menu in text:
            # 수량 추출 - 간소화된 로직
            menu_quantity = parse_quantity(text, menu)
            menu_quantities[menu] = menu_quantity
            discovered_menus.append(menu)
            
    # 메뉴가 있으면 슬롯 설정
    if discovered_menus:
        # "추가" 키워드 처리
        if "추가" in text:
            # 추가 주문 플래그 설정
            slots["is_additional_order"] = True
        
        # 메뉴 및 수량 정보 저장
        slots["menu_quantities"] = menu_quantities
        slots["count"] = sum(menu_quantities.values())
        
        # 호환성을 위한 menu 필드 설정
        if len(discovered_menus) > 1:
            slots["menu"] = discovered_menus[0]  # 첫 번째 메뉴를 대표 메뉴로
            slots["menu_list"] = discovered_menus  # 전체 메뉴 리스트
        else:
            slots["menu"] = discovered_menus[0]
        
        # 주문 상세 정보 구성
        order_details = []
        for menu, quantity in menu_quantities.items():
            order_details.append(f"{menu} {quantity}잔")
        
        slots["order_details"] = ", ".join(order_details)
        
        # 총 가격 계산 - 캐싱된 가격 사용하여 속도 향상
        total_price = 0
        for menu, quantity in menu_quantities.items():
            # 캐싱된 메뉴 가격 사용
            base_price = MENU_PRICES.get(menu, 4500)  
            total_price += base_price * quantity
        
        slots["total_price"] = f"{total_price:,}"
    
    # 결제 방법 추출 - 직접 문자열 검색으로 속도 향상
    if "카드" in text:
        slots["payment_method"] = "카드"
    elif "페이" in text:
        slots["payment_method"] = "모바일페이"
    
    # 포장/매장 옵션 추출 - 직접 문자열 검색으로 속도 향상 
    if "포장" in text or "테이크아웃" in text:
        slots["takeout"] = True
    elif "매장" in text or "드시고" in text:
        slots["takeout"] = False
    
    # 온도 옵션 추출 - 직접 문자열 검색으로 속도 향상
    if "아이스" in text or "차가운" in text:
        slots["temperature"] = "아이스"
    elif "따뜻한" in text or "핫" in text:
        slots["temperature"] = "핫"
    
    # 사이즈 옵션 추출 - 직접 문자열 검색으로 속도 향상
    if "라지" in text or "large" in text:
        slots["size"] = "라지"
    elif "레귤러" in text or "regular" in text:
        slots["size"] = "레귤러"
    
    # 의도 감지 - 간소화된 방식으로 속도 향상
    detected_intents = []
    
    # 메뉴가 있으면 'order' 의도 추가
    if "menu" in slots:
        detected_intents.append("order")
        
    # 결제 관련 키워드가 있으면 'payment' 의도 추가
    if "payment_method" in slots or "결제" in text or "카드" in text:
        detected_intents.append("payment")
        
    # 옵션 관련 키워드가 있으면 'option' 의도 추가
    if "temperature" in slots or "size" in slots or "아이스" in text or "따뜻한" in text:
        detected_intents.append("option")
        
    # 의도 결정 - 핵심 패턴만 확인
    if not detected_intents:
        # 한 번에 모든 의도 확인 (중첩 루프 제거)
        all_intents = {}
        for word in text.split():
            for intent, patterns in intent_patterns.items():
                for pattern in patterns:
                    if pattern in word:
                        all_intents[intent] = True
                        break
        
        detected_intents = list(all_intents.keys())
    
    # 최종 의도 결정
    if "menu" in slots and "remove" in detected_intents:
        intent = "remove"  # 메뉴 제거 의도
    elif "menu" in slots and ("option" in detected_intents or "size" in slots or "temperature" in slots):
        intent = "order_with_options"  # 메뉴와 옵션이 함께 있는 경우
    elif "menu" in slots:
        intent = "order"  # 메뉴만 있는 경우
    elif "추천" in text or "인기" in text:
        intent = "recommend"
    elif detected_intents:
        intent = detected_intents[0]
    else:
        intent = "greeting"
    
    # 결과 반환
    result = {"intent": intent, "slots": slots}
    return result


def extract_keywords(text: str) -> List[str]:
    """텍스트에서 키워드 추출 - 간소화된 버전"""
    text = text.lower()
    keywords = re.findall(r'\b[가-힣a-zA-Z]+\b', text)
    
    extracted_keywords = []
    for word in keywords:
        # FSM의 synonym_dict를 사용하여 유사어 처리
        canonical_found = False
        for key, synonyms in fsm.synonym_dict.items():
            if word in synonyms:
                extracted_keywords.append(key)
                canonical_found = True
                break
        
        # 일반 키워드 추가 (유사어에서 찾지 못한 경우)
        if not canonical_found and word not in extracted_keywords:
            extracted_keywords.append(word)
    
    return extracted_keywords

# GPT 관련 코드 최적화 - 비동기 처리 개선
async def gpt_extract_intent_and_slots(text: str) -> Dict[str, Any]:
    """GPT를 사용하여 의도와 슬롯 추출 (rule-based 방식 보완) - 노트북 최적화 버전"""
    # 기본 규칙 기반 분석 수행
    rule_based = extract_intent_and_slots(text)
    
    # OpenAI API 키가 없으면 규칙 기반 결과만 반환
    if not os.getenv("OPENAI_API_KEY"):
        return rule_based
    
    # 규칙 기반 결과가 충분히 명확하면 GPT 호출 생략 (최적화)
    if rule_based["intent"] != "greeting" and rule_based["intent"] != "unknown" and rule_based["slots"]:
        return rule_based
    
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 메뉴 정보 구성 - 더 간결한 형태로
        menu_info = ", ".join(MENU_NAMES)
        
        # 더 짧은 시스템 프롬프트 (토큰 수 감소)
        system_prompt = f"""
        카페 키오스크 NLP 서비스입니다. 주문 의도와 메뉴, 수량, 옵션 정보를 추출하세요.
        메뉴 목록: {menu_info}
        JSON 형식으로 반환: {{"intent": "의도", "slots": {{"menu": "메뉴", "count": 수량}}}}
        """
        
        # GPT API 호출 - 작은 모델 사용 (3.5-turbo)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo",  # 4에서 3.5로 다운그레이드
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"분석할 텍스트: {text}"}
            ],
            max_tokens=150,  # 토큰 수 감소 (200 -> 150)
            temperature=0.3,  # 온도 낮춤 (더 확정적인 응답)
            response_format={"type": "json_object"}
        )
        
        # JSON 파싱
        gpt_result = json.loads(response.choices[0].message.content)
        
        # 규칙 기반 결과와 GPT 결과 병합
        merged = {"intent": rule_based["intent"], "slots": rule_based["slots"].copy()}
        
        # 의도 병합
        if "intent" in gpt_result and gpt_result["intent"]:
            # 규칙 기반 의도가 불확실한 경우 GPT 의도 우선
            if rule_based["intent"] in ["greeting", "unknown"] or not rule_based["intent"]:
                merged["intent"] = gpt_result["intent"]
        
        # 슬롯 병합 - 꼭 필요한 정보만
        if "slots" in gpt_result and isinstance(gpt_result["slots"], dict):
            for key in ["menu", "count", "menu_quantities"]:
                if key in gpt_result["slots"] and gpt_result["slots"][key]:
                    # 기존 값이 없거나 GPT 값이 더 명확한 경우 GPT 값 사용
                    if key not in merged["slots"] or not merged["slots"][key]:
                        merged["slots"][key] = gpt_result["slots"][key]
        
        return merged
        
    except Exception as e:
        logger.error(f"GPT 분석 실패: {str(e)}")
        # 오류 발생 시 규칙 기반 결과 반환
        return rule_based