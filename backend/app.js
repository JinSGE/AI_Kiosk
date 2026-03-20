// app.js
const express = require('express');
const cors = require('cors');
const path = require('path');
const axios = require('axios');

const app = express();

// axios 글로벌 인터셉터 설정
axios.interceptors.request.use(config => {
  console.log(`[API 요청] ${config.method.toUpperCase()} ${config.url}`);
  return config;
}, error => {
  console.error('[API 요청 오류]', error);
  return Promise.reject(error);
});

axios.interceptors.response.use(response => {
  console.log(`[API 응답] ${response.config.method.toUpperCase()} ${response.config.url}:`, response.status);
  return response;
}, error => {
  console.error('[API 응답 오류]', 
    error.response ? {
      status: error.response.status,
      data: error.response.data
    } : error.message
  );
  return Promise.reject(error);
});

// CORS 설정
app.use(cors({
  origin: '*',
  credentials: true
}));

// JSON 본문 파싱
app.use(express.json());

// API 라우트 설정
const menuRoutes = require('./routes/menuRoutes');
const orderRoutes = require('./routes/orderRoutes');
const { router: adminRoutes } = require('./routes/adminRoutes');

app.use('/api/menu', menuRoutes);
app.use('/api/orders', orderRoutes);
app.use('/api/admin', adminRoutes);

// 정적 파일 제공 (React 빌드 파일)
app.use(express.static(path.join(__dirname, './build')));
// 이미지 파일 경로 설정
app.use('/images', express.static(path.join(__dirname, '/images')));

// 모든 다른 GET 요청은 React 앱으로 라우팅
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, './build', 'index.html'));
});

module.exports = app;
