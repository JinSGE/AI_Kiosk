# app/models/text_generation.py

import os
import json
import logging
import asyncio
import re
import random

import torch
import openai
from transformers import AutoModelForCausalLM, AutoTokenizer

from typing import List, Dict, Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# settings 객체에 MODEL_CACHE_DIR 설정 - 노트북 환경 대응
settings.MODEL_CACHE_DIR = "C:/User/ssunge/OneDrive/바탕 화면/SE/AI-API/model_cache/models--EleutherAI--polyglot-ko-1.3b"

class GPTContextualGenerator:
    """GPT를 활용한 맥락 인식 대화 생성기 - 노트북 최적화 버전"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        GPT 컨텍스트 생성기 초기화
        
        :param api_key: OpenAI API 키 (선택적)
        """
        # API 키 우선순위: 
        # 1. 직접 전달된 키
        # 2. 환경 변수
        # 3. None (GPT 기능 비활성화)
        self.openai_client = None
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        # API 키가 있는 경우에만 클라이언트 초기화
        if self.api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=self.api_key)
                logger.info("OpenAI 클라이언트 초기화 완료")
            except Exception as e:
                logger.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
                self.openai_client = None
        else:
            logger.warning("OpenAI API 키가 설정되지 않았습니다. GPT 기능이 비활성화됩니다.")
    
    async def generate_contextual_response(
        self, 
        user_input: str, 
        conversation_history: List[Dict[str, str]], 
        current_state: str
    ) -> str:
        """
        대화 이력과 현재 상태를 고려한 응답 생성 - 노트북 최적화 버전
        
        :param user_input: 사용자 입력
        :param conversation_history: 대화 이력
        :param current_state: 현재 대화 상태
        :return: 생성된 응답
        """
        # OpenAI 클라이언트가 없으면 기본 응답
        if not self.openai_client:
            return "죄송합니다, 현재 AI 응답 기능을 사용할 수 없습니다."

        try:
            # 최근 5개의 대화만 사용 (토큰 절약)
            recent_history = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            
            # 대화 이력을 JSON으로 변환
            history_text = json.dumps(recent_history)
            
            # 시스템 프롬프트 간소화 (노트북 최적화)
            system_prompt = f"""
            너는 카페 키오스크 대화 생성기야. 
            현재 대화 상태: {current_state}
            사용자 입력에 간결하게 응답해.
            """
            
            response = await asyncio.to_thread(
                self.openai_client.chat.completions.create,
                model="gpt-3.5-turbo",  # 더 작은 모델 사용
                messages=[
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user", 
                        "content": user_input
                    }
                ],
                temperature=0.6,  # 낮은 온도로 더 빠른 결정
                max_tokens=80,    # 더 짧은 응답
                top_p=0.85        # 낮은 top_p 값
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"맥락 기반 응답 생성 실패: {str(e)}")
            return "죄송합니다, 다시 말씀해주세요."

    def generate_context(
        self, 
        user_input: str, 
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        기본 대화 컨텍스트 생성 메서드 - 노트북 최적화 버전
        비동기 generate_contextual_response의 동기 버전
        """
        try:
            # OpenAI 클라이언트가 없으면 기본 응답
            if not self.openai_client:
                return "죄송합니다, 현재 AI 응답 기능을 사용할 수 없습니다."
            
            # 최근 3개의 대화만 사용 (더 토큰 절약)
            recent_history = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            
            # 시스템 프롬프트 간소화
            system_prompt = """카페 키오스크 대화 생성기야. 간결하게 응답해."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # 더 작은 모델 사용
                messages=[
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user", 
                        "content": user_input
                    }
                ],
                temperature=0.6,  # 낮은 온도로 더 빠른 결정
                max_tokens=60,    # 더 짧은 응답
                top_p=0.85        # 낮은 top_p 값
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"대화 컨텍스트 생성 실패: {str(e)}")
            return "죄송합니다, 다시 말씀해주세요."
        
