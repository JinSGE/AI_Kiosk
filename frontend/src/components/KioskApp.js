// KioskApp.js에 대화형 주문 옵션 추가 기능 구현

import React, { useEffect, useState } from 'react';
import { useFSM } from '../context/FSMContext';
import { useNavigate } from 'react-router-dom';
import '../css/KioskApp.css';
import MenuBoard from './MenuBoard';
import CartSidebar from './CartSidebar';
import { kioskAPI } from '../services/api';
import websocketService from '../services/websocket';
import { calculateOptionPrice, extractImagePath, getMenuDescription } from '../utils/helpers';

const KioskApp = () => {
  // navigate 훅 추가
  const navigate = useNavigate();
  
  // FSM 컨텍스트에서 필요한 상태 및 함수 가져오기
  const {
    isConnected,
    connectionError,
    cart,
    setCart
  } = useFSM();

  // 로컬 상태 정의
  const [categories] = useState({
    "커피": ["아메리카노", "카페 라떼", "카페 모카", "바닐라 라떼", "카라멜 마끼아또", "초코 라떼", "그린 라떼"],
    "티": ["복숭아아이스티", "허브티"],
    "에이드/주스": ["레몬에이드"]
  });
  const [menuItems, setMenuItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState("전체");
  
  // 현재 대화 컨텍스트 - 마지막으로 언급된 메뉴 추적
  const [orderContext, setOrderContext] = useState({
    lastMentionedMenu: null,  // 마지막으로 언급된 메뉴
    lastMenuIndex: -1,        // 마지막 메뉴의 장바구니 인덱스
    orderInProgress: false    // 주문 진행 중 플래그
  });
  
  // 주문 완료 처리 콜백 함수
  const handleOrderComplete = () => {
    // 3초 후 랜딩 페이지로 이동
    setTimeout(() => {
      navigate('/');
    }, 3000);
  };

  // 음성 주문 데이터 처리 - 대화형 주문 지원
  const handleVoiceOrderData = (orderData) => {
    console.log('음성 주문 데이터 수신:', orderData);
    
    // 주문 명령을 분석합니다 (주문 추가, 취소, 삭제, 옵션 추가 등)
    if (orderData && orderData.command) {
      switch (orderData.command) {
        case 'clear':
          // 장바구니 비우기
          setCart([]);
          setOrderContext({ lastMentionedMenu: null, lastMenuIndex: -1, orderInProgress: false });
          break;
          
        case 'remove':
          // 특정 메뉴 제거
          if (orderData.menuName) {
            removeMenuFromCart(orderData.menuName);
            // 제거된 메뉴가 마지막 언급 메뉴였으면 컨텍스트 초기화
            if (orderContext.lastMentionedMenu === orderData.menuName) {
              setOrderContext({ lastMentionedMenu: null, lastMenuIndex: -1, orderInProgress: false });
            }
          }
          break;
          
        case 'add':
          // 메뉴 추가
          if (orderData.items && orderData.items.length > 0) {
            const addedMenu = addOrUpdateCartItems(orderData.items);
            // 메뉴 추가 시 컨텍스트 업데이트
            if (addedMenu) {
              setOrderContext({
                lastMentionedMenu: addedMenu.name,
                lastMenuIndex: addedMenu.index,
                orderInProgress: true
              });
            }
          }
          break;

        case 'add_option':
          // 마지막 언급 메뉴에 옵션 추가
          if (orderData.options && orderData.options.length > 0) {
            addOptionsToLastMenu(orderData.options);
          }
          break;
          
        case 'complete':
          // 현재 주문 마무리
          setOrderContext({ lastMentionedMenu: null, lastMenuIndex: -1, orderInProgress: false });
          break;
          
        default:
          // 기본 동작은 장바구니 업데이트
          if (orderData.items && orderData.items.length > 0) {
            const addedMenu = addOrUpdateCartItems(orderData.items);
            if (addedMenu) {
              setOrderContext({
                lastMentionedMenu: addedMenu.name,
                lastMenuIndex: addedMenu.index,
                orderInProgress: true
              });
            }
          }
      }
    } else if (orderData && orderData.items && orderData.items.length > 0) {
      // command가 없어도 items가 있으면 추가 로직 실행
      const addedMenu = addOrUpdateCartItems(orderData.items);
      if (addedMenu) {
        setOrderContext({
          lastMentionedMenu: addedMenu.name,
          lastMenuIndex: addedMenu.index,
          orderInProgress: true
        });
      }
    } else if (orderData && orderData.options && orderData.options.length > 0) {
      // items는 없지만 options가 있는 경우 - 마지막 메뉴에 옵션 추가
      addOptionsToLastMenu(orderData.options);
    }
  };
  
  // 마지막으로 언급된 메뉴에 옵션 추가
  const addOptionsToLastMenu = (options) => {
    // 마지막 언급 메뉴가 없으면 무시
    if (orderContext.lastMenuIndex === -1 || !orderContext.lastMentionedMenu) {
      console.log('옵션 추가할 메뉴가 없습니다.');
      return;
    }
    
    setCart(prevCart => {
      // 메뉴가 없어졌을 경우 처리
      if (!prevCart[orderContext.lastMenuIndex]) {
        console.log('해당 메뉴가 장바구니에 없습니다.');
        return prevCart;
      }
      
      // 깊은 복사본 만들기
      const updatedCart = [...prevCart];
      const item = {...updatedCart[orderContext.lastMenuIndex]};
      
      // 기존 옵션 배열 가져오기
      const existingOptions = Array.isArray(item.options) ? [...item.options] : [];
      
      // 새 옵션 추가 (중복 방지)
      options.forEach(option => {
        if (!existingOptions.includes(option)) {
          existingOptions.push(option);
        }
      });
      
      // 옵션 업데이트
      item.options = existingOptions;
      
      // 가격 재계산
      const optionPrice = calculateOptionPrice(existingOptions);
      item.totalPrice = (item.price + optionPrice) * item.quantity;
      
      // 업데이트된 아이템 적용
      updatedCart[orderContext.lastMenuIndex] = item;
      
      console.log(`"${orderContext.lastMentionedMenu}"에 옵션 추가됨:`, options);
      
      return updatedCart;
    });
  };
  
  // 장바구니에서 특정 메뉴를 제거하는 함수
  const removeMenuFromCart = (menuName) => {
    setCart(prevCart => {
      // 주어진 메뉴명과 일치하는 아이템 필터링
      return prevCart.filter(item => 
        item.name.toLowerCase() !== menuName.toLowerCase()
      );
    });
  };
  
  // 장바구니에 아이템 추가 또는 업데이트 - 중복 처리 최적화
  const addOrUpdateCartItems = (newItems) => {
    let lastAddedMenu = null;
    
    const processedItems = {};

    // 메뉴 이름+옵션별로 수량 집계
    newItems.forEach(item => {
      const optionsKey = JSON.stringify(item.options || []);
      const key = `${item.name}|${optionsKey}`;
      
      if (!processedItems[key]) {
        processedItems[key] = {...item};
      } else {
        processedItems[key].quantity += (item.quantity || 1);
      }
    });

    setCart(prevCart => {
      const updatedCart = [...prevCart];
      let lastIndex = -1;

      // 각 처리된 항목에 대해
      Object.values(processedItems).forEach(newItem => {
        // 동일한 메뉴+옵션 항목 찾기
        const existingItemIndex = updatedCart.findIndex(item => 
          item.name === newItem.name && 
          JSON.stringify(item.options || []) === JSON.stringify(newItem.options || [])
        );
        
        if (existingItemIndex !== -1) {
          // 기존 항목이 있으면 수량 업데이트
          updatedCart[existingItemIndex].quantity = newItem.quantity;
          lastIndex = existingItemIndex;
        } else {
          // 새 항목 추가
          updatedCart.push(newItem);
          lastIndex = updatedCart.length - 1;
        }
      });
      
      // 마지막 처리된 메뉴 정보 업데이트
      if (lastIndex !== -1) {
        lastAddedMenu = {
          name: updatedCart[lastIndex].name,
          index: lastIndex
        };
      }
      
      return updatedCart;
    });
    
    return lastAddedMenu;
  };
  
  // 옵션 가격 계산 함수 - helpers.js 사용
  // 컴포넌트 마운트 시 초기화 및 웹소켓 설정
  useEffect(() => {
    // 키오스크 초기화
    const initializeKiosk = async () => {
      try {
        await kioskAPI.initialize();
        
        // 웹소켓 연결 설정
        if (!websocketService.isConnected()) {
          websocketService.connect();
        }
      } catch (error) {
        console.error('키오스크 초기화 오류:', error);
      }
    };
    
    initializeKiosk();

    // 웹소켓 이벤트 리스너 설정
    const handleCartUpdate = (data) => {
      console.log('장바구니 업데이트 수신:', data);
      // 장바구니 업데이트 처리 함수 호출
      handleVoiceOrderData(data);
    };

    // 메뉴 로딩 처리 함수 추가 (여기에 새로운 함수 추가)
    const handleMenuLoading = (data) => {
  console.log('메뉴 로딩 신호 수신:', data);
  
  // 서버에서 받은 메뉴 데이터가 있으면 처리
  if (data && data.menu_data && Object.keys(data.menu_data).length > 0) {
    console.log('서버에서 메뉴 데이터 수신:', data.menu_data);
    
    // 메뉴 데이터가 있는 경우, 상태 업데이트
    if (data.menu_data.menus && Array.isArray(data.menu_data.menus)) {
      // 메뉴 데이터 유효성 검사 및 정제
      const processedMenus = data.menu_data.menus.map(menu => {
        // 가격 필드 검증 및 기본값 설정
        let price = 0;
        if (typeof menu.basePrice === 'number' && !isNaN(menu.basePrice)) {
          price = menu.basePrice;
        } else if (typeof menu.price === 'number' && !isNaN(menu.price)) {
          price = menu.price;
        } else {
          // 기본 가격 매핑
          const defaultPrices = {
            "아메리카노": 4500,
            "카페 라떼": 5000,
            "카페 모카": 5500,
            "바닐라 라떼": 5500,
            "카라멜 마끼아또": 5800,
            "초코 라떼": 5000,
            "그린 라떼": 5000,
            "복숭아 아이스 티": 5200,
            "허브 티": 5000,
            "레몬 에이드": 5500
          };
          price = defaultPrices[menu.name] || 4500;
          console.log(`메뉴 "${menu.name}"에 가격 정보가 없어 기본값 ${price}원을 사용합니다.`);
        }
        
        return {
          ...menu,
          price: price, // 검증된 가격으로 교체
          basePrice: price
        };
      });
      
      setMenuItems(processedMenus);
      setLoading(false);
    }
  }
  
  // 메뉴 로딩 완료 알림
  websocketService.send(JSON.stringify({
    type: "ui_ready",
    component: "menu",
    status: "loaded"
  }));
};
    // 웹소켓 리스너 추가
    websocketService.on('cartUpdate', handleCartUpdate);
    websocketService.on('load_menu', handleMenuLoading); // 새로 추가

    return () => {
      // 이벤트 리스너 정리
      websocketService.off('cartUpdate', handleCartUpdate);
      websocketService.off('load_menu', handleMenuLoading); // 새로 추가
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuItems, orderContext]);

  // 컴포넌트 마운트 시 메뉴 데이터 가져오기
  useEffect(() => {
    const fetchMenuItems = async () => {
      try {
        setLoading(true);
        console.log('메뉴 데이터 요청 중...');
        const data = await kioskAPI.getAllMenuItems();
        console.log('API 응답 데이터:', data);
        
        // 데이터 형식 검증 및 기본값 설정
        const processedMenuItems = data.map(item => {
          // 가격 데이터 안전하게 처리
          let price = 0;
          if (typeof item.basePrice === 'number' && !isNaN(item.basePrice)) {
            price = item.basePrice;
          } else if (typeof item.price === 'number' && !isNaN(item.price)) {
            price = item.price;
          } else {
            // 기본 가격 매핑 (메뉴별 기본 가격)
            const defaultPrices = {
              "아메리카노": 4500,
              "카페라떼": 5000,
              "카페모카": 5500,
              "바닐라 라떼": 5500,
              "카라멜 마끼아또": 5800,
              "초코라떼": 5000,
              "녹차라떼": 5000,
              "복숭아 아이스 티": 5200,
              "허브 티": 5000,
              "레몬 에이드": 5500
            };
            price = defaultPrices[item.name] || 4500; // 기본값 4500
            console.log(`메뉴 "${item.name}"에 가격 정보가 없어 기본값 ${price}원을 사용합니다.`);
          }
          const getCategoryForMenu = (menuName) => {
            if (!menuName) return '기타';
            
            // 커피 카테고리
            const coffeeItems = ["아메리카노", "카페 라떼", "카페 모카", "바닐라 라떼", "카라멜 마끼아또", "초코 라떼", "그린 라떼"];
            if (coffeeItems.includes(menuName)) return "커피";
            
            // 티 카테고리
            const teaItems = ["복숭아 아이스 티", "허브 티"];
            if (teaItems.includes(menuName)) return "티";
            
            // 에이드/주스 카테고리
            const adeItems = ["레몬 에이드"];
            if (adeItems.includes(menuName)) return "에이드/주스";
            
            // 카테고리 로직 끝
          };
          return {
            id: item.id || item.name || Math.random().toString(36).substring(2, 9),
            name: item.name || '메뉴 이름 없음',
            price: price, // 안전하게 처리된 가격
            description: item.description || getMenuDescription(item.name),
            image: extractImagePath(item),
            category: item.category || getCategoryForMenu(item.name) || '기타',
            options: item.options || {}
          };
        });
  
        console.log('처리된 메뉴 데이터:', processedMenuItems);
        setMenuItems(processedMenuItems);
      } catch (err) {
        console.error('메뉴 데이터를 가져오는 중 오류 발생:', err);
      } finally {
        setLoading(false);
      }
    };
  
    fetchMenuItems();
  }, [categories]); // categories 의존성 추가

  // 장바구니에 메뉴 추가 (UI에서 메뉴 선택 시)
  const addToCart = (menu, options = []) => {
    // 개선된 addOrUpdateCartItems 함수 사용
    const addedMenu = addOrUpdateCartItems([{
      ...menu,
      options: options,
      quantity: 1
    }]);
    
    // 주문 컨텍스트 업데이트
    if (addedMenu) {
      setOrderContext({
        lastMentionedMenu: addedMenu.name,
        lastMenuIndex: addedMenu.index,
        orderInProgress: true
      });
    }
  };
  
  // 카테고리 변경 처리
  const handleCategoryChange = (category) => {
    setSelectedCategory(category);
  };
  
  // 웹소켓 연결 상태 표시
  const renderConnectionStatus = () => {
    return (
      <div className="connection-status">
        {isConnected ? (
          <span className="connected">연결됨</span>
        ) : (
          <span className="disconnected">
            {connectionError ? '연결 오류' : '연결 중...'}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="kiosk-container">
      {/* 배경 이미지 */}
      <div className="kiosk-background"></div>
      
      {/* 웹소켓 연결 상태 표시 */}
      {renderConnectionStatus()}
      
      {/* 메인 콘텐츠 영역 - 세로 배치로 메뉴판과 장바구니 배치 */}
      <div className="kiosk-content vertical-layout">
        {/* 메뉴판 영역 (상단) */}
        <div className="menu-board-container">
          <MenuBoard 
            menuItems={menuItems}
            categories={categories}
            selectedCategory={selectedCategory}
            onCategoryChange={handleCategoryChange}
            onAddToCart={addToCart}
            loading={loading}
          />
        </div>
        
        {/* 장바구니 영역 (하단) */}
        <div className="cart-container">
          <CartSidebar 
            cart={cart}
            setCart={setCart}
            show={true} // 항상 표시
            isFixed={true} // 고정 모드 추가
            onOrderComplete={handleOrderComplete} // 주문 완료 콜백 전달
          />
        </div>
      </div>
    </div>
  );
};

export default KioskApp;