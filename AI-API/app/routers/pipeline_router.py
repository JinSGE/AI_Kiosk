from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import Response
from typing import Dict, Any
from pydantic import BaseModel
from app.services.pipeline_service import PipelineService

router = APIRouter()
pipeline_service = PipelineService()

# 텍스트 쿼리 요청 모델
class TextQueryRequest(BaseModel):
    text: str
    retrieve_docs: bool = True

@router.post("/process_audio")
async def process_audio_query(audio: UploadFile = File(...)):
    """음성 쿼리 처리 파이프라인 API 엔드포인트 (STT -> NLP/RAG -> TTS)"""
    try:
        # 오디오 데이터 읽기
        audio_data = await audio.read()
        
        # 파이프라인 실행
        result = await pipeline_service.process_audio_query(audio_data)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"파이프라인 실패 (단계: {result.get('stage')}): {result.get('error')}"
            )
        
        # 오디오 바이트 반환
        return Response(
            content=result["audio"],
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=response.wav",
                "X-Query-Text": result["query"],
                "X-Response-Text": result["response_text"]
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_text")
async def process_text_query(request: TextQueryRequest):
    """텍스트 쿼리 처리 파이프라인 API 엔드포인트 (NLP/RAG -> TTS)"""
    try:
        # 파이프라인 실행
        result = await pipeline_service.process_text_query(request.text)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"파이프라인 실패 (단계: {result.get('stage')}): {result.get('error')}"
            )
        
        # 오디오 바이트 반환
        return Response(
            content=result["audio"],
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=response.wav",
                "X-Query-Text": result["query"],
                "X-Response-Text": result["response_text"]
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_audio_with_details", response_model=Dict[str, Any])
async def process_audio_query_with_details(audio: UploadFile = File(...)):
    """음성 쿼리 처리 파이프라인 API 엔드포인트 (상세 정보 포함)"""
    try:
        # 오디오 데이터 읽기
        audio_data = await audio.read()
        
        # 파이프라인 실행
        result = await pipeline_service.process_audio_query(audio_data)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"파이프라인 실패 (단계: {result.get('stage')}): {result.get('error')}"
            )
        
        # 오디오 데이터를 base64로 인코딩하여 JSON 응답에 포함
        import base64
        audio_base64 = base64.b64encode(result["audio"]).decode("utf-8")
        
        # 상세 정보 반환
        return {
            "success": True,
            "audio_base64": audio_base64,
            "query": result["query"],
            "response_text": result["response_text"],
            "documents": result["documents"],
            "processing_info": result.get("processing_info", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_text_with_details", response_model=Dict[str, Any])
async def process_text_query_with_details(request: TextQueryRequest):
    """텍스트 쿼리 처리 파이프라인 API 엔드포인트 (상세 정보 포함)"""
    try:
        # 파이프라인 실행
        result = await pipeline_service.process_text_query(request.text)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"파이프라인 실패 (단계: {result.get('stage')}): {result.get('error')}"
            )
        
        # 오디오 데이터를 base64로 인코딩하여 JSON 응답에 포함
        import base64
        audio_base64 = base64.b64encode(result["audio"]).decode("utf-8")
        
        response_data = {
            "success": True,
            "audio_base64": audio_base64,
            "query": result["query"],
            "response_text": result["response_text"],
        }
        
        # 문서 검색 결과 포함 여부 결정
        if request.retrieve_docs:
            response_data["documents"] = result["documents"]
        
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """상태 확인 엔드포인트"""
    return {"status": "ok"}