import os
import torch
import logging
from typing import List, Dict, Any
from transformers import AutoTokenizer, AutoModelForCausalLM
from app.models.text_generation import TextGenerationModel
from app.models.text_generation import text_model as model_instance
logger = logging.getLogger(__name__)

class TextGenerationService:
    """텍스트 생성 서비스 클래스 - 노트북 최적화 버전"""
    def __init__(self, model : TextGenerationModel):
        # 모델 경로 유지
        self.model_path = "EleutherAI/polyglot-ko-1.3b"
        
        self.tokenizer = None
        self.model = model

    def generate_text(self, prompt: str, **kwargs):
        """텍스트 생성 함수 - 노트북 최적화 버전"""
        try:
            # 모델 로드 확인
            if not self.model.model:
                logger.info("모델이 로드되지 않았습니다. 로드 중...")
                self.model.load_model()
                
            # 생성 매개변수 최적화
            optimized_kwargs = kwargs.copy()
            
            # 노트북 최적화: 더 과감한 매개변수 조정
            if 'max_length' in optimized_kwargs and optimized_kwargs['max_length'] > 100:
                optimized_kwargs['max_length'] = 100  # 최대 토큰 수 더 제한
                
            if 'top_k' in optimized_kwargs and optimized_kwargs['top_k'] > 40:
                optimized_kwargs['top_k'] = 40  # top_k 매개변수 더 낮게 조정
            
            # 온도(temperature) 최적화: 낮은 온도 = 더 빠른 결정
            if 'temperature' in optimized_kwargs and optimized_kwargs['temperature'] > 0.5:
                optimized_kwargs['temperature'] = 0.5
                
            # 주문 처리 시 더 빠른 파라미터 적용 (is_order 플래그 사용)
            if optimized_kwargs.get('is_order', False):
                optimized_kwargs['temperature'] = 0.5  # 온도 더 낮춤
                optimized_kwargs['max_length'] = 80  # 더 짧은 응답 생성
                optimized_kwargs['top_p'] = 0.85  # top_p 값도 낮게 조정
                
            # 반복 패널티 개선 (중복 감소 + 속도 향상)
            optimized_kwargs['repetition_penalty'] = 1.2  # 중간 값으로 설정
            
            # early_stopping 활성화로 생성 시간 단축
            optimized_kwargs['early_stopping'] = True
            
            # no_repeat_ngram_size 감소 (처리 속도 향상)
            optimized_kwargs['no_repeat_ngram_size'] = 2  # 3에서 2로 감소
                
            # 모델 호출
            generated_texts = self.model.generate_text(
                prompt=prompt,
                **optimized_kwargs
            )
            
            # 첫 번째 생성된 텍스트 반환
            return generated_texts if isinstance(generated_texts, list) else [generated_texts]
            
        except Exception as e:
            logger.error(f"텍스트 생성 서비스 오류: {str(e)}")
            # 오류 시 기본 응답 반환
            return ["죄송합니다. 응답 생성 중 오류가 발생했습니다."]
        
    def load_model(self):
        """모델 로드 함수 - 노트북 최적화 버전"""
        try:
            # 1.3B 모델 경로 사용
            model_path = self.model_path
            
            # 토크나이저 로드 - 캐시 디렉토리 명시적 지정
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "transformers")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True,
                cache_dir=cache_dir,
                local_files_only=True  # 이미 다운로드된 파일만 사용 (속도 향상)
            )
            
            # 특수 토큰 설정
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 모델 로드 설정 - 노트북 최적화
            model_kwargs = {
                "trust_remote_code": True,
                "low_cpu_mem_usage": True,  # 메모리 최적화
                "cache_dir": cache_dir,
                "local_files_only": True    # 로컬 파일 우선 사용
            }
            
            # GPU 설정 - 8비트 양자화로 메모리 사용량 대폭 감소
            if torch.cuda.is_available():
                model_kwargs["torch_dtype"] = torch.float16
                model_kwargs["load_in_8bit"] = True  # 8비트 양자화 활성화
                model_kwargs["device_map"] = "auto"
            
            # CPU 최적화 (GPU 없는 경우)
            else:
                # CPU 최적화 설정
                model_kwargs["torch_dtype"] = torch.float32  # 기본 정밀도 사용
                
            # 모델 로드 - 더 빠른 옵션으로
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                **model_kwargs
            )
            
            return True
        
        except Exception as e:
            logger.error(f"모델 로드 오류: {e}")
            raise

    def check_model_status(self):
        """모델 상태 확인"""
        if hasattr(self.model, 'model'):
            return {
                "is_loaded": self.model.model is not None and self.model.tokenizer is not None,
                "model_name": self.model.model_path,
                "device": self.model.device
            }
        else:
            return {
                "is_loaded": self.model is not None and self.tokenizer is not None,
                "model_name": self.model_path,
                "device": "cuda" if torch.cuda.is_available() else "cpu"
            }
            
    def reset_conversation(self):
        """대화 이력 초기화"""
        if hasattr(self.model, 'reset_conversation') and callable(self.model.reset_conversation):
            return self.model.reset_conversation()
        
        if hasattr(self.model, 'conversation_history'):
            self.model.conversation_history = []
        
        return True
        
# 싱글톤 인스턴스
text_model = TextGenerationService(model_instance)