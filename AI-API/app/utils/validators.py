"""
사용자 입력 검증을 위한 유틸리티 함수들
"""
import os
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

# 허용된 오디오 파일 확장자
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

def validate_audio_file(filename: str) -> bool:
    """
    오디오 파일 확장자 검증
    
    Args:
        filename: 검증할 파일 이름
        
    Returns:
        bool: 유효한 오디오 파일이면 True, 아니면 False
    """
    if not filename:
        return False
    
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALLOWED_AUDIO_EXTENSIONS

def validate_korean_text(text: str) -> bool:
    """
    한국어 텍스트 검증 (최소한의 한글 포함 여부 확인)
    
    Args:
        text: 검증할 텍스트
        
    Returns:
        bool: 한글이 포함된 유효한 텍스트이면 True, 아니면 False
    """
    if not text or not text.strip():
        return False
    
    # 최소한 한 개 이상의 한글 문자가 포함되어 있는지 확인
    for char in text:
        if '가' <= char <= '힣':
            return True
    
    return False

def truncate_text(text: str, max_length: int = 1024) -> str:
    """
    텍스트 길이 제한
    
    Args:
        text: 자를 텍스트
        max_length: 최대 길이
        
    Returns:
        str: 제한된 길이의 텍스트
    """
    if len(text) <= max_length:
        return text
    
    # 문장 중간에 자르지 않고 가능한 문장 단위로 자르기
    truncated = text[:max_length]
    
    # 마지막 완전한 문장으로 자르기
    sentence_endings = ['.', '!', '?', '\n']
    for ending in sentence_endings:
        last_pos = truncated.rfind(ending)
        if last_pos > max_length * 0.8:  # 최소 80% 이상 사용
            return truncated[:last_pos+1]
    
    return truncated