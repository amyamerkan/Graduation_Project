import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from vn_assistant.corpus_update import PublicCrawler, collect_administration, collect_tourism, write_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2]/"data/raw/2026-10-24")
    parser.add_argument("--per-province", type=int, default=6)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    admin, provinces, admin_report = collect_administration()
    write_jsonl(args.output/"administration.jsonl", admin)
    crawler = PublicCrawler(args.output/"http_cache")
    tourism, tourism_report = collect_tourism(crawler, provinces, per_province=args.per_province, progress=args.output/"tourism.jsonl")
    write_jsonl(args.output/"tourism.jsonl", tourism)
    write_jsonl(args.output/"http_manifest.jsonl", crawler.manifest)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "administration": admin_report, "tourism": tourism_report}
    (args.output/"collection_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({"administration_records":len(admin),"tourism_records":len(tourism),"report":str(args.output/"collection_report.json")}),flush=True)


if __name__ == "__main__":
    main()
