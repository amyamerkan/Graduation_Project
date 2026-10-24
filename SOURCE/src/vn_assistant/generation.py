from __future__ import annotations

import copy
import json
import math
import re
from time import perf_counter
from urllib.parse import urlsplit

from .cross_check import CrossChecker
from .evidence import build_evidence
from .prompts import build_messages


_IDENTITY_FIELDS = ("entity", "unit", "ward", "heritage", "oldUnit", "newUnit", "province", "type")
_LIST_QUERIES = {"01_list_provinces", "02_wards_in_province", "05_heritage_in_province", "06_entity_search", "07_kg_statistics"}


def _identity(row: dict) -> tuple:
    return tuple((key, str(row[key])) for key in _IDENTITY_FIELDS if row.get(key))


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite_json_constant")


def _parse_selection(raw: str, registry: dict) -> list[dict]:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 8192:
        raise ValueError("invalid_output_size")
    text = raw.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
        if match is None:
            raise ValueError("invalid_json_fence")
        text = match.group(1).strip()
    # Small local models may append sentence punctuation to an otherwise exact
    # JSON object. Strip only one final full stop; arbitrary prose stays invalid.
    if text.endswith("}."):
        text = text[:-1]
    try:
        data = json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(data, dict) or set(data) != {"claim_ids"}:
        raise ValueError("invalid_output_schema")
    ids = data["claim_ids"]
    if not isinstance(ids, list) or len(ids) > 3 or any(not isinstance(item, str) or not item for item in ids):
        raise ValueError("invalid_claim_ids")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_claim_id")
    if any(item not in registry for item in ids):
        raise ValueError("unknown_claim_id")
    return [copy.deepcopy(registry[item]) for item in ids]


def _check_result(status: str, reason: str) -> dict:
    rejected = [{"index": None, "claim": None, "reasons": [reason]}] if status == "invalid_output" else []
    return {
        "status": status,
        "supported": [],
        "rejected": rejected,
        "checked_count": 0,
        "supported_count": 0,
        "rejected_count": len(rejected),
        "verification_scope": "extractive_text_and_structured_kg_facts",
        "reason": reason,
    }


