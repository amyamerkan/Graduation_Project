from __future__ import annotations

from pathlib import Path
import threading
from typing import Any
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from typing import Literal

from .config import SETTINGS
from .embedding import EmbeddingConfig
from .faiss_store import FaissRetriever
from .llm import LLMConfig, LLMContextError, LLMError, create_generator
from .normalization import clean_text
from .question_processing import QuestionProcessor
from .router import QuestionRouter, extract_query_plan
from .sparql_service import SparqlService
from .dialogue import resolve_question
from .metadata_retriever import MetadataFaissRetriever
from .runtime import single_instance


app = FastAPI(
    title="VN Hybrid Assistant API",
    version="1.2.0",
    description="Question Processing -> KG / FAISS -> LLM -> Cross-check và minh chứng.",
)

_runtime_state = {"router_ready": False, "kg_ready": False, "faiss_ready": False}
_warmup_lock = threading.Lock()
_static_dir = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=_static_dir, check_dir=False), name="assets")


@app.get("/", include_in_schema=False)
def assistant_ui():
    return FileResponse(_static_dir / "index.html", headers={"Cache-Control": "no-cache"})


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = clean_text(value)
        if len(value) < 2:
            raise ValueError("Câu hỏi cần ít nhất 2 ký tự sau khi chuẩn hóa")
        return value


class RagRequest(QuestionRequest):
    domain: str | None = Field(default=None, pattern="^(law|administration|heritage|tourism)$")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(QuestionRequest):
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


@single_instance
def get_router() -> QuestionRouter:
    router = QuestionRouter(SETTINGS.router_model_path)
    _runtime_state["router_ready"] = True
    return router


@single_instance
def get_kg() -> SparqlService | None:
    if SETTINGS.kg_ttl_path.exists():
        service = SparqlService(SETTINGS.kg_ttl_path, SETTINGS.query_dir)
        _runtime_state["kg_ready"] = True
        return service
    return None


@single_instance
def get_faiss() -> FaissRetriever | MetadataFaissRetriever | None:
    if not SETTINGS.faiss_metadata_path.exists():
        return None
    config = EmbeddingConfig(model_name=SETTINGS.embedding_model, device=SETTINGS.embedding_device)
    retriever = FaissRetriever(SETTINGS.faiss_index_path, SETTINGS.faiss_metadata_path, config) if SETTINGS.faiss_index_path.exists() else MetadataFaissRetriever(SETTINGS.faiss_metadata_path, config)
    _runtime_state["faiss_ready"] = not isinstance(retriever, MetadataFaissRetriever)
    _runtime_state["retrieval_mode"] = getattr(retriever, "mode", "full_faiss")
    return retriever


class _LazyFaissRetriever:
    def search(self, question: str, **kwargs) -> list[dict[str, Any]]:
        retriever = get_faiss()
        if retriever is None:
            raise RuntimeError("FAISS index chưa sẵn sàng")
        result = retriever.search(question, **kwargs)
        _runtime_state["faiss_ready"] = True
        return result


@single_instance
def get_processor() -> QuestionProcessor:
    return QuestionProcessor(get_router(), get_kg(), _LazyFaissRetriever())


@single_instance
def get_generator():
    try:
        config = LLMConfig(
            backend=SETTINGS.llm_backend,
            model_name=SETTINGS.llm_model,
            device=SETTINGS.llm_device,
            max_new_tokens=SETTINGS.llm_max_new_tokens,
            context_window=SETTINGS.llm_context_window,
            timeout_s=SETTINGS.llm_timeout_s,
            base_url=SETTINGS.llm_base_url,
            api_key=SETTINGS.llm_api_key,
            local_files_only=SETTINGS.llm_local_files_only,
        )
        return create_generator(config)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"Cấu hình LLM không hợp lệ: {exc}") from exc


@single_instance
def get_answer_service():
    from .generation import AnswerService

    try:
        return AnswerService(
            get_processor(), get_generator(), max_evidence=SETTINGS.answer_max_evidence,
            min_rag_score=SETTINGS.answer_min_rag_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"Cấu hình trả lời không hợp lệ: {exc}") from exc


def warmup_generator(generator) -> dict[str, Any]:
    load = getattr(generator, "load", None)
    probe = getattr(generator, "probe", None)
    if callable(load):
        return load()
    if callable(probe):
        return probe()
    raise LLMError("Backend LLM không hỗ trợ warmup")


