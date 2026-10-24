from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent if (PROJECT_ROOT.parent / "data").is_dir() else PROJECT_ROOT

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass


def _path(name: str, default: str) -> Path:
    value = os.getenv(name)
    if value is None:
        return WORKSPACE_ROOT / default if default.startswith(("data/", "artifacts/", "models/")) else PROJECT_ROOT / default
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _model_name() -> str:
    value = os.getenv("LLM_MODEL")
    if value is None:
        return str(WORKSPACE_ROOT / "models/Qwen3-0.6B")
    return str((PROJECT_ROOT / value).resolve()) if value.startswith((".", "/")) else value


@dataclass(frozen=True)
class Settings:
    dataset_path: Path = _path("DATASET_PATH", "data/structured_records.jsonl")
    ontology_path: Path = _path("ONTOLOGY_PATH", "ontology/vn_heritage_admin.ttl")
    query_dir: Path = _path("QUERY_DIR", "queries")
    kg_ttl_path: Path = _path("KG_TTL_PATH", "artifacts/kg/vn_knowledge_graph.ttl")
    kg_owl_path: Path = _path("KG_OWL_PATH", "artifacts/kg/vn_knowledge_graph.owl")
    kg_nodes_path: Path = _path("KG_NODES_PATH", "artifacts/kg/nodes.csv")
    kg_relationships_path: Path = _path("KG_RELATIONSHIPS_PATH", "artifacts/kg/relationships.csv")
    faiss_index_path: Path = _path("FAISS_INDEX_PATH", "artifacts/faiss/vn.index")
    faiss_metadata_path: Path = _path("FAISS_METADATA_PATH", "artifacts/faiss/metadata.sqlite3")
    router_model_path: Path = _path("ROUTER_MODEL_PATH", "artifacts/router/router.joblib")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    top_k: int = int(os.getenv("TOP_K", "5"))
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "change-me")
    llm_backend: str = os.getenv("LLM_BACKEND", "transformers")
    llm_model: str = _model_name()
    llm_device: str = os.getenv("LLM_DEVICE", "auto")
    llm_max_new_tokens: int = int(os.getenv("LLM_MAX_NEW_TOKENS", "384"))
    llm_context_window: int = int(os.getenv("LLM_CONTEXT_WINDOW", "4096"))
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_S", "60"))
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8002/v1")
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_local_files_only: bool = os.getenv("LLM_LOCAL_FILES_ONLY", "true").lower() in {"1", "true", "yes"}
    answer_max_evidence: int = int(os.getenv("ANSWER_MAX_EVIDENCE", "6"))
    answer_min_rag_score: float = float(os.getenv("ANSWER_MIN_RAG_SCORE", "0.70"))


SETTINGS = Settings()
