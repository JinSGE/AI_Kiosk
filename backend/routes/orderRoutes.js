// routes/orderRoutes.js - 주문 관련 라우트
const express = require('express');
const router = express.Router();
const Order = require('../models/Order');

// 주문 생성
router.post('/', async (req, res) => {
  // 주문번호 생성 (없을 경우)
  if (!req.body.orderNumber) {
    const date = new Date();
    const dateStr = date.getFullYear().toString().slice(-2) + 
                    String(date.getMonth() + 1).padStart(2, '0') + 
                    String(date.getDate()).padStart(2, '0');
    const random = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    req.body.orderNumber = `ORD-${dateStr}-${random}`;
  }

  const order = new Order({
    orderNumber: req.body.orderNumber,
    date: req.body.date || new Date(),
    items: req.body.items.map(item => ({
      name: item.name,
      price: item.price,
      quantity: item.quantity,
      options: item.options,
      optionsPrice: item.optionsPrice,
      image: item.image,
      category: item.category
    })),
    totalPrice: req.body.totalPrice,
    status: req.body.status || '접수'
  });

  try {
    const newOrder = await order.save();
    res.status(201).json(newOrder);
  } catch (err) {
    res.status(400).json({ message: err.message });
  }
});

// 모든 주문 가져오기
router.get('/', async (req, res) => {
  try {
    const query = {};
    
    // 상태별 필터링 지원
    if (req.query.status) {
      query.status = req.query.status;
    }
    
    // 날짜별 필터링 지원
    if (req.query.date) {
      const date = new Date(req.query.date);
      const nextDay = new Date(date);
      nextDay.setDate(date.getDate() + 1);
      
      query.date = {
        $gte: date,
        $lt: nextDay
      };
    }
    
    const orders = await Order.find(query).sort({ date: -1 });
    res.json(orders);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// 특정 주문 가져오기
router.get('/:id', async (req, res) => {
  try {
    const order = await Order.findById(req.params.id);
    if (!order) return res.status(404).json({ message: '주문을 찾을 수 없습니다' });
    res.json(order);
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// 주문 상태 업데이트
router.put('/:id', async (req, res) => {
  try {
    const order = await Order.findByIdAndUpdate(
      req.params.id,
      { status: req.body.status },
      { new: true }
    );
    
    if (!order) return res.status(404).json({ message: '주문을 찾을 수 없습니다' });
    res.json(order);
  } catch (err) {
    res.status(400).json({ message: err.message });
  }
});

// 결제 처리 엔드포인트 추가
router.post('/:id/payment', async (req, res) => {
  try {
    const orderId = req.params.id;
    const { paymentMethod } = req.body;
    
    // 주문 조회
    const order = await Order.findById(orderId);
    if (!order) {
      return res.status(404).json({ message: '주문을 찾을 수 없습니다' });
    }
    
    // 결제 처리 (간소화된 구현)
    order.status = '결제완료';
    order.paymentMethod = paymentMethod;
    order.paidAt = new Date();
    
    const updatedOrder = await order.save();
    
    res.json({
      success: true,
      message: '결제가 성공적으로 처리되었습니다',
      order: updatedOrder
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

// 주문 삭제 (관리자용)
router.delete('/:id', async (req, res) => {
  try {
    const order = await Order.findByIdAndDelete(req.params.id);
    if (!order) return res.status(404).json({ message: '주문을 찾을 수 없습니다' });
    res.json({ message: '주문이 삭제되었습니다' });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

module.exports = router;