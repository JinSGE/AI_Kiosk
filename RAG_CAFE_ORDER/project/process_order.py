import random
from collections import Counter
import pickle

# 메뉴별 다양한 응답 정의 (Pickle 파일에서 로드)
def load_basic_responses():
    with open("models/basic_response.pkl", "rb") as f:
        return pickle.load(f)

basic_responses = load_basic_responses()

# 자연스러운 응답 생성 함수
def process_order(order_list):
    responses = []
    order_counter = Counter(order_list)

    if len(order_list) > 1:
        # 여러 메뉴가 있을 때
        for item, count in order_counter.items():
            if count > 1:
                responses.append(f"{item} {count}잔 준비해드릴게요.")
            else:
                responses.append(f"{random.choice(basic_responses.get(item))}")
        # 여러 메뉴를 묶어서 응답
        ordered_items = "와 ".join(order_list[:-1]) + "와 " + order_list[-1]
        responses.append(f"{ordered_items} 맞으실까요?")
    else:
        # 하나의 메뉴만 있을 때
        item = order_list[0]
        responses.append(f"{random.choice(basic_responses.get(item))}")
    
    return responses

# 예시 주문
order_input = ["아메리카노", "카페라떼", "카페라떼", "바닐라라떼"]
order_response = process_order(order_input)

# 응답 출력
for response in order_response:
    print(response)
