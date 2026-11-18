"""Measure sequential warm HTTP latency; not a concurrent-load benchmark."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
from time import perf_counter
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--cases", type=Path, default=Path(__file__).resolve().parents[1] / "evaluation/system_queries.json")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error("--repeats must be at least 2")
    if args.output.exists():
        parser.error("Choose a new output path to preserve previous measurements")

    def call(path, payload=None):
        request = Request(args.url.rstrip("/") + path,
                          data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(),
                          headers={"Content-Type": "application/json"})
        start = perf_counter()
        with urlopen(request, timeout=180) as response:
            result = json.load(response)
        return result, round((perf_counter() - start) * 1000, 3)

    report = {"created_at": datetime.now(timezone.utc).isoformat(),
              "scope": "Three development questions, sequential requests, one discarded warm-up per question. No concurrent-load or independent QA-quality claim. Question processing includes encoding and search; these are not timed separately.",
              "platform": platform.platform(), "machine": platform.machine(),
              "python": platform.python_version(), "repeats": args.repeats,
              "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(), "cases": []}
    report["warmup"], report["warmup_ms"] = call("/v1/system/warmup", {})
    if report["warmup"].get("status") != "ready":
        raise RuntimeError("Models are not ready")
    cases = {c["id"]: c for c in json.loads(args.cases.read_text())}
    for case_id in ("bare_00008", "rag_tourism", "hybrid_tourism"):
        case = cases[case_id]
        payload = {k: case[k] for k in ("question", "history", "top_k") if k in case}
        _, discarded = call("/v1/chat", payload)
        item = {"id": case_id, "payload": payload, "discarded_warmup_ms": discarded, "samples": []}
        for repeat in range(args.repeats):
            response, elapsed = call("/v1/chat", payload)
            item["samples"].append({"repeat": repeat + 1, "http_ms": elapsed,
                                    "status": response.get("status"), "route": response.get("classification", {}).get("route"),
                                    "generation_mode": response.get("generation_mode"),
                                    "timings_ms": response.get("timings_ms", {}),
                                    "expected_status": response.get("status") == case["status"]})
        values = sorted(s["http_ms"] for s in item["samples"])
        item["http_ms"] = {"p50": statistics.median(values), "p95": values[max(0, int(.95 * len(values) + .999) - 1)],
                           "min": min(values), "max": max(values), "n": len(values)}
        report["cases"].append(item)
        print(json.dumps({"id": case_id, **item["http_ms"]}), flush=True)
    report["health"], _ = call("/health")
    report["expected_statuses_passed"] = all(s["expected_status"] for c in report["cases"] for s in c["samples"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if report["expected_statuses_passed"] else 1)


if __name__ == "__main__":
    main()
