from __future__ import annotations

import json
import math
import re
from typing import Any
from urllib.parse import urlparse

from .cross_check import SUPPORTED_FACT_FIELDS, render_fact_claim
from .normalization import clean_text


def _source_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlparse(value.strip())
        return value.strip() if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def _fact_fields(facts: dict[str, Any], question: str) -> list[str]:
    query = clean_text(question).casefold()
    focus = []
    if "mã" in query:
        focus.extend(["code", "newCode"])
    if "hiệu lực" in query or re.search(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", query):
        focus.extend(["snapshotDate", "validFrom", "validTo"])
    if any(term in query for term in ["sáp nhập", "sắp xếp", "đổi tên"]):
        focus.extend(["oldName", "newName", "transitionType", "newCode"])
    if any(term in query for term in ["địa chỉ", "ở đâu", "nằm ở"]):
        focus.append("address")
    if any(term in query for term in ["bao nhiêu", "số lượng"]):
        focus.append("count")
    order = ["name", "wardName", *focus, "count", "oldName", "newName", "code", "newCode", "provinceName", "snapshotDate", "type"]
    fields = []
    for field in dict.fromkeys(order):
        value = facts.get(field)
        if field in SUPPORTED_FACT_FIELDS and isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip() and len(str(value)) <= 300:
            fields.append(field)
        if len(fields) >= 5:
            break
    return fields


def _sentences(text: str, question: str) -> list[str]:
    source = " ".join(text.split())
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", source) if part.strip()]
    words = set(re.findall(r"\w+", clean_text(question).casefold())) - {"là", "và", "của", "ở", "có", "gì", "nào", "như", "thế"}
    eligible = [(index, sentence) for index, sentence in enumerate(sentences) if 20 <= len(sentence) <= 420 and not sentence.endswith("?")]
    eligible.sort(key=lambda item: (-len(words & set(re.findall(r"\w+", item[1].casefold()))), item[0]))
    return [sentence for _, sentence in eligible[:3]]


def build_evidence(processed: dict[str, Any], max_evidence: int = 6, min_rag_score: float = 0.70) -> list[dict[str, Any]]:
    if not 1 <= max_evidence <= 12 or not math.isfinite(min_rag_score) or not -1 <= min_rag_score <= 1:
        raise ValueError("Cấu hình minh chứng không hợp lệ")
    question = processed.get("question", "")
    kg_rows = processed.get("kg_results", [])
    rag_rows = processed.get("rag_results", [])
    kg_plan = processed.get("plan", {}).get("kg") or {}
    anchor = clean_text(kg_plan.get("params", {}).get("keyword", "")).casefold() if kg_plan.get("query") == "08_entity_facts" and not kg_rows else ""
    kg_limit = max(1, max_evidence // 2) if rag_rows else max_evidence
    records: list[dict[str, Any]] = []
    seen = set()
    for row in kg_rows:
        fingerprint = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        fields = _fact_fields(row, question)
        if not fields:
            continue
        evidence_id = f"E{len(records) + 1:02d}"
        text = render_fact_claim(row, fields)
        records.append({
            "id": evidence_id, "kind": "kg", "text": text, "facts": dict(row),
            "title": str(row.get("name", row.get("wardName", row.get("oldName", "Kết quả SPARQL")))),
            "source": "; ".join(row.get("source_names", [])) or "Đồ thị tri thức cục bộ",
            "source_url": next((valid for value in row.get("source_urls", []) if (valid := _source_url(value))), ""), "source_record_ids": list(row.get("source_record_ids", [])),
            "source_verified": False,
            "allowed_claims": [{
                "claim_id": f"{evidence_id}-C01", "mode": "fact", "text": text,
                "evidence_ids": [evidence_id], "fields": fields,
                "fact_checks": [{"evidence_id": evidence_id, "field": field, "value": row[field]} for field in fields],
            }],
        })
        if len(records) >= kg_limit:
            break
    seen_chunks = set()
    for row in rag_rows:
        if len(records) >= max_evidence:
            break
        score = row.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or score < min_rag_score:
            continue
        fingerprint = row.get("chunk_id") or (row.get("doc_id"), row.get("text"))
        if fingerprint in seen_chunks:
            continue
        seen_chunks.add(fingerprint)
        text = row.get("text", "")
        if not isinstance(text, str):
            continue
        if anchor and anchor not in clean_text(text).casefold() and anchor not in clean_text(row.get("title", "")).casefold():
            continue
        sentences = _sentences(text, question)
        if not sentences:
            continue
        evidence_id = f"E{len(records) + 1:02d}"
        records.append({
            "id": evidence_id, "kind": "rag", "text": text,
            "title": str(row.get("title") or "Đoạn văn được truy xuất"),
            "source": str(row.get("source") or "Tập văn bản cục bộ"),
            "source_url": _source_url(row.get("source_url")),
            "source_record_ids": [str(row["doc_id"])] if row.get("doc_id") else [],
            "chunk_id": row.get("chunk_id"), "score": score, "source_verified": False,
            "allowed_claims": [{"claim_id": f"{evidence_id}-C{index:02d}", "mode": "extractive", "text": sentence,
                                "evidence_ids": [evidence_id]} for index, sentence in enumerate(sentences, 1)],
        })
    return records
