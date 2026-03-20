// src/services/websocket.js - 오류 처리 개선
import EventEmitter from 'events';

class WebSocketService extends EventEmitter {
  constructor() {
    super();
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectInterval = 2000;
    this.isConnecting = false;
    this.wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:5000/ws';
    this.debug = true;
    this.connectionTimer = null;
  }
  // websocket.js에 추가할 메서드
  startContinuousDialog() {
    const payload = {
      action: 'start_continuous_dialog'
    };
    
    this.log('연속 대화 세션 시작 요청');
    return this.send(payload);
  }

  stopContinuousDialog() {
    const payload = {
      action: 'stop_continuous_dialog'
    };
    
    this.log('연속 대화 세션 중지 요청');
    return this.send(payload);
  }

  // Kiosk 서비스 통합
  startVoiceRecognition(duration = 10) {
    const payload = {
      action: 'start_voice_recognition',
      duration
    };
    
    this.log(`음성 인식 시작 요청 (${duration}초)`);
    return this.send(payload);
  }

  // 음성으로 직접 텍스트 처리 (enhanced_pipeline_service.py 호출)
  processVoiceInput(audioBlob) {
    // 웹소켓은 바이너리 데이터 전송 가능
    if (!this.isConnected()) {
      this.log('WebSocket이 연결되어 있지 않습니다. 오디오를 전송할 수 없습니다.');
      return false;
    }
    
    try {
      // 바이너리 데이터 전송
      this.socket.send(audioBlob);
      this.log('오디오 데이터 전송 완료');
      return true;
    } catch (error) {
      this.error('오디오 데이터 전송 오류:', error);
      return false;
    }
  }
  log(message, ...args) {
    if (this.debug) {
      console.log(`[WebSocketService] ${message}`, ...args);
    }
  }

  error(message, ...args) {
    console.error(`[WebSocketService] ${message}`, ...args);
  }

