from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from vn_assistant.corpus_update import PublicCrawler, _record, document_from_record, write_jsonl
from vn_assistant.dataio import iter_records


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    progress = root / "artifacts/faiss/build_progress.json"
    if json.loads(progress.read_text()).get("status") != "complete":
        raise ValueError("Wait for the running index build to finish before changing its input")
    raw = root / "data/raw/2026-10-24"
    records = list(iter_records(raw / "selected_destinations.jsonl"))
    crawler = PublicCrawler(raw / "http_cache")
    url = "https://vietnamtourism.vn/index.php/tourism/items/1627/6"
    soup = crawler.get(url)
    summary = soup.select_one(".tourism-summery .summery")
    if summary is None:
        raise ValueError("Missing official Ha Long location summary")
    description = summary.get_text(" ", strip=True).split("Ðặc điểm:")[0].strip()
    if not description.startswith("Vị trí:") or "Quảng Ninh" not in description:
        raise ValueError("Unexpected Ha Long location text")
    halong = _record("tourism_place", {"name":"Vịnh Hạ Long", "description":description,
                     "address":"Quảng Ninh — địa danh theo trang nguồn", "province_code":"22", "province_name":"Thành phố Quảng Ninh",
                     "country":"VN", "retrieved_at":datetime.now(timezone.utc).isoformat(),
                     "province_mapping_basis":"official tourism page identifies Quảng Ninh; current catalogue code 22",
                     "address_time_scope":"legacy locality names in official source; no automatic ward-level conversion"},
                     "tourism", "Cục Du lịch Quốc gia Việt Nam — trang điểm đến", url)
    records.append(halong)
    write_jsonl(raw / "halong_destination.jsonl", [halong])
    write_jsonl(raw / "halong_http_manifest.jsonl", crawler.manifest)
    structured = list(iter_records(root / "data/structured_records.jsonl"))
    documents = list(iter_records(root / "data/rag_dataset_final.jsonl"))
    existing = {r["record_id"] for r in structured}
    additions = [r for r in records if r["record_id"] not in existing]
    structured.extend(additions)
    documents.extend(document_from_record(r) for r in additions)
    write_jsonl(root / "data/structured_records.jsonl", structured)
    write_jsonl(root / "data/rag_dataset_final.jsonl", documents)
    report = {"added_documents":len(additions), "total_documents":len(documents),
              "documents_by_domain":dict(Counter(r["domain"] for r in documents)),
              "added_titles":[r["data"]["name"] for r in additions]}
    (root / "artifacts/maintenance/destination_enrichment_2026-10-24.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
