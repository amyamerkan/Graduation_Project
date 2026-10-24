from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import math
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vn_assistant.api import get_answer_service, get_faiss, get_generator, warmup_generator
from vn_assistant.config import PROJECT_ROOT, SETTINGS, WORKSPACE_ROOT
from vn_assistant.llm import TransformerGenerator, VLLMGenerator


class ObservedProcessor:
    def __init__(self, processor):
        self.processor = processor
        self.last_result = None

    def __getattr__(self, name):
        return getattr(self.processor, name)

    def process(self, question, top_k=5):
        self.last_result = self.processor.process(question, top_k=top_k)
        return self.last_result


def _package_versions():
    packages = ["torch", "transformers", "sentence-transformers", "faiss-cpu", "rdflib", "scikit-learn", "fastapi", "numpy"]
    result = {}
    for package in packages:
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = None
    return result


def _hardware():
    result = {"os": platform.platform(), "machine": platform.machine(), "processor": platform.processor(), "python": platform.python_version(), "executable": sys.executable}
    if platform.system() == "Darwin":
        for key, command in [("memory_bytes", "hw.memsize"), ("logical_cores", "hw.ncpu")]:
            try:
                completed = subprocess.run(["sysctl", "-n", command], capture_output=True, text=True, timeout=3, check=False)
                result[key] = int(completed.stdout.strip()) if completed.returncode == 0 else None
            except (OSError, ValueError, subprocess.TimeoutExpired):
                result[key] = None
    return result


