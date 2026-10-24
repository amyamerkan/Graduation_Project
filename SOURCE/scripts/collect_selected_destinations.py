import json
from pathlib import Path

from vietnam_provinces import Province

from vn_assistant.corpus_update import PublicCrawler, collect_selected_destinations, write_jsonl
from vn_assistant.dataio import iter_records


if __name__ == "__main__":
    directory = Path(__file__).resolve().parents[2] / "data/raw/2026-10-24"
    crawler = PublicCrawler(directory / "http_cache")
    additions, report = collect_selected_destinations(crawler, {int(p.code):p for p in Province.iter_all()},
                                                       list(iter_records(directory / "tourism.jsonl")))
    write_jsonl(directory / "selected_destinations.jsonl", additions)
    write_jsonl(directory / "selected_http_manifest.jsonl", crawler.manifest)
    (directory / "selected_destinations_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
