// src/utils/helpers.js

/**
 * 옵션 가격 계산
 * @param {Array<string>} options - 선택된 옵션 목록
 * @returns {number} 총 추가 금액
 */
export const calculateOptionPrice = (options) => {
  const optionPrices = {
    'Hot': 0,
    'Ice': 0,
    'Small': 0,
    'Regular': 500,
    'Large': 1000,
    '샷 추가': 500,
    '시럽 추가': 300,
    '휘핑크림 추가': 500
  };

  const optionsArray = Array.isArray(options) ? options : [];
  return optionsArray.reduce((total, option) => total + (optionPrices[option] || 0), 0);
};

/**
 * 메뉴 이름에 해당하는 이미지 경로 반환
 * @param {string} menuName - 메뉴명
 * @returns {string} 이미지 절대 경로
 */
export const getImagePathByName = (menuName) => {
  if (!menuName) return '/images/default-menu-image.jpg';
  
  const menuImages = {
    "아메리카노": "/images/americano.jpg",
    "카페라떼": "/images/cafelatte.jpg",
    "카페 라떼": "/images/cafelatte.jpg",
    "카페모카": "/images/cafemocha.jpg",
    "카페 모카": "/images/cafemocha.jpg",
    "바닐라 라떼": "/images/vanillalatte.jpg",
    "바닐라라떼": "/images/vanillalatte.jpg",
    "카라멜 마끼아또": "/images/caramelmacchiato.jpg",
    "카라멜마끼아또": "/images/caramelmacchiato.jpg",
    "초코 라떼": "/images/chocolatte.jpg",
    "초코라떼": "/images/chocolatte.jpg",
    "그린 라떼": "/images/greentealatte.jpg",
    "그린라떼": "/images/greentealatte.jpg",
    "녹차 라떼": "/images/greentealatte.jpg",
    "녹차라떼": "/images/greentealatte.jpg",
    "복숭아아이스티": "/images/peachicedtea.jpg",
    "복숭아 아이스 티": "/images/peachicedtea.jpg",
    "복숭아 아이스티": "/images/peachicedtea.jpg",
    "허브 티": "/images/herbtea.jpg",
    "허브티": "/images/herbtea.jpg",
    "레몬 에이드": "/images/lemonade.jpg",
    "레몬에이드": "/images/lemonade.jpg"
  };

  return menuImages[menuName] || '/images/default-menu-image.jpg';
};

/**
 * 메뉴 설명 반환
 * @param {string} menuName - 메뉴명
 * @returns {string} 메뉴 설명
 */
export const getMenuDescription = (menuName) => {
  if (!menuName) return '메뉴 설명 없음';
  
  const menuDescriptions = {
    "아메리카노": "깊고 진한 에스프레소에 물을 더해 깔끔한 맛의 스탠다드 커피",
    "카페라떼": "진한 에스프레소와 부드러운 우유가 조화를 이루는 대표적인 라떼",
    "카페 라떼": "진한 에스프레소와 부드러운 우유가 조화를 이루는 대표적인 라떼",
    "카페모카": "진한 초콜릿과 에스프레소의 완벽한 조화, 달콤 쌉싸름한 맛",
    "카페 모카": "진한 초콜릿과 에스프레소의 완벽한 조화, 달콤 쌉싸름한 맛",
    "바닐라 라떼": "달콤한 바닐라 시럽이 추가된 크리미한 라떼",
    "바닐라라떼": "달콤한 바닐라 시럽이 추가된 크리미한 라떼",
    "카라멜 마끼아또": "바닐라 시럽과 카라멜 소스가 어우러진 달콤한 에스프레소 음료",
    "카라멜마끼아또": "바닐라 시럽과 카라멜 소스가 어우러진 달콤한 에스프레소 음료",
    "초코 라떼": "진한 초콜릿과 부드러운 우유가 만나 달콤한 맛의 음료",
    "초코라떼": "진한 초콜릿과 부드러운 우유가 만나 달콤한 맛의 음료",
    "그린 라떼": "은은한 녹차 향과 부드러운 우유의 조화로운 맛",
    "그린라떼": "은은한 녹차 향과 부드러운 우유의 조화로운 맛",
    "녹차 라떼": "은은한 녹차 향과 부드러운 우유의 조화로운 맛",
    "녹차라떼": "은은한 녹차 향과 부드러운 우유의 조화로운 맛",
    "복숭아아이스티": "향긋한 복숭아 향이 가득한 시원한 아이스티",
    "복숭아 아이스 티": "향긋한 복숭아 향이 가득한 시원한 아이스티",
    "복숭아 아이스티": "향긋한 복숭아 향이 가득한 시원한 아이스티",
    "허브티": "다양한 허브의 은은한 향과 맛을 즐길 수 있는 전통 차",
    "허브 티": "다양한 허브의 은은한 향과 맛을 즐길 수 있는 전통 차",
    "레몬에이드": "상큼한 레몬과 탄산의 청량함이 가득한 시원한 음료",
    "레몬 에이드": "상큼한 레몬과 탄산의 청량함이 가득한 시원한 음료"
  };

  return menuDescriptions[menuName] || '메뉴 설명 없음';
};

/**
 * 메뉴 아이템 기반 포괄적인 이미지 검출 로직
 */
export const extractImagePath = (item) => {
  if (item.name && getImagePathByName(item.name) !== '/images/default-menu-image.jpg') {
    return getImagePathByName(item.name);
  }
  
  if (item.imageUrl) {
    if (item.imageUrl.startsWith('http://') || item.imageUrl.startsWith('https://')) return item.imageUrl;
    return item.imageUrl.startsWith('/') ? item.imageUrl : `/${item.imageUrl}`;
  }
  
  if (item.image) {
    if (item.image.startsWith('http://') || item.image.startsWith('https://')) return item.image;
    return item.image.startsWith('/') ? item.image : `/${item.image}`;
  }
  
  return '/images/default-menu-image.jpg';
};
