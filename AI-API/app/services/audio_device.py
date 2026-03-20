# app/services/audio_device.py
import pyaudio
import wave
import numpy as np
import time
import logging
import os
import threading
import tempfile
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class AudioDeviceService:
    """오디오 입력(마이크) 및 출력(스피커) 장치를 직접 제어하는 서비스"""
    
    def __init__(self):
        self.pyaudio = pyaudio.PyAudio()
        self.is_recording = False
        self.recording_thread = None
        self.input_device_index = None
        self.output_device_index = None
        self.temp_dir = tempfile.gettempdir()
        
        # 기본 설정
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000  # 녹음용 샘플링 레이트
        self.chunk = 1024
        self.output_rate = 24000  # 재생용 샘플링 레이트 (TTS 기본값과 일치)
        
        # 설정 초기화
        self._initialize_devices()
        
    def _initialize_devices(self):
        """사용 가능한 오디오 입출력 장치를 확인하고 초기화"""
        logger.info("오디오 장치 초기화 중...")
        
        # 사용 가능한 모든 오디오 장치 정보 출력
        info = self.pyaudio.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        
        found_input = False
        found_output = False
        
        for i in range(num_devices):
            device_info = self.pyaudio.get_device_info_by_host_api_device_index(0, i)
            device_name = device_info.get('name')
            max_input_channels = device_info.get('maxInputChannels')
            max_output_channels = device_info.get('maxOutputChannels')
            
            logger.info(f"장치 {i}: {device_name} "
                     f"(입력 채널: {max_input_channels}, 출력 채널: {max_output_channels})")
            
            # 입력 장치 자동 선택 (첫 번째 유효한 장치)
            if not found_input and max_input_channels > 0:
                self.input_device_index = i
                found_input = True
                logger.info(f"기본 입력 장치로 선택: {i} - {device_name}")
            
            # 출력 장치 자동 선택 (첫 번째 유효한 장치)
            if not found_output and max_output_channels > 0:
                self.output_device_index = i
                found_output = True
                logger.info(f"기본 출력 장치로 선택: {i} - {device_name}")
        
        if not found_input:
            logger.warning("유효한 입력 장치를 찾을 수 없습니다. 기본 장치를 사용합니다.")
            self.input_device_index = None
        
        if not found_output:
            logger.warning("유효한 출력 장치를 찾을 수 없습니다. 기본 장치를 사용합니다.")
            self.output_device_index = None
    
    def set_input_device(self, device_index: int):
        """입력 장치 수동 설정"""
        try:
            device_info = self.pyaudio.get_device_info_by_host_api_device_index(0, device_index)
            if device_info.get('maxInputChannels') > 0:
                self.input_device_index = device_index
                logger.info(f"입력 장치 설정: {device_index} - {device_info.get('name')}")
                return True
            else:
                logger.error(f"장치 {device_index}는 입력을 지원하지 않습니다")
                return False
        except Exception as e:
            logger.error(f"입력 장치 설정 실패: {str(e)}")
            return False
    
    def set_output_device(self, device_index: int):
        """출력 장치 수동 설정"""
        try:
            device_info = self.pyaudio.get_device_info_by_host_api_device_index(0, device_index)
            if device_info.get('maxOutputChannels') > 0:
                self.output_device_index = device_index
                logger.info(f"출력 장치 설정: {device_index} - {device_info.get('name')}")
                return True
            else:
                logger.error(f"장치 {device_index}는 출력을 지원하지 않습니다")
                return False
        except Exception as e:
            logger.error(f"출력 장치 설정 실패: {str(e)}")
            return False
    
    def list_devices(self) -> Dict[str, Any]:
        """사용 가능한 모든 오디오 장치 목록 반환"""
        devices = []
        info = self.pyaudio.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        
        for i in range(num_devices):
            try:
                device_info = self.pyaudio.get_device_info_by_host_api_device_index(0, i)
                
                devices.append({
                    "index": i,
                    "name": device_info.get('name'),
                    "input_channels": device_info.get('maxInputChannels'),
                    "output_channels": device_info.get('maxOutputChannels'),
                    "default_sample_rate": device_info.get('defaultSampleRate'),
                    "is_current_input": i == self.input_device_index,
                    "is_current_output": i == self.output_device_index
                })
            except Exception as e:
                logger.error(f"장치 정보 가져오기 실패 (인덱스 {i}): {str(e)}")
        
        return {
            "devices": devices,
            "current_input_index": self.input_device_index,
            "current_output_index": self.output_device_index
        }
    
    def start_recording(self, duration: int = 5, save_path: Optional[str] = None) -> str:
        """
        마이크 녹음 시작
        
        Args:
            duration: 녹음 시간(초)
            save_path: 저장 경로 (지정하지 않으면 임시 파일 생성)
            
        Returns:
            녹음 파일 경로
        """
        if self.is_recording:
            logger.warning("이미 녹음 중입니다")
            return ""
        
        if not save_path:
            # 임시 파일 생성
            save_path = os.path.join(self.temp_dir, f"recording_{int(time.time())}.wav")
        
        try:
            self.is_recording = True
            self.recording_thread = threading.Thread(
                target=self._record_thread, 
                args=(save_path, duration)
            )
            self.recording_thread.start()
            
            logger.info(f"녹음 시작: {duration}초, 저장 경로: {save_path}")
            return save_path
        except Exception as e:
            self.is_recording = False
            logger.error(f"녹음 시작 실패: {str(e)}")
            return ""
    
    def _record_thread(self, save_path: str, duration: int):
        """녹음 스레드 함수"""
        try:
            stream = self.pyaudio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )
            
            frames = []
            
            # 지정된 시간 동안 녹음
            for i in range(0, int(self.rate / self.chunk * duration)):
                if not self.is_recording:
                    break
                data = stream.read(self.chunk)
                frames.append(data)
            
            # 스트림 정리
            stream.stop_stream()
            stream.close()
            
            # WAV 파일로 저장
            wf = wave.open(save_path, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.pyaudio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            logger.info(f"녹음 완료: {save_path}")
            
        except Exception as e:
            logger.error(f"녹음 중 오류 발생: {str(e)}")
        finally:
            self.is_recording = False
    
    def stop_recording(self):
        """녹음 중지"""
        if self.is_recording:
            self.is_recording = False
            logger.info("녹음 중지 요청됨")
            return True
        return False
    
    def play_audio(self, audio_path: str) -> bool:
        """
        오디오 파일 재생
        
        Args:
            audio_path: 재생할 오디오 파일 경로
            
        Returns:
            성공 여부
        """
        if not os.path.exists(audio_path):
            logger.error(f"오디오 파일이 존재하지 않습니다: {audio_path}")
            return False
        
        try:
            # wav 파일 열기
            wf = wave.open(audio_path, 'rb')
            
            # 오디오 스트림 설정
            stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=self.output_device_index
            )
            
            # 청크 단위로 데이터 읽고 재생
            data = wf.readframes(self.chunk)
            
            logger.info(f"오디오 재생 시작: {audio_path}")
            
            while data:
                stream.write(data)
                data = wf.readframes(self.chunk)
            
            # 스트림 정리
            stream.stop_stream()
            stream.close()
            
            logger.info(f"오디오 재생 완료: {audio_path}")
            return True
            
        except Exception as e:
            logger.error(f"오디오 재생 중 오류 발생: {str(e)}")
            return False
    
    def play_raw_audio(self, audio_data: np.ndarray, sample_rate: int = 24000) -> bool:
        """
        Raw 오디오 데이터 재생
        
        Args:
            audio_data: 재생할 오디오 데이터 (numpy 배열)
            sample_rate: 샘플링 레이트
            
        Returns:
            성공 여부
        """
        try:
            # float32로 변환
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # 정규화
            if np.max(np.abs(audio_data)) > 1.0:
                audio_data = audio_data / np.max(np.abs(audio_data))
            
            # 출력 스트림 설정
            stream = self.pyaudio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=sample_rate,
                output=True,
                output_device_index=self.output_device_index
            )
            
            # 오디오 데이터 재생
            stream.write(audio_data.tobytes())
            
            # 스트림 정리
            stream.stop_stream()
            stream.close()
            
            logger.info(f"Raw 오디오 재생 완료: 길이 {len(audio_data)/sample_rate:.2f}초")
            return True
            
        except Exception as e:
            logger.error(f"Raw 오디오 재생 중 오류 발생: {str(e)}")
            return False
    
    def cleanup(self):
        """자원 정리"""
        # 녹음 중이면 중지
        if self.is_recording:
            self.stop_recording()
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(1.0)  # 최대 1초 대기
        
        # PyAudio 정리
        if self.pyaudio:
            self.pyaudio.terminate()
            logger.info("오디오 자원 정리 완료")

# 싱글톤 인스턴스
audio_device_service = AudioDeviceService()