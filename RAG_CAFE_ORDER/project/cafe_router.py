# router/cafe_router.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
from service.response_service import generate_response
from nlp.nlp_processor import extract_keywords

router = APIRouter()

class Query(BaseModel):
    user_input: str

@router.post("/query")
async def handle_query(query: Query):
    tokens = extract_keywords(query.user_input)
    response = generate_response(query.user_input, tokens)
    return {"response": response}
