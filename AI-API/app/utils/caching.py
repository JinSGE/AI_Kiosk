"""
결과 캐싱을 위한 유틸리티 함수들
"""
import os
import json
import hashlib
import logging
import time
from typing import Dict, Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

# 기본 캐시 디렉토리
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")

# 캐시 수명 (초)
DEFAULT_CACHE_TTL = 3600  # 1시간

def ensure_cache_dir(cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """
    캐시 디렉토리가 존재하는지 확인하고 없으면 생성
    
    Args:
        cache_dir: 캐시 디렉토리 경로
        
    Returns:
        str: 캐시 디렉토리 경로
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_cache_key(prefix: str, data: Any) -> str:
    """
    데이터로부터 캐시 키 생성
    
    Args:
        prefix: 캐시 키 접두사
        data: 캐시 키를 생성할 데이터
        
    Returns:
        str: 생성된 캐시 키
    """
    if isinstance(data, str):
        serialized = data.encode('utf-8')
    else:
        serialized = json.dumps(data, sort_keys=True).encode('utf-8')
    
    hash_key = hashlib.md5(serialized).hexdigest()
    return f"{prefix}_{hash_key}"

def save_to_cache(cache_key: str, data: Any, cache_dir: str = DEFAULT_CACHE_DIR, ttl: int = DEFAULT_CACHE_TTL) -> bool:
    """
    데이터를 캐시에 저장
    
    Args:
        cache_key: 캐시 키
        data: 저장할 데이터
        cache_dir: 캐시 디렉토리 경로
        ttl: 캐시 수명(초)
        
    Returns:
        bool: 저장 성공 시 True
    """
    try:
        ensure_cache_dir(cache_dir)
        cache_path = os.path.join(cache_dir, cache_key)
        
        # 캐시 메타데이터 및 데이터 저장
        cache_data = {
            "timestamp": time.time(),
            "ttl": ttl,
            "data": data
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
            
        return True
    except Exception as e:
        logger.warning(f"캐시 저장 실패: {str(e)}")
        return False

def get_from_cache(cache_key: str, cache_dir: str = DEFAULT_CACHE_DIR) -> Optional[Any]:
    """
    캐시에서 데이터 검색
    
    Args:
        cache_key: 캐시 키
        cache_dir: 캐시 디렉토리 경로
        
    Returns:
        Optional[Any]: 캐시된 데이터 또는 None (캐시 없음 또는 만료)
    """
    try:
        cache_path = os.path.join(cache_dir, cache_key)
        
        if not os.path.exists(cache_path):
            return None
            
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            
        # 캐시 만료 여부 확인
        current_time = time.time()
        if current_time - cache_data["timestamp"] > cache_data["ttl"]:
            # 캐시 만료
            logger.debug(f"캐시 만료: {cache_key}")
            os.remove(cache_path)
            return None
            
        return cache_data["data"]
    except Exception as e:
        logger.warning(f"캐시 검색 실패: {str(e)}")
        return None

def cached(prefix: str, ttl: int = DEFAULT_CACHE_TTL):
    """
    함수 결과를 캐시하는 데코레이터
    
    Args:
        prefix: 캐시 키 접두사
        ttl: 캐시 수명(초)
        
    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 함수 호출 정보로 캐시 키 생성
            cache_data = {
                "args": args,
                "kwargs": {k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool, list, dict))}
            }
            cache_key = get_cache_key(prefix, cache_data)
            
            # 캐시 확인
            cached_result = get_from_cache(cache_key)
            if cached_result is not None:
                logger.debug(f"캐시 히트: {func.__name__}")
                return cached_result
                
            # 캐시 없음, 함수 실행
            logger.debug(f"캐시 미스: {func.__name__}")
            result = func(*args, **kwargs)
            
            # 결과 캐싱
            save_to_cache(cache_key, result, ttl=ttl)
            
            return result
        return wrapper
    return decorator