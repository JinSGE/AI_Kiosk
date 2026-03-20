// src/services/audioService.js
import { useState, useRef, useCallback, useEffect } from 'react';

/**
 * 마이크 녹음 기능을 제공하는 React Hook
 * @returns {Object} - 녹음 관련 상태 및 함수들
 */
export const useAudioRecorder = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioData, setAudioData] = useState(null);
  const [recordingError, setRecordingError] = useState(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const volumeCallbackRef = useRef(null);

  // 녹음 시작 함수
  const startRecording = useCallback(async () => {
    if (isRecording) {
      console.warn('이미 녹음 중입니다.');
      return;
    }

    try {
      setRecordingError(null);
      audioChunksRef.current = [];
      
      // 마이크 접근 권한 요청
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      // MediaRecorder 설정
      mediaRecorderRef.current = new MediaRecorder(stream);
      
      // 데이터 수집 리스너
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      // 녹음 종료 리스너
      mediaRecorderRef.current.onstop = async () => {
        // 녹음된 오디오 데이터 처리
        if (audioChunksRef.current.length > 0) {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          
          // Base64로 변환
          const reader = new FileReader();
          reader.onloadend = () => {
            setAudioData(reader.result);
          };
          reader.readAsDataURL(audioBlob);
        }
        
        // 스트림 종료
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }
        
        setIsRecording(false);
      };
      
      // 녹음 시작
      mediaRecorderRef.current.start();
      setIsRecording(true);
      
    } catch (error) {
      console.error('녹음 시작 오류:', error);
      setRecordingError(error.message || '마이크 접근 권한이 필요합니다.');
      setIsRecording(false);
    }
  }, [isRecording]);

  // 녹음 중지 함수
  const stopRecording = useCallback(() => {
    if (!isRecording || !mediaRecorderRef.current) {
      console.warn('녹음 중이 아닙니다.');
      return;
    }
    
    try {
      mediaRecorderRef.current.stop();
    } catch (error) {
      console.error('녹음 중지 오류:', error);
      setRecordingError(error.message || '녹음 중지 중 오류가 발생했습니다.');
      
      // 오류 발생해도 상태 정리
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      
      setIsRecording(false);
    }
  }, [isRecording]);

  // 음성 레벨 모니터링을 위한 볼륨 미터 설정
  useEffect(() => {
    let audioContext = null;
    let analyser = null;
    let microphone = null;
    let javascriptNode = null;
    
    const setupVolumeMonitoring = () => {
      if (!streamRef.current || !isRecording) return;
      
      try {
        // 오디오 컨텍스트 및 분석기 설정
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        microphone = audioContext.createMediaStreamSource(streamRef.current);
        javascriptNode = audioContext.createScriptProcessor(2048, 1, 1);
        
        analyser.smoothingTimeConstant = 0.8;
        analyser.fftSize = 1024;
        
        microphone.connect(analyser);
        analyser.connect(javascriptNode);
        javascriptNode.connect(audioContext.destination);
        
        // 볼륨 레벨 계산 콜백
        javascriptNode.onaudioprocess = () => {
          const array = new Uint8Array(analyser.frequencyBinCount);
          analyser.getByteFrequencyData(array);
          const values = array.reduce((a, b) => a + b, 0);
          const average = values / array.length;
          
          // 볼륨 콜백이 있으면 호출
          if (volumeCallbackRef.current) {
            volumeCallbackRef.current(average);
          }
        };
      } catch (error) {
        console.error('볼륨 모니터링 설정 오류:', error);
      }
    };
    
    // 녹음 중일 때만 볼륨 모니터링 설정
    if (isRecording) {
      setupVolumeMonitoring();
    }
    
    // 정리 함수
    return () => {
      if (javascriptNode) {
        javascriptNode.disconnect();
      }
      if (analyser) {
        analyser.disconnect();
      }
      if (microphone) {
        microphone.disconnect();
      }
      if (audioContext) {
        audioContext.close().catch(console.error);
      }
    };
  }, [isRecording]);

  // 메모리 누수 방지를 위한 추가 정리
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      audioChunksRef.current = [];
    };
  }, []);

  // 볼륨 콜백 설정 함수
  const setVolumeCallback = useCallback((callback) => {
    volumeCallbackRef.current = callback;
  }, []);

  return {
    isRecording,
    audioData,
    recordingError,
    startRecording,
    stopRecording,
    setVolumeCallback
  };
};

/**
 * 오디오 재생 기능을 제공하는 React Hook
 * @returns {Object} - 오디오 재생 관련 상태 및 함수들
 */
