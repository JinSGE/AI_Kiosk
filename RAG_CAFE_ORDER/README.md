# ☕ RAG 기반 카페 주문 프로젝트

이 프로젝트는 카페 메뉴 JSON 파일을 바탕으로,
자연어로 입력된 주문 요청을 처리할 수 있도록
RAG(Retrieval-Augmented Generation) 구조를 활용합니다.

## 구조

- `data/menu.json`: 원본 메뉴 데이터
- `scripts/1_convert_to_text.py`: 메뉴 → 텍스트 문서화
- `scripts/2_generate_embedding.py`: 문서 → 임베딩
- `scripts/3_query_test.py`: 사용자 쿼리 → 유사 메뉴 추천
- `docs/*.pkl`: 벡터 저장소

## 실행 방법

```bash
# 1단계: 텍스트 생성
python scripts/1_convert_to_text.py

# 2단계: 임베딩 생성
python scripts/2_generate_embedding.py

# 3단계: 테스트 쿼리 실행
python scripts/3_query_test.py
내일 할일

pkl로 파일 만들어서 단어끼리 유사한단어 하나 카테고리로 매핑 (감정, 추천, 시간 등등)
