// MenuItemCard.js
import React from 'react';
import '../css/MenuItemCard.css';

const MenuItemCard = ({ item, onClick }) => {
  
  // 가격 안전하게 포맷
  const formatPrice = () => {
  // item, price, basePrice가 undefined나 NaN인 경우 처리
  if (!item || 
      (item.price === undefined && item.basePrice === undefined) || 
      (isNaN(item.price) && isNaN(item.basePrice))) {
    return '₩0';
  }
  
  // price 또는 basePrice 중 존재하는 값 사용, 없으면 0
  const price = (!isNaN(item.price) && item.price !== null) ? item.price : 
               (!isNaN(item.basePrice) && item.basePrice !== null) ? item.basePrice : 0;
  
  return `₩${price.toLocaleString()}`;
  };
  
  const handleClick = () => {
    // 메뉴 클릭 시 옵션 정보와 함께 전달
    onClick(item);
  };
  
  return (
    <div className="menu-item-card" onClick={handleClick}>
      <div className="menu-image-container">
        <img 
          src={
            item.image || 
            item.imageUrl || 
            '/images/americano.jpg'
          } 
          alt={item.name || '메뉴 이미지'}
          onError={(e) => {
            e.target.src = '/images/americano.jpg';
            e.target.onerror = null;
          }}
        />
      </div>
      <div className="menu-item-info">
        <h3 className="menu-item-name">{item.name || '메뉴 이름 없음'}</h3>
        <p className="menu-item-price">{formatPrice()}</p>
      </div>
    </div>
  );
};

export default MenuItemCard;