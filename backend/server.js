// server.js - 메인 서버 파일
const http = require('http');
const axios = require('axios');
const app = require('./app');
const connectDB = require('./config/db');

// 환경 변수 설정
try {
  const dotenv = require('dotenv');
  dotenv.config();
} catch (error) {
  console.warn("dotenv 로드 실패, 기본 환경 변수를 사용합니다:", error.message);
  process.env.MONGODB_URI = "mongodb://localhost:27017/cafe-kiosk";
  process.env.JWT_SECRET = "your_very_secure_jwt_secret_key_change_this";
  process.env.PORT = 8000;
}

const PORT = process.env.PORT || 8000;

console.log('환경 변수 확인:');
console.log('AI_API_URL:', process.env.AI_API_URL);
console.log('NODE_ENV:', process.env.NODE_ENV);

// DB 연결
connectDB();

// HTTP 콜백 서버 생성
const server = http.createServer(app);

// 서버 리스닝
server.listen(PORT, '0.0.0.0', async () => {
  console.log(`서버가 포트 ${PORT}에서 실행 중입니다`);
  
  // AI API 연결 확인
  try {
    const AI_API_BASE_URL = process.env.AI_API_URL || 'http://localhost:5000/api/v1';
    
    console.group('🔍 AI API 연결 확인');
    console.log('기본 URL:', AI_API_BASE_URL);
    
    const possibleHealthEndpoints = [
      `${AI_API_BASE_URL}/health`,  
      `${AI_API_BASE_URL.replace('/api/v1', '')}/health`,  
      'http://localhost:5000/health',  
      'http://localhost:5000/api/v1/health'  
    ];
    
    let successfulConnection = false;
    
    for (const endpoint of possibleHealthEndpoints) {
      try {
        console.log(`📡 엔드포인트 시도: ${endpoint}`);
        
        const response = await axios.get(endpoint, { 
          timeout: 5000,
          validateStatus: function (status) {
            return status >= 200 && status < 500;
          }
        });
        
        console.log(`✅ 성공적인 연결: ${endpoint}`);
        console.log('응답:', { status: response.status, data: response.data });
        
        successfulConnection = true;
        break;  
      } catch (endpointError) {
        console.warn(`❌ 엔드포인트 연결 실패: ${endpoint}`);
        console.warn('오류 상세:', endpointError.message);
      }
    }
    
    if (!successfulConnection) console.warn('❗ 모든 엔드포인트 연결 실패');
    console.groupEnd();
  } catch (error) {
    console.warn('AI API 연결 확인 전체 실패. AI 기능이 작동하지 않을 수 있습니다.');
    console.error('AI API 연결 전체 오류:', error);
  }
});