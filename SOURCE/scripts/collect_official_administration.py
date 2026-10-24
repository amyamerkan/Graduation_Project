import json
from pathlib import Path

from vn_assistant.corpus_update import PublicCrawler, collect_official_administration, write_jsonl


if __name__ == "__main__":
    directory = Path(__file__).resolve().parents[2] / "data/raw/2026-10-24"
    crawler = PublicCrawler(directory / "http_cache")
    records, report = collect_official_administration(crawler)
    write_jsonl(directory / "official_administration.jsonl", records)
    write_jsonl(directory / "official_http_manifest.jsonl", crawler.manifest)
    (directory / "official_administration_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
