"""Build KG and retrain the router inside an isolated corpus release directory."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import joblib

from train_domain_models import training_rows, write_csv
from vn_assistant.config import PROJECT_ROOT, SETTINGS
from vn_assistant.dataio import iter_records
from vn_assistant.kg_builder import build_kg
from vn_assistant.kg_evaluation import evaluate_kg
from vn_assistant.router import train_router, evaluate_router


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    args = parser.parse_args()
    root = args.release.resolve()
    kg, router = root / "artifacts/kg", root / "artifacts/router"
    kg.mkdir(parents=True, exist_ok=True)
    router.mkdir(parents=True, exist_ok=True)
    records = list(iter_records(root / "data/structured_records.jsonl"))
    report = {"created_at": datetime.now(timezone.utc).isoformat(),
              "training_scope": "Retrain TF-IDF/Logistic Regression router; pretrained E5/Qwen weights unchanged"}
    report["kg"] = build_kg(root / "data/structured_records.jsonl", SETTINGS.ontology_path,
                            kg / "vn_knowledge_graph.ttl", kg / "vn_knowledge_graph.owl", kg / "nodes.csv",
                            kg / "relationships.csv", kg / "build_report.json")
    test = PROJECT_ROOT / "evaluation/router_test.csv"
    with test.open(encoding="utf-8", newline="") as stream:
        excluded = {r["question"].strip().casefold() for r in csv.DictReader(stream)}
    rows = [r for r in training_rows(records) if r["question"].strip().casefold() not in excluded]
    write_csv(root / "data/router_training.csv", rows)
    report["router_train"] = train_router(root / "data/router_training.csv", router / "router.joblib", router / "train_report.json")
    artifact = joblib.load(router / "router.joblib")
    names = sorted({r["data"]["name"] for r in records if r["record_type"] == "tourism_place"})
    aliases = ["Hội An", "Mỹ Sơn", "Hạ Long", "Sa Pa", "Phú Quốc", "Nha Trang", "Đà Lạt", "Phong Nha", "Cát Bà", "Côn Đảo"]
    artifact.update({"tourism_entities": names,
                     "tourism_aliases": {a: [n for n in names if a.casefold() in n.casefold()] for a in aliases},
                     "dataset_scope": "administration and Vietnam tourism; intangible-heritage content excluded",
                     "trained_at": report["created_at"]})
    artifact["tourism_aliases"]["Hồ Gươm"] = [n for n in names if n == "Hồ Hoàn Kiếm"]
    joblib.dump(artifact, router / "router.joblib")
    r = evaluate_router(router / "router.joblib", test, router / "evaluation_report.json")
    report["router_evaluation"] = {k: r[k] for k in ("cases", "route_accuracy", "domain_accuracy", "joint_accuracy", "model_without_rules")}
    r = evaluate_kg(kg / "vn_knowledge_graph.ttl", SETTINGS.query_dir, PROJECT_ROOT / "evaluation/kg_gold.jsonl", kg / "evaluation_report.json")
    report["kg_evaluation"] = {k: v for k, v in r.items() if k != "details"}
    (root / "training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
