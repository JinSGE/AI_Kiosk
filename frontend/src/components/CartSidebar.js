// CartSidebar.js 수정 - 한 줄 레이아웃 최적화 및 음성 주문 옵션창 개선

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import '../css/CartSidebar.css';
import websocketService from '../services/websocket'; // WebSocket 서비스 import 추가
import { getImagePathByName, getMenuDescription, calculateOptionPrice } from '../utils/helpers';

const CartSidebar = ({ cart, setCart, show, onClose, isFixed = false, onOrderComplete = null }) => {
  const [paymentMethod, setPaymentMethod] = useState('card');
  const [orderCompleted, setOrderCompleted] = useState(false);
  const [orderNumber, setOrderNumber] = useState('');
  const [showOptionModal, setShowOptionModal] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedOptions, setSelectedOptions] = useState([]);
  const [selectedItemIndex, setSelectedItemIndex] = useState(-1);
  
  // 디버깅: 장바구니 내용 로그
  useEffect(() => {
    console.log("현재 장바구니 상태:", cart);
  }, [cart]);

  const clearCart = useCallback(() => {
    setCart([]);
  }, [setCart]);
  
  // WebSocket 이벤트 리스너 추가
  useEffect(() => {
    // 장바구니 업데이트 이벤트 핸들러
    const handleCartUpdate = (data) => {
      console.log("WebSocket 장바구니 업데이트:", data);
      
      // 타입이 cart_update가 아니거나 items가 없으면 무시
      if (!data.items || !Array.isArray(data.items)) return;
  
      // 초기화 명령 처리
      if (data.operation === 'reset') {
        console.log("장바구니 초기화 명령 수신");
        clearCart();
        return;
      }

      // 메뉴 이름 기반 맵 생성 (메뉴 이름:수량)
      const menuNameToQuantityMap = {};
      data.items.forEach(item => {
        const key = `${item.name}|${JSON.stringify(item.options || [])}`;
        menuNameToQuantityMap[key] = (menuNameToQuantityMap[key] || 0) + item.quantity;
      });
      
      // 기존 장바구니 항목 확인
      if (cart.length > 0) {
        // 이미 장바구니에 같은 메뉴가 있는지 확인
        const newCart = [...cart];
        let updated = false;
        
        // 각 메뉴 이름에 대해 이미 장바구니에 있는지 확인
        Object.keys(menuNameToQuantityMap).forEach(key => {
          const [name, optionsStr] = key.split('|');
          const quantity = menuNameToQuantityMap[key];
          
          // 같은 이름과 옵션을 가진 항목 찾기
          const existingItemIndex = newCart.findIndex(item => 
            item.name === name && 
            JSON.stringify(item.options || []) === optionsStr
          );
          
          if (existingItemIndex !== -1) {
            // 이미 있으면 수량만 업데이트
            newCart[existingItemIndex].quantity = quantity;
            updated = true;
          } else {
            // 없으면 새 항목으로 추가 (data.items에서 해당 항목 찾기)
            const newItem = data.items.find(item => 
              item.name === name && 
              JSON.stringify(item.options || []) === optionsStr
            );
            
            if (newItem) {
              // 추가: 메뉴 이미지 및 설명 보강
              const enhancedItem = {
                ...newItem,
                image: newItem.image || getImagePathByName(newItem.name),
                description: newItem.description || getMenuDescription(newItem.name),
                quantity: quantity
              };
              newCart.push(enhancedItem);
              updated = true;
            }
          }
        });
        
        if (updated) {
          setCart(newCart);
        }
      } else {
        // 장바구니가 비어있으면 메뉴 정보 보강 후 설정
        const enhancedItems = data.items.map(item => ({
          ...item,
          image: item.image || getImagePathByName(item.name),
          description: item.description || getMenuDescription(item.name)
        }));
        setCart(enhancedItems);
      }
    };
    
    // 이벤트 리스너 등록
    websocketService.on('cartUpdate', handleCartUpdate);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      websocketService.off('cartUpdate', handleCartUpdate);
    };
  }, [cart, clearCart, setCart]);

  const updateQuantity = (index, newQuantity) => {
    if (newQuantity < 1) {
      // 수량이 0이하면 항목 삭제
      removeItem(index);
    } else {
      const updatedCart = [...cart];
      updatedCart[index].quantity = newQuantity;
      
      // 옵션 가격 계산
      const optionPrice = calculateOptionPrice(updatedCart[index].options || []);
      
      // totalPrice 업데이트
      updatedCart[index].totalPrice = (updatedCart[index].price + optionPrice) * newQuantity;
      
      setCart(updatedCart);
    }
  };
  
  // 항목 삭제
  const removeItem = (index) => {
    const updatedCart = [...cart];
    updatedCart.splice(index, 1);
    setCart(updatedCart);
  };
  
  // 총액 계산
  const calculateTotal = () => {
    return cart.reduce((total, item) => {
      // 이미 totalPrice가 있고 유효한 숫자면 그걸 사용
      if (typeof item.totalPrice === 'number' && !isNaN(item.totalPrice)) {
        return total + item.totalPrice;
      }
      
      // item.price가 없거나 NaN이면 0으로 설정
      const itemPrice = (typeof item.price === 'number' && !isNaN(item.price)) ? 
                       item.price : 0;
      
      // 옵션 가격 계산
      const optionPrice = calculateOptionPrice(item.options || []);
      
      // 수량 확인 (수량이 없거나 NaN이면 1로 설정)
      const quantity = (typeof item.quantity === 'number' && !isNaN(item.quantity)) ? 
                     item.quantity : 1;
      
      return total + ((itemPrice + optionPrice) * quantity);
    }, 0);
  };
  
  // 장바구니에서 결제하기 버튼 클릭 핸들러
  const handlePayment = async () => {
    try {
      console.log('결제 시작:', {
        cart,
        paymentMethod,
        total: calculateTotal()
      });
      
      // 결제 정보 준비
      const paymentData = {
        items: cart.map(item => ({
          name: item.name,
          price: item.price,
          quantity: item.quantity,
          options: Array.isArray(item.options) ? item.options : [],
          image: item.image || getImagePathByName(item.name),
          total: item.totalPrice || ((item.price + calculateOptionPrice(item.options || [])) * item.quantity)
        })),
        totalPrice: calculateTotal(),
        payment_method: paymentMethod
      };
      
      // 웹소켓을 통해 결제 완료 메시지 전송
      if (websocketService.isConnected()) {
        console.log('웹소켓을 통해 결제 메시지 전송:', paymentData);
        
        // 메시지 전송
        websocketService.send({
          action: 'payment_complete',
          payment_data: paymentData,
          timestamp: new Date().toISOString()
        });
        
        // 결제 완료 상태로 UI 업데이트
        setOrderCompleted(true);
        setOrderNumber(`A-${Math.floor(Math.random() * 1000000).toString().padStart(6, '0')}`);
        
        // 주문 완료 콜백 호출 (있는 경우)
        if (onOrderComplete && typeof onOrderComplete === 'function') {
          // 약간의 지연 후 콜백 호출 (주문 완료 화면을 잠시 보여주기 위해)
          setTimeout(() => {
            onOrderComplete(orderNumber);
          }, 2000);
        } else {
          // 콜백이 없는 경우 기존 로직 - 5초 후 장바구니 초기화
          setTimeout(() => {
            setCart([]);
            setOrderCompleted(false);
            if (!isFixed && onClose) {
              onClose();
            }
          }, 5000);
        }
      } else {
        // 웹소켓 연결이 없는 경우 기존 API 호출 방식으로 폴백
        console.warn('웹소켓 연결이 없어 API로 결제를 진행합니다.');
        
        // 주문 API 호출
        const API_BASE_URL = window.process?.env?.REACT_APP_API_URL || 'http://192.168.45.193:5000/api/v1';
        const response = await axios.post(`${API_BASE_URL}/orders`, paymentData);
        
        // 주문번호 설정
        const newOrderNumber = response.data.orderNumber || `A-${Math.floor(Math.random() * 1000000).toString().padStart(6, '0')}`;
        setOrderNumber(newOrderNumber);
        setOrderCompleted(true);
        
        // 5초 후 장바구니 초기화 (폴백 로직)
        setTimeout(() => {
          setCart([]);
          setOrderCompleted(false);
          if (!isFixed && onClose) {
            onClose();
          }
        }, 5000);
      }
    } catch (error) {
      console.error('결제 처리 중 오류 발생:', error);
      alert('결제 처리 중 오류가 발생했습니다.');
    }
  };
  
  // 옵션 텍스트 표시 준비 - 최대 길이 제한
  const getOptionsDisplay = (options) => {
    if (!options) return null;
    
    // 옵션이 객체 배열인 경우 (백엔드에서 온 형식)
    if (Array.isArray(options) && options.length > 0 && typeof options[0] === 'object') {
      const optionNames = options.map(opt => opt.name);
      return formatOptionText(optionNames.join(', '));
    }
    
    // 옵션이 문자열 배열인 경우 (프론트엔드에서 선택한 형식)
    const optArray = Array.isArray(options) ? options : 
                    (typeof options === 'string' ? [options] : []);
    
    if (optArray.length === 0) return null;
    
    return formatOptionText(optArray.join(', '));
  };
  
  // 옵션 텍스트 길이 제한 함수
  const formatOptionText = (text) => {
    if (!text) return '';
    
    // 15자 이상이면 줄임표 추가
    if (text.length > 15) {
      return text.substring(0, 12) + '...';
    }
    return text;
  };
  
  // 가격 표시 포맷
  const formatPrice = (price) => {
    return `₩${price.toLocaleString()}`;
  };
  
  // 옵션 변경 모달 열기 - 개선된 버전
  const handleOptionClick = (item, index) => {
    // 메뉴 정보 보강 - 이미지와 설명 정보 확인
    const enhancedItem = {
      ...item,
      // 이미지가 없는 경우 메뉴 이름으로 기본 이미지 경로 구성
      image: item.image || getImagePathByName(item.name),
      // 설명이 없는 경우 기본 설명 추가
      description: item.description || getMenuDescription(item.name)
    };
    
    setSelectedItem(enhancedItem);
    setSelectedOptions(item.options || []);
    setSelectedItemIndex(index);
    setShowOptionModal(true);
  };
  
  // 옵션 선택 처리
  const handleOptionSelect = (optionType, option) => {
    const newOptions = [...selectedOptions];
    
    // 옵션 타입에 따라 다른 처리
    if (optionType === 'temperature' || optionType === 'size') {
      // 온도나 크기는 중복 선택 불가능 (기존 선택 제거 후 새로 선택)
      const filteredOptions = newOptions.filter(item => {
        // 온도 옵션인 경우 Hot, Ice를 모두 제거
        if (optionType === 'temperature' && (item === 'Hot' || item === 'Ice')) {
          return false;
        }
        // 크기 옵션인 경우 Small, Regular, Large를 모두 제거
        if (optionType === 'size' && (item === 'Small' || item === 'Regular' || item === 'Large')) {
          return false;
        }
        return true;
      });
      
      // 새 옵션 추가
      filteredOptions.push(option);
      setSelectedOptions(filteredOptions);
    } else {
      // 추가 옵션은 토글 방식 (있으면 제거, 없으면 추가)
      const index = newOptions.indexOf(option);
      if (index === -1) {
        newOptions.push(option);
      } else {
        newOptions.splice(index, 1);
      }
      setSelectedOptions(newOptions);
    }
  };
  
  // 옵션 변경 적용 - 개선된 버전
  const handleApplyOptions = () => {
    if (selectedItem && selectedItemIndex !== -1) {
      const updatedCart = [...cart];
      
      // 옵션 가격 계산
      const optionPrice = calculateOptionPrice(selectedOptions);
      
      // 항목 업데이트 (메뉴 정보 보존 및 강화)
      updatedCart[selectedItemIndex] = {
        ...updatedCart[selectedItemIndex],
        options: selectedOptions,
        // 이미지 및 설명 유지
        image: selectedItem.image || updatedCart[selectedItemIndex].image || getImagePathByName(selectedItem.name),
        description: selectedItem.description || updatedCart[selectedItemIndex].description || getMenuDescription(selectedItem.name),
        totalPrice: (updatedCart[selectedItemIndex].price + optionPrice) * updatedCart[selectedItemIndex].quantity
      };
      
      setCart(updatedCart);
      setShowOptionModal(false);
      setSelectedItem(null);
      setSelectedOptions([]);
      setSelectedItemIndex(-1);
    }
  };
  
  // 옵션 모달 닫기
  const handleCloseOptionModal = () => {
    setShowOptionModal(false);
    setSelectedItem(null);
    setSelectedOptions([]);
    setSelectedItemIndex(-1);
  };
  
  // 옵션 가격 계산 (옵션 모달용)
  const getOptionPrice = (option) => {
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
    
    return optionPrices[option] || 0;
  };
  
  // 옵션 총액 계산 (옵션 모달용)
  const calculateOptionsTotal = () => {
    return selectedOptions.reduce((total, option) => total + getOptionPrice(option), 0);
  };
  
  // 고정 모드가 아니고 show가 false면 렌더링하지 않음
  if (!isFixed && !show) return null;

