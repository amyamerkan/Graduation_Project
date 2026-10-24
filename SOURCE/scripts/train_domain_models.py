import csv
import json
from pathlib import Path

import joblib

from vn_assistant.config import SETTINGS, WORKSPACE_ROOT
from vn_assistant.dataio import iter_records
from vn_assistant.kg_builder import build_kg
from vn_assistant.router import evaluate_router, train_router


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["question", "route", "domain"])
        writer.writeheader()
        writer.writerows(rows)


def training_rows(records):
    rows = []
    for record in records:
        data = record["data"]
        name = data["name"]
        if record["record_type"] == "administrative_snapshot" and data["snapshot"] == "current" and (data["level"] == "province" or int(data["code"]) % 47 == 0):
            patterns = [(f"Mã {data['code']} thuộc tỉnh nào?", "kg"), (f"{name} có mã hành chính gì?", "kg"),
                        (f"Tra cứu tên đơn vị có mã {data['code']}.", "kg"), (f"Giới thiệu danh mục hành chính của {name}.", "rag"),
                        (f"Mô tả thông tin đơn vị {name} trong dữ liệu.", "rag"),
                        (f"{name} thuộc tỉnh nào và giới thiệu thông tin đơn vị.", "hybrid")]
        elif record["record_type"] == "administrative_conversion" and data["level"] == "province":
            patterns = [(f"{data['old_name']} sáp nhập vào đâu?", "kg"),
                        (f"{data['old_name']} sắp xếp như thế nào và thuộc tỉnh nào?", "hybrid")]
        elif record["record_type"] == "tourism_place":
            patterns = [(f"Giới thiệu {name}.", "rag"), (f"Tham quan {name} có gì đặc sắc?", "rag"),
                        (f"Mô tả trải nghiệm du lịch tại {name}.", "rag"), (f"{name} nằm ở đâu?", "kg"),
                        (f"Địa chỉ của {name} là gì?", "kg"),
                        (f"{name} thuộc tỉnh nào và có gì đáng chú ý?", "hybrid"),
                        (f"Các điểm du lịch nào ở {data['province_name']}?", "kg")]
        else:
            continue
        rows.extend({"question": question, "route": route, "domain": record["domain"]} for question,route in patterns)
    return list({row["question"]: row for row in rows}.values())


if __name__ == "__main__":
    records = list(iter_records(SETTINGS.dataset_path))
    kg_report = build_kg(SETTINGS.dataset_path, SETTINGS.ontology_path, SETTINGS.kg_ttl_path,
                         SETTINGS.kg_owl_path, SETTINGS.kg_nodes_path, SETTINGS.kg_relationships_path,
                         SETTINGS.kg_ttl_path.parent / "build_report.json")
    test_path = Path(__file__).resolve().parents[1] / "evaluation/router_test.csv"
    with test_path.open(encoding="utf-8", newline="") as stream:
        test_questions = {row["question"].casefold().strip() for row in csv.DictReader(stream)}
    rows = [row for row in training_rows(records) if row["question"].casefold().strip() not in test_questions]
    train_path = WORKSPACE_ROOT / "data/router_training.csv"
    write_csv(train_path, rows)
    train_report = train_router(train_path, SETTINGS.router_model_path, SETTINGS.router_model_path.parent / "train_report.json")
    artifact = joblib.load(SETTINGS.router_model_path)
    artifact["tourism_entities"] = sorted({r["data"]["name"] for r in records if r["record_type"] == "tourism_place"})
    aliases = ["Hội An", "Mỹ Sơn", "Hạ Long", "Sa Pa", "Phú Quốc", "Nha Trang", "Đà Lạt", "Phong Nha", "Cát Bà", "Côn Đảo"]
    artifact["tourism_aliases"] = {alias:[name for name in artifact["tourism_entities"] if alias.casefold() in name.casefold()] for alias in aliases}
    artifact["tourism_aliases"]["Hồ Gươm"] = [name for name in artifact["tourism_entities"] if name == "Hồ Hoàn Kiếm"]
    artifact["dataset_scope"] = "administrative snapshots and Vietnam tourism, 2026-10-24"
    joblib.dump(artifact, SETTINGS.router_model_path)
    evaluation = evaluate_router(SETTINGS.router_model_path, test_path,
                                  SETTINGS.router_model_path.parent / "evaluation_report.json")
    output = {"kg": kg_report, "router_train": train_report,
              "router_evaluation": {key: evaluation[key] for key in ("cases", "route_accuracy", "domain_accuracy", "joint_accuracy")},
              "evaluation_scope": "Manually written development queries; not an independent public benchmark",
              "embedding": "Re-encode with pretrained multilingual-e5-base; no embedding/LLM weight fine-tuning"}
    (WORKSPACE_ROOT / "artifacts/domain_retrain_report.json").write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(json.dumps(output, ensure_ascii=False, indent=2))