  connect() {
    // 이미 연결 중이거나 연결된 경우 처리
    if (this.isConnecting) {
      this.log('이미 연결 시도 중입니다.');
      return;
    }

    if (this.socket) {
      if (this.socket.readyState === WebSocket.OPEN) {
        this.log('이미 연결되어 있습니다.');
        return;
      }
      
      if (this.socket.readyState === WebSocket.CONNECTING) {
        this.log('이미 연결 중입니다.');
        return;
      }
      
      // 연결 종료 중인 소켓은 정리
      if (this.socket.readyState === WebSocket.CLOSING || this.socket.readyState === WebSocket.CLOSED) {
        this.socket = null;
      }
    }

    this.isConnecting = true;
    this.log(`WebSocket 연결 시도: ${this.wsUrl}`);

    try {
      // 기존 타이머 제거
      if (this.connectionTimer) {
        clearTimeout(this.connectionTimer);
        this.connectionTimer = null;
      }

      // 새 WebSocket 연결 생성
      this.socket = new WebSocket(this.wsUrl);
      
      // 연결 타임아웃 설정 (5초)
      this.connectionTimer = setTimeout(() => {
        if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
          this.error('연결 타임아웃. 소켓을 강제로 닫습니다.');
          this.socket.close();
          this.socket = null;
          this.isConnecting = false;
          this.emit('error', new Error('Connection timeout'));

          // 재연결 시도
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            this.log(`${this.reconnectInterval / 1000}초 후 재연결 시도 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => this.connect(), this.reconnectInterval);
          }
        }
      }, 5000);

      // 이벤트 핸들러 등록
      this.socket.onopen = () => {
        this.log('WebSocket 연결 성공');
        if (this.connectionTimer) {
          clearTimeout(this.connectionTimer);
          this.connectionTimer = null;
        }
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.emit('connect');
      };
      
      this.socket.onmessage = (event) => {
        try {
          this.log('원본 메시지 수신:', event.data);
          
          // 원시 메시지 이벤트 먼저 발행 (오류에 관계없이)
          this.emit('rawMessage', event.data);
          
          // 메시지 파싱 시도
          let data;
          try {
            data = JSON.parse(event.data);
            this.log('파싱된 메시지:', data);
          } catch (parseError) {
            this.error('메시지 파싱 오류:', parseError);
            return; // 파싱 실패 시 더 이상 처리하지 않음
          }
          
          // 수정: cart_update 메시지 처리 추가
          if (data.type === 'cart_update') {
            // 장바구니 초기화 처리 추가
            if (data.operation === 'reset') {
              this.log('장바구니 초기화 메시지 감지');
              this.emit('cartReset');
            }
            
            this.emit('cartUpdate', data);
            this.log('장바구니 업데이트 이벤트 발행', data);
          }
          
          // 상태 업데이트 이벤트 처리
          else if (data.type === 'state_update') {
            // 상태가 직렬화 가능한지 확인
            const state = this.normalizeState(data.state);
            
            this.emit('stateUpdate', {
              state: state,
              message: data.message || '',
              context: data.context || {}
            });
          } else if (data.type === 'text_processed') {
            // 텍스트 처리 결과
            this.emit('textProcessed', data);
          } else if (data.type === 'state_changed') {
            // 상태 변경 결과
            this.emit('stateChanged', data);
          } else if (data.type === 'error') {
            // 오류 메시지
            this.emit('messageError', data);
          } else {
            // 기타 메시지 타입 이벤트 발행
            this.emit(data.type || 'message', data);
          }
        } catch (error) {
          this.error('메시지 처리 중 오류:', error);
        }
      };

      this.socket.onerror = (error) => {
        this.error('WebSocket 오류:', error);
        this.isConnecting = false;
        this.emit('error', error);
      };

      this.socket.onclose = (event) => {
        this.log(`WebSocket 연결 종료: 코드=${event.code}, 이유=${event.reason || '알 수 없음'}`);
        
        if (this.connectionTimer) {
          clearTimeout(this.connectionTimer);
          this.connectionTimer = null;
        }
        
        this.isConnecting = false;
        this.emit('disconnect', event);
        
        // 비정상 종료인 경우에만 재연결 시도 (1000은 정상 종료)
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          this.log(`${this.reconnectInterval / 1000}초 후 재연결 시도 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
          setTimeout(() => this.connect(), this.reconnectInterval);
        } else if (event.code !== 1000) {
          this.error('최대 재연결 시도 횟수 초과. 사용자 개입이 필요합니다.');
          this.emit('maxReconnectAttemptsReached');
        }
      };
    } catch (error) {
      this.error('WebSocket 초기화 오류:', error);
      this.isConnecting = false;
      
      if (this.connectionTimer) {
        clearTimeout(this.connectionTimer);
        this.connectionTimer = null;
      }
      
      this.emit('initError', error);
      
      // 초기화 오류 후 재연결 시도
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        this.log(`${this.reconnectInterval / 1000}초 후 재연결 시도 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
        setTimeout(() => this.connect(), this.reconnectInterval);
      }
    }
  }

  // State 객체가 직렬화 불가능한 경우 처리
  normalizeState(state) {
    if (state === null || state === undefined) {
      return 'unknown';
    }
    
    // 객체인 경우 문자열로 변환 시도
    if (typeof state === 'object') {
      // toString 메서드가 있으면 사용
      if (state.toString && typeof state.toString === 'function' && state.toString() !== '[object Object]') {
        return state.toString();
      }
      
      // name 속성이 있으면 사용
      if (state.name) {
        return state.name;
      }
      
      // 타입 이름 사용
      return state.constructor ? state.constructor.name : 'unknown';
    }
    
    return state;
  }

  connectAndTrack() {
    // connectAndTrack은 connect를 호출하도록 간소화
    this.connect();
  }

  disconnect() {
    if (this.socket) {
      this.log('WebSocket 연결 종료 요청');
      
      try {
        this.socket.close(1000, 'Normal closure');
      } catch (error) {
        this.error('소켓 종료 중 오류:', error);
      }
      
      this.socket = null;
      
      if (this.connectionTimer) {
        clearTimeout(this.connectionTimer);
        this.connectionTimer = null;
      }
    }
  }

  isConnected() {
    return this.socket && this.socket.readyState === WebSocket.OPEN;
  }

  getConnectionState() {
    if (!this.socket) return 'CLOSED';
    
    switch(this.socket.readyState) {
      case WebSocket.CONNECTING: return 'CONNECTING';
      case WebSocket.OPEN: return 'OPEN';
      case WebSocket.CLOSING: return 'CLOSING';
      case WebSocket.CLOSED: return 'CLOSED';
      default: return 'UNKNOWN';
    }
  }

  send(data) {
    if (!this.isConnected()) {
      this.error('WebSocket이 연결되어 있지 않습니다. 메시지를 보낼 수 없습니다.');
      return false;
    }

    try {
      const message = typeof data === 'string' ? data : JSON.stringify(data);
      this.socket.send(message);
      this.log('메시지 전송:', data);
      return true;
    } catch (error) {
      this.error('메시지 전송 오류:', error);
      return false;
    }
  }

  // 백엔드 서버의 메시지 형식에 맞게 수정
  changeState(state, context = {}) {
    const payload = {
      action: 'change_state', // type -> action으로 변경
      state,
      slots: context // context -> slots으로 변경
    };
    
    this.log(`상태 변경 요청: ${state}`, context);
    return this.send(payload);
  }

  // 백엔드 서버의 메시지 형식에 맞게 수정
  processText(text) {
    const payload = {
      action: 'process_text', // type -> action으로 변경
      text
    };
    
    this.log(`텍스트 처리 요청: ${text}`);
    return this.send(payload);
  }
}

// 싱글톤 인스턴스 생성
const websocketService = new WebSocketService();

export default websocketService;