// routes/menuRoutes.js - 메뉴 관련 라우트
const express = require('express');
const router = express.Router();
const MenuItem = require('../models/MenuItem');

// 모든 메뉴 아이템 가져오기
router.get('/', async (req, res) => {
  try {
    const query = {};
    
    // 카테고리별 필터링 지원
    if (req.query.category) {
      query.category = req.query.category;
    }
    
    console.log('메뉴 조회 쿼리:', query); // 쿼리 로깅 추가
    const menuItems = await MenuItem.find(query);
    
    console.log('조회된 메뉴 항목:', menuItems); // 결과 로깅 추가
    res.json(menuItems);
  } catch (err) {
    console.error('메뉴 조회 오류:', err); // 오류 로깅 추가
    res.status(500).json({ message: err.message });
  }
});

// ID로 메뉴 아이템 가져오기
router.get('/:id', async (req, res) => {
  try {
    const menuItem = await MenuItem.findOne({ id: req.params.id });
    if (!menuItem) return res.status(404).json({ message: '메뉴 아이템을 찾을 수 없습니다' });
    res.json(menuItem);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// 새 메뉴 아이템 추가 (관리자용)
router.post('/', async (req, res) => {
  const menuItem = new MenuItem({
    id: req.body.id,
    name: req.body.name,
    price: req.body.price,
    category: req.body.category,
    image: req.body.image,
    description: req.body.description
  });

  try {
    const newMenuItem = await menuItem.save();
    res.status(201).json(newMenuItem);
  } catch (err) {
    res.status(400).json({ message: err.message });
  }
});

// 메뉴 아이템 업데이트 (관리자용)
router.put('/:id', async (req, res) => {
  try {
    const menuItem = await MenuItem.findOneAndUpdate(
      { id: req.params.id },
      req.body,
      { new: true }
    );
    
    if (!menuItem) return res.status(404).json({ message: '메뉴 아이템을 찾을 수 없습니다' });
    res.json(menuItem);
  } catch (err) {
    res.status(400).json({ message: err.message });
  }
});

// 메뉴 아이템 삭제 (관리자용)
router.delete('/:id', async (req, res) => {
  try {
    const menuItem = await MenuItem.findOneAndDelete({ id: req.params.id });
    if (!menuItem) return res.status(404).json({ message: '메뉴 아이템을 찾을 수 없습니다' });
    res.json({ message: '메뉴 아이템이 삭제되었습니다' });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

module.exports = router;