import pytest
from fastapi.testclient import TestClient
import json
from unittest.mock import MagicMock, patch

from app.main import app
from app.models.text_generation import TextGenerationModel

client = TestClient(app)

# 텍스트 생성 모델 모킹
@pytest.fixture
def mock_text_model():
    with patch("app.routers.text_generation.text_model") as mock:
        # 모델 상태 설정
        mock.model = MagicMock()
        mock.tokenizer = MagicMock()
        mock.device = "cpu"
        
        # generate_text 메서드 모킹
        mock.generate_text.return_value = ["안녕하세요, 아메리카노랑 카페라떼 한잔 주세요."]
        
        yield mock

def test_generate_text(mock_text_model):
    """텍스트 생성 API 테스트"""
    payload = {
        "prompt": "안녕하세요, 아메리카노랑 카페라떼",
        "max_length": 50,
        "temperature": 0.7
    }
    
    response = client.post("/api/v1/generate-text", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "generated_texts" in data
    assert isinstance(data["generated_texts"], list)
    assert len(data["generated_texts"]) == 1
    assert data["prompt"] == payload["prompt"]
    
    # 모델 호출 검증
    mock_text_model.generate_text.assert_called_once()
    args, kwargs = mock_text_model.generate_text.call_args
    assert kwargs["prompt"] == payload["prompt"]
    assert kwargs["max_length"] == payload["max_length"]
    assert kwargs["temperature"] == payload["temperature"]

def test_model_status(mock_text_model):
    """모델 상태 확인 API 테스트"""
    response = client.get("/api/v1/models/text/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "is_loaded" in data
    assert data["is_loaded"] is True
    assert "device" in data
    assert data["device"] == "cpu"

def test_invalid_prompt():
    """잘못된 프롬프트 테스트"""
    payload = {
        "prompt": "",  # 비어있는 프롬프트
        "max_length": 50
    }
    
    response = client.post("/api/v1/generate-text", json=payload)
    
    assert response.status_code == 422  # 유효성 검증 실패

def test_load_model(mock_text_model):
    """모델 로드 API 테스트"""
    mock_text_model.load_model.return_value = True
    
    response = client.post("/api/v1/models/text/load")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "loading"