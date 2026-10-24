import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil

from vn_assistant.corpus_update import document_from_record, write_jsonl
from vn_assistant.dataio import infer_domain, iter_records, source_name


INTANGIBLE = re.compile(r"\b(?:ca trù|nhã nhạc|quan họ|đờn ca tài tử|di sản phi vật thể|tín ngưỡng thờ mẫu|thực hành tín ngưỡng)\b", re.I)


def excluded(record):
    if infer_domain(record) == "heritage":
        return True
    return bool(INTANGIBLE.search(json.dumps(record, ensure_ascii=False, default=float)))


def archive_filtered(source, destination):
    counts = Counter()
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=5) as stream:
        for row in iter_records(source):
            if excluded(row):
                counts["removed_heritage"] += 1
                continue
            counts["retained_nonheritage"] += 1
            stream.write(json.dumps(row, ensure_ascii=False, default=float) + "\n")
    temporary.replace(destination)
    return dict(counts)


def prepare(root, raw):
    data = root / "data"
    report_path = root / "artifacts/maintenance/domain_migration_2026-10-24.json"
    if report_path.exists():
        raise ValueError("Migration already completed; use the retained raw collection to rebuild artifacts")
    archive = data / "archive"
    archive.mkdir(exist_ok=True)
    report = {"updated_at": datetime.now(timezone.utc).isoformat(), "active_domains": ["administration", "tourism"],
              "legacy_policy": "Nonheritage legacy data retained compressed and inactive; unverified image QA and foreign travel excluded from training.",
              "deleted_artifacts": []}
    for filename in ("rag_dataset_final.jsonl", "vn_complete_dataset.json"):
        original = data / filename
        if original.exists():
            target = archive / (original.stem + ".nonheritage.jsonl.gz")
            if target.exists():
                raise ValueError("Refusing to overwrite archive " + str(target))
            report[filename] = archive_filtered(original, target)
    records = []
    rejected = []
    for filename in ("administration.jsonl", "tourism.jsonl", "official_administration.jsonl"):
        source = raw / filename
        if not source.exists():
            continue
        for row in iter_records(source):
            title = row.get("data", {}).get("name", "")
            if INTANGIBLE.search(title) or title.casefold().startswith("lễ hội"):
                rejected.append({"title": title, "source_url": row.get("source_url", "")})
                continue
            records.append(row)
    if not records or not any(row["domain"] == "tourism" for row in records):
        raise ValueError("Missing replacement administrative/tourism corpus")
    if len({row["record_id"] for row in records}) != len(records):
        raise ValueError("Duplicate record identities")
    documents = [document_from_record(row) for row in records]
    write_jsonl(data / "structured_records.jsonl", records)
    write_jsonl(data / "rag_dataset_final.jsonl", documents)
    (data / "vn_complete_dataset.json").unlink(missing_ok=True)
    report.update({"structured_records": len(records), "active_documents": len(documents),
                   "documents_by_domain": dict(Counter(row["domain"] for row in documents)),
                   "documents_by_source": dict(Counter(source_name(row) for row in documents)),
                   "rejected_new_records": rejected,
                   "active_corpus_sha256": hashlib.sha256((data / "rag_dataset_final.jsonl").read_bytes()).hexdigest(),
                   "active_heritage_documents": sum(row["domain"] == "heritage" for row in documents)})
    for relative in ("artifacts/faiss", "artifacts/faiss_pilot", "artifacts/kg", "artifacts/router", "artifacts/evaluation/sample_index"):
        obsolete = root / relative
        if obsolete.exists():
            report["deleted_artifacts"].append({"path": relative, "bytes": sum(p.stat().st_size for p in obsolete.rglob("*") if p.is_file())})
            shutil.rmtree(obsolete)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--raw", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.raw or args.root / "data/raw/2026-10-24"), ensure_ascii=False, indent=2))