def _artifact(path):
    path = Path(path)
    result = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        stat = path.stat()
        result.update({"bytes": stat.st_size, "modified_at_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
    return result


def _configuration():
    paths = {"kg": SETTINGS.kg_ttl_path, "router": SETTINGS.router_model_path, "faiss_index": SETTINGS.faiss_index_path, "faiss_metadata": SETTINGS.faiss_metadata_path}
    result = {
        "project_root": str(PROJECT_ROOT),
        "workspace_root": str(WORKSPACE_ROOT),
        "llm": {"backend": SETTINGS.llm_backend, "model": SETTINGS.llm_model, "device": SETTINGS.llm_device, "max_new_tokens": SETTINGS.llm_max_new_tokens, "context_window": SETTINGS.llm_context_window, "timeout_s": SETTINGS.llm_timeout_s, "local_files_only": SETTINGS.llm_local_files_only, "base_url": SETTINGS.llm_base_url if SETTINGS.llm_backend == "vllm" else None, "api_key_configured": bool(SETTINGS.llm_api_key)},
        "embedding": {"model": SETTINGS.embedding_model, "device": SETTINGS.embedding_device},
        "evidence": {"max_evidence": SETTINGS.answer_max_evidence, "min_rag_score": SETTINGS.answer_min_rag_score},
        "artifacts": {key: _artifact(path) for key, path in paths.items()},
    }
    index_config = SETTINGS.faiss_index_path.parent / "index_config.json"
    if index_config.is_file():
        saved = json.loads(index_config.read_text(encoding="utf-8"))
        result["index"] = {key: saved.get(key) for key in ["backend", "documents", "vectors", "dimension", "metric", "chunk_size", "overlap", "chunks_by_domain", "embedding"]}
    return result


def _preflight(service):
    kg = service.processor.kg_service
    if kg is None:
        raise RuntimeError("KG chưa sẵn sàng cho kiểm thử backend")
    code = kg.execute("03_unit_by_code", {"code": "00070"})
    missing = kg.execute("03_unit_by_code", {"code": "99999"})
    ca_tru = kg.execute("08_entity_facts", {"keyword": "Ca trù", "limit": 10})
    my_son = kg.execute("08_entity_facts", {"keyword": "Mỹ Sơn", "limit": 10})
    eligible_ca_tru = service.processor.filter_kg_rows(ca_tru, "heritage", "08_entity_facts")
    eligible_my_son = service.processor.filter_kg_rows(my_son, "heritage", "08_entity_facts")
    database = SETTINGS.faiss_metadata_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(database, uri=True) as connection:
        ca_tru_text = connection.execute("SELECT COUNT(*) FROM chunks WHERE domain = ? AND (text LIKE ? OR title LIKE ?)", ("heritage", "%Ca trù%", "%Ca trù%")).fetchone()[0]
    result = {
        "known_code_00070": code,
        "missing_code_99999_rows": len(missing),
        "ca_tru_eligible_kg_names": [row.get("name") for row in eligible_ca_tru],
        "ca_tru_text_chunks": ca_tru_text,
        "my_son_kg_matches": [{"name": row.get("name"), "type": row.get("type")} for row in my_son],
        "my_son_eligible_heritage_rows": len(eligible_my_son),
        "fixture_scope": "Tên Mỹ Sơn trong KG hiện chỉ khớp đơn vị hành chính. Ca trù được dùng cho luồng di sản hybrid; kiểm thử xác minh luồng và độ bám dữ liệu cục bộ.",
    }
    checks = {
        "known_code": any(row.get("code") == "00070" and row.get("name") == "Phường Hoàn Kiếm" for row in code),
        "missing_code": not missing,
        "ca_tru_kg": bool(eligible_ca_tru),
        "ca_tru_rag": ca_tru_text > 0,
        "my_son_scope": bool(my_son) and not eligible_my_son,
    }
    result["checks"] = checks
    result["passed"] = all(checks.values())
    return result


def _invariants(case, response, processed, before_llm, after_llm):
    expect = case["expect"]
    kg_rows = processed.get("kg_results", [])
    rag_rows = processed.get("rag_results", [])
    citations = response.get("citations", [])
    claims = response.get("claims", [])
    checked = response.get("cross_check", {})
    checks = {}
    if expect["status"] == "answered":
        checks["answer_status"] = response.get("status") in {"answered", "partial"}
        checks["answer_and_citations"] = bool(response.get("answer")) and bool(citations) and bool(claims)
        checks["supported_cross_check"] = checked.get("status") in {"supported", "partial"} and checked.get("supported_count", 0) > 0
        referenced = {evidence_id for claim in claims for evidence_id in claim.get("evidence_ids", [])}
        checks["citation_consistency"] = referenced == {citation.get("evidence_id") for citation in citations}
    else:
        checks["answer_status"] = response.get("status") == "abstained"
        checks["no_unsupported_claims"] = not citations and not claims and checked.get("supported_count", 0) == 0
    for key in ("route", "domain"):
        if key in expect:
            actual = processed.get("effective_route") if key == "route" else processed.get("classification", {}).get("domain")
            checks[key] = actual == expect[key]
    if "retrieval_status" in expect:
        checks["retrieval_status"] = processed.get("status") == expect["retrieval_status"]
    for kind, rows in [("kg", kg_rows), ("rag", rag_rows)]:
        if f"min_{kind}_rows" in expect:
            checks[f"min_{kind}_rows"] = len(rows) >= expect[f"min_{kind}_rows"]
        if f"max_{kind}_rows" in expect:
            checks[f"max_{kind}_rows"] = len(rows) <= expect[f"max_{kind}_rows"]
    if "kg_must_contain" in expect:
        checks["kg_must_contain"] = any(all(row.get(key) == value for key, value in expect["kg_must_contain"].items()) for row in kg_rows)
    if "citation_kinds" in expect:
        checks["citation_kinds"] = set(expect["citation_kinds"]).issubset({citation.get("kind") for citation in citations})
    if expect.get("physical_kg_scope"):
        filters = processed.get("physical_filters", {})
        checks["physical_kg_scope"] = bool(filters.get("doc_ids") or filters.get("entity_terms"))
    if "warning_prefix" in expect:
        checks["scope_warning"] = any(str(warning).startswith(expect["warning_prefix"]) for warning in processed.get("warnings", []))
    if "reason" in expect:
        checks["abstention_reason"] = checked.get("reason") == expect["reason"]
    if "llm_calls" in expect:
        checks["llm_calls"] = type(before_llm.get("generation_count")) is int and type(after_llm.get("generation_count")) is int and after_llm["generation_count"] - before_llm["generation_count"] == expect["llm_calls"]
    timings = response.get("timings_ms", {})
    checks["valid_timings"] = isinstance(timings, dict) and all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in timings.values()) and timings.get("total", 0) > 0
    if expect.get("llm_calls") == 1:
        checks["generation_measured"] = timings.get("generation", 0) > 0
    if expect.get("llm_calls") == 0:
        checks["generation_skipped"] = timings.get("generation") == 0
    return checks


def verify(cases_path: Path, output_path: Path, top_k: int):
    started = perf_counter()
    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Kiểm thử tích hợp chức năng trên 7 câu được chọn từ dữ liệu hiện có; không phải đánh giá độ chính xác tổng quát, xác nhận nguồn chính thống hoặc benchmark độ trễ.",
        "cases_file": str(cases_path.resolve()),
        "top_k": top_k,
        "configuration": _configuration(),
        "hardware": _hardware(),
        "package_versions": _package_versions(),
        "cases": [],
        "passed": False,
    }
    original_processor = None
    service = None
    try:
        missing_artifacts = [name for name, value in report["configuration"]["artifacts"].items() if not value["exists"]]
        if missing_artifacts:
            raise RuntimeError("Thiếu artifact: " + ", ".join(missing_artifacts))
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        if not isinstance(cases, list) or not cases or any(not isinstance(case, dict) or not isinstance(case.get("question"), str) or not isinstance(case.get("expect"), dict) for case in cases):
            raise ValueError("Tập smoke cases không hợp lệ")
        generator = get_generator()
        if not isinstance(generator, (TransformerGenerator, VLLMGenerator)):
            raise RuntimeError("Kiểm thử yêu cầu generator thật; không chấp nhận mock hoặc stub")
        report["generator_class"] = type(generator).__name__
        warmup_started = perf_counter()
        report["warmup"] = {"status": warmup_generator(generator), "latency_ms": round((perf_counter() - warmup_started) * 1000, 3)}
        if not report["warmup"]["status"].get("ready"):
            raise RuntimeError("LLM chưa sẵn sàng sau warmup")
        model = getattr(generator, "_model", None)
        if model is not None:
            report["model_parameter_count"] = sum(parameter.numel() for parameter in model.parameters())
        service_started = perf_counter()
        service = get_answer_service()
        report["service_initialization_ms"] = round((perf_counter() - service_started) * 1000, 3)
        report["preflight"] = _preflight(service)
        if not report["preflight"]["passed"]:
            raise RuntimeError("Dữ liệu hiện tại không khớp điều kiện của smoke cases")
        original_processor = service.processor
        observer = ObservedProcessor(original_processor)
        service.processor = observer
        for case in cases:
            before_llm = generator.status()
            cold_faiss = get_faiss.cache_info().currsize == 0
            case_started = perf_counter()
            item = {"case_id": case["case_id"], "question": case["question"], "expect": case["expect"], "faiss_not_loaded_before_case": cold_faiss}
            observer.last_result = None
            try:
                response = service.answer(case["question"], top_k=top_k)
                processed = observer.last_result or {}
                after_llm = generator.status()
                checks = _invariants(case, response, processed, before_llm, after_llm)
                citations = response.get("citations", [])
                item.update({
                    "response": response,
                    "retrieval": {"kg_rows": len(processed.get("kg_results", [])), "rag_rows": len(processed.get("rag_results", [])), "kg_results": processed.get("kg_results", []), "rag_results": processed.get("rag_results", []), "physical_filters": processed.get("physical_filters", {}), "warnings": processed.get("warnings", []), "timings_ms": processed.get("timings_ms", {})},
                    "selected_citation_kinds": sorted({citation.get("kind") for citation in citations if citation.get("kind")}),
                    "generation_counter_delta": after_llm.get("generation_count", 0) - before_llm.get("generation_count", 0),
                    "checks": checks,
                    "passed": all(checks.values()),
                    "hybrid_note": "Hai nhánh cùng truy xuất không bắt buộc LLM chọn mệnh đề từ cả hai nhánh; loại nguồn được chọn được ghi riêng." if case["expect"].get("route") == "hybrid" else None,
                })
            except Exception as exc:
                item.update({"passed": False, "error": {"type": type(exc).__name__, "message": str(exc)}, "retrieval": observer.last_result})
            item["wall_latency_ms"] = round((perf_counter() - case_started) * 1000, 3)
            report["cases"].append(item)
            print(json.dumps({"case_id": item["case_id"], "passed": item["passed"], "status": item.get("response", {}).get("status"), "wall_latency_ms": item["wall_latency_ms"]}, ensure_ascii=False), flush=True)
        report["passed"] = len(report["cases"]) == len(cases) and all(item["passed"] for item in report["cases"])
        report["llm_final_status"] = generator.status()
    except Exception as exc:
        report["setup_error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if service is not None and original_processor is not None:
            service.processor = original_processor
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
        report["case_count"] = len(report["cases"])
        report["passed_case_count"] = sum(item["passed"] for item in report["cases"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output_path)
        print(json.dumps({"passed": report["passed"], "cases": report["case_count"], "passed_cases": report["passed_case_count"], "report": str(output_path.resolve())}, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=PROJECT_ROOT / "evaluation/backend_smoke.json")
    parser.add_argument("--output", type=Path, default=WORKSPACE_ROOT / "artifacts/backend/integration_report.json")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.top_k <= 20:
        parser.error("top_k phải nằm trong [1, 20]")
    result = verify(args.cases, args.output, args.top_k)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
