"""Collect additional official tourism data without replacing the active corpus."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from vn_assistant.corpus_update import PublicCrawler, collect_administration, collect_tourism, write_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-seed", type=Path)
    parser.add_argument("--per-province", type=int, default=18)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / "http_cache"
    cache.mkdir(exist_ok=True)
    if args.cache_seed:
        for source in args.cache_seed.glob("*.html"):
            target = cache / source.name
            if not target.exists():
                os.link(source, target)
    _, provinces, _ = collect_administration()
    crawler = PublicCrawler(cache)
    try:
        records, report = collect_tourism(crawler, provinces, per_province=args.per_province,
                                          progress=args.output / "tourism.jsonl")
        write_jsonl(args.output / "tourism.jsonl", records)
        report["created_at"] = datetime.now(timezone.utc).isoformat()
        (args.output / "tourism_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({"documents": len(records), "output": str(args.output)}, ensure_ascii=False), flush=True)
    finally:
        write_jsonl(args.output / "http_manifest.jsonl", crawler.manifest)


if __name__ == "__main__":
    main()
