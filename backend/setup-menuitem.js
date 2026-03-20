// setup-menuItem.js - 카페 메뉴 생성 스크립트
require('dotenv').config(); // 환경 변수 로드
const mongoose = require('mongoose'); // MongoDB ODM 라이브러리 가져오기
const MenuItem = require('./models/MenuItem'); // MenuItem 모델 가져오기

// MongoDB 연결 - 간소화된 연결 옵션
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('MongoDB 연결 성공'))
  .catch(err => {
    console.error('MongoDB 연결 오류:', err);
    process.exit(1); // 오류 시 프로세스 종료
  });

// 메뉴 아이템 생성 함수
async function createMenuItems() {
  try {
    // 기존 메뉴 삭제 - 바로 삭제하도록 간소화
    await MenuItem.deleteMany({});
    console.log('기존 메뉴 삭제 완료');
    
    // 메뉴 아이템 데이터 정의 - 10개 메뉴 항목
    const menuItems = [
      {
        id: 1,
        name: '아메리카노',
        price: 4500,
        category: '커피',
        image: '/images/americano.jpg',
        description: '깊고 진한 에스프레소에 물을 더해 깔끔한 맛의 스탠다드 커피'
      },
      {
        id: 2,
        name: '카페 라떼',
        price: 5000,
        category: '커피',
        image: '/images/cafelatte.jpg',
        description: '진한 에스프레소와 부드러운 우유가 조화를 이루는 대표적인 라떼'
      },
      {
        id: 3,
        name: '바닐라 라떼',
        price: 5500,
        category: '커피',
        image: '/images/vanillalatte.jpg',
        description: '달콤한 바닐라 시럽이 추가된 크리미한 라떼'
      },
      {
        id: 4,
        name: '카페 모카',
        price: 5500,
        category: '커피',
        image: '/images/cafemocha.jpg',
        description: '진한 초콜릿과 에스프레소의 완벽한 조화, 달콤 쌉싸름한 맛'
      },
      {
        id: 5,
        name: '카라멜 마끼아또',
        price: 5800,
        category: '커피',
        image: '/images/caramelmacchiato.jpg',
        description: '바닐라 시럽과 카라멜 소스가 어우러진 달콤한 에스프레소 음료'
      },
      {
        id: 6,
        name: '복숭아 아이스 티',
        price: 5000,
        category: '티',
        image: '/images/peachicedtea.jpg',
        description: '향긋한 복숭아 향이 가득한 시원한 아이스티'
      },
      {
        id: 7,
        name: '초코 라떼',
        price: 5500,
        category: '커피',
        image: '/images/chocolatte.jpg',
        description: '진한 초콜릿과 부드러운 우유가 만나 달콤한 맛의 음료'
      },
      {
        id: 8,
        name: '그린 라떼',
        price: 5500,
        category: '커피',
        image: '/images/greentealatte.jpg',
        description: '은은한 녹차 향과 부드러운 우유의 조화로운 맛'
      },
      {
        id: 9,
        name: '레몬 에이드',
        price: 5500,
        category: '에이드/주스',
        image: '/images/lemonade.jpg',
        description: '상큼한 레몬과 탄산의 청량함이 가득한 시원한 음료'
      },
      {
        id: 10,
        name: '허브 티',
        price: 5000,
        category: '티',
        image: '/images/herbtea.jpg',
        description: '다양한 허브의 은은한 향과 맛을 즐길 수 있는 전통 차'
      }
    ];
    
    // 메뉴 아이템 저장
    const result = await MenuItem.insertMany(menuItems);
    console.log(`${result.length}개 메뉴 추가 완료`);
    
    // 카테고리별 메뉴 출력 - 간소화된 출력 형식
    console.log('\n===== 카페 메뉴 목록 =====');
    // Set을 사용하여 고유 카테고리 추출
    const categories = [...new Set(menuItems.map(item => item.category))];
    
    // 카테고리별로 메뉴 출력
    categories.forEach(category => {
      console.log(`\n[${category}]`);
      menuItems
        .filter(item => item.category === category)
        .forEach(item => console.log(`- ${item.name}: ${item.price.toLocaleString()}원`));
    });
    
    console.log('\n메뉴 데이터 저장 완료');
    process.exit(0); // 성공 시 종료
  } catch (error) {
    // 오류 처리
    console.error('메뉴 생성 오류:', error);
    process.exit(1); // 오류 시 종료
  }
}

// 함수 실행
createMenuItems();