from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import SETTINGS
from .embedding import EmbeddingConfig
from .faiss_store import FaissRetriever
from .question_processing import QuestionProcessor
from .router import QuestionRouter, extract_query_plan
from .sparql_service import SparqlService


app = FastAPI(
    title="VN Hybrid Assistant Retrieval API",
    version="1.0.0",
    description="API tầng tri thức: Question Router -> Knowledge Graph / FAISS RAG.",
)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RagRequest(QuestionRequest):
    domain: str | None = Field(default=None, pattern="^(law|administration|heritage|tourism)$")


@lru_cache(maxsize=1)
def get_router() -> QuestionRouter:
    return QuestionRouter(SETTINGS.router_model_path)


@lru_cache(maxsize=1)
def get_kg() -> SparqlService | None:
    if SETTINGS.kg_ttl_path.exists():
        return SparqlService(SETTINGS.kg_ttl_path, SETTINGS.query_dir)
    return None


@lru_cache(maxsize=1)
def get_faiss() -> FaissRetriever | None:
    if not (SETTINGS.faiss_index_path.exists() and SETTINGS.faiss_metadata_path.exists()):
        return None
    config = EmbeddingConfig(model_name=SETTINGS.embedding_model, device=SETTINGS.embedding_device)
    return FaissRetriever(SETTINGS.faiss_index_path, SETTINGS.faiss_metadata_path, config)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "router_ready": SETTINGS.router_model_path.exists(),
        "kg_ready": SETTINGS.kg_ttl_path.exists(),
        "faiss_ready": SETTINGS.faiss_index_path.exists() and SETTINGS.faiss_metadata_path.exists(),
    }


@app.post("/v1/classify")
def classify(request: QuestionRequest) -> dict[str, Any]:
    result = get_router().classify(request.question)
    return {"classification": result.to_dict(), "plan": extract_query_plan(request.question, result)}


@app.post("/v1/rag/search")
def rag_search(request: RagRequest) -> dict[str, Any]:
    retriever = get_faiss()
    if retriever is None:
        raise HTTPException(status_code=503, detail="FAISS index chưa sẵn sàng")
    return {"results": retriever.search(request.question, request.top_k, request.domain)}


@app.post("/v1/query")
def query(request: QuestionRequest) -> dict[str, Any]:
    processor = QuestionProcessor(get_router(), get_kg(), get_faiss())
    try:
        return processor.process(request.question, request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

