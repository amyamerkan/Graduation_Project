"""Run the reproducible local pipeline except the optional Neo4j server import."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vn_assistant.config import PROJECT_ROOT, SETTINGS
from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import build_faiss_index
from vn_assistant.kg_builder import build_kg
from vn_assistant.kg_evaluation import evaluate_kg
from vn_assistant.router import evaluate_router, train_router


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--skip-faiss", action="store_true")
    parser.add_argument("--limit-documents", type=int, default=0)
    parser.add_argument("--device", default=SETTINGS.embedding_device)
    args = parser.parse_args()

    reports = {}
    reports["kg_build"] = build_kg(
        args.dataset, SETTINGS.ontology_path, SETTINGS.kg_ttl_path, SETTINGS.kg_owl_path,
        SETTINGS.kg_nodes_path, SETTINGS.kg_relationships_path,
        SETTINGS.kg_ttl_path.parent / "build_report.json",
    )
    reports["kg_evaluation"] = evaluate_kg(
        SETTINGS.kg_ttl_path, SETTINGS.query_dir, PROJECT_ROOT / "evaluation/kg_gold.jsonl",
        SETTINGS.kg_ttl_path.parent / "evaluation_report.json",
    )
    reports["router_train"] = train_router(
        SETTINGS.dataset_path.parent / "router_training.csv", SETTINGS.router_model_path,
        SETTINGS.router_model_path.parent / "train_report.json",
    )
    reports["router_evaluation"] = evaluate_router(
        SETTINGS.router_model_path, PROJECT_ROOT / "evaluation/router_test.csv",
        SETTINGS.router_model_path.parent / "evaluation_report.json",
    )
    if not args.skip_faiss:
        reports["faiss"] = build_faiss_index(
            args.dataset, SETTINGS.faiss_index_path, SETTINGS.faiss_metadata_path,
            SETTINGS.faiss_index_path.parent / "index_config.json",
            EmbeddingConfig(model_name=SETTINGS.embedding_model, device=args.device),
            limit_documents=args.limit_documents,
        )
    output = SETTINGS.kg_ttl_path.parent.parent / "pipeline_report.json"
    output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

