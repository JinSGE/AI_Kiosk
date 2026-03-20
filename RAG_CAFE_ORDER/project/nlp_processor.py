import re
from synonyms import synonym_dict

def extract_keywords(text: str):
    """
    입력된 텍스트에서 유사어를 처리하여 의미가 동일한 단어를 그룹화하는 함수.
    """
    text = text.lower()
    keywords = re.findall(r'\b[가-힣a-zA-Z]+\b', text)

    extracted_keywords = []
    for word in keywords:
        # 유사어가 있다면 해당 카테고리로 변환
        for key, synonyms in synonym_dict.items():
            if word in synonyms:
                extracted_keywords.append(key)  # 유사어를 대표 단어로 변경
                break
    
    return extracted_keywords
