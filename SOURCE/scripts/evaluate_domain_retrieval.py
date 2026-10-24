"""Evaluate the current two-domain corpus with explicit known-positive records."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from vn_assistant.dataio import iter_records
from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import FaissRetriever
from vn_assistant.domain_scope import contains_intangible


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    records = list(iter_records(args.release / "data/structured_records.jsonl"))
    cases = []
    for code, snapshot, question in [
        ("00070", "legacy", "Tra cứu mã 00070 Phường Hàng Trống trong danh mục trước sắp xếp tháng 7/2025."),
        ("00070", "reorganized2025", "Danh mục sau sắp xếp năm 2025 ghi mã phường Hoàn Kiếm thế nào?"),
        ("22", "current", "Danh mục thu thập ngày 2026-10-24 ghi đơn vị có mã 22 là gì?"),
        ("24", "current", "Tra cứu mã hành chính 24 của Bắc Ninh theo danh mục thu thập 2026-10-24."),
        ("31261", "current", "Xã Cờ Đỏ có mã số 31261 trong danh mục hành chính hiện tại."),
    ]:
        row = next(r for r in records if r["record_type"] == "administrative_snapshot" and
                   r["data"]["code"] == code and r["data"]["snapshot"] == snapshot)
        cases.append({"question": question, "domain": "administration", "relevant_doc_ids": [row["record_id"]]})
    for code in ["00004", "00008", "07294", "26368"]:
        row = next(r for r in records if r["record_type"] == "administrative_reference" and r["data"]["code"] == code)
        cases.append({"question": f"Bảng đối chiếu Cục Thống kê ghi chú thay đổi {row['data']['name']} mã {code} như thế nào?",
                      "domain": "administration", "relevant_doc_ids": [row["record_id"]]})
    for name, question in [
        ("Hồ Hoàn Kiếm", "Tìm thông tin tham quan Hồ Hoàn Kiếm tại Hà Nội."),
        ("Văn Miếu - Quốc Tử Giám", "Tìm hiểu kiến trúc và tham quan Văn Miếu - Quốc Tử Giám."),
        ("Khu phố cổ Hội An", "Tại khu phố cổ Hội An du khách có thể tham quan và trải nghiệm điều gì?"),
        ("Vịnh Hạ Long", "Tìm thông tin vị trí của Vịnh Hạ Long ở Quảng Ninh."),
        ("Động Phong Nha", "Khám phá cảnh quan thiên nhiên ở Động Phong Nha."),
        ("Vịnh Nha Trang", "Giới thiệu cảnh quan của Vịnh Nha Trang cho khách tham quan."),
        ("Quần đảo Cát Bà", "Du lịch khám phá thiên nhiên Quần đảo Cát Bà."),
    ]:
        matches = [r for r in records if r["record_type"] == "tourism_place" and r["data"]["name"] == name]
        if not matches:
            raise ValueError("Missing benchmark destination " + name)
        cases.append({"question": question, "domain": "tourism", "relevant_doc_ids": [r["record_id"] for r in matches]})
    index_dir = args.release / "artifacts/faiss"
    retriever = FaissRetriever(index_dir / "vn.index", index_dir / "metadata.sqlite3", EmbeddingConfig(device=args.device))
    details = []
    for case in cases:
        rows = retriever.search(case["question"], top_k=5, domain=case["domain"])
        # Evaluate distinct documents, not multiple chunks from the same destination.
        ids = list(dict.fromkeys(r["doc_id"] for r in rows))
        rank = next((i for i, doc_id in enumerate(ids, 1) if doc_id in case["relevant_doc_ids"]), None)
        details.append({**case, "rank": rank, "retrieved_doc_ids": ids,
                        "domain_integrity": all(r["domain"] == case["domain"] for r in rows),
                        "excluded_subject_free": not any(contains_intangible(r["text"]) for r in rows)})
    n = len(details)
    report = {"created_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Development known-positive retrieval set for current corpus; manually authored, not an independent factual benchmark.",
              "metric_scope": "Distinct documents within five retrieved chunks; known positives, unjudged alternatives may also be relevant.",
              "mode": "full_faiss", "cases": n,
              "hit_at_1": sum(r["rank"] == 1 for r in details) / n,
              "known_positive_hit_at_5": sum(r["rank"] is not None for r in details) / n,
              "mrr_at_5": sum(1/r["rank"] for r in details if r["rank"]) / n,
              "domain_integrity": all(r["domain_integrity"] for r in details),
              "excluded_subject_free": all(r["excluded_subject_free"] for r in details), "details": details}
    (args.release / "retrieval_evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (args.release / "retrieval_gold.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in cases) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
