// src/components/MenuBoard.js
import React, { useState } from 'react';
import '../css/MenuBoard.css';
import MenuItemCard from './MenuItemCard';


const MenuBoard = ({ 
  menuItems, 
  categories, 
  selectedCategory, 
  onCategoryChange, 
  onAddToCart,
  loading
}) => {

  
  // 모달 상태 관리
  const [selectedItem, setSelectedItem] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedOptions, setSelectedOptions] = useState([]);
  
  // 가격 안전하게 포맷
  const formatPrice = (price) => {
  if (price === undefined || price === null || isNaN(price)) {
    return '₩0';
  }
  return `₩${price.toLocaleString()}`;
  };

  // 카테고리 탭 렌더링
  const renderCategoryTabs = () => {
    // 모든 카테고리 목록 생성 (전체 포함)
    const allCategories = ["전체", ...Object.keys(categories)];
    
    return (
      <div className="category-tabs">
        {allCategories.map((category) => (
          <button
            key={category}
            className={`category-tab ${selectedCategory === category ? 'active' : ''}`}
            onClick={() => onCategoryChange(category)}
          >
            {category}
          </button>
        ))}
      </div>
    );
  };
  
  // 카테고리별 메뉴 필터링
  const filteredMenuItems = selectedCategory === "전체" 
  ? menuItems 
  : menuItems.filter(item => 
      item.category === selectedCategory || 
      (Array.isArray(item.categories) && item.categories.includes(selectedCategory))
    );
  
  // 메뉴 아이템 클릭 핸들러
  const handleMenuItemClick = (item) => {
    setSelectedItem(item);
    setSelectedOptions([]);
    setShowModal(true);
  };
  
  // 모달 닫기 핸들러
  const handleCloseModal = () => {
    setShowModal(false);
    setSelectedItem(null);
    setSelectedOptions([]);
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
  
  // 장바구니에 추가
  const handleAddToCart = () => {
    if (selectedItem) {
      onAddToCart(selectedItem, selectedOptions);
      handleCloseModal();
    }
  };

  // 옵션 가격 계산
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
  
  // 옵션 총액 계산
  const calculateOptionsTotal = () => {
    return selectedOptions.reduce((total, option) => total + getOptionPrice(option), 0);
  };

  return (
    <div className="menu-board">
      <h1 className="menu-title">카페 메뉴</h1>
      
      {/* 카테고리 탭 */}
      {renderCategoryTabs()}
      
      {/* 메뉴 아이템 그리드 */}
      {loading ? (
        <div className="loading-indicator">메뉴를 불러오는 중...</div>
      ) : (
        <div className="menu-grid">
          {filteredMenuItems.length > 0 ? (
            filteredMenuItems.map((item) => (
              <MenuItemCard 
              key={item.id || item.name}  // id가 없으면 name 사용
              item={item}
              onClick={() => handleMenuItemClick(item)}
            />
            ))
          ) : (
            <div className="no-items-message">
              이 카테고리에 메뉴가 없습니다.
            </div>
          )}
        </div>
      )}
      
      {/* 메뉴 상세 모달 */}
      {showModal && selectedItem && (
        <div className="menu-modal-overlay" onClick={handleCloseModal}>
          <div className="menu-modal" onClick={(e) => e.stopPropagation()}>
            <button className="close-button" onClick={handleCloseModal}>×</button>
            
            <div className="modal-content">
              <div className="item-image-container">
                <img 
                  src={
                    selectedItem.image || 
                    selectedItem.imageUrl || 
                    '/images/americano.jpg'
                  } 
                  alt={selectedItem.name}
                  onError={(e) => {
                    e.target.src = '/images/americano.jpg';
                    e.target.onerror = null;
                  }}
                />
              </div>
              
              <div className="item-details">
                <h2>{selectedItem.name}</h2>
                <p className="item-description">{selectedItem.description}</p>
                <p className="item-price">{formatPrice(selectedItem.price || selectedItem.basePrice)}</p>
                
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
                
                <button className="add-to-cart-button" onClick={handleAddToCart}>
                  장바구니에 추가
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MenuBoard;