// src/context/FSMContext.js - 장바구니 상태 관리 추가

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import websocketService from '../services/websocket';

// FSM 상태 컨텍스트 생성
const FSMContext = createContext();

// FSM 상태 제공자 컴포넌트
export const FSMProvider = ({ children }) => {
  // FSM 상태
  const [currentState, setCurrentState] = useState('start');
  const [stateMessage, setStateMessage] = useState('');
  const [stateContext, setStateContext] = useState({});
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(false);
  const connectionAttempts = useRef(0);
  const maxConnectionAttempts = 5;
  
  // UI 관련 상태
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedMenu, setSelectedMenu] = useState(null);
  const [selectedOptions, setSelectedOptions] = useState([]);
  const [cart, setCart] = useState([]);
  const [paymentMethod, setPaymentMethod] = useState('card');
  const [orderNumber, setOrderNumber] = useState('');
  
  // 상태 문자열 정규화 함수
  const normalizeState = (state) => {
    if (!state) return 'unknown';
    
    // 문자열인 경우 처리
    if (typeof state === 'string') {
      // "State.START" 형식인 경우 "START"만 추출
      if (state.includes('.')) {
        return state.split('.').pop().toLowerCase();
      }
      // 일반 문자열은 소문자로 변환
      return state.toLowerCase();
    }
    
    // 객체인 경우
    if (typeof state === 'object') {
      // toString 메서드가 있으면 사용하고 정규화
      if (state.toString && typeof state.toString === 'function') {
        const stateStr = state.toString();
        if (stateStr.includes('.')) {
          return stateStr.split('.').pop().toLowerCase();
        }
        return stateStr.toLowerCase();
      }
      
      // name 속성이 있으면 사용
      if (state.name) {
        return state.name.toLowerCase();
      }
    }
    
    // 기본값
    return 'unknown';
  };
  
  // FSM 상태 변경 함수
  const changeState = useCallback((state, context = {}) => {
    console.log(`상태 변경 요청: ${state}`, context);
    return websocketService.changeState(state, context);
  }, []);
  
  // 텍스트 처리 함수
  const processText = (text) => {
    console.log(`텍스트 처리 요청: ${text}`);
    return websocketService.processText(text);
  };
  

  
  // 연결 상태 확인 및 관리
  useEffect(() => {
    // 연결 상태 주기적 확인
    const connectionCheck = setInterval(() => {
      if (!isConnected && !connectionError) {
        // 연결이 안된 상태이고 에러도 없다면 자동 재연결 시도
        console.log('FSMProvider: 연결 상태 확인 중...');
        
        if (connectionAttempts.current < maxConnectionAttempts) {
          connectionAttempts.current += 1;
          console.log(`FSMProvider: 재연결 시도 (${connectionAttempts.current}/${maxConnectionAttempts})`);
          websocketService.connect();
        } else if (!connectionError) {
          console.log('FSMProvider: 최대 연결 시도 횟수 초과');
          setConnectionError(true);
        }
      }
    }, 5000); // 5초마다 연결 상태 확인
    
    return () => {
      clearInterval(connectionCheck);
    };
  }, [isConnected, connectionError]);
  
  // FSM 상태에 따른 UI 업데이트
  const updateUIForState = useCallback((state, context) => {
    console.log(`FSM 상태 ${state}에 따른 UI 업데이트:`, context);
    
    switch (state) {
      case 'start':
      case 'greeting':
        // 초기 화면
        setCurrentStep(1);
        break;
        
      case 'order_taking':
        // 메뉴 선택 화면
        setCurrentStep(1);
        
        // 선택된 메뉴 업데이트
        if (context.menu) {
          setSelectedMenu({
            id: context.menu,
            name: context.menu,
            price: 4500, // 기본 가격 (실제로는 API에서 가져와야 함)
            description: '',
            image: `/images/${context.menu.toLowerCase()}.jpg`
          });
        }
        break;
        
      case 'option_select':
        // 옵션 선택 화면
        setCurrentStep(2);
        
        // 선택된 옵션 업데이트
        if (context.options) {
          setSelectedOptions(context.options);
        }
        break;
        
      case 'order_confirm':
        // 주문 확인 화면
        setCurrentStep(3);
        
        // 장바구니 업데이트
        if (context.cart) {
          setCart(context.cart);
        }
        break;
        
      case 'payment':
        // 결제 화면
        setCurrentStep(3);
        
        // 결제 방법 업데이트
        if (context.payment) {
          setPaymentMethod(context.payment);
        }
        break;
        
      case 'farewell':
        // 결제 완료 화면
        setCurrentStep(4);
        
        // 주문 번호 생성 (실제로는 서버에서 받아야 함)
        if (context.orderNumber) {
          setOrderNumber(context.orderNumber);
        } else {
          setOrderNumber(`A-${Math.floor(Math.random() * 1000000).toString().padStart(6, '0')}`);
        }
        
        // 5초 후 초기 화면으로 돌아가기
        setTimeout(() => {
          changeState('start');
          setCart([]); // 장바구니 초기화
        }, 5000);
        break;
        
      default:
        console.warn(`알 수 없는 FSM 상태: ${state}`);
        break;
    }
  }, [changeState]);

  // 상태 업데이트 처리 함수
  const handleStateUpdate = useCallback(({ state, message, context }) => {
    try {
      const normalizedState = normalizeState(state);
      console.log(`상태 업데이트 수신: 원본=${state}, 정규화=${normalizedState}`);
      
      setCurrentState(normalizedState);
      setStateMessage(message || '');
      setStateContext(context || {});
      
      // UI 상태 업데이트
      updateUIForState(normalizedState, context || {});
    } catch (error) {
      console.error('상태 업데이트 처리 오류:', error);
    }
  }, [updateUIForState]);

  // 장바구니 관련 함수
  // 장바구니에 메뉴 추가
  const addToCart = (menu, options = []) => {
    // 옵션 가격 계산 (실제 구현에 따라 수정 필요)
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
    
    const optionPrice = options.reduce((total, option) => 
      total + (optionPrices[option] || 0), 0);

    const totalPrice = menu.price + optionPrice;

    const cartItem = {
      ...menu,
      options: [...options],
      totalPrice,
      quantity: 1
    };

    // 기존 장바구니에 추가 또는 수량 증가
    const existingItemIndex = cart.findIndex(
      item => item.id === cartItem.id && 
             JSON.stringify(item.options) === JSON.stringify(cartItem.options)
    );

    if (existingItemIndex > -1) {
      const updatedCart = [...cart];
      updatedCart[existingItemIndex].quantity += 1;
      updatedCart[existingItemIndex].totalPrice = 
        (updatedCart[existingItemIndex].price + optionPrice) * 
        updatedCart[existingItemIndex].quantity;
      setCart(updatedCart);
    } else {
      setCart([...cart, cartItem]);
    }
  };
  
  // 장바구니 비우기
  const clearCart = () => {
    setCart([]);
  };
  
  // WebSocket 연결 초기화 및 이벤트 리스너 설정
  useEffect(() => {
    console.log('FSMProvider 마운트 - WebSocket 연결 시도...');
    
    // 이벤트 리스너 등록
    const handleConnect = () => {
      console.log('WebSocket 연결됨');
      setIsConnected(true);
      setConnectionError(false);
      connectionAttempts.current = 0;
    };
    
    const handleDisconnect = () => {
      console.log('WebSocket 연결 해제됨');
      setIsConnected(false);
    };
    
    const handleError = (error) => {
      console.error('WebSocket 오류:', error);
      // setConnectionError(true); // 오류 발생해도 자동 재연결 시도하므로 에러 상태는 즉시 설정하지 않음
    };
    
    const handleMaxReconnectAttempts = () => {
      console.error('최대 재연결 시도 횟수 초과');
      setConnectionError(true);
    };
    
    const handleRawMessage = (rawMessage) => {
      console.log('원시 메시지 수신:', rawMessage);
      try {
        // 직접 파싱 시도
        const data = typeof rawMessage === 'string' ? JSON.parse(rawMessage) : rawMessage;
        
        // 상태 업데이트 처리
        if (data.type === 'state_update') {
          handleStateUpdate({
            state: data.state || 'unknown',
            message: data.message || '',
            context: data.context || {}
          });
        }
      } catch (error) {
        console.error('원시 메시지 파싱 오류:', error);
      }
    };
    
    // 추가: 장바구니 업데이트 처리 함수
    const handleCartUpdate = (cartData) => {
      console.log('장바구니 업데이트 수신:', cartData);
      
      // 장바구니 초기화 명령 처리
      if (cartData.operation === 'reset') {
        console.log('장바구니 초기화 요청');
        setCart([]);
        return;
      }
      
      if (cartData.operation === 'add' && cartData.items && cartData.items.length > 0) {
        // 기존 장바구니 항목과 중복 체크 (이름과 옵션 기준)
        const menuMap = {};
        
        // 새 항목 처리
        cartData.items.forEach(item => {
          const optionsKey = JSON.stringify(item.options || []);
          menuMap[`${item.name}|${optionsKey}`] = item;
        });
        
        // 기존 장바구니 처리
        setCart(prevCart => {
          const newCart = [...prevCart];
          let isUpdated = false;
          
          // 새 항목 각각에 대해 처리
          Object.values(menuMap).forEach(newItem => {
            // 같은 이름과 옵션을 가진 아이템 찾기
            const index = newCart.findIndex(item => 
              item.name === newItem.name && 
              JSON.stringify(item.options || []) === JSON.stringify(newItem.options || [])
            );
            
            if (index >= 0) {
              // 있으면 수량 업데이트
              newCart[index].quantity = newItem.quantity || 1;
              isUpdated = true;
            } else {
              // 없으면 새로 추가
              newCart.push({
                id: newItem.id || `item-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
                name: newItem.name,
                price: newItem.price,
                options: Array.isArray(newItem.options) ? newItem.options : [],
                optionsText: Array.isArray(newItem.options) ? newItem.options.join(', ') : '',
                quantity: newItem.quantity || 1,
                totalPrice: newItem.total || newItem.price
              });
              isUpdated = true;
            }
          });
          
          return isUpdated ? newCart : prevCart;
        });
      }
    };
    
    // 추가: 장바구니 업데이트 리스너 등록
    websocketService.on('cartUpdate', handleCartUpdate);
    // 이벤트 리스너 등록
    websocketService
      .on('stateUpdate', handleStateUpdate)
      .on('connect', handleConnect)
      .on('disconnect', handleDisconnect)
      .on('error', handleError)
      .on('rawMessage', handleRawMessage)
      .on('maxReconnectAttemptsReached', handleMaxReconnectAttempts);
    
    // 초기 연결 시도
    websocketService.connect();
    
    // 컴포넌트 언마운트 시 리스너 제거 및 연결 해제
    return () => {
      console.log('FSMProvider 언마운트 - 리스너 제거 및 연결 해제');
      
      websocketService
        .off('stateUpdate', handleStateUpdate)
        .off('connect', handleConnect)
        .off('disconnect', handleDisconnect)
        .off('error', handleError)
        .off('rawMessage', handleRawMessage)
        .off('maxReconnectAttemptsReached', handleMaxReconnectAttempts);
      
      // WebSocket 연결 해제
      websocketService.disconnect();
    };
  }, [handleStateUpdate]);
  
  // 컨텍스트 값
  const value = {
    // FSM 상태
    currentState,
    stateMessage,
    stateContext,
    isConnected,
    connectionError,
    
    // UI 상태
    currentStep,
    selectedMenu,
    selectedOptions,
    cart,
    paymentMethod,
    orderNumber,
    
    // 액션 함수
    changeState,
    processText,
    setSelectedMenu,
    setSelectedOptions,
    setCart,
    setPaymentMethod,
    addToCart,
    clearCart,
    
    // UI 업데이트 함수
    updateUIForState
  };
  
  return (
    <FSMContext.Provider value={value}>
      {children}
    </FSMContext.Provider>
  );
};

// FSM 훅
export const useFSM = () => {
  const context = useContext(FSMContext);
  
  if (!context) {
    throw new Error('useFSM must be used within an FSMProvider');
  }
  
  return context;
};