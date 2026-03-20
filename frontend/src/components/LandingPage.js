// src/components/LandingPage.js - 랜딩 페이지 컴포넌트
import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../css/LandingPage.css';

function LandingPage() {
  const navigate = useNavigate();

  const handleOrderClick = () => {
    // state를 포함하여 kiosk 페이지로 이동
    navigate('/kiosk', { state: { fromLanding: true } });
  };

  return (
    <div className="landing-container">
      <div className="landing-content">
        <div className="title-area">
          <h1 className="main-title">AI 카페 키오스크</h1>
        </div>
        
        <div className="button-area">
          <button className="order-button" onClick={handleOrderClick}>
            주문하기
          </button>
        </div>
      </div>
    </div>
  );
}

export default LandingPage;