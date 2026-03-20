// src/services/api.js - API 통신 서비스
import axios from 'axios';

const API_BASE_URL = window.process?.env?.REACT_APP_API_URL || 'http://localhost:5000/api/v1';

const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

axiosInstance.interceptors.request.use(
  config => {
    console.log(`[API Request] ${config.method.toUpperCase()} ${config.url}`, config.data);
    return config;
  },
  error => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

axiosInstance.interceptors.response.use(
  response => {
    console.log(`[API Response] ${response.config.method.toUpperCase()} ${response.config.url}`, response.data);
    return response;
  },
  error => {
    console.error('[API Response Error]', error.response || error);
    return Promise.reject(error);
  }
);

// api.js - API 로그 개선을 위한 추가 코드
axiosInstance.interceptors.request.use(
  config => {
    // 주문 데이터의 경우 옵션 정보 추가 로깅
    if (config.url.includes('/orders') && config.method === 'post') {
      console.log('[주문 데이터]', config.data);
      console.log('[주문 옵션 상세]', config.data.items.map(item => ({
        name: item.name,
        options: item.options
      })));
    }
    console.log(`[API Request] ${config.method.toUpperCase()} ${config.url}`, config.data);
    return config;
  },
  error => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

let isInitializing = false;
let lastInitTime = 0;
const INIT_COOLDOWN = 5000;
let currentConversationId = null;

const kioskAPI = {
  initialize: async () => {
    try {
      if (isInitializing) {
        return { status: 'pending', conversation_id: currentConversationId, device_id: currentConversationId };
      }
      const now = Date.now();
      if (currentConversationId && (now - lastInitTime < INIT_COOLDOWN)) {
        return { status: 'reused', conversation_id: currentConversationId, device_id: currentConversationId };
      }
      isInitializing = true;
      lastInitTime = now;
      const response = await axiosInstance.post('/kiosk/initialize', {}, { timeout: 15000 });
      const newConversationId = response.data.device_id || response.data.conversation_id;
      currentConversationId = newConversationId || `temp-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
      return { ...response.data, conversation_id: currentConversationId, device_id: currentConversationId };
    } catch (error) {
      const fallbackId = `fallback-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
      currentConversationId = fallbackId;
      return { status: 'error', conversation_id: fallbackId, device_id: fallbackId, error: error.response?.data || error.message };
    } finally {
      isInitializing = false;
    }
  },

  recordMicrophone: async (duration, conversationId) => {
    try {
      const response = await axiosInstance.post('/kiosk/audio', { duration, conversation_id: conversationId || currentConversationId });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  reset: async () => {
    try {
      const response = await axios.post(`${API_BASE_URL}/kiosk/reset`);
      currentConversationId = null;
      lastInitTime = 0;
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  getFullAudioUrl: (audioPath) => {
    const fileName = typeof audioPath === 'string' ? audioPath.split(/[/\\]/).pop() : '';
    return fileName ? `${API_BASE_URL}/kiosk/audio/${fileName}` : '';
  },

  getCurrentConversationId: () => currentConversationId,
  isInitializing: () => isInitializing,

  getAllMenuItems: async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/menu`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  getMenuItemsByCategory: async (category) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/menu?category=${category}`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  createOrder: async (orderData) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/orders`, orderData);
      if (!response.data || !response.data._id) {
        throw new Error('유효한 주문 ID를 받지 못했습니다.');
      }
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  updateOrderStatus: async (orderId, status) => {
    try {
      const response = await axios.put(`${API_BASE_URL}/orders/${orderId}`, { status });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  processPayment: async (orderId, paymentMethod) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/orders/${orderId}/payment`, { method: paymentMethod });
      if (!response.data || response.data.status !== 'success') {
        throw new Error('결제 처리에 실패했습니다.');
      }
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  transcribeAudio: async (audioBlob) => {
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob);
      const response = await axiosInstance.post('/kiosk/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  }
};

export { kioskAPI };
export default kioskAPI;
