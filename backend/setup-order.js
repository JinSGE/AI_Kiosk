// setup-order.js - 샘플 주문 생성 스크립트
require('dotenv').config(); // 환경 변수 로드
const mongoose = require('mongoose'); // MongoDB ODM 라이브러리 가져오기
const Order = require('./models/Order'); // Order 모델 가져오기

// MongoDB 연결 - 간소화된 연결 옵션
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('MongoDB 연결 성공'))
  .catch(err => {
    console.error('MongoDB 연결 오류:', err);
    process.exit(1); // 오류 시 프로세스 종료
  });

// 주문 번호 생성 함수 - 날짜와 랜덤 번호 조합
function generateOrderNumber() {
  const date = new Date();
  const dateStr = date.getFullYear().toString().slice(-2) + 
                 String(date.getMonth() + 1).padStart(2, '0') + 
                 String(date.getDate()).padStart(2, '0');
  const random = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
  return `ORD-${dateStr}-${random}`;
}

// 가격 계산 함수 - 아이템 가격 * 수량 + 옵션 가격의 합계
function calculateTotalPrice(items) {
  return items.reduce((total, item) => 
    total + (item.price * item.quantity) + (item.optionsPrice || 0), 0);
}

// 주문 날짜 생성 함수 - 현재 기준 특정 시간 이전
function generateOrderDate(hoursAgo) {
  const date = new Date();
  date.setHours(date.getHours() - hoursAgo);
  return date;
}

// 메뉴 데이터 - 필수 속성만 유지 (id, name, price, category, image)
const menuItems = [
  { id: 1, name: '아메리카노', price: 4500, category: '커피', image: '/images/menu/americano.jpg' },
  { id: 2, name: '카페 라떼', price: 5000, category: '커피', image: '/images/menu/cafelatte.jpg' },
  { id: 3, name: '바닐라 라떼', price: 5500, category: '커피', image: '/images/menu/vanillalatte.jpg' },
  { id: 4, name: '카페 모카', price: 5500, category: '커피', image: '/images/menu/cafemocha.jpg' },
  { id: 5, name: '카라멜 마끼아또', price: 5800, category: '커피', image: '/images/menu/caramelmacchiato.jpg' },
  { id: 6, name: '복숭아 아이스 티', price: 5000, category: '티', image: '/images/menu/peachicedtea.jpg' },
  { id: 7, name: '초코 라떼', price: 5500, category: '논커피', image: '/images/menu/chocolatte.jpg' },
  { id: 8, name: '녹차 라떼', price: 5500, category: '논커피', image: '/images/menu/greentealatte.jpg' },
  { id: 9, name: '레몬 에이드', price: 5500, category: '에이드', image: '/images/menu/lemonade.jpg' },
  { id: 10, name: '허브 티', price: 5000, category: '티', image: '/images/menu/herbtea.jpg' }
];

// 옵션 데이터 - 종류별 옵션 정의
const opt = {
  // 온도 옵션
  temp: [
    { id: 'temp1', name: '온도', price: 0, choice: '아이스' },
    { id: 'temp2', name: '온도', price: 0, choice: '핫' }
  ],
  // 사이즈 옵션
  size: [
    { id: 'size1', name: '사이즈', price: 0, choice: '레귤러' },
    { id: 'size2', name: '사이즈', price: 500, choice: '라지' }
  ],
  // 샷 추가 옵션
  shot: [
    { id: 'shot1', name: '샷 추가', price: 500, choice: '1샷 추가' },
    { id: 'shot2', name: '샷 추가', price: 1000, choice: '2샷 추가' }
  ],
  // 시럽 옵션
  syrup: [
    { id: 'syrup1', name: '시럽', price: 300, choice: '바닐라 시럽' },
    { id: 'syrup2', name: '시럽', price: 300, choice: '헤이즐넛 시럽' },
    { id: 'syrup3', name: '시럽', price: 300, choice: '카라멜 시럽' }
  ]
};

