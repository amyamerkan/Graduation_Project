"""Merge reviewed raw additions into a separate, sanitized corpus version."""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from vn_assistant.corpus_update import document_from_record, write_jsonl
from vn_assistant.dataio import iter_records
from vn_assistant.domain_scope import contains_intangible, sanitize_tourism_record


def prepare(root, raw, output):
    root, raw, output = map(Path, (root, raw, output))
    target = output / "data"
    target.mkdir(parents=True, exist_ok=True)
    previous = list(iter_records(root / "data/structured_records.jsonl"))
    before = {r["record_id"] for r in previous}
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "before_documents": len(previous),
              "scope": "Vietnam administrative geography and visitor destinations; no intangible-heritage QA",
              "filtered": [], "official_matches": Counter(), "official_corrections": []}
    official = json.loads((raw / "official_admin_report.json").read_text())
    observed_date = datetime.strptime(official["observed_date"], "%d/%m/%Y").date().isoformat()
    current_dates = {r["data"]["snapshot_date"] for r in previous if r.get("record_type") == "administrative_snapshot" and r["data"].get("snapshot") == "current"}
    if current_dates != {observed_date}:
        raise ValueError("Official observed date differs from the current snapshot; prepare an explicitly dated snapshot before merging")
    references = list(iter_records(raw / "official_admin_references.jsonl"))
    if len(references) != 3321:
        raise ValueError("Official administrative comparison must be complete")
    current = {p["code"]: p for p in official["current_provinces"]}
    baseline = {p["code"]: p for p in official["baseline_provinces"]}
    wards = {r["data"]["code"]: r["data"] for r in references}
    records = {}
    for original in previous:
        row = copy.deepcopy(original)
        if row.get("domain") not in {"administration", "tourism"}:
            report["filtered"].append({"record_id": row["record_id"], "reason": "inactive_domain"})
            continue
        if row["record_type"] == "administrative_snapshot":
            data = row["data"]
            match, source = None, None
            if data["level"] == "province":
                if data["snapshot"] == "current":
                    match, source = current.get(data["code"]), official["current_source"]
                elif data["snapshot"] == "reorganized2025":
                    match, source = baseline.get(data["code"]), official["baseline_source"]
            elif data["level"] == "ward" and data["snapshot"] == "current":
                match, source = wards.get(data["code"]), official["comparison_source"]
                if match and match["province_code"] != data["province_code"]:
                    raise ValueError("Official current ward/province code mismatch")
            if match:
                if match["name"] != data["name"]:
                    correction = {"code": data["code"], "previous_name": data["name"], "official_name": match["name"],
                                  "snapshot": data["snapshot"], "source_url": source}
                    report["official_corrections"].append(correction)
                    data["description"] = data["description"].replace(data["name"], match["name"])
                    data["name"] = match["name"]
                    if data["level"] == "ward":
                        data["division_type"] = next((kind for prefix, kind in [("Phường ", "phường"), ("Xã ", "xã"), ("Đặc khu ", "đặc khu")]
                                                     if match["name"].startswith(prefix)), data["division_type"])
                    data["previous_catalogue_name"] = correction["previous_name"]
                data["source_audit"] = {"original_source_name": row["source_name"], "original_source_url": row["source_url"],
                                         "checked_at": report["created_at"], "matched_fields": ["code", "name"],
                                         "scope": "official table field match; not independent verification of every legal change"}
                if data["level"] == "ward":
                    data["source_audit"]["matched_fields"].append("province_code")
                row["source_name"] = "Cục Thống kê — danh mục ĐVHC" if data["snapshot"] == "current" else "Báo Điện tử Chính phủ — danh mục 2025"
                row["source_url"] = source
                report["official_matches"][data["snapshot"] + ":" + data["level"]] += 1
        records[row["record_id"]] = row
    # Refresh original destinations as well as incorporating new URLs.
    additions = list(iter_records(raw / "tourism.jsonl"))
    destination_ids = {r["source_url"]: r["record_id"] for r in previous if r.get("record_type") == "tourism_place"}
    for row in additions:
        if row["source_url"] in destination_ids:
            row["record_id"] = destination_ids[row["source_url"]]
        records[row["record_id"]] = row
    for row in references:
        records[row["record_id"]] = row
    cleaned = []
    for row in records.values():
        if row["domain"] == "tourism":
            result, audit = sanitize_tourism_record(row)
            if audit["removed_sentences"] or result is None:
                report["filtered"].append(audit)
            if result is None:
                continue
            row = result
        if contains_intangible(json.dumps(row.get("data", {}), ensure_ascii=False)):
            raise ValueError("Excluded subject remains in retained record " + row["record_id"])
        cleaned.append(row)
    if len({r["record_id"] for r in cleaned}) != len(cleaned):
        raise ValueError("Duplicate corpus identities")
    documents = [document_from_record(row) for row in cleaned]
    write_jsonl(target / "structured_records.jsonl", cleaned)
    write_jsonl(target / "rag_dataset_final.jsonl", documents)
    report.update({"after_documents": len(cleaned), "added_documents": sum(r["record_id"] not in before for r in cleaned),
                   "documents_by_domain": dict(Counter(r["domain"] for r in cleaned)),
                   "record_types": dict(Counter(r["record_type"] for r in cleaned)),
                   "removed_sentences": sum(r["removed_sentences"] for r in report["filtered"] if "removed_sentences" in r),
                   "excluded_subject_matches_in_active_data": 0,
                   "rag_sha256": hashlib.sha256((target / "rag_dataset_final.jsonl").read_bytes()).hexdigest()})
    report["official_matches"] = dict(report["official_matches"])
    (output / "corpus_refresh_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.root, args.raw, args.output)
    print(json.dumps({k: v for k, v in report.items() if k not in {"filtered", "official_corrections"}}, ensure_ascii=False, indent=2))
