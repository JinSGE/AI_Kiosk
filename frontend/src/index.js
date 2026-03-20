// src/index.js - 애플리케이션 진입점
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

// 환경 변수 설정 (필요한 경우)
if (!window.process) {
  window.process = { env: {} };
}
window.process.env.REACT_APP_API_URL = 'http://localhost:5000/api/v1'
window.process.env.REACT_APP_WS_URL = 'ws://localhost:5000/ws'

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// 성능 측정을 위한 기본 설정
reportWebVitals();
