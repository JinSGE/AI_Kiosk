# 🎙️ AI 카페 키오스크 API

**STT → NLP → FSM → RAG → TTS** 통합 파이프라인 기반의 한국어 음성 인식 카페 키오스크 백엔드 API 서버입니다.  
고객의 음성 주문을 실시간으로 인식하고 자연어로 응답하며, WebSocket을 통해 프론트엔드와 실시간 상태를 동기화합니다.

---

## 🧠 시스템 파이프라인

```mermaid
graph LR
    A[🎤 마이크 입력] --> B[STT\nWhisper / Google STT]
    B --> C[NLP\n의도 · 슬롯 추출]
    C --> D[FSM\n주문 상태 관리]
    D --> E[RAG\nFAISS + Ko-SBERT]
    E --> F[응답 생성\nGPT-4o / KoAlpaca]
    F --> G[TTS\ngTTS / Coqui]
    G --> H[🔊 음성 출력]
```

---

## 🛠 기술 스택

| 컴포넌트 | 기술 |
|----------|------|
| **STT** | OpenAI Whisper (faster-whisper), Google SpeechRecognition |
| **NLP** | 규칙 기반 의도/슬롯 추출 (`nlp_processor.py`) |
| **FSM** | 커스텀 유한 상태 기계 (`models/fsm.py`) |
| **RAG** | FAISS + sentence-transformers (Ko-SBERT) |
| **LLM** | GPT-4o (OpenAI, 설정 시), KoAlpaca / Polyglot-Ko (로컬 폴백) |
| **TTS** | gTTS (Google), Coqui TTS (오프라인) |
| **서버** | FastAPI + Uvicorn |
| **실시간** | WebSocket |

---

## 📁 디렉토리 구조

```
AI-API/
├── app/
│   ├── main.py                    # FastAPI 앱 진입점, ServiceManager, 라우터 등록
│   ├── config.py                  # 설정 (pydantic-settings 기반)
│   ├── __init__.py                # 패키지 초기화, 로그 설정
│   ├── models/
│   │   ├── fsm.py                 # 유한 상태 기계 (주문 흐름)
│   │   ├── stt.py                 # STT 모델 래퍼
│   │   ├── tts.py                 # TTS 모델 래퍼
│   │   ├── text_generation.py    # 텍스트 생성 모델
│   │   └── rag_models.py          # RAG 관련 모델
│   ├── routers/
│   │   ├── kiosk_router.py        # 키오스크 API (주문, 오디오, 장바구니)
│   │   ├── websocket_router.py    # WebSocket 엔드포인트 및 이벤트 함수
│   │   ├── fsm_router.py          # FSM 상태 관리 API
│   │   ├── stt_router.py          # STT API
│   │   ├── tts_router.py          # TTS API
│   │   ├── pipeline_router.py     # 전체 파이프라인 API
│   │   ├── rag_router.py          # RAG 검색 API
│   │   ├── menu_router.py         # 메뉴 조회 API
│   │   └── order_router.py        # 주문 API
│   ├── services/
│   │   ├── connection_manager.py  # WebSocket 연결 관리 (ConnectionManager)
│   │   ├── kiosk_service.py       # 키오스크 핵심 비즈니스 로직
│   │   ├── enhanced_pipeline_service.py  # GPT 통합 파이프라인
│   │   ├── pipeline_service.py    # 기본 파이프라인
│   │   ├── enhanced_continuous_dialog_service.py  # VAD 기반 연속 대화
│   │   ├── rag_service.py         # RAG 검색 서비스
│   │   ├── nlp_processor.py       # NLP 의도/슬롯 추출
│   │   ├── stt_service_model.py   # STT 서비스
│   │   ├── tts_service_model.py   # TTS 서비스
│   │   └── audio_device.py        # 오디오 장치 관리
│   ├── utils/
│   │   ├── caching.py             # 응답 캐싱
│   │   ├── kb_manager.py          # 지식 베이스 관리
│   │   ├── menu_processor.py      # 메뉴 데이터 전처리
│   │   └── validators.py          # 입력 유효성 검증
│   └── data/
│       └── menu_data.json         # 메뉴 데이터
├── public/                        # 정적 파일 (프론트엔드 빌드)
├── audio_input/                   # 오디오 입력 임시 저장
├── audio_output/                  # TTS 생성 오디오 저장
├── model_cache/                   # 모델 가중치 캐시
├── setup_knowledge_base.py        # RAG 지식 베이스 초기화 스크립트
├── requirements.txt
├── .env.example
└── .env                           # (gitignore 대상)
```

---

## ⚙️ 설치 및 설정

### 1. 필수 패키지 설치

```bash
# Python 의존성
pip install --upgrade pip
pip install -r requirements.txt

# 시스템 패키지 (Linux/WSL 환경)
apt-get install -y portaudio19-dev ffmpeg
```

### 2. 환경 설정

`.env.example`을 복사하여 `.env` 파일을 생성합니다.

```bash
cp .env.example .env
```

`.env` 파일 주요 설정:

```env
# OpenAI API 키 (GPT 기능 사용 시 필수)
OPENAI_API_KEY=your-openai-api-key-here

# TTS 엔진 선택: gtts (기본) 또는 coqui
TTS_MODEL_PATH=gtts

# STT 엔진 선택: google (기본) 또는 whisper
STT_MODEL_PATH=google

# GPU 설정 (GPU 사용 시 True)
USE_GPU=False

# 디버그 모드
DEBUG=False
```