export const useAudioPlayer = () => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState(null);
  const audioRef = useRef(null);

  // 오디오 재생 함수
  const playAudio = useCallback((audioSrc) => {
    // 함수 시작 시 오류 상태 초기화
    setError(null);
    
    if (!audioSrc) {
      setError('재생할 오디오가 없습니다.');
      return false;
    }

    try {
      // 이미 재생 중이면 중지
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }

      // 새 오디오 요소 생성
      const audio = new Audio();
      audioRef.current = audio;

      // 이벤트 리스너 설정
      audio.onplay = () => setIsPlaying(true);
      audio.onpause = () => setIsPlaying(false);
      audio.onended = () => {
        setIsPlaying(false);
        audioRef.current = null;
      };
      audio.onerror = (e) => {
        console.error('오디오 재생 오류:', e);
        setError('오디오 재생 중 오류가 발생했습니다.');
        setIsPlaying(false);
      };

      // 소스 설정 및 재생
      audio.src = audioSrc;
      audio.play().catch(err => {
        console.error('자동 재생 실패:', err);
        setError('브라우저에서 자동 재생이 차단되었습니다. 사용자 상호작용이 필요합니다.');
        setIsPlaying(false);
      });

      return true;
    } catch (err) {
      console.error('오디오 설정 오류:', err);
      setError(`오디오 설정 오류: ${err.message}`);
      setIsPlaying(false);
      return false;
    }
  }, []);

  // 오디오 중지 함수
  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlaying(false);
    }
  }, []);

  // 클린업 함수
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  return {
    isPlaying,
    error,
    playAudio,
    stopAudio
  };
};

// 오디오 변환 유틸리티 함수들
export const audioUtils = {
  /**
   * Blob을 Base64 문자열로 변환
   * @param {Blob} blob - 변환할 Blob 객체
   * @returns {Promise<string>} Base64 문자열
   */
  blobToBase64: (blob) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  },

  /**
   * Base64 문자열을 Blob으로 변환
   * @param {string} base64 - Base64 문자열
   * @param {string} [mimeType='audio/webm'] - MIME 타입
   * @returns {Blob} Blob 객체
   */
  base64ToBlob: (base64, mimeType = 'audio/webm') => {
    // Base64 데이터 URI에서 실제 base64 문자열 추출
    const base64Data = base64.split(',')[1] || base64;
    
    // base64 디코딩 및 Blob 생성
    const byteCharacters = atob(base64Data);
    const byteNumbers = new Array(byteCharacters.length);
    
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], { type: mimeType });
  },

  /**
   * 오디오 길이 측정
   * @param {Blob|File} audioBlob - 오디오 Blob
   * @returns {Promise<number>} 오디오 길이 (초 단위)
   */
  getAudioDuration: (audioBlob) => {
    return new Promise((resolve, reject) => {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const arrayBuffer = e.target.result;
        
        audioContext.decodeAudioData(
          arrayBuffer,
          (audioBuffer) => {
            resolve(audioBuffer.duration);
            audioContext.close();
          },
          (error) => {
            console.error('오디오 길이 측정 오류:', error);
            reject(error);
            audioContext.close();
          }
        );
      };
      
      reader.onerror = (error) => {
        console.error('파일 읽기 오류:', error);
        reject(error);
      };
      
      reader.readAsArrayBuffer(audioBlob);
    });
  },

  /**
   * 오디오 레벨 분석
   * @param {Blob} audioBlob - 분석할 오디오 Blob
   * @returns {Promise<Object>} 오디오 레벨 분석 결과
   */
  analyzeAudioLevels: (audioBlob) => {
    return new Promise((resolve, reject) => {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const arrayBuffer = e.target.result;
        
        audioContext.decodeAudioData(
          arrayBuffer,
          (audioBuffer) => {
            const channelData = audioBuffer.getChannelData(0);
            
            // 최대, 최소, 평균 레벨 계산
            const maxLevel = Math.max(...channelData.map(Math.abs));
            const averageLevel = channelData.reduce((a, b) => a + Math.abs(b), 0) / channelData.length;
            
            resolve({
              duration: audioBuffer.duration,
              maxLevel,
              averageLevel,
              channelCount: audioBuffer.numberOfChannels
            });
            
            audioContext.close();
          },
          (error) => {
            console.error('오디오 분석 오류:', error);
            reject(error);
            audioContext.close();
          }
        );
      };
      
      reader.onerror = (error) => {
        console.error('파일 읽기 오류:', error);
        reject(error);
      };
      
      reader.readAsArrayBuffer(audioBlob);
    });
  }
};

export default {
  useAudioRecorder,
  useAudioPlayer,
  audioUtils
};