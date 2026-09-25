from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _path(name: str, default: str) -> Path:
    value = os.getenv(name, default)
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    dataset_path: Path = _path("DATASET_PATH", "data/vn_complete_dataset.json")
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


SETTINGS = Settings()