### 3. RAG 지식 베이스 초기화

서버 실행 전 반드시 1회 실행합니다.

```bash
python setup_knowledge_base.py --force
python -m app.utils.menu_processor
```

### 4. 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

또는 직접 실행:

```bash
python -m app.main
```

---

## 🌐 API 엔드포인트

### 공통

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/` | API 정보 및 라우트 목록 |
| `GET` | `/api/v1/health` | 서비스 상태 확인 |
| `GET` | `/models/status` | STT/TTS/NLP/FSM/RAG 모델 상태 |

### 키오스크 (`/api/v1/kiosk`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/v1/kiosk/text-input` | 텍스트 입력으로 주문 처리 |
| `POST` | `/api/v1/kiosk/process-audio` | 오디오 파일로 주문 처리 |
| `POST` | `/api/v1/kiosk/audio` | 오디오 처리 (중복 방지 로직 포함) |
| `GET` | `/api/v1/kiosk/cart` | 현재 장바구니 조회 |
| `POST` | `/api/v1/kiosk/cart/clear` | 장바구니 초기화 |

### STT (`/api/stt`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/stt/transcribe` | 오디오 → 텍스트 변환 |

### TTS (`/api/tts`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/tts/synthesize` | 텍스트 → 음성 변환 |
| `POST` | `/api/tts/synthesize_base64` | 텍스트 → 음성 (Base64 반환) |
| `GET` | `/api/tts/speakers` | 사용 가능한 화자 목록 |
| `GET` | `/api/tts/info` | TTS 모델 정보 |

### 파이프라인 (`/api/pipeline`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/pipeline/process_audio` | 오디오 전체 파이프라인 처리 |
| `POST` | `/api/pipeline/process_text` | 텍스트 전체 파이프라인 처리 |

### RAG (`/api/rag`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/api/rag/search` | 지식 베이스 검색 |

### 메뉴 / 주문

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/v1/menu` | 전체 메뉴 조회 |
| `POST` | `/api/v1/orders` | 주문 생성 |

### FSM (`/fsm`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/fsm/status` | 현재 FSM 상태 조회 |
| `POST` | `/fsm/transition` | 상태 전이 요청 |

---

## 🔌 WebSocket

### 엔드포인트

| 경로 | 설명 |
|------|------|
| `ws://host:5000/ws` | FSM 상태 및 음성 처리 결과 수신 |
| `ws://host:5000/ws/cart` | 장바구니 실시간 동기화 |

### 클라이언트 → 서버 (action 타입)

```json
{ "action": "process_text", "text": "아메리카노 두 잔 주세요" }
{ "action": "change_state", "state": "order_confirm", "slots": {} }
{ "action": "payment_complete" }
{ "action": "reset_session", "full_reset": true }
{ "action": "request_greeting", "force_new": false }
```

### 서버 → 클라이언트 (type 타입)

| type | 설명 |
|------|------|
| `state_update` | FSM 상태 변경 알림 |
| `cart_update` | 장바구니 업데이트 (add / remove / reset) |
| `load_menu` | 메뉴 데이터 전송 |
| `payment_completed` | 결제 완료 알림 |
| `order_processed` | 음성 주문 처리 결과 |
| `error` | 오류 알림 |

---

## 🔊 TTS 엔진 옵션

| 엔진 | 설정값 | 특징 |
|------|--------|------|
| **gTTS** | `gtts` | Google 기반, 인터넷 연결 필요, 고품질 한국어 |
| **Coqui TTS** | `coqui` | 오프라인, 다양한 화자/스타일, 피치·속도 조절 가능 |

> 모든 TTS 엔진 실패 시 시스템이 자동으로 **gTTS**로 폴백합니다.

---

## 🤖 서비스 아키텍처

서비스 인스턴스는 `app/main.py`의 **`ServiceManager` 싱글톤**에서 중앙 관리됩니다.  
라우터에서 서비스가 필요한 경우 FastAPI 의존성 주입(`Depends`)을 사용합니다.

```python
from app.main import get_kiosk_service

@router.post("/endpoint")
async def my_endpoint(kiosk_service: KioskService = Depends(get_kiosk_service)):
    ...
```

---

## 🐛 문제 해결

### 서버 시작 오류

```bash
# 의존성 재설치
pip install -r requirements.txt --force-reinstall

# pydantic 버전 확인 (v2 이상 필요)
python -c "import pydantic; print(pydantic.VERSION)"
```

### VAD / 마이크 오류

```bash
# webrtcvad 설치
pip install webrtcvad

# PyAudio 설치 (Windows)
pip install pipwin && pipwin install pyaudio
```

### RAG 초기화 실패

```bash
python setup_knowledge_base.py --force
```

### 로그 확인

서버 로그는 **`app.log`** 파일에 저장됩니다.

```bash
# 실시간 로그 확인
tail -f app.log
```

---

## 📋 개발 참고

- **Python 버전**: 3.10+
- **FastAPI 버전**: 0.100.0+
- **Pydantic 버전**: v2 (pydantic-settings 2.x)
- **API 문서**: 서버 실행 후 `http://localhost:5000/docs`