return (
    <div className={`cart-sidebar ${isFixed ? 'fixed' : ''} ${show || isFixed ? 'show' : ''}`}>
      <div className="cart-header">
        <h2>{orderCompleted ? '주문 완료' : '장바구니'}</h2>
        {!isFixed && <button className="close-button" onClick={onClose}>×</button>}
      </div>
      
      {/* 주문 완료 화면 */}
      {orderCompleted ? (
        <div className="order-complete">
          <div className="success-icon">✓</div>
          <h3>주문이 완료되었습니다!</h3>
          <p>주문번호: <strong>{orderNumber}</strong></p>
          <p>잠시만 기다려주시면 음료를 준비해 드리겠습니다.</p>
          <p className="thank-you">이용해 주셔서 감사합니다.</p>
          <p className="auto-return">잠시 후 메인 화면으로 이동합니다</p>
        </div>
      ) : (
        <>
          {/* 장바구니 아이템 */}
          <div className="cart-items">
            {cart.length === 0 ? (
              <div className="empty-cart">장바구니가 비어있습니다</div>
            ) : (
              cart.map((item, index) => {
                const optionsDisplay = getOptionsDisplay(item.options);
                
                return (
                  <div key={index} className="cart-item">
                    <div className="item-info">
                      <h4>{item.name}</h4>
                      {optionsDisplay && (
                        <span className="item-options">({optionsDisplay})</span>
                      )}
                      <span className="item-price">
                        {formatPrice(
                          item.totalPrice || 
                          ((item.price + calculateOptionPrice(item.options || [])) * item.quantity)
                        )}
                      </span>
                    </div>
                    <div className="item-controls">
                      <button 
                        className="quantity-btn minus"
                        onClick={() => updateQuantity(index, item.quantity - 1)}
                      >
                        -
                      </button>
                      <span className="quantity">{item.quantity}</span>
                      <button 
                        className="quantity-btn plus"
                        onClick={() => updateQuantity(index, item.quantity + 1)}
                      >
                        +
                      </button>
                      <button 
                        className="option-btn"
                        onClick={() => handleOptionClick(item, index)}
                      >
                        옵션
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
          
          {/* 결제 영역 */}
          {cart.length > 0 && (
            <div className="payment-section">
              <div className="total-amount">
                <span>총 결제금액</span>
                <span>{formatPrice(calculateTotal())}</span>
              </div>
              
              <div className="payment-methods">
                <div className="payment-option">
                  <input 
                    type="radio" 
                    id="card-payment" 
                    name="payment" 
                    value="card"
                    checked={paymentMethod === 'card'}
                    onChange={() => setPaymentMethod('card')}
                  />
                  <label htmlFor="card-payment">신용카드</label>
                </div>
                
                <div className="payment-option">
                  <input 
                    type="radio" 
                    id="mobile-payment" 
                    name="payment" 
                    value="mobile"
                    checked={paymentMethod === 'mobile'}
                    onChange={() => setPaymentMethod('mobile')}
                  />
                  <label htmlFor="mobile-payment">모바일 결제</label>
                </div>
              </div>
              
              <div className="action-buttons">
                <button className="clear-cart-btn" onClick={clearCart}>
                  장바구니 비우기
                </button>
                <button className="payment-btn" onClick={handlePayment}>
                  결제하기
                </button>
              </div>
            </div>
          )}
        </>
      )}
      
      {/* 옵션 변경 모달 */}
      {showOptionModal && selectedItem && (
        <div className="menu-modal-overlay" onClick={handleCloseOptionModal}>
          <div className="menu-modal" onClick={(e) => e.stopPropagation()}>
            <button className="close-button" onClick={handleCloseOptionModal}>×</button>
            
            <div className="modal-content">
              <div className="item-image-container">
                <img 
                  src={
                    selectedItem.image || 
                    selectedItem.imageUrl || 
                    getImagePathByName(selectedItem.name) ||
                    '/images/default-menu-image.jpg'
                  } 
                  alt={selectedItem.name}
                  onError={(e) => {
                    e.target.src = '/images/default-menu-image.jpg';
                    e.target.onerror = null;
                  }}
                />
              </div>
              
              <div className="item-details">
                <h2>{selectedItem.name}</h2>
                <p className="item-description">{selectedItem.description || getMenuDescription(selectedItem.name) || '상세 설명 없음'}</p>
                <p className="item-price">
                  {formatPrice(selectedItem.price || selectedItem.basePrice || 0)}
                </p>
                
                <div className="options-container">
                  <h3>옵션 선택</h3>
                  
                  <div className="option-group">
                    <h4>온도</h4>
                    <div className="options">
                      <button 
                        className={`option-button ${selectedOptions.includes('Hot') ? 'selected' : ''}`} 
                        onClick={() => handleOptionSelect('temperature', 'Hot')}
                      >
                        Hot
                      </button>
                      <button 
                        className={`option-button ${selectedOptions.includes('Ice') ? 'selected' : ''}`}
                        onClick={() => handleOptionSelect('temperature', 'Ice')}
                      >
                        Ice
                      </button>
                    </div>
                  </div>
                  
                  <div className="option-group">
                    <h4>크기</h4>
                    <div className="options">
                      <button 
                        className={`option-button ${selectedOptions.includes('Small') ? 'selected' : ''}`}
                        onClick={() => handleOptionSelect('size', 'Small')}
                      >
                        Small (+0원)
                      </button>
                      <button 
                        className={`option-button ${selectedOptions.includes('Regular') ? 'selected' : ''}`}
                        onClick={() => handleOptionSelect('size', 'Regular')}
                      >
                        Regular (+500원)
                      </button>
                      <button 
                        className={`option-button ${selectedOptions.includes('Large') ? 'selected' : ''}`}
                        onClick={() => handleOptionSelect('size','Large')}
                      >
                        Large (+1,000원)
                      </button>
                    </div>
                  </div>
                  
                  <div className="option-group">
                    <h4>추가 옵션</h4>
                    <div className="options">
                      <button 
                        className={`option-button ${selectedOptions.includes('샷 추가') ? 'selected' : ''}`}
                        onClick={() => handleOptionSelect('extra', '샷 추가')}
                      >
                        샷 추가 (+500원)
                      </button>
                      <button 
                        className={`option-button ${selectedOptions.includes('시럽 추가') ? 'selected' : ''}`}
                        onClick={() => handleOptionSelect('extra', '시럽 추가')}
                      >
                        시럽 추가 (+300원)
                      </button>
                      <button 
                        className={`option-button ${selectedOptions.includes('휘핑크림 추가') ? 'selected' : ''}`}
                        onClick={() => handleOptionSelect('extra', '휘핑크림 추가')}
                      >
                        휘핑크림 추가 (+500원)
                      </button>
                    </div>
                  </div>
                </div>
                
                <div className="total-price">
                  <h4>총 가격</h4>
                  <p>
                    {formatPrice(
                      (selectedItem.price || selectedItem.basePrice || 0) + 
                      calculateOptionsTotal()
                    )}
                  </p>
                </div>
                
                <button className="add-to-cart-button" onClick={handleApplyOptions}>
                  옵션 적용하기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CartSidebar;