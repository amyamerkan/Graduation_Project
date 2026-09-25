from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import PROJECT_ROOT, SETTINGS


def _print(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="vn-assistant", description="KG + RAG pipeline cho trợ lý ảo Việt Nam")
    commands = parser.add_subparsers(dest="command", required=True)

    kg = commands.add_parser("build-kg", help="Dựng RDF/OWL và CSV import Neo4j")
    kg.add_argument("--dataset", type=Path, default=SETTINGS.dataset_path)
    kg.add_argument("--limit", type=int, default=0)

    eval_kg = commands.add_parser("eval-kg", help="Đánh giá SPARQL bằng gold cases")
    eval_kg.add_argument("--gold", type=Path, default=PROJECT_ROOT / "evaluation/kg_gold.jsonl")

    train_router_parser = commands.add_parser("train-router", help="Train TF-IDF + Logistic Regression router")
    train_router_parser.add_argument("--train", type=Path, default=PROJECT_ROOT / "data/router_training.csv")

    eval_router_parser = commands.add_parser("eval-router", help="Đánh giá router")
    eval_router_parser.add_argument("--test", type=Path, default=PROJECT_ROOT / "evaluation/router_test.csv")

    faiss_parser = commands.add_parser("build-faiss", help="Chunking -> Transformer embedding -> cosine FAISS")
    faiss_parser.add_argument("--dataset", type=Path, default=SETTINGS.dataset_path)
    faiss_parser.add_argument("--model", default=SETTINGS.embedding_model)
    faiss_parser.add_argument("--device", default=SETTINGS.embedding_device)
    faiss_parser.add_argument("--batch-size", type=int, default=32)
    faiss_parser.add_argument("--chunk-size", type=int, default=900)
    faiss_parser.add_argument("--overlap", type=int, default=150)
    faiss_parser.add_argument("--limit-documents", type=int, default=0)
    faiss_parser.add_argument("--backend", choices=["transformer", "hashing"], default="transformer")

    query_parser = commands.add_parser("query", help="Chạy Question Processing Step 1 + Step 2")
    query_parser.add_argument("question")
    query_parser.add_argument("--top-k", type=int, default=SETTINGS.top_k)
    query_parser.add_argument("--backend", choices=["transformer", "hashing"], default="transformer")

    neo4j_parser = commands.add_parser("load-neo4j", help="Nạp nodes/relationships vào Neo4j")
    neo4j_parser.add_argument("--uri", default=SETTINGS.neo4j_uri)
    neo4j_parser.add_argument("--user", default=SETTINGS.neo4j_user)
    neo4j_parser.add_argument("--password", default=SETTINGS.neo4j_password)

    serve = commands.add_parser("serve", help="Khởi chạy FastAPI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if args.command == "build-kg":
        from .kg_builder import build_kg

        _print(build_kg(
            args.dataset, SETTINGS.ontology_path, SETTINGS.kg_ttl_path, SETTINGS.kg_owl_path,
            SETTINGS.kg_nodes_path, SETTINGS.kg_relationships_path,
            SETTINGS.kg_ttl_path.parent / "build_report.json", args.limit,
        ))
    elif args.command == "eval-kg":
        from .kg_evaluation import evaluate_kg

        _print(evaluate_kg(SETTINGS.kg_ttl_path, SETTINGS.query_dir, args.gold, SETTINGS.kg_ttl_path.parent / "evaluation_report.json"))
    elif args.command == "train-router":
        from .router import train_router

        _print(train_router(args.train, SETTINGS.router_model_path, SETTINGS.router_model_path.parent / "train_report.json"))
    elif args.command == "eval-router":
        from .router import evaluate_router

        _print(evaluate_router(SETTINGS.router_model_path, args.test, SETTINGS.router_model_path.parent / "evaluation_report.json"))
    elif args.command == "build-faiss":
        from .embedding import EmbeddingConfig
        from .faiss_store import build_faiss_index

        config = EmbeddingConfig(model_name=args.model, device=args.device, batch_size=args.batch_size)
        _print(build_faiss_index(
            args.dataset, SETTINGS.faiss_index_path, SETTINGS.faiss_metadata_path,
            SETTINGS.faiss_index_path.parent / "index_config.json", config,
            backend=args.backend, chunk_size=args.chunk_size, overlap=args.overlap,
            limit_documents=args.limit_documents,
        ))
    elif args.command == "query":
        from .embedding import EmbeddingConfig
        from .faiss_store import FaissRetriever
        from .question_processing import QuestionProcessor
        from .router import QuestionRouter
        from .sparql_service import SparqlService

        kg_service = SparqlService(SETTINGS.kg_ttl_path, SETTINGS.query_dir) if SETTINGS.kg_ttl_path.exists() else None
        faiss_service = None
        if SETTINGS.faiss_index_path.exists() and SETTINGS.faiss_metadata_path.exists():
            faiss_service = FaissRetriever(
                SETTINGS.faiss_index_path, SETTINGS.faiss_metadata_path,
                EmbeddingConfig(model_name=SETTINGS.embedding_model, device=SETTINGS.embedding_device),
                backend=args.backend,
            )
        _print(QuestionProcessor(QuestionRouter(SETTINGS.router_model_path), kg_service, faiss_service).process(args.question, args.top_k))
    elif args.command == "load-neo4j":
        from .neo4j_loader import load_neo4j

        _print(load_neo4j(SETTINGS.kg_nodes_path, SETTINGS.kg_relationships_path, args.uri, args.user, args.password))
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("vn_assistant.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()

