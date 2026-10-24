from __future__ import annotations

import json
from time import perf_counter
from pathlib import Path
from typing import Any

from .normalization import normalized_key
from .sparql_service import SparqlService


def _row_matches(actual: dict[str, str], expected: dict[str, Any]) -> bool:
    return all(normalized_key(actual.get(key, "")) == normalized_key(value) for key, value in expected.items())


def evaluate_kg(
    graph_path: str | Path,
    query_dir: str | Path,
    gold_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    service = SparqlService(graph_path, query_dir)
    cases = [json.loads(line) for line in Path(gold_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    details = []
    tp = fp = fn = 0
    passed = 0
    exhaustive_cases = 0
    required_matched = required_total = 0
    for case in cases:
        start = perf_counter()
        rows = service.execute(case["query"], case.get("params"))
        elapsed_ms = (perf_counter() - start) * 1000
        complete = "expected_rows" in case
        expected_rows = case.get("expected_rows", case.get("must_contain", []))
        # Maximum one-to-one matching: duplicate actual rows cannot inflate recall.
        assigned: dict[int, int] = {}
        def assign(expected_index: int, visited: set[int]) -> bool:
            for actual_index, row in enumerate(rows):
                if actual_index in visited or not _row_matches(row, expected_rows[expected_index]):
                    continue
                visited.add(actual_index)
                if actual_index not in assigned or assign(assigned[actual_index], visited):
                    assigned[actual_index] = expected_index
                    return True
            return False
        matched = sum(assign(i, set()) for i in range(len(expected_rows)))
        case_fn = len(expected_rows) - matched
        case_fp = len(rows) - matched if complete else None
        required_matched += matched
        required_total += len(expected_rows)
        min_rows_ok = len(rows) >= int(case.get("min_rows", 0))
        max_rows_ok = "max_rows" not in case or len(rows) <= int(case["max_rows"])
        case_passed = case_fn == 0 and min_rows_ok and max_rows_ok and (case_fp in (None, 0))
        passed += int(case_passed)
        if complete:
            exhaustive_cases += 1
            tp += matched
            fn += case_fn
            fp += case_fp
        details.append({
            "case_id": case["case_id"], "passed": case_passed, "rows_returned": len(rows),
            "expected_matched": matched, "expected_total": len(expected_rows),
            "exhaustive": complete, "false_positives": case_fp,
            "latency_ms": elapsed_ms, "sample": rows[:5],
        })
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    report = {
        "cases": len(cases), "passed": passed, "accuracy": passed / max(len(cases), 1),
        "exhaustive_cases": exhaustive_cases, "true_positives": tp,
        "false_positives": fp, "false_negatives": fn,
        "precision": precision, "recall": recall,
        "f1": (2 * precision * recall / (precision + recall) if precision + recall else 0.0)
              if precision is not None and recall is not None else None,
        "required_binding_recall": required_matched / max(required_total, 1),
        "metric_scope": "Precision/recall/F1 use exhaustive expected_rows cases only; must_contain cases check coverage.",
        "details": details,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report

