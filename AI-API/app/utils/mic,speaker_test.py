# cli_test.py
import argparse
import time
import sys
import os
from app.services.audio_device import audio_device_service
from app.services.stt_service_model import STTService
from app.services.tts_service_model import TTSService
from app.services.pipeline_service import PipelineService

def print_header(message):
    """서식이 지정된 헤더 출력"""
    print("\n" + "=" * 50)
    print(f" {message}")
    print("=" * 50)

def list_devices():
    """사용 가능한 모든 오디오 장치 나열"""
    print_header("사용 가능한 오디오 장치")
    
    devices_info = audio_device_service.list_devices()
    devices = devices_info["devices"]
    
    print(f"현재 입력 장치 인덱스: {devices_info['current_input_index']}")
    print(f"현재 출력 장치 인덱스: {devices_info['current_output_index']}")
    print("\n[사용 가능한 장치 목록]")
    
    for device in devices:
        input_mark = "◉" if device["is_current_input"] else "○"
        output_mark = "◉" if device["is_current_output"] else "○"
        
        print(f"인덱스 {device['index']}: {device['name']}")
        print(f"  입력({input_mark}): {device['input_channels']} 채널")
        print(f"  출력({output_mark}): {device['output_channels']} 채널")
        print(f"  기본 샘플링 레이트: {device['default_sample_rate']}")
        print()

def set_input_device(index):
    """입력 장치 설정"""
    print_header(f"입력 장치 설정 (인덱스: {index})")
    
    success = audio_device_service.set_input_device(index)
    if success:
        print(f"입력 장치 {index}번이 성공적으로 설정되었습니다.")
    else:
        print(f"입력 장치 {index}번 설정에 실패했습니다.")

def set_output_device(index):
    """출력 장치 설정"""
    print_header(f"출력 장치 설정 (인덱스: {index})")
    
    success = audio_device_service.set_output_device(index)
    if success:
        print(f"출력 장치 {index}번이 성공적으로 설정되었습니다.")
    else:
        print(f"출력 장치 {index}번 설정에 실패했습니다.")

def test_recording(duration=5):
    """마이크 녹음 테스트"""
    print_header(f"마이크 녹음 테스트 ({duration}초)")
    
    print(f"녹음 시작... {duration}초 동안 말씀해 주세요.")
    save_path = os.path.join(os.getcwd(), f"test_recording_{int(time.time())}.wav")
    audio_device_service.start_recording(duration, save_path)
    
    # 녹음이 완료될 때까지 대기
    elapsed = 0
    while audio_device_service.is_recording:
        time.sleep(0.1)
        elapsed += 0.1
        if elapsed >= duration + 2:  # 약간의 추가 시간
            audio_device_service.stop_recording()
            break
        
        # cli_test.py (계속)
        # 진행 상황 표시
        sys.stdout.write(f"\r녹음 중... {elapsed:.1f}/{duration}초 ")
        sys.stdout.flush()
    
    print(f"\n녹음 완료: {save_path}")
    return save_path

def test_playback(audio_path):
    """오디오 재생 테스트"""
    print_header(f"오디오 재생 테스트: {audio_path}")
    
    if not os.path.exists(audio_path):
        print(f"파일을 찾을 수 없습니다: {audio_path}")
        return False
    
    print("오디오 재생 중...")
    success = audio_device_service.play_audio(audio_path)
    
    if success:
        print("재생 완료!")
    else:
        print("재생 실패!")
    
    return success

def test_tts(text="안녕하세요, 테스트 메시지입니다."):
    """TTS 테스트"""
    print_header(f"TTS 테스트: '{text}'")
    
    try:
        print("TTS 서비스 초기화 중...")
        tts_service = TTSService()
        
        print("텍스트에서 음성 생성 중...")
        result = tts_service.generate_speech(text)
        
        if len(result) < 3:
            print("TTS 생성 실패")
            return None
            
        audio_data, sample_rate, audio_path = result
        
        print(f"음성 생성 완료: {audio_path} (길이: {len(audio_data)/sample_rate:.2f}초)")
        
        print("생성된 오디오 재생 중...")
        success = audio_device_service.play_audio(audio_path)
        
        if success:
            print("재생 완료!")
        else:
            print("재생 실패!")
        
        return audio_path
        
    except Exception as e:
        print(f"TTS 테스트 오류: {str(e)}")
        return None

def test_stt(audio_path):
    """STT 테스트"""
    print_header(f"STT 테스트: {audio_path}")
    
    try:
        if not os.path.exists(audio_path):
            print(f"파일을 찾을 수 없습니다: {audio_path}")
            return None
        
        print("STT 서비스 초기화 중...")
        stt_service = STTService()
        
        print("오디오를 텍스트로 변환 중...")
        with open(audio_path, "rb") as audio_file:
            result = stt_service.transcribe(audio_file)
        
        if not result or not result.get("success"):
            print("STT 변환 실패")
            return None
            
        text = result.get("text", "")
        
        print(f"텍스트 변환 완료: '{text}'")
        return text
        
    except Exception as e:
        print(f"STT 테스트 오류: {str(e)}")
        return None

