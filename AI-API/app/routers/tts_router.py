# app/routers/tts_router.py
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import base64
import os

from app.services.tts_service_model import TTSService  # 수정된 임포트 경로

router = APIRouter(tags=["TTS"])
tts_service = TTSService()

class TTSRequest(BaseModel):
    """TTS 요청 모델"""
    text: str = Field(..., description="변환할 텍스트")
    speaker_id: Optional[int] = Field(0, description="화자 ID (0: 여성, 1: 남성)")
    speed: Optional[float] = Field(1.2, description="음성 속도 (0.5-2.0)")
    pitch_adjustment: Optional[float] = Field(0.0, description="피치 조정 (-1.0-1.0)")
    energy_adjustment: Optional[float] = Field(1.0, description="에너지 조정 (0.1-2.0)")

@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """
    텍스트를 음성으로 변환하여 WAV 파일로 반환
    """
    try:
        # TTS 서비스를 통한 음성 생성
        result = await tts_service.synthesize(
            text=request.text,
            speaker_id=request.speaker_id,
            speed=request.speed,
            pitch_adjustment=request.pitch_adjustment,
            energy_adjustment=request.energy_adjustment
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "음성 합성 실패"))
        
        # 오디오 파일 반환
        return FileResponse(
            path=result['audio_path'], 
            media_type='audio/wav', 
            filename='synthesized_speech.wav'
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/synthesize_base64")
async def synthesize_speech_base64(request: TTSRequest):
    """
    텍스트를 Base64로 인코딩된 음성으로 변환
    """
    try:
        # TTS 서비스를 통한 음성 생성
        result = await tts_service.synthesize(
            text=request.text,
            speaker_id=request.speaker_id,
            speed=request.speed,
            pitch_adjustment=request.pitch_adjustment,
            energy_adjustment=request.energy_adjustment
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "음성 합성 실패"))
        
        # JSON 응답으로 반환
        return JSONResponse(content={
            "success": True,
            "audio_base64": result["audio_base64"],
            "duration": result["duration"],
            "sample_rate": result["sample_rate"]
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/synthesize")
async def synthesize_speech_get(
    text: str = Query(..., description="변환할 텍스트"),
    speaker_id: Optional[int] = Query(0, description="화자 ID (0: 여성, 1: 남성)"),
    speed: Optional[float] = Query(1.2, description="음성 속도 (0.5-2.0)"),
    format: Optional[str] = Query("wav", description="출력 형식 (wav 또는 base64)")
):
    """
    GET 요청으로 텍스트를 음성으로 변환
    """
    try:
        # TTS 서비스를 통한 음성 생성
        result = await tts_service.synthesize(
            text=text,
            speaker_id=speaker_id,
            speed=speed
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "음성 합성 실패"))
        
        # 요청된 형식에 따라 반환
        if format.lower() == "base64":
            return JSONResponse(content={
                "success": True,
                "audio_base64": result["audio_base64"],
                "duration": result["duration"],
                "sample_rate": result["sample_rate"]
            })
        else:
            return FileResponse(
                path=result['audio_path'], 
                media_type='audio/wav', 
                filename='synthesized_speech.wav'
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/speakers")
async def get_available_speakers():
    """사용 가능한 화자 목록 반환"""
    try:
        result = await tts_service.get_available_speakers()
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "화자 목록 조회 실패"))
        
        return JSONResponse(content={
            "success": True,
            "speakers": result["speakers"]
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/info")
async def get_model_info():
    """TTS 모델 정보 반환"""
    try:
        result = await tts_service.get_model_info()
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "모델 정보 조회 실패"))
        
        return JSONResponse(content={
            "success": True,
            "info": result["info"]
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))