# Cafe AI Kiosk 🤖☕

카페 키오스크 AI 주문 시스템입니다. 한국어 음성 인식과 AI 기반 주문 처리를 지원합니다.

## 시스템 구성

```
SE/
├── frontend/          # React 기반 키오스크 UI
├── backend/           # Node.js/Express + MongoDB API 서버
└── AI-API/            # Python FastAPI AI 파이프라인 서버 (STT → NLP → RAG → TTS)
```

## 기술 스택

| 구성 요소 | 기술 |
|---|---|
| **Frontend** | React, Axios, WebSocket |
| **Backend** | Node.js, Express, MongoDB, JWT |
| **AI-API** | Python, FastAPI, OpenAI, gTTS, Whisper |

## 설치 및 실행

### 1. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # 환경변수 설정
npm start              # http://localhost:3000
```

### 2. Backend (Node.js)

```bash
cd backend
npm install
cp .env.example .env   # 환경변수 설정 (MONGODB_URI, JWT_SECRET 등)
node setup-admin.js    # 초기 관리자 계정 생성
node setup-menuitem.js # 초기 메뉴 데이터 삽입
npm start              # http://localhost:5000
```

### 3. AI-API (Python)

```bash
cd AI-API
pip install -r requirements.txt
cp .env.example .env   # OPENAI_API_KEY 등 환경변수 설정
python -m uvicorn app.main:app --port 8000 --reload
```

## 환경 변수

각 서비스 폴더의 `.env.example` 파일을 참고하여 `.env` 파일을 생성하세요.

### AI-API 주요 변수
- `OPENAI_API_KEY` : GPT 기반 기능 활성화에 필요한 OpenAI API 키

### Backend 주요 변수
- `MONGODB_URI` : MongoDB 연결 문자열
- `JWT_SECRET` : 관리자 인증 JWT 시크릿

## 주요 기능

- 🎤 **음성 주문**: 한국어 STT(Whisper/Google) → NLP → 장바구니 업데이트
- 🧠 **AI 대화**: OpenAI GPT + RAG 기반 메뉴 추천 및 주문 안내
- 🛒 **실시간 동기화**: WebSocket으로 메뉴판과 장바구니 실시간 연동
- 🔐 **관리자 패널**: JWT 인증 기반 주문 관리 대시보드

## API 엔드포인트

| 서비스 | 주소 |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:5000/api/v1 |
| AI-API | http://localhost:8000 |
| AI-API 상태 | http://localhost:8000/api/v1/health |