// 샘플 주문 생성 함수
async function createSampleOrders() {
  try {
    // 기존 주문 삭제
    await Order.deleteMany({});
    console.log('기존 주문 데이터 삭제 완료');
    
    // 샘플 주문 데이터 정의 - 5개 주문, 10개 메뉴 모두 활용
    const sampleOrders = [
      // 주문 1: 아메리카노와 카페라떼 (완료)
      {
        orderNumber: generateOrderNumber(),
        date: generateOrderDate(5), // 5시간 전
        items: [
          {
            ...menuItems[0], // 아메리카노
            quantity: 2,
            options: [opt.temp[0], opt.size[1]], // 아이스, 라지
            optionsPrice: 500 // 라지 사이즈 비용
          },
          {
            ...menuItems[1], // 카페라떼
            quantity: 1,
            options: [opt.temp[1]], // 핫
            optionsPrice: 0
          }
        ],
        status: '완료'
      },
      
      // 주문 2: 바닐라라떼와 카페모카 (완료)
      {
        orderNumber: generateOrderNumber(),
        date: generateOrderDate(3), // 3시간 전
        items: [
          {
            ...menuItems[2], // 바닐라라떼
            quantity: 1,
            options: [opt.temp[0], opt.shot[0]], // 아이스, 1샷 추가
            optionsPrice: 500 // 1샷 추가 비용
          },
          {
            ...menuItems[3], // 카페모카
            quantity: 1,
            options: [opt.temp[1], opt.size[1]], // 핫, 라지
            optionsPrice: 500 // 라지 사이즈 비용
          }
        ],
        status: '완료'
      },
      
      // 주문 3: 카라멜 마키아토와 복숭아 아이스티 (준비중)
      {
        orderNumber: generateOrderNumber(),
        date: generateOrderDate(1), // 1시간 전
        items: [
          {
            ...menuItems[4], // 카라멜 마키아토
            quantity: 1,
            options: [opt.temp[1], opt.syrup[2]], // 핫, 카라멜 시럽
            optionsPrice: 300 // 시럽 추가 비용
          },
          {
            ...menuItems[5], // 복숭아 아이스티
            quantity: 2,
            options: [opt.size[1]], // 라지
            optionsPrice: 500 // 라지 사이즈 비용
          }
        ],
        status: '준비중'
      },
      
      // 주문 4: 초코라떼와 녹차라떼 (준비중)
      {
        orderNumber: generateOrderNumber(),
        date: generateOrderDate(0.5), // 30분 전
        items: [
          {
            ...menuItems[6], // 초코라떼
            quantity: 1,
            options: [opt.temp[0]], // 아이스
            optionsPrice: 0
          },
          {
            ...menuItems[7], // 녹차라떼
            quantity: 1,
            options: [opt.temp[1], opt.size[1]], // 핫, 라지
            optionsPrice: 500 // 라지 사이즈 비용
          }
        ],
        status: '준비중'
      },
      
      // 주문 5: 레몬에이드와 허브티 (접수)
      {
        orderNumber: generateOrderNumber(),
        date: new Date(), // 현재
        items: [
          {
            ...menuItems[8], // 레몬에이드
            quantity: 2,
            options: [],
            optionsPrice: 0
          },
          {
            ...menuItems[9], // 허브티
            quantity: 1,
            options: [opt.temp[1]], // 핫
            optionsPrice: 0
          }
        ],
        status: '접수'
      }
    ];
    
    // 총액 계산
    sampleOrders.forEach(order => {
      order.totalPrice = calculateTotalPrice(order.items);
    });
    
    // 주문 데이터 저장
    await Order.insertMany(sampleOrders);
    console.log(`${sampleOrders.length}개 샘플 주문 추가 완료`);
    
    // 주문 정보 요약 출력 - 간소화된 출력
    console.log('\n===== 생성된 주문 요약 =====');
    sampleOrders.forEach((order, i) => {
      console.log(`\n[주문 ${i + 1}] ${order.orderNumber}`);
      console.log(`- 날짜: ${order.date.toLocaleString()}`);
      console.log(`- 상태: ${order.status}`);
      console.log(`- 항목: ${order.items.map(item => `${item.name} x${item.quantity}`).join(', ')}`);
      console.log(`- 총액: ${order.totalPrice.toLocaleString()}원`);
    });
    
    console.log('\n주문 데이터 저장 완료');
    process.exit(0); // 성공 시 종료
  } catch (error) {
    // 오류 처리
    console.error('주문 생성 오류:', error);
    process.exit(1); // 오류 시 종료
  }
}

// 함수 실행
createSampleOrders();