class TextGenerationModel:
    """EleutherAI/polyglot-ko-1.3b 텍스트 생성 모델 래퍼 클래스 - 노트북 최적화 버전"""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        
        # 모델 경로는 그대로 유지
        self.model_path = "EleutherAI/polyglot-ko-1.3b"
        
        # GPU 사용 설정 - 노트북 환경에 맞게 조정
        self.device = "cuda" if torch.cuda.is_available() and settings.USE_GPU else "cpu"
        logger.info(f"텍스트 생성 모델 초기화 중: {self.model_path} (device: {self.device})")
        logger.info(f"모델 캐시 디렉토리: {settings.MODEL_CACHE_DIR}")
        
        # 대화 맥락을 저장할 변수
        self.conversation_history = []
        
        # 대화 상태
        self.dialog_state = "greeting"  # 초기 상태는 인사
        
        # 카페 키오스크 관련 키워드 - 간소화된 목록
        self.cafe_keywords = [
            "카페", "주문", "메뉴", "음료", "커피", "라떼", "아메리카노", 
            "사이즈", "옵션", "결제", "카드", "금액", "가격",
            "얼음", "따뜻한", "아이스"
        ]
        
    def load_model(self):
        """모델과 토크나이저 로드 - 노트북 최적화 버전"""
        try:
            logger.info(f"모델 경로 사용: {self.model_path}")
            logger.info(f"캐시 디렉토리: {settings.MODEL_CACHE_DIR}")
            
            logger.info("토크나이저 로드 중...")
            
            # 중요 변경: local_files_only=False로 변경하여 필요시 온라인 다운로드 허용
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                cache_dir=settings.MODEL_CACHE_DIR,
                local_files_only=False  # 온라인 다운로드 허용으로 변경
            )
            
            # 토큰나이저 특수 토큰 설정
            special_tokens = {
                "pad_token": "<pad>" if not self.tokenizer.pad_token else self.tokenizer.pad_token,
                "eos_token": "</s>" if not self.tokenizer.eos_token else self.tokenizer.eos_token,
                "bos_token": "<s>" if not self.tokenizer.bos_token else self.tokenizer.bos_token
            }
            
            # 필요한 토큰만 추가 (이미 있으면 추가하지 않음)
            tokens_to_add = {}
            for token_name, token_value in special_tokens.items():
                if getattr(self.tokenizer, token_name) is None:
                    tokens_to_add[token_name] = token_value
            
            if tokens_to_add:
                self.tokenizer.add_special_tokens(tokens_to_add)
            
            logger.info("모델 로드 중...")
            
            # 8비트 양자화 활성화 - 노트북에서 메모리 사용량 대폭 감소
            use_8bit = self.device == "cuda" and settings.USE_8BIT_QUANTIZATION
            
            # 모델 로드 옵션 최적화 - local_files_only=False로 변경
            model_kwargs = {
                "cache_dir": settings.MODEL_CACHE_DIR,
                "low_cpu_mem_usage": True,  # 메모리 최적화
                "local_files_only": False  # 온라인 다운로드 허용으로 변경
            }
            
            if self.device == "cuda":
                model_kwargs["torch_dtype"] = torch.float16
                
                # 8비트 양자화 옵션 (노트북 메모리 제한 대응)
                if use_8bit:
                    model_kwargs["load_in_8bit"] = True
                    logger.info("8비트 양자화 활성화 - 메모리 최적화")
            
            # 모델 로드 - 기본 모델만 사용
            # 실패하더라도 최소 3번 시도하는 로직 추가
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.model_path,
                        **model_kwargs
                    )
                    break  # 성공하면 반복문 종료
                except Exception as model_e:
                    logger.warning(f"모델 로드 시도 {attempt+1}/{max_attempts} 실패: {str(model_e)}")
                    if attempt == max_attempts - 1:  # 마지막 시도까지 실패
                        raise  # 예외 재발생
                    # 잠시 대기 후 재시도
                    import time
                    time.sleep(1)
            
            # 토크나이저 크기 조정 필요시
            if len(self.tokenizer) != self.model.config.vocab_size:
                self.model.resize_token_embeddings(len(self.tokenizer))
            
            # 양자화하지 않았을 경우에만 디바이스로 이동
            if not use_8bit:
                self.model.to(self.device)
                if self.device == "cuda" and not use_8bit:
                    logger.info("GPU 메모리 최적화 적용")
                    self.model.half()  # 메모리 최적화
                    
            logger.info("텍스트 생성 모델 로드 완료")
            
            # 모델이 대화형 파인튜닝되었는지 확인
            self.is_dialog_model = False  # EleutherAI/polyglot-ko-1.3b는 대화형 파인튜닝이 되어있지 않음
            logger.info(f"대화형 모델 여부: {self.is_dialog_model}")
            return True
            
        except Exception as e:
            logger.error(f"모델 로드 실패: {str(e)}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
            # 모델 로드 실패 시 폴백 로직 추가
            try:
                logger.info("폴백: 기본 텍스트 생성 모델 사용 시도")
                # GPT 기반 폴백 로직 구현 (모델이 로드되지 않아도 GPT로 응답 생성)
                self.model = None  # 모델은 None으로 설정
                self.is_fallback_mode = True  # 폴백 모드 플래그 설정
                return False  # 로드 실패 표시
            except:
                return False
        
    def _build_conversation_prompt(self, prompt: str, conversation_history=None) -> str:
        """대화 형식의 프롬프트 구성 - 간소화 버전"""
        # 더 짧은 시스템 프롬프트 사용 (토큰 수 감소)
        system_prompt = """당신은 카페 키오스크입니다. 카페 주문만 응답하고, 짧게 답변하세요.
메뉴: 아메리카노, 카페라떼, 카페모카, 바닐라라떼, 카라멜마끼아또, 초코라떼, 그린라떼, 아이스티, 허브티, 레몬에이드
옵션: 온도(핫/아이스), 사이즈(S/L), 샷추가, 시럽추가"""

        # 더 간결한 형식
        formatted_prompt = f"""시스템: {system_prompt}
사용자: {prompt}
키오스크:"""

        return formatted_prompt
    
    def _format_order_prompt(self, prompt: str) -> str:
        """단순 주문 형식의 프롬프트 구성 - 간소화 버전"""
        system_prompt = """당신은 카페 키오스크입니다. 짧게 응답하세요.
메뉴: 아메리카노, 카페라떼, 카페모카, 바닐라라떼, 카라멜마끼아또, 초코라떼, 그린라떼, 아이스티, 허브티, 레몬에이드"""

        context = f"""시스템: {system_prompt}
사용자: {prompt}
키오스크:"""
        return context
    
    def _check_if_dialog_model(self):
        """모델이 대화형으로 파인튜닝되었는지 확인"""
        # EleutherAI/polyglot-ko-1.3b는 기본적으로 대화형으로 파인튜닝되지 않음
        return False

    def _postprocess_response(self, response: str, max_sentences: int = 5) -> str:
        """생성된 응답 후처리 - 노트북 최적화 버전"""
        # 입력된 전체 응답에서 실제 AI 답변만 추출
        
        # 사용자 질문과 과거 대화 제거 - 더 효율적인 문자열 처리
        parts = response.split("키오스크:")
        if len(parts) > 1:
            response = parts[-1].strip()
        else:
            parts = response.split("사용자:")
            if len(parts) > 1:
                response = parts[-1].strip()
            
        # 응답에서 불필요한 접두사 제거 - 더 적은 패턴 검사
        prefixes_to_remove = ["키오스크:", "시스템:", "응답:", "AI:"]
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
                break  # 첫 번째 매칭되는 접두사만 제거하고 중단

        # 문장 분리 및 처리 - 더 간단한 정규식 사용
        sentences = re.split(r'[.!?] ', response)
        
        # 중복된 문장 제거 - 속도 향상을 위해 간소화
        unique_sentences = []
        seen = set()
        for sentence in sentences:
            cleaned = sentence.strip()
            if cleaned and cleaned not in seen and len(cleaned) > 1:
                unique_sentences.append(cleaned)
                seen.add(cleaned)
        
        # 문장 수 제한 - 5 문장으로 더 제한 (원래 8)
        if len(unique_sentences) > max_sentences:
            short_response = '. '.join(unique_sentences[:max_sentences]) + '.'
        else:
            short_response = '. '.join(unique_sentences) + '.'
        
        # 최소 길이 보장
        if not short_response or len(short_response.split()) < 3:
            short_response = "무엇을 도와드릴까요?"
        
        # 특수 문자 및 불필요한 표현 제거 - 최소한의 패턴만 검사
        short_response = re.sub(r"http[s]?://\S+", "", short_response)
        
        # 응답 정리
        short_response = re.sub(r'\s+', ' ', short_response).strip()
        
        # 카페 키오스크 도메인 관련 필터링 - 필터링을 좀 더 유연하게 적용
        is_cafe_related = False
        for keyword in self.cafe_keywords:
            if keyword in short_response.lower():
                is_cafe_related = True
                break
                
        # 카페와 관련 없는 응답인 경우에도 인사/소개 문구는 허용
        intro_patterns = ["안녕하세요", "환영합니다", "도와드릴까요", "무엇을", "주문"]
        is_intro = any(pattern in short_response for pattern in intro_patterns)
        
        # 카페와 관련 없고 인사도 아닌 긴 응답만 필터링
        if not is_cafe_related and not is_intro and len(short_response) > 30:
            short_response = "카페 주문과 관련된 질문만 답변해드릴 수 있습니다."
    
        return short_response
    
    def generate_text(
        self, 
        prompt: str, 
        max_length: int = 100,  # 최적화: 더 짧은 텍스트 생성 (512 -> 100)
        temperature: float = 0.6,  # 최적화: 온도 낮춤 (0.7 -> 0.6)
        top_p: float = 0.85,  # 최적화: top_p 감소 (0.9 -> 0.85)
        top_k: int = 40,  # 최적화: top_k 감소 (50 -> 40)
        repetition_penalty: float = 1.1,  # 최적화: 반복 페널티 감소 (1.2 -> 1.1)
        num_return_sequences: int = 1,
        use_dialog: bool = False,  # 대화형 모드 사용 여부
        is_order: bool = False    # 주문 모드 추가
    ) -> List[str]:
        if not self.model or not self.tokenizer:
            logger.info("모델이 로드되지 않았습니다. 로드 중...")
            self.load_model()
        
        try:
            # 매 요청마다 대화 이력 초기화
            self.reset_conversation()
            
            # 입력 길이 제한 (최적화)
            if len(prompt) > 150:  # 더 적은 입력 허용 (200 -> 150)
                prompt = prompt[:150]
                logger.warning(f"입력 텍스트가 너무 깁니다. 150자로 잘랐습니다.")
            
            # 카페 키오스크 관련 키워드 포함 여부 확인 - 더 빠른 확인
            is_cafe_related = any(keyword in prompt.lower() for keyword in self.cafe_keywords)
                    
            # 카페와 무관한 질문인 경우 기본 응답 반환 (더 빠른 종료)
            if not is_cafe_related and len(prompt) > 5:  # 짧은 인사는 예외
                logger.info(f"카페와 무관한 질문 감지: '{prompt}'")
                return ["카페 주문과 관련된 질문에만 답변해 드립니다."]
            
            # 개선된 프롬프트 구성 - 더 간결한 프롬프트 사용
            processed_prompt = self._format_order_prompt(prompt) if not use_dialog else self._build_conversation_prompt(prompt)
            
            # 파라미터 최적화 - 노트북에 맞게 조정 (속도 향상)
            temperature = min(0.6, temperature)  # 낮은 온도 = 더 빠른 결정
            max_new_tokens = min(max_length, 80)  # 토큰 수 제한 (100 -> 80)
            repetition_penalty = min(repetition_penalty, 1.1)  # 반복 페널티 조정
            
            # 주문 모드에 대한 추가 최적화
            if is_order:
                temperature = 0.5  # 더 낮은 온도 값 (더 결정적인 응답)
                max_new_tokens = 60  # 더 짧은 응답 생성
                top_p = 0.8  # 더 낮은 top_p 값
            
            # 입력 토큰화 - 최적화
            inputs = self.tokenizer(processed_prompt, return_tensors="pt", max_length=200, truncation=True)
            
            # token_type_ids 제거 (필요한 경우)
            if 'token_type_ids' in inputs:
                del inputs['token_type_ids']
                
            # 디바이스로 이동
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # 생성 파라미터 설정 - 노트북 최적화
            gen_kwargs = {
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "repetition_penalty": repetition_penalty,
                "num_return_sequences": num_return_sequences,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer.eos_token_id,
                "no_repeat_ngram_size": 2,  # 3에서 2로 감소
                "max_length": 200,  # 400에서 200으로 대폭 감소
                "early_stopping": True  # 일찍 생성 중단
            }
            
            # 텍스트 생성
            logger.info(f"텍스트 생성 시작: '{prompt[:30]}...'")
            with torch.no_grad():
                output_sequences = self.model.generate(**inputs, **gen_kwargs)
            
            # 결과 디코딩 및 후처리
            generated_texts = []
            for output in output_sequences:
                generated_text = self.tokenizer.decode(output, skip_special_tokens=True)
                
                # 프롬프트 부분 제거하고 응답만 추출
                if processed_prompt in generated_text:
                    response = generated_text.replace(processed_prompt, "").strip()
                else:
                    response = generated_text.strip()
                
                # 후처리 적용 - 카페 키오스크 컨텍스트 유지 및 5줄 제한 (8에서 5로 축소)
                processed_text = self._postprocess_response(response, max_sentences=5)
                
                generated_texts.append(processed_text)
                
            logger.info(f"텍스트 생성 완료: {len(generated_texts)} 개의 결과")
            return generated_texts
            
        except Exception as e:
            logger.error(f"텍스트 생성 실패: {str(e)}")
            # 더 간결한 오류 응답
            return ["죄송합니다. 응답을 생성할 수 없습니다."]
    
    def reset_conversation(self):
        """대화 이력 초기화"""
        self.conversation_history = []
        self.dialog_state = "greeting"
        logger.info("대화 이력이 초기화되었습니다.")
        return True

# 싱글톤 인스턴스 생성 
text_model = TextGenerationModel()