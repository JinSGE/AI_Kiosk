import axios from 'axios';

// API 기본 URL 설정
const API_BASE_URL = window.process?.env?.REACT_APP_API_URL || 'http://localhost:5000/api/v1';

export const menuService = {
    /**
     * 전체 메뉴 조회
     * @param {string} [category] - 선택적 카테고리 필터
     * @returns {Promise<Array>} 메뉴 아이템 배열
     */
    async getAllMenuItems(category) {
        try {
            const url = category 
                ? `${API_BASE_URL}/menu?category=${category}` 
                : `${API_BASE_URL}/menu`;
            
            const response = await axios.get(url);
            return response.data;
        } catch (error) {
            console.error('메뉴 조회 중 오류 발생:', error);
            throw error;
        }
    },

    /**
     * 메뉴 카테고리 목록 조회
     * @returns {Promise<Array<string>>} 카테고리 목록
     */
    async getMenuCategories() {
        try {
            const response = await axios.get(`${API_BASE_URL}/menu/categories`);
            return response.data;
        } catch (error) {
            console.error('메뉴 카테고리 조회 중 오류 발생:', error);
            throw error;
        }
    },

    /**
     * 특정 메뉴 상세 정보 조회
     * @param {string} menuName - 메뉴 이름
     * @returns {Promise<Object>} 메뉴 상세 정보
     */
    async getMenuItemByName(menuName) {
        try {
            const response = await axios.get(`${API_BASE_URL}/menu/${menuName}`);
            return response.data;
        } catch (error) {
            console.error(`${menuName} 메뉴 조회 중 오류 발생:`, error);
            throw error;
        }
    },

    /**
     * 메뉴 옵션 정보 추출
     * @param {Object} menuItem - 메뉴 아이템
     * @returns {Object} 정리된 옵션 정보
     */
    extractMenuOptions(menuItem) {
        const options = menuItem.options || {};
        const processedOptions = {};

        Object.keys(options).forEach(optionType => {
            processedOptions[optionType] = Object.entries(options[optionType]).map(
                ([name, price]) => ({ name, price })
            );
        });

        return processedOptions;
    },

    /**
     * 메뉴 최종 가격 계산
     * @param {Object} menuItem - 메뉴 아이템
     * @param {Array} selectedOptions - 선택된 옵션 배열
     * @returns {number} 최종 가격
     */
    calculateMenuPrice(menuItem, selectedOptions = []) {
        let totalPrice = menuItem.basePrice || 0;

        if (selectedOptions && selectedOptions.length > 0) {
            selectedOptions.forEach(option => {
                // 옵션들 돌면서 가격 추가
                Object.values(menuItem.options || {}).forEach(optionGroup => {
                    if (optionGroup[option]) {
                        totalPrice += optionGroup[option];
                    }
                });
            });
        }

        return totalPrice;
    },

    /**
     * 음성 주문으로부터 주문 생성 요청
     * @param {Object} orderData - 예: { items: [...], totalPrice: 5000 }
     * @returns {Promise<Object>} 주문 생성 결과
     */
    async createOrder(orderData) {
        try {
            console.log('주문 생성 요청 데이터:', orderData);
            
            // 옵션 정보 정리
            const processedOrder = {
            ...orderData,
            items: orderData.items.map(item => ({
                ...item,
                options: Array.isArray(item.options) ? item.options.map(opt => {
                // 이미 객체면 그대로 사용
                if (typeof opt === 'object' && opt !== null) {
                    return {
                    id: opt.id || '',
                    name: opt.name,
                    price: opt.price || 0,
                    choice: opt.choice || opt.name
                    };
                }
                
                // 문자열이면 옵션 객체로 변환
                return {
                    id: '',
                    name: opt,
                    price: this.getOptionPrice(opt),
                    choice: opt
                };
                }) : []
            }))
            };
            
            console.log('가공된 주문 데이터:', processedOrder);
            const response = await axios.post(`${API_BASE_URL}/orders`, processedOrder);
            return response.data;
        } catch (error) {
            console.error("주문 생성 중 오류 발생:", error);
            throw error;
        }
        },

        // 옵션 가격 조회 함수 추가
        getOptionPrice(optionName) {
        const optionPrices = {
            'Hot': 0,
            'Ice': 0,
            'Small': 0,
            'Regular': 500,
            'Large': 1000,
            '샷 추가': 500,
            '시럽 추가': 300,
            '휘핑크림 추가': 500
        };
        
        return optionPrices[optionName] || 0;
        },

    /**
     * 결제 처리 요청
     * @param {string} orderId - 주문 ID
     * @param {string} method - 결제 수단 예: '카드', '현금'
     * @returns {Promise<Object>} 결제 처리 결과
     */
    async processPayment(orderId, method) {
        try {
            const response = await axios.post(`${API_BASE_URL}/order/${orderId}/payment`, {
                method
            });
            return response.data;
        } catch (error) {
            console.error("결제 처리 중 오류 발생:", error);
            throw error;
        }
    },

    /**
     * 특정 주문 상세 정보 조회
     * @param {string} orderId - 주문 ID
     * @returns {Promise<Object>} 주문 상세 정보
     */
    async getOrderDetails(orderId) {
        try {
            const response = await axios.get(`${API_BASE_URL}/order/${orderId}`);
            return response.data;
        } catch (error) {
            console.error("주문 상세 조회 중 오류 발생:", error);
            throw error;
        }
    }
};

export default menuService;
