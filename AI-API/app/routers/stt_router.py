# app/routers/stt_router.py
from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Query
from fastapi.responses import JSONResponse
from typing import Optional
import base64
import tempfile
import os

from app.services.stt_service_model import STTService  # 수정된 임포트 경로

router = APIRouter(tags=["STT"])
stt_service = STTService()

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    return_timestamps: Optional[bool] = Form(False)
):
    """
    오디오 파일을 텍스트로 변환하는 엔드포인트
    
    Args:
        file: 업로드된 오디오 파일
        return_timestamps: 단어별 타임스탬프 반환 여부
    """
    try:
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name
        
        try:
            # STT 서비스를 통한 변환
            result = await stt_service.transcribe(temp_file_path)
            
            if not result["success"]:
                raise HTTPException(status_code=500, detail=result.get("error", "음성 인식 실패"))
            
            # 결과 반환
            response = {
                "success": True,
                "text": result.get("text", ""),
                "language": result.get("language", "ko"),
                "duration": result.get("duration", 0.0),
                "confidence": result.get("confidence", 1.0)
            }
            
            # 타임스탬프 요청 시 포함
            if return_timestamps and "timestamps" in result:
                response["timestamps"] = result["timestamps"]
            
            return JSONResponse(content=response)
        
        finally:
            # 임시 파일 삭제
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except Exception as e:
                pass  # 파일 삭제 실패는 무시
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribe_base64")
async def transcribe_base64_audio(
    audio_base64: str = Form(...),
    return_timestamps: Optional[bool] = Form(False)
):
    """
    Base64로 인코딩된 오디오 데이터를 텍스트로 변환
    
    Args:
        audio_base64: Base64 인코딩된 오디오 데이터
        return_timestamps: 단어별 타임스탬프 반환 여부
    """
    try:
        # Base64 디코딩
        if "base64," in audio_base64:
            audio_base64 = audio_base64.split("base64,")[1]
        
        audio_data = base64.b64decode(audio_base64)
        
        # STT 서비스를 통한 변환
        result = await stt_service.transcribe(audio_data)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "음성 인식 실패"))
        
        # 결과 반환
        response = {
            "success": True,
            "text": result.get("text", ""),
            "language": result.get("language", "ko"),
            "duration": result.get("duration", 0.0),
            "confidence": result.get("confidence", 1.0)
        }
        
        # 타임스탬프 요청 시 포함
        if return_timestamps and "timestamps" in result:
            response["timestamps"] = result["timestamps"]
        
        return JSONResponse(content=response)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/record")
async def record_and_transcribe(
    duration: Optional[int] = Query(5, description="녹음 시간(초)")
):
    """
    마이크로 녹음 후 텍스트로 변환
    
    Args:
        duration: 녹음 시간(초)
    """
    try:
        # 마이크 녹음 및 음성 인식
        result = await stt_service.record_and_transcribe(duration=duration)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "마이크 녹음 또는 인식 실패"))
        
        # 결과 반환
        return JSONResponse(content={
            "success": True,
            "text": result.get("text", ""),
            "language": result.get("language", "ko"),
            "duration": result.get("duration", 0.0),
            "confidence": result.get("confidence", 1.0)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))