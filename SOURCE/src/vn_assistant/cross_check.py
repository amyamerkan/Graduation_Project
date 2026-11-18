from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any
from .administrative_codes import recognize_administrative_code, validate_code_facts, province_matches


_FIELD_LABELS = {
    "address": "Địa chỉ được nguồn ghi nhận",
    "transitionType": "Hình thức chuyển đổi",
    "snapshotDate": "Ngày chụp danh mục",
    "name": "Tên thực thể",
    "wardName": "Tên xã/phường",
    "oldName": "Tên đơn vị trước sắp xếp",
    "newName": "Tên đơn vị sau sắp xếp",
    "code": "Mã",
    "newCode": "Mã của đơn vị sau sắp xếp",
    "provinceName": "Tỉnh/thành phố trực thuộc",
    "validFrom": "Mốc bắt đầu hiệu lực được ghi trong KG",
    "validTo": "Mốc kết thúc hiệu lực được ghi trong KG",
    "description": "Mô tả được ghi trong KG",
    "type": "Loại thực thể",
    "count": "Số thực thể trong kết quả thống kê KG",
    "inscriptionYear": "Năm ghi danh được ghi trong KG",
    "sourceName": "Nguồn dữ liệu được ghi trong KG",
    "sourceRecordId": "Mã bản ghi nguồn",
}
SUPPORTED_FACT_FIELDS = tuple(_FIELD_LABELS)
_CLASS_LABELS = {
    "HistoricalProvince": "tỉnh/thành phố trong danh mục lịch sử",
    "Province": "tỉnh/thành phố",
    "District": "đơn vị hành chính cấp huyện",
    "Ward": "đơn vị hành chính cấp xã",
    "HistoricalAdministrativeUnit": "đơn vị hành chính lịch sử",
    "AdministrativeUnit": "đơn vị hành chính",
    "TangibleHeritage": "di sản vật thể",
    "IntangibleHeritage": "di sản phi vật thể",
    "WorldHeritage": "di sản thế giới",
    "HeritageSite": "địa điểm di sản",
    "Heritage": "di sản",
    "Museum": "bảo tàng",
    "TourismPlace": "địa điểm du lịch",
    "TourismActivity": "hoạt động du lịch",
    "LegalDocument": "văn bản pháp luật",
    "LegalArticle": "điều khoản pháp luật",
    "AdministrativeProcedure": "thủ tục hành chính",
    "Organization": "tổ chức",
    "SourceDocument": "tài liệu nguồn",
}
_CODE_PATTERN = re.compile(
    r"\bmã(?:\s+(?:hành\s+chính|đơn\s+vị))?(?:\s+(?:số|là))?\s*[:=]?\s*[\"']?(\d{2,})",
    re.IGNORECASE,
)
_DATE_PATTERNS = {
    "validFrom": re.compile(r"(?:hiệu\s+lực\s+từ|bắt\s+đầu\s+hiệu\s+lực)\s*[:=]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE),
    "validTo": re.compile(r"(?:hết\s+hiệu\s+lực|kết\s+thúc\s+hiệu\s+lực)\s*[:=]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE),
}


def _normalise(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _value(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Giá trị sự kiện phải là chuỗi hoặc số nguyên")
    result = _normalise(str(value))
    if not result or len(result) > 8000:
        raise ValueError("Giá trị sự kiện rỗng hoặc quá dài")
    return result


def _is_sentence_excerpt(text: str, source: str) -> bool:
    cursor = 0
    while True:
        start = source.find(text, cursor)
        if start < 0:
            return False
        end = start + len(text)
        prefix = source[:start].rstrip()
        suffix = source[end:].lstrip()
        left_boundary = not prefix or prefix[-1] in ".!?"
        right_boundary = not suffix or suffix[0] in ".!?" or (text[-1] in ".!?" and source[end].isspace())
        if left_boundary and right_boundary:
            return True
        cursor = start + 1


def _entity_name(facts: Mapping[str, Any]) -> str:
    for field in ("name", "wardName", "oldName", "newName"):
        if field in facts:
            try:
                return _value(facts[field])
            except ValueError:
                pass
    return ""


def render_kg_fact(field: str, value: Any, entity_name: str = "") -> str:
    if field not in _FIELD_LABELS:
        raise ValueError(f"Trường KG chưa có mẫu diễn đạt: {field}")
    rendered = _value(value)
    if field == "count" and not re.fullmatch(r"\d+", rendered):
        raise ValueError("Số lượng KG phải là số nguyên không âm")
    if field == "type":
        local_name = rendered.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        rendered = _CLASS_LABELS.get(local_name, rendered)
    label = _FIELD_LABELS[field]
    entity_name = _normalise(entity_name)
    if entity_name and field not in {"name", "wardName", "oldName", "newName", "description", "count"}:
        label = f"{label} của {entity_name}"
    ending = "" if rendered[-1] in ".!?" else "."
    return f"{label}: {rendered}{ending}"


def render_fact_claim(facts: Mapping[str, Any], fields: list[str] | None = None) -> str:
    if not isinstance(facts, Mapping):
        raise ValueError("Sự kiện KG phải là đối tượng")
    selected = fields if fields is not None else [field for field in _FIELD_LABELS if field in facts]
    if not isinstance(selected, list) or not selected or any(not isinstance(field, str) for field in selected):
        raise ValueError("Cần danh sách trường KG hợp lệ")
    if len(set(selected)) != len(selected):
        raise ValueError("Trường KG không được lặp lại")
    if any(field not in facts for field in selected):
        raise ValueError("Trường được chọn không có trong sự kiện KG")
    entity_name = _entity_name(facts)
    return " ".join(render_kg_fact(field, facts[field], entity_name) for field in selected)


def render_administrative_lookup(facts: Mapping[str, Any], fields: list[str]) -> str:
    # Validate all selected fields with the same value rules as other KG claims.
    render_fact_claim(facts, fields)
    if not {"name", "code"}.issubset(fields):
        raise ValueError("Tra mã cần tên và mã đơn vị")
    text = f"Mã hành chính {_value(facts['code'])} là {_value(facts['name'])}"
    if "provinceName" in fields and not province_matches(str(facts["name"]), str(facts["provinceName"])):
        text += f", thuộc {_value(facts['provinceName'])}"
    text += "."
    if "snapshotDate" in fields:
        text += f" Thông tin theo bản chụp danh mục ngày {_value(facts['snapshotDate'])}."
    for field in ("validFrom", "validTo"):
        if field in fields:
            text += " " + render_kg_fact(field, facts[field])
    return text


def _date_value(value: str) -> str:
    if "/" in value:
        day, month, year = value.split("/")
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return value


class CrossChecker:
    def __init__(self, max_claims: int = 30, max_claim_chars: int = 3000):
        if max_claims < 1 or max_claim_chars < 1:
            raise ValueError("Giới hạn kiểm tra phải dương")
        self.max_claims = max_claims
        self.max_claim_chars = max_claim_chars

    def verify(
        self,
        claims: Any,
        evidence: Any,
        question: str = "",
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(claims, list) or len(claims) > self.max_claims:
            return self._invalid("claims_must_be_bounded_list")
        if not isinstance(evidence, list):
            return self._invalid("evidence_must_be_list")
        registry: dict[str, dict[str, Any]] = {}
        for entry in evidence:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
                return self._invalid("invalid_evidence_record")
            if entry["id"] in registry:
                return self._invalid("duplicate_evidence_id")
            registry[entry["id"]] = entry
        supported: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for index, claim in enumerate(claims):
            reasons = self._verify_claim(claim, registry)
            if not reasons:
                reasons.extend(self._verify_constraints(claim, registry, plan or {}, question))
            if reasons:
                rejected.append({"index": index, "claim": claim, "reasons": sorted(set(reasons))})
            else:
                accepted = dict(claim)
                accepted["verification"] = "exact_evidence_match" if claim["mode"] == "extractive" else "exact_kg_fact_match"
                accepted["source_verified"] = all(registry[item].get("source_verified") is True for item in claim["evidence_ids"])
                supported.append(accepted)
        status = "supported" if supported and not rejected else "partial" if supported else "insufficient_evidence"
        code_lookup = ((plan or {}).get("kg") or {}).get("query") in {"03_unit_by_code", "09_unit_at_time"}
        return {
            "status": status,
            "supported": supported,
            "rejected": rejected,
            "checked_count": len(claims),
            "supported_count": len(supported),
            "rejected_count": len(rejected),
            "verification_scope": "extractive_text_and_structured_kg_facts",
            "constraints_checked": code_lookup,
            "question_constraints_checked": bool(code_lookup and question and recognize_administrative_code(question).code
                                                   and supported and not rejected),
        }

    def _verify_constraints(self, claim, registry, plan, question=""):
        kg_plan = plan.get("kg") or {}
        reference = recognize_administrative_code(question)
        if reference.status == "clarify":
            return ["ambiguous_question_identifier"]
        if reference.code:
            # Reconstruct the question contract rather than trusting that the
            # previous routing stage copied its key/date/province correctly.
            from .router import Classification, extract_query_plan
            expected = extract_query_plan(question, Classification(question, "kg", "administration", 1, 1, "check"))
            if expected.get("kg") != kg_plan or expected.get("constraints", {}).get("unsupported"):
                return ["question_plan_constraint_mismatch"]
        if kg_plan.get("query") not in {"03_unit_by_code", "09_unit_at_time"}:
            return []
        params = kg_plan.get("params", {})
        if claim["mode"] != "fact":
            return ["text_does_not_verify_spatiotemporal_constraints"]
        reasons = []
        for evidence_id in claim["evidence_ids"]:
            entry = registry[evidence_id]
            facts = entry.get("current_facts", entry.get("facts", {}))
            reasons.extend(validate_code_facts(facts, params))
            fields = set(claim.get("fields", []))
            if params.get("code") and not {"code", "name"}.issubset(fields):
                reasons.append("missing_requested_code_fields")
            if (params.get("province") or facts.get("provinceName")) and "provinceName" not in fields:
                # Province records can identify themselves without a parent.
                if facts.get("type", "").rsplit("#", 1)[-1] not in {"Province", "HistoricalProvince"}:
                    reasons.append("missing_requested_province_field")
            if params.get("as_of") and not {"snapshotDate", "validFrom", "validTo"}.intersection(fields):
                reasons.append("missing_requested_temporal_field")
        return reasons

    def _invalid(self, reason: str) -> dict[str, Any]:
        return {
            "status": "invalid_output",
            "supported": [],
            "rejected": [{"index": None, "claim": None, "reasons": [reason]}],
            "checked_count": 0,
            "supported_count": 0,
            "rejected_count": 1,
            "verification_scope": "extractive_text_and_structured_kg_facts",
        }

    def _verify_claim(self, claim: Any, registry: dict[str, dict[str, Any]]) -> list[str]:
        if not isinstance(claim, dict):
            return ["claim_must_be_object"]
        text = claim.get("text")
        if not isinstance(text, str) or not _normalise(text) or len(text) > self.max_claim_chars:
            return ["invalid_claim_text"]
        ids = claim.get("evidence_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(item, str) for item in ids):
            return ["missing_citations"]
        if len(set(ids)) != len(ids):
            return ["duplicate_citation"]
        if any(item not in registry for item in ids):
            return ["unknown_citation"]
        if claim.get("mode") == "extractive":
            return self._verify_extract(claim, registry)
        if claim.get("mode") == "fact":
            return self._verify_fact(claim, registry)
        return ["unsupported_claim_mode"]

    def _verify_extract(self, claim: dict[str, Any], registry: dict[str, dict[str, Any]]) -> list[str]:
        text = _normalise(claim["text"])
        reasons: list[str] = []
        if claim.get("fact_checks"):
            reasons.append("extractive_claim_cannot_include_fact_checks")
        for evidence_id in claim["evidence_ids"]:
            entry = registry[evidence_id]
            source_text = entry.get("text")
            if not isinstance(source_text, str) or not _is_sentence_excerpt(text, _normalise(source_text)):
                reasons.append("claim_not_exact_excerpt")
        reasons.extend(self._kg_conflicts(text, registry))
        return reasons

    def _verify_fact(self, claim: dict[str, Any], registry: dict[str, dict[str, Any]]) -> list[str]:
        ids = claim["evidence_ids"]
        if len(ids) != 1:
            return ["fact_requires_one_kg_record"]
        entry = registry[ids[0]]
        facts = entry.get("facts")
        if entry.get("kind") != "kg" or not isinstance(facts, dict):
            return ["fact_requires_kg_evidence"]
        checks = claim.get("fact_checks")
        if not isinstance(checks, list) or not checks:
            return ["missing_fact_checks"]
        fields: list[str] = []
        reasons: list[str] = []
        for check in checks:
            if not isinstance(check, dict) or check.get("evidence_id") != ids[0] or not isinstance(check.get("field"), str):
                reasons.append("invalid_fact_check")
                continue
            field = check["field"]
            fields.append(field)
            if field not in facts:
                reasons.append("unknown_kg_field")
                continue
            try:
                if _value(check.get("value")) != _value(facts[field]):
                    reasons.append("kg_value_mismatch")
            except ValueError:
                reasons.append("invalid_fact_value")
        if len(set(fields)) != len(fields):
            reasons.append("duplicate_fact_field")
        if "fields" in claim and claim["fields"] != fields:
            reasons.append("fields_do_not_match_fact_checks")
        current = entry.get("current_facts")
        if current is not None:
            if not isinstance(current, dict):
                reasons.append("invalid_current_kg_record")
            else:
                for field in set(fields) | ({"name", "wardName", "oldName", "newName"} & facts.keys()):
                    if field not in current or str(current[field]) != str(facts.get(field)):
                        reasons.append("kg_snapshot_changed")
        try:
            template = claim.get("template")
            if template not in {None, "administrative_code_lookup"}:
                raise ValueError("Mẫu diễn đạt chưa được hỗ trợ")
            expected = render_administrative_lookup(facts, fields) if template else render_fact_claim(facts, fields)
            if _normalise(claim["text"]) != _normalise(expected):
                reasons.append("claim_does_not_match_kg_rendering")
        except (ValueError, TypeError):
            reasons.append("invalid_fact_rendering")
        return reasons

    def _kg_conflicts(self, text: str, registry: dict[str, dict[str, Any]]) -> list[str]:
        reasons: list[str] = []
        named_records = []
        for entry in registry.values():
            if entry.get("kind") != "kg" or not isinstance(entry.get("facts"), dict):
                continue
            facts = entry.get("current_facts", entry["facts"])
            if not isinstance(facts, dict):
                continue
            entity = _entity_name(facts)
            if not entity or entity.casefold() not in text.casefold():
                continue
            named_records.append((entity, facts))
        if len({entity.casefold() for entity, _ in named_records}) != 1:
            return reasons
        for entity, facts in named_records:
            if "code" in facts:
                codes = _CODE_PATTERN.findall(text)
                if len(codes) == 1 and codes[0] != str(facts["code"]):
                    reasons.append("kg_code_conflict")
            for field, pattern in _DATE_PATTERNS.items():
                if field in facts:
                    dates = pattern.findall(text)
                    if len(dates) == 1 and _date_value(dates[0]) != str(facts[field]):
                        reasons.append("kg_date_conflict")
        return reasons
