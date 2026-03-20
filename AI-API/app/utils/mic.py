# app/utils/comprehensive_vad_diagnostic.py

import platform
import sys
import numpy as np
import traceback

def check_vad_dependencies():
    """VAD 의존성 라이브러리 확인"""
    try:
        import pyaudio
        import webrtcvad
        import numpy as np
        
        print("라이브러리 버전:")
        print(f"PyAudio 버전: {pyaudio.__version__}")
        print(f"WebRTC VAD 버전: {webrtcvad.__version__}")
        print(f"NumPy 버전: {np.__version__}")
        return True
    except ImportError as e:
        print(f"라이브러리 가져오기 실패: {e}")
        return False

def list_audio_devices():
    """오디오 장치 상세 정보 나열"""
    try:
        import pyaudio
        
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        
        print("\n오디오 장치 정보:")
        for i in range(device_count):
            device_info = p.get_device_info_by_index(i)
            print(f"\n장치 {i}:")
            print(f"  이름: {device_info['name']}")
            print(f"  입력 채널: {device_info['maxInputChannels']}")
            print(f"  출력 채널: {device_info['maxOutputChannels']}")
            print(f"  기본 샘플 레이트: {device_info['defaultSampleRate']}")
        
        p.terminate()
    except Exception as e:
        print(f"오디오 장치 나열 중 오류: {e}")

def find_compatible_input_devices():
    """WebRTC VAD와 호환되는 입력 장치 찾기"""
    try:
        import pyaudio
        import webrtcvad
        
        p = pyaudio.PyAudio()
        vad = webrtcvad.Vad(3)  # 최대 민감도
        
        # WebRTC VAD 지원 샘플 레이트
        supported_rates = [8000, 16000, 32000, 48000]
        compatible_devices = []
        
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            
            if device_info['maxInputChannels'] > 0:
                compatible_rates = []
                for rate in supported_rates:
                    try:
                        # 짧은 프레임 생성
                        frame = np.zeros(rate * 30 // 1000, dtype=np.int16).tobytes()
                        
                        # VAD 테스트
                        vad.is_speech(frame, rate)
                        compatible_rates.append(rate)
                    except Exception:
                        pass
                
                if compatible_rates:
                    compatible_devices.append({
                        'device_index': i,
                        'device_name': device_info['name'],
                        'compatible_rates': compatible_rates
                    })
        
        p.terminate()
        return compatible_devices
    except Exception as e:
        print(f"호환 장치 찾기 중 오류: {e}")
        return []

def detailed_vad_test(device_index, sample_rates):
    """상세 VAD 테스트"""
    try:
        import pyaudio
        import webrtcvad
        import numpy as np
        
        p = pyaudio.PyAudio()
        device_info = p.get_device_info_by_index(device_index)
        
        print(f"\n상세 VAD 테스트:")
        print(f"장치: {device_info['name']}")
        print(f"입력 채널: {device_info['maxInputChannels']}")
        
        vad = webrtcvad.Vad(3)  # 최대 민감도
        
        for rate in sample_rates:
            try:
                print(f"\n샘플 레이트: {rate} Hz 테스트")
                
                # 오디오 스트림 설정
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=rate // 1000 * 30  # 30ms 청크
                )
                
                # 다양한 시나리오 테스트
                test_scenarios = [
                    ("백색 잡음", np.random.randint(-32768, 32767, rate // 1000 * 30, dtype=np.int16).tobytes()),
                    ("작은 진폭 잡음", np.random.randint(-100, 100, rate // 1000 * 30, dtype=np.int16).tobytes()),
                    ("거의 무음", np.zeros(rate // 1000 * 30, dtype=np.int16).tobytes()),
                ]
                
                for scenario_name, frame in test_scenarios:
                    is_speech = vad.is_speech(frame, rate)
                    print(f"시나리오 '{scenario_name}': {'음성' if is_speech else '무음'}")
                
                # 실제 음성 청크 녹음 및 테스트
                print("\n실제 음성 청크 테스트:")
                for _ in range(3):
                    frame = stream.read(rate // 1000 * 30)
                    is_speech = vad.is_speech(frame, rate)
                    print(f"녹음된 청크: {'음성' if is_speech else '무음'}")
                
                stream.stop_stream()
                stream.close()
                
            except Exception as rate_error:
                print(f"샘플 레이트 {rate} Hz 테스트 실패: {rate_error}")
        
        p.terminate()
    except Exception as e:
        print(f"VAD 테스트 중 오류: {e}")
        traceback.print_exc()

def main():
    """전체 VAD 진단 실행"""
    print("시스템 환경 정보:")
    print(f"운영체제: {platform.system()}")
    print(f"Python 버전: {sys.version}")
    print(f"Python 아키텍처: {platform.architecture()[0]}")
    
    # 의존성 라이브러리 확인
    if not check_vad_dependencies():
        print("필수 라이브러리를 설치해주세요.")
        return
    
    # 오디오 장치 목록
    list_audio_devices()
    
    # 호환 가능한 장치 찾기
    compatible_devices = find_compatible_input_devices()
    
    if not compatible_devices:
        print("WebRTC VAD와 호환되는 오디오 장치를 찾을 수 없습니다.")
        return
    
    print("\n호환 가능한 장치:")
    for device in compatible_devices:
        print(f"장치 {device['device_index']}: {device['device_name']}")
        print(f"  호환 샘플 레이트: {device['compatible_rates']}")
    
    # 첫 번째 호환 가능한 장치로 VAD 테스트
    first_device = compatible_devices[0]
    detailed_vad_test(first_device['device_index'], first_device['compatible_rates'])

if __name__ == "__main__":
    main()