# main.py

from fastapi import FastAPI
from router.cafe_router import router

app = FastAPI(title="☕ Cafe RAG API")
app.include_router(router)
