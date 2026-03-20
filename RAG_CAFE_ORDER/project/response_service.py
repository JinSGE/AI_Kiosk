import random
import pickle
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# 추천 응답 처리 (랜덤 추천)
def get_recommendation_response(tokens):
    with open('models/recommendation_response.pkl', 'rb') as f:
        reco = pickle.load(f)

    # 감정, 날씨, 시간 키워드로 분류하여 추천
    for tok in tokens:
        if tok in reco:
            categories = reco[tok]
            # 각 카테고리에서 랜덤으로 하나의 문장 선택
            selected_response = random.choice(categories)
            return selected_response
    
    # 기본 추천 (사용자 요구가 명확하지 않은 경우)
    return random.choice(reco["추천"])

# 기본 응답 처리
def get_basic_response(tokens):
    with open('models/basic_response.pkl', 'rb') as f:
        basic_responses = pickle.load(f)
    result = [basic_responses.get(tok) for tok in tokens if tok in basic_responses]
    return '\n'.join(filter(None, result))

# 통합 응답 생성
def generate_response(query, tokens):
    basic = get_basic_response(tokens)
    if basic:
        return basic
    return get_recommendation_response(tokens)
