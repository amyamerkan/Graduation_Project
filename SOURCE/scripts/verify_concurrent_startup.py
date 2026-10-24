from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "artifacts/system_tests/startup_concurrency_report.json")
    args = parser.parse_args()

    def call(path, payload=None):
        started = perf_counter()
        try:
            request = Request(args.url + path, data=json.dumps(payload).encode() if payload is not None else None,
                              headers={"Content-Type": "application/json"}, method="POST" if payload is not None else "GET")
            with urlopen(request, timeout=150) as response:
                result = json.load(response)
                code = response.status
            passed = code == 200 and (result.get("status") in {"ready", "answered", "ok"} or result.get("ready") is True)
            return {"path": path, "passed": passed, "http_status": code, "latency_ms": round((perf_counter() - started) * 1000, 3), "response": result}
        except Exception as error:
            return {"path": path, "passed": False, "error": str(error), "latency_ms": round((perf_counter() - started) * 1000, 3)}

    initial = call("/health")
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "scope": "Concurrent real model initialization and mixed requests, with current index recovery left running.",
              "cold_start": not initial.get("response", {}).get("llm", {}).get("ready", False), "initial_health": initial, "phases": []}
    recovery = args.output.parent.parent / "faiss/recovery_progress.json"
    report["recovery_before"] = json.loads(recovery.read_text()) if recovery.exists() else None
    phases = [
        ("simultaneous_initialization", [("/v1/system/warmup", {})] * 4 + [("/v1/llm/warmup", {}), ("/v1/chat", {"question": "Đơn vị có mã 00070 là gì?", "top_k": 3})]),
        ("mixed_model_requests", [("/v1/system/warmup", {})] * 2 + [("/v1/chat", {"question": "Đơn vị có mã 00070 là gì?", "top_k": 3})] * 2 + [("/v1/chat", {"question": "Giới thiệu giá trị văn hóa của Ca trù.", "top_k": 3})] * 2),
    ]
    for name, requests in phases:
        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            results = list(pool.map(lambda request: call(*request), requests))
        phase = {"name": name, "passed": all(item["passed"] for item in results), "requests": results}
        report["phases"].append(phase)
        print(json.dumps({"phase": name, "passed": phase["passed"], "requests": len(results)}), flush=True)
    report["final_health"] = call("/health")
    report["recovery_after"] = json.loads(recovery.read_text()) if recovery.exists() else None
    report["passed"] = initial["passed"] and all(phase["passed"] for phase in report["phases"]) and report["final_health"]["passed"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"passed": report["passed"], "cold_start": report["cold_start"], "report": str(args.output)}), flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