def test_full_pipeline():
    """전체 파이프라인 테스트 (녹음 → STT → TTS → 재생)"""
    print_header("전체 음성 파이프라인 테스트")
    
    try:
        # 1. 녹음
        print("1단계: 마이크 녹음")
        audio_path = test_recording(5)
        
        if not audio_path or not os.path.exists(audio_path):
            print("녹음 실패. 테스트를 중단합니다.")
            return
            
        # 잠시 대기
        time.sleep(1)
        
        # 2. STT
        print("\n2단계: 음성 인식(STT)")
        recognized_text = test_stt(audio_path)
        
        if not recognized_text:
            print("음성 인식 실패. 테스트를 중단합니다.")
            return
            
        # 3. 파이프라인 처리 (NLP/RAG)
        print("\n3단계: 텍스트 처리 및 응답 생성")
        try:
            pipeline_service = PipelineService()
            result = pipeline_service.process_text_query(recognized_text)
            
            if not result or not result.get("success"):
                print("응답 생성 실패. 테스트를 중단합니다.")
                return
                
            response_text = result.get("response_text", "")
            response_audio_path = result.get("audio_path", "")
            
            print(f"응답 텍스트: '{response_text}'")
            
            # 4. 응답 재생
            print("\n4단계: 응답 오디오 재생")
            if response_audio_path and os.path.exists(response_audio_path):
                success = audio_device_service.play_audio(response_audio_path)
                
                if success:
                    print("재생 완료!")
                else:
                    print("재생 실패!")
            else:
                print("응답 오디오 파일을 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"파이프라인 처리 오류: {str(e)}")
            return
            
    except Exception as e:
        print(f"전체 파이프라인 테스트 오류: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="오디오 장치 테스트 유틸리티")
    
    # 하위 명령어 설정
    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")
    
    # 장치 목록 명령
    subparsers.add_parser("list", help="사용 가능한 오디오 장치 목록 표시")
    
    # 입력 장치 설정 명령
    input_parser = subparsers.add_parser("input", help="입력 장치 설정")
    input_parser.add_argument("index", type=int, help="설정할 입력 장치 인덱스")
    
    # 출력 장치 설정 명령
    output_parser = subparsers.add_parser("output", help="출력 장치 설정")
    output_parser.add_argument("index", type=int, help="설정할 출력 장치 인덱스")
    
    # 녹음 테스트 명령
    record_parser = subparsers.add_parser("record", help="마이크 녹음 테스트")
    record_parser.add_argument("--duration", type=int, default=5, help="녹음 시간(초) (기본값: 5)")
    
    # 재생 테스트 명령
    play_parser = subparsers.add_parser("play", help="오디오 재생 테스트")
    play_parser.add_argument("path", help="재생할 오디오 파일 경로")
    
    # TTS 테스트 명령
    tts_parser = subparsers.add_parser("tts", help="TTS(Text-to-Speech) 테스트")
    tts_parser.add_argument("--text", default="안녕하세요, 테스트 메시지입니다.", help="음성으로 변환할 텍스트")
    
    # STT 테스트 명령
    stt_parser = subparsers.add_parser("stt", help="STT(Speech-to-Text) 테스트")
    stt_parser.add_argument("path", help="텍스트로 변환할 오디오 파일 경로")
    
    # 전체 파이프라인 테스트 명령
    subparsers.add_parser("pipeline", help="전체 음성 파이프라인 테스트 (녹음 → STT → TTS → 재생)")
    
    # 인터랙티브 모드 명령
    subparsers.add_parser("interactive", help="인터랙티브 모드 실행")
    
    # 명령줄 인수 파싱
    args = parser.parse_args()
    
    # 명령 실행
    if args.command == "list":
        list_devices()
    elif args.command == "input":
        set_input_device(args.index)
    elif args.command == "output":
        set_output_device(args.index)
    elif args.command == "record":
        test_recording(args.duration)
    elif args.command == "play":
        test_playback(args.path)
    elif args.command == "tts":
        test_tts(args.text)
    elif args.command == "stt":
        test_stt(args.path)
    elif args.command == "pipeline":
        test_full_pipeline()
    elif args.command == "interactive":
        run_interactive_mode()
    else:
        # 명령이 지정되지 않은 경우 도움말 표시
        parser.print_help()

def run_interactive_mode():
    """인터랙티브 모드 실행"""
    print_header("인터랙티브 모드")
    
    while True:
        print("\n다음 명령 중 하나를 선택하세요:")
        print("1. 장치 목록 표시")
        print("2. 입력 장치 설정")
        print("3. 출력 장치 설정")
        print("4. 마이크 녹음 테스트")
        print("5. 오디오 재생 테스트")
        print("6. TTS 테스트")
        print("7. STT 테스트")
        print("8. 전체 파이프라인 테스트")
        print("9. 종료")
        
        choice = input("\n선택: ")
        
        if choice == "1":
            list_devices()
        elif choice == "2":
            try:
                index = int(input("설정할 입력 장치 인덱스: "))
                set_input_device(index)
            except ValueError:
                print("유효한 숫자를 입력하세요.")
        elif choice == "3":
            try:
                index = int(input("설정할 출력 장치 인덱스: "))
                set_output_device(index)
            except ValueError:
                print("유효한 숫자를 입력하세요.")
        elif choice == "4":
            try:
                duration = int(input("녹음 시간(초): ") or "5")
                test_recording(duration)
            except ValueError:
                print("유효한 숫자를 입력하세요.")
        elif choice == "5":
            path = input("재생할 오디오 파일 경로: ")
            test_playback(path)
        elif choice == "6":
            text = input("음성으로 변환할 텍스트: ") or "안녕하세요, 테스트 메시지입니다."
            test_tts(text)
        elif choice == "7":
            path = input("텍스트로 변환할 오디오 파일 경로: ")
            test_stt(path)
        elif choice == "8":
            test_full_pipeline()
        elif choice == "9":
            print("프로그램을 종료합니다.")
            break
        else:
            print("잘못된 선택입니다. 다시 시도하세요.")

if __name__ == "__main__":
    main()