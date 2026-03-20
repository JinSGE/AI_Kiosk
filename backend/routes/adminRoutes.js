// routes/adminRoutes.js - 관리자 인증 및 기능
const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const Admin = require('../models/Admin');

// 관리자 로그인
router.post('/login', async (req, res) => {
  try {
    // 사용자 이름으로 관리자 찾기
    const admin = await Admin.findOne({ username: req.body.username });
    if (!admin) {
      return res.status(401).json({ message: '유효하지 않은 사용자 이름 또는 비밀번호입니다.' });
    }
    
    // 비밀번호 확인
    const isMatch = await admin.comparePassword(req.body.password);
    if (!isMatch) {
      return res.status(401).json({ message: '유효하지 않은 사용자 이름 또는 비밀번호입니다.' });
    }
    
    // JWT 토큰 생성
    const token = jwt.sign(
      { id: admin._id, username: admin.username, role: admin.role },
      process.env.JWT_SECRET,
      { expiresIn: '1d' }
    );
    
    res.json({
      token,
      admin: {
        id: admin._id,
        username: admin.username,
        name: admin.name,
        role: admin.role
      }
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// 미들웨어: JWT 인증 확인
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ message: '인증 토큰이 필요합니다.' });
  }
  
  jwt.verify(token, process.env.JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ message: '인증 토큰이 유효하지 않습니다.' });
    }
    
    req.user = user;
    next();
  });
};

// 보호된 라우트: 관리자 정보 가져오기
router.get('/me', authenticateToken, async (req, res) => {
  try {
    const admin = await Admin.findById(req.user.id).select('-password');
    if (!admin) {
      return res.status(404).json({ message: '관리자를 찾을 수 없습니다.' });
    }
    
    res.json(admin);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// 보호된 라우트: 관리자 정보 업데이트
router.put('/me', authenticateToken, async (req, res) => {
  try {
    const updateData = {};
    
    if (req.body.name) updateData.name = req.body.name;
    
    // 비밀번호 변경 요청이 있는 경우
    if (req.body.password) {
      const salt = await bcrypt.genSalt(10);
      updateData.password = await bcrypt.hash(req.body.password, salt);
    }
    
    const admin = await Admin.findByIdAndUpdate(
      req.user.id,
      updateData,
      { new: true }
    ).select('-password');
    
    if (!admin) {
      return res.status(404).json({ message: '관리자를 찾을 수 없습니다.' });
    }
    
    res.json(admin);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

module.exports = {
  router,
  authenticateToken
};
