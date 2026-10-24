from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--cases", type=Path, default=Path(__file__).resolve().parents[1] / "evaluation/system_queries.json")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "artifacts/system_tests/backend_report.json")
    args = parser.parse_args()
    def call(path, payload=None):
        request = Request(args.url + path, data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request, timeout=120) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "scope": "Real HTTP, full KG, Qwen and E5 weights; retrieval mode explicitly reported. Query development suite, not independent factual-accuracy benchmark.", "cases": []}
    start = perf_counter()
    code, warm = call("/v1/system/warmup", {})
    report["warmup"] = {"http_status": code, "status": warm, "elapsed_ms": round((perf_counter() - start) * 1000, 3)}
    if code != 200 or warm.get("status") != "ready":
        raise RuntimeError("Không warmup được mô hình thật")
    for case in json.loads(args.cases.read_text()):
        start = perf_counter()
        payload = {key: case[key] for key in ("question", "history", "top_k") if key in case}
        code, result = call("/v1/chat", payload)
        elapsed = round((perf_counter() - start) * 1000, 3)
        checks = {"http_status": code == case.get("http_status", 200)}
        if code == 200:
            checks["status"] = result.get("status") == case["status"]
            if case.get("contains"):
                checks["expected_fact"] = case["contains"] in result.get("answer", "")
            if case.get("sources"):
                checks["source_kinds"] = set(case["sources"]).issubset({source.get("kind") for source in result.get("citations", [])})
            if case.get("constraints_checked"):
                checks["independent_constraints_check"] = result.get("cross_check", {}).get("constraints_checked") is True
            if case.get("resolved"):
                checks["context_resolution"] = result.get("context_resolution", {}).get("resolved") is True
            if result.get("status") in {"abstained", "needs_clarification"}:
                checks["no_unverified_claims"] = not result.get("claims") and not result.get("citations")
            else:
                checks["all_claims_verified"] = bool(result.get("claims")) and not result.get("cross_check", {}).get("rejected")
                checks["source_integrity"] = {evidence for claim in result.get("claims", []) for evidence in claim.get("evidence_ids", [])} == {source["evidence_id"] for source in result.get("citations", [])}
        item = {"id": case["id"], "question": case["question"], "http_status": code, "latency_ms": elapsed,
                "checks": checks, "passed": all(checks.values()), "response": result}
        report["cases"].append(item)
        print(json.dumps({key: item[key] for key in ("id", "passed", "latency_ms")}), flush=True)
    report["health"] = call("/health")[1]
    latencies = sorted(item["latency_ms"] for item in report["cases"])
    report["latency_ms"] = {"p50": statistics.median(latencies), "p95": latencies[max(0, int(len(latencies) * .95 + .999) - 1)], "max": max(latencies), "sample_size": len(latencies), "includes_first_retrieval_load": False, "initialization_measured_separately": True}
    report["latency_by_outcome_ms"] = {}
    for outcome in ["answered", "abstained", "needs_clarification"]:
        group = sorted(item["latency_ms"] for item in report["cases"] if item["response"].get("status") == outcome)
        if group:
            report["latency_by_outcome_ms"][outcome] = {"samples": len(group), "p50": statistics.median(group),
                "p95": group[max(0, int(len(group) * .95 + .999) - 1)], "max": max(group)}
    report["passed"] = all(item["passed"] for item in report["cases"])
    report["passed_cases"] = sum(item["passed"] for item in report["cases"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]), "report": str(args.output)}), flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
