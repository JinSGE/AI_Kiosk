// config/db.js
const mongoose = require('mongoose');

const connectDB = async () => {
  try {
    await mongoose.connect(process.env.MONGODB_URI);
    console.log('MongoDB에 성공적으로 연결되었습니다');
    
    // 연결 성공 시 초기 데이터 로드 실행
    const MenuItem = require('../models/MenuItem');
    const existingMenus = await MenuItem.find();
    
    if (existingMenus.length === 0) {
      const { createMenuItems } = require('../setup-menuItem');
      await createMenuItems(); 
    }
  } catch (error) {
    console.error('MongoDB 연결/초기화 오류:', error.message || error);
  }
};

module.exports = connectDB;
