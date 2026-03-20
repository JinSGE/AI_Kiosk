// models/Order.js - 주문 모델
const mongoose = require('mongoose');

const orderSchema = new mongoose.Schema({
  orderNumber: { type: String, required: true, unique: true },
  date: { type: Date, default: Date.now },
  items: [{
    name: { type: String, required: true },
    price: { type: Number, required: true },
    quantity: { type: Number, required: true },
    options: [{
      id: String,
      name: String,
      price: Number,
      choice: String
    }],
    optionsPrice: String,
    image: String,
    category: String
  }],
  totalPrice: { type: Number, required: true },
  status: { type: String, default: '준비중' },
  paymentMethod: { type: String, enum: ['card', 'cash', 'mobile'], default: 'card' },
  paidAt: { type: Date }
});

module.exports = mongoose.model('Order', orderSchema);