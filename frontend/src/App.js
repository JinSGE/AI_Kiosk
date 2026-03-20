// src/App.js - 메인 애플리케이션 컴포넌트
import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LandingPage from './components/LandingPage';
import KioskApp from './components/KioskApp';
import { FSMProvider } from './context/FSMContext';
import { createGlobalStyle } from 'styled-components';
import './App.css';

// 전역 스타일 설정
const GlobalStyle = createGlobalStyle`
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  
  body {
    font-family: 'Noto Sans KR', sans-serif;
    background-color: #f5f5f5;
    color: #333;
  }
`;

function App() {
  return (
    <>
      <GlobalStyle />
      <Router>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/kiosk" element={
            <FSMProvider>
              <KioskApp />
            </FSMProvider>
          } />
        </Routes>
      </Router>
    </>
  );
}

export default App;