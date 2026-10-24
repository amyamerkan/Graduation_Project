"""Remove excluded heritage subjects from inactive JSONL archives, retaining travel records."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import shutil

from vn_assistant.dataio import infer_domain
from vn_assistant.domain_scope import contains_intangible, strip_intangible_sentences


def clean_nested(value, counts, field=""):
    if isinstance(value, dict):
        return {k: clean_nested(v, counts, k) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_nested(v, counts, field) for v in value]
    if isinstance(value, str) and contains_intangible(value):
        result, removed = strip_intangible_sentences(value)
        counts["removed_sentences"] += len(removed)
        return result
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backup-directory", type=Path, required=True,
                        help="Preserve input archives outside the active corpus before any edits")
    args = parser.parse_args()
    args.backup_directory.mkdir(parents=True, exist_ok=True)
    reports = {}
    for path in sorted(args.directory.glob("*.nonheritage.jsonl.gz")):
        backup = args.backup_directory / path.name
        if backup.exists():
            raise ValueError("Refusing to overwrite the archive backup " + str(backup))
        shutil.copy2(path, backup)
        counts = Counter()
        temporary = path.with_suffix(path.suffix + ".filtering")
        with gzip.open(path, "rt", encoding="utf-8") as source, gzip.open(temporary, "wt", encoding="utf-8", compresslevel=5) as target:
            for line in source:
                row = json.loads(line)
                counts["before_records"] += 1
                if infer_domain(row) == "heritage":
                    counts["removed_records"] += 1
                    continue
                if contains_intangible(json.dumps(row, ensure_ascii=False)):
                    data = row.get("data", row)
                    if any(contains_intangible(str(data.get(k, row.get(k, "")))) for k in ("name", "title", "question", "Question", "query")):
                        counts["removed_records"] += 1
                        continue
                    row = clean_nested(row, counts)
                    if contains_intangible(json.dumps(row, ensure_ascii=False)):
                        raise ValueError("Excluded subject remains after archive cleaning")
                    counts["edited_records"] += 1
                target.write(json.dumps(row, ensure_ascii=False) + "\n")
                counts["retained_records"] += 1
        temporary.replace(path)
        reports[path.name] = dict(counts)
        print(json.dumps({"archive": path.name, **counts}), flush=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "archives": reports,
                                      "raw_policy": "Original HTTP source snapshots are provenance evidence, excluded from training/retrieval."}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