def _safe_url(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password:
            return value.strip()
    except ValueError:
        pass
    return None


def _display(value, limit=200) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


class AnswerService:
    def __init__(self, processor, generator, max_evidence=6, min_rag_score=.70, checker=None):
        if type(max_evidence) is not int or not 1 <= max_evidence <= 12:
            raise ValueError("max_evidence phải nằm trong [1, 12]")
        if type(min_rag_score) not in {float, int} or not math.isfinite(min_rag_score) or not -1 <= min_rag_score <= 1:
            raise ValueError("min_rag_score phải nằm trong [-1, 1]")
        self.processor = processor
        self.generator = generator
        self.max_evidence = max_evidence
        self.min_rag_score = min_rag_score
        self.checker = checker or CrossChecker()

    def _refresh_kg(self, processed: dict, evidence: list[dict]) -> None:
        plan = processed.get("plan", {}).get("kg")
        if not plan:
            return
        service = getattr(self.processor, "kg_service", None)
        if service is None:
            raise ValueError("kg_service_unavailable")
        rows = service.execute(plan["query"], plan.get("params", {}))
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("invalid_refreshed_kg_rows")
        filter_rows = getattr(self.processor, "filter_kg_rows", None)
        if callable(filter_rows):
            rows = filter_rows(rows, processed.get("classification", {}).get("domain", ""), plan["query"])
        previous = processed.get("kg_results", [])
        before = {_identity(row) for row in previous}
        after = {_identity(row) for row in rows}
        if before != after:
            raise ValueError("kg_snapshot_membership_changed")
        current = {}
        for row in rows:
            identity = _identity(row)
            if identity:
                current.setdefault(identity, []).append(row)
        for entry in evidence:
            if entry.get("kind") != "kg":
                continue
            facts = entry.get("facts", {})
            identity = _identity(facts) if isinstance(facts, dict) else ()
            candidates = current.get(identity, []) if identity else []
            if len(candidates) == 1:
                entry["current_facts"] = dict(candidates[0])
            else:
                entry["current_facts"] = {}

    def answer(self, question: str, top_k: int = 5) -> dict:
        started = perf_counter()
        processed = self.processor.process(question, top_k=top_k)
        question = processed.get("question", question)
        warnings = list(processed.get("warnings", []))
        timings = {
            "question_processing": round((perf_counter() - started) * 1000, 3),
            "generation": 0.0,
            "kg_refresh": 0.0,
            "cross_check": 0.0,
            "total": 0.0,
        }
        base = {
            "question": question,
            "classification": processed.get("classification", {}),
            "plan": processed.get("plan", {}),
            "effective_route": processed.get("effective_route"),
            "retrieval_status": processed.get("status"),
        }

        def abstain(reason: str, check_status="insufficient_evidence", cross_check=None):
            timings["total"] = round((perf_counter() - started) * 1000, 3)
            return {
                **base,
                "status": "abstained",
                "answer": {
                    "unsupported_constraints": "Dữ liệu hiện có chưa đủ để xác nhận điều kiện thời gian hoặc khoảng cách trong câu hỏi. Bạn có thể hỏi mã đơn vị, tỉnh/thành trực thuộc hoặc tra mã tại một ngày cụ thể; truy vấn bán kính cần bổ sung tọa độ.",
                    "out_of_scope": "Mình hỗ trợ tra cứu địa giới hành chính cũ–mới và du lịch Việt Nam trong bộ dữ liệu. Câu hỏi này nằm ngoài phạm vi đó; bạn có thể chọn một câu hỏi gợi ý để bắt đầu.",
                    "missing_verified_code": "Mình chưa tìm được bản ghi KG khớp mã đơn vị và các điều kiện bạn yêu cầu. Bạn kiểm tra lại mã hoặc thay đổi ngày, địa phương cần tra cứu nhé.",
                    "no_eligible_evidence": "Mình chưa tìm được minh chứng đủ phù hợp trong dữ liệu hiện có. Bạn có thể bổ sung tên đầy đủ, địa phương hoặc mã đơn vị để mình tra cứu chính xác hơn.",
                }.get(reason, "Mình chưa có đủ minh chứng phù hợp để trả lời câu hỏi này một cách đáng tin cậy."),
                "citations": [],
                "claims": [],
                "cross_check": cross_check or _check_result(check_status, reason),
                "warnings": list(dict.fromkeys([*warnings, reason])),
                "llm": self.generator.status(),
                "timings_ms": dict(timings),
            }

        if processed.get("status") == "out_of_scope":
            return abstain("out_of_scope")
        if processed.get("status") == "unsupported_constraints" or processed.get("plan", {}).get("constraints", {}).get("unsupported"):
            return abstain("unsupported_constraints")
        planned_kg = processed.get("plan", {}).get("kg") or {}
        if planned_kg.get("params", {}).get("code") and not processed.get("kg_results"):
            return abstain("missing_verified_code")
        if planned_kg and (planned_kg.get("query") == "07_kg_statistics" or re.search(r"\b(?:bao nhiêu|số lượng)\b", question.casefold())):
            if not any(isinstance(row, dict) and str(row.get("count", "")).isdigit() for row in processed.get("kg_results", [])):
                return abstain("missing_verified_count")
        evidence = build_evidence(processed, max_evidence=self.max_evidence, min_rag_score=self.min_rag_score)
        if not evidence:
            return abstain("no_eligible_evidence")
        registry = {}
        for entry in evidence:
            for claim in entry.get("allowed_claims", []):
                claim_id = claim.get("claim_id") if isinstance(claim, dict) else None
                if not isinstance(claim_id, str) or not claim_id or claim_id in registry:
                    return abstain("invalid_claim_registry", "invalid_output")
                registry[claim_id] = claim
        if not registry:
            return abstain("no_eligible_claims")
        generation_started = perf_counter()
        raw = self.generator.generate(build_messages(question, evidence))
        timings["generation"] = round((perf_counter() - generation_started) * 1000, 3)
        try:
            claims = _parse_selection(raw, registry)
        except ValueError as exc:
            return abstain(str(exc), "invalid_output")
        if not claims:
            return abstain("model_selected_no_claims")
        refresh_started = perf_counter()
        try:
            self._refresh_kg(processed, evidence)
        except Exception as exc:
            timings["kg_refresh"] = round((perf_counter() - refresh_started) * 1000, 3)
            warnings.append("KG không thể xác nhận lại cùng tập minh chứng sau khi LLM sinh kết quả.")
            reason = str(exc) if isinstance(exc, ValueError) and str(exc) in {"kg_service_unavailable", "invalid_refreshed_kg_rows", "kg_snapshot_membership_changed"} else "kg_refresh_failed:" + type(exc).__name__
            return abstain(reason)
        timings["kg_refresh"] = round((perf_counter() - refresh_started) * 1000, 3)
        check_started = perf_counter()
        checked = self.checker.verify(claims, evidence, question=question, plan=processed.get("plan"))
        checked["kg_rechecked"] = bool(processed.get("plan", {}).get("kg"))
        timings["cross_check"] = round((perf_counter() - check_started) * 1000, 3)
        supported = checked.get("supported", [])
        if not supported:
            return abstain("cross_check_rejected_all_claims", cross_check=checked)
        supported_fields = {
            check["field"]
            for claim in supported if claim.get("mode") == "fact"
            for check in claim.get("fact_checks", [])
            if isinstance(check, dict) and isinstance(check.get("field"), str)
        }
        requested_code = planned_kg.get("params", {}).get("code")
        if requested_code is not None and not any(
            check.get("field") in {"code", "newCode"} and str(check.get("value")) == str(requested_code)
            for claim in supported if claim.get("mode") == "fact"
            for check in claim.get("fact_checks", []) if isinstance(check, dict)
        ):
            return abstain("missing_requested_fact(code)")
        if planned_kg and (planned_kg.get("query") == "07_kg_statistics" or re.search(r"\b(?:bao nhiêu|số lượng)\b", question.casefold())):
            if "count" not in supported_fields:
                return abstain("missing_requested_fact(count)")
        query_text = question.casefold()
        requested_fields = {}
        if re.search(r"\bloại\s+di\s+sản\b", query_text):
            requested_fields["type"] = "loại di sản"
        if any(term in query_text for term in ("thuộc tỉnh", "thuộc thành phố", "tỉnh nào", "thành phố nào")):
            requested_fields["provinceName"] = "tỉnh/thành phố trực thuộc"
        if any(term in query_text for term in ("hiệu lực từ", "bắt đầu hiệu lực", "ngày có hiệu lực")):
            requested_fields["validFrom"] = "mốc bắt đầu hiệu lực"
        if any(term in query_text for term in ("hết hiệu lực", "kết thúc hiệu lực", "hiệu lực đến")):
            requested_fields["validTo"] = "mốc kết thúc hiệu lực"
        missing_fields = {field: label for field, label in requested_fields.items() if field not in supported_fields}
        for field in missing_fields:
            warnings.append(f"missing_requested_fact({field})")
        if checked.get("rejected"):
            warnings.append("Một số mệnh đề đã bị loại vì không khớp minh chứng hoặc KG hiện tại.")
        records = {entry["id"]: entry for entry in evidence}
        numbers = {}
        rendered = []
        citations = []
        for claim in supported:
            markers = []
            for evidence_id in claim["evidence_ids"]:
                if evidence_id not in numbers:
                    entry = records[evidence_id]
                    number = len(numbers) + 1
                    numbers[evidence_id] = number
                    citations.append({
                        "number": number,
                        "evidence_id": evidence_id,
                        "kind": entry.get("kind"),
                        "title": entry.get("title", ""),
                        "source": entry.get("source", ""),
                        "source_url": _safe_url(entry.get("source_url")),
                        "source_record_ids": entry.get("source_record_ids", []),
                        "source_verified": entry.get("source_verified") is True,
                    })
                markers.append(f"[{numbers[evidence_id]}]")
            rendered.append(claim["text"] + " " + "".join(markers))
        partial = bool(checked.get("rejected")) or processed.get("status") == "partial" or bool(missing_fields)
        kg_plan = processed.get("plan", {}).get("kg") or {}
        entities = {
            str(row.get("entity") or row.get("unit") or row.get("heritage") or row.get("ward"))
            for row in processed.get("kg_results", [])
            if row.get("entity") or row.get("unit") or row.get("heritage") or row.get("ward")
        }
        ambiguous = kg_plan.get("query") == "08_entity_facts" and len(entities) > 1
        if ambiguous:
            partial = True
            warnings.append("ambiguous_entity")
            warnings.append("Tên được hỏi khớp với nhiều thực thể; cần thêm địa phương hoặc mã để xác định thực thể mong muốn.")
        referenced_kg = {item["evidence_id"] for item in citations if item["kind"] == "kg"}
        if kg_plan.get("query") in _LIST_QUERIES and len(referenced_kg) < len(processed.get("kg_results", [])):
            partial = True
            warnings.append("Câu trả lời chỉ trình bày các bản ghi đã chọn; chưa phải danh sách đầy đủ.")
            warnings.append("evidence_truncated")
        sources = []
        for citation in citations:
            title = _display(citation["title"] or citation["source"] or "Minh chứng truy xuất")
            if citation["source_url"]:
                location = citation["source_url"]
            elif citation["kind"] == "kg":
                source = _display(citation["source"] or "Đồ thị tri thức cục bộ")
                count = len(citation["source_record_ids"])
                location = f"bản ghi KG nội bộ; {source}" + (f" ({count} bản ghi nguồn)" if count else "")
            else:
                location = "tài liệu trong bộ dữ liệu cục bộ"
            sources.append(f"[{citation['number']}] {title} — {location}")
        introduction = "Tên được hỏi khớp với nhiều thực thể. Các thông tin dưới đây thuộc những bản ghi được dẫn nguồn; cần thêm địa phương hoặc mã để xác định thực thể bạn muốn hỏi.\n" if ambiguous else "Theo các minh chứng tìm được:\n"
        if missing_fields:
            introduction = "Minh chứng hiện có chưa xác nhận được " + ", ".join(missing_fields.values()) + ". Dưới đây là phần thông tin đã kiểm tra được:\n" + (introduction if ambiguous else "")
        text = introduction + "\n".join(rendered) + "\n\nNguồn minh chứng:\n" + "\n".join(sources)
        timings["total"] = round((perf_counter() - started) * 1000, 3)
        return {
            **base,
            "status": "partial" if partial else "answered",
            "answer": text,
            "citations": citations,
            "claims": supported,
            "cross_check": checked,
            "warnings": list(dict.fromkeys(warnings)),
            "llm": self.generator.status(),
            "timings_ms": timings,
        }
