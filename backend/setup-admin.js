// setup-admin.js - 관리자 계정 생성 스크립트
require('dotenv').config(); // 환경 변수 로드
const mongoose = require('mongoose'); // MongoDB ODM 라이브러리 가져오기
const bcrypt = require('bcryptjs'); // 비밀번호 해싱 라이브러리
const Admin = require('./models/Admin'); // Admin 모델 가져오기

// MongoDB 연결 - 간소화된 연결 옵션
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('MongoDB 연결 성공'))
  .catch(err => {
    console.error('MongoDB 연결 오류:', err);
    process.exit(1); // 오류 시 프로세스 종료
  });

// 기본 관리자 계정 생성 함수
async function createAdmin() {
  try {
    // 기존 관리자 계정 확인
    const adminExists = await Admin.findOne({ username: 'admin' });
    
    if (adminExists) {
      console.log('관리자 계정이 이미 존재합니다.');
      return process.exit(0); // 이미 존재하면 종료
    }
    
    // 비밀번호 해싱 - salt 생성 및 비밀번호 암호화
    const hashedPassword = await bcrypt.hash('qwer', await bcrypt.genSalt(10));
    
    // 관리자 계정 생성 및 저장
    await new Admin({
      username: 'admin',
      password: hashedPassword,
      name: '기본 관리자'
    }).save(); // 인스턴스 생성과 저장을 한 줄로 통합
    
    // 결과 출력
    console.log('관리자 계정 생성 완료 (사용자: admin / 비밀번호: qwer)');
    process.exit(0); // 성공 시 종료
  } catch (error) {
    // 오류 처리
    console.error('관리자 계정 생성 오류:', error);
    process.exit(1); // 오류 시 종료
  }
}

// 함수 실행
createAdmin();