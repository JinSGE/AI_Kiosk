// models/MenuItem.js - 메뉴 아이템 모델
const mongoose = require('mongoose');

const menuItemSchema = new mongoose.Schema({
  id: Number,
  name: { type: String, required: true },
  price: { type: Number, required: true },
  category: { type: String, required: true },
  image: { type: String, required: true },
  description: { type: String }
});

module.exports = mongoose.model('MenuItem', menuItemSchema);
