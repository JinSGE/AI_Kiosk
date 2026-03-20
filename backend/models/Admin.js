// models/Admin.js - 관리자 모델
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');

const adminSchema = new mongoose.Schema({
  username: { 
    type: String, 
    required: true, 
    unique: true 
  },
  password: { 
    type: String, 
    required: true 
  },
  name: { 
    type: String 
  },
  role: { 
    type: String, 
    default: 'admin' 
  },
  createdAt: { 
    type: Date, 
    default: Date.now 
  }
});

// 비밀번호 검증 메소드
adminSchema.methods.comparePassword = async function(candidatePassword) {
  return await bcrypt.compare(candidatePassword, this.password);
};

module.exports = mongoose.model('Admin', adminSchema);