@app.get("/health")
def health(generator=Depends(get_generator)) -> dict[str, Any]:
    return {
        "status": "ok",
        **_runtime_state,
        "artifacts_present": {
            "router": SETTINGS.router_model_path.exists(),
            "kg": SETTINGS.kg_ttl_path.exists(),
            "faiss": SETTINGS.faiss_index_path.exists() and SETTINGS.faiss_metadata_path.exists(),
        },
        "llm": generator.status(),
        "retrieval_mode": _runtime_state.get("retrieval_mode") or ("full_faiss" if SETTINGS.faiss_index_path.exists() else "lexical_candidates_faiss" if SETTINGS.faiss_metadata_path.exists() else "unavailable"),
        "capabilities": {"unit_at_date": True, "unit_in_province_at_date": True, "geometry_distance": False, "citation_verification": "evidence_match"},
    }


@app.post("/v1/classify")
def classify(request: QuestionRequest, router=Depends(get_router)) -> dict[str, Any]:
    try:
        result = router.classify(request.question)
        plan = extract_query_plan(result.question, result)
        if plan["rag"]:
            plan["rag"]["top_k"] = request.top_k
        return {"classification": result.to_dict(), "plan": plan}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/rag/search")
def rag_search(request: RagRequest, retriever=Depends(get_faiss)) -> dict[str, Any]:
    if retriever is None:
        raise HTTPException(status_code=503, detail="FAISS index chưa sẵn sàng")
    try:
        return {"results": retriever.search(request.question, request.top_k, request.domain)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/query")
def query(request: QuestionRequest, processor=Depends(get_processor)) -> dict[str, Any]:
    try:
        return processor.process(request.question, request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/answer")
def answer(request: QuestionRequest, service=Depends(get_answer_service)) -> dict[str, Any]:
    try:
        return service.answer(request.question, top_k=request.top_k)
    except LLMContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/llm/status")
def llm_status(generator=Depends(get_generator)) -> dict[str, Any]:
    return generator.status()


@app.post("/v1/chat")
def chat(request: ChatRequest, service=Depends(get_answer_service)) -> dict[str, Any]:
    resolution = resolve_question(request.question, [turn.model_dump() for turn in request.history])
    if resolution["needs_context"]:
        return {"question": request.question, "status": "needs_clarification",
                "answer": "Bạn muốn hỏi về đơn vị hoặc di sản nào? Hãy cho mình tên đầy đủ hoặc mã đơn vị nhé.",
                "claims": [], "citations": [], "warnings": ["missing_conversation_context"],
                "cross_check": {"status": "insufficient_evidence", "supported_count": 0}, "timings_ms": {"total": 0},
                "context_resolution": resolution}
    try:
        result = service.answer(resolution["question"], top_k=request.top_k)
        result["original_question"] = request.question
        result["context_resolution"] = resolution
        result["retrieval_mode"] = _runtime_state.get("retrieval_mode") or ("full_faiss" if SETTINGS.faiss_index_path.exists() else "lexical_candidates_faiss")
        return result
    except LLMContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/llm/warmup")
def llm_warmup(generator=Depends(get_generator)) -> dict[str, Any]:
    try:
        return warmup_generator(generator)
    except LLMContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/system/warmup")
def system_warmup(generator=Depends(get_generator)) -> dict[str, Any]:
    started = perf_counter()
    try:
        with _warmup_lock:
            if get_kg() is None:
                raise HTTPException(status_code=503, detail="KG chưa sẵn sàng")
            retriever = get_faiss()
            if retriever is None:
                raise HTTPException(status_code=503, detail="Dữ liệu truy xuất chưa sẵn sàng")
            if not _runtime_state["faiss_ready"]:
                if hasattr(retriever, "warmup"):
                    retriever.warmup()
                retriever.encoder.encode_queries(["Thông tin di sản văn hóa Việt Nam"])
                _runtime_state["faiss_ready"] = True
            status = warmup_generator(generator)
            return {"status": "ready", "llm": status, "kg_ready": True, "rag_ready": True,
                    "elapsed_ms": round((perf_counter() - started) * 1000, 3)}
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (RuntimeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Chưa chuẩn bị được mô hình hoặc dữ liệu truy xuất") from exc
