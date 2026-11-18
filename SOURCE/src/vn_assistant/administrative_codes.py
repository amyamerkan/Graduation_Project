"""Conservative recognition of administrative identifiers in user questions.

Only query text is accent-folded. Stored geographical names and source text are
never normalized or rewritten by these rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
import unicodedata

from .normalization import clean_text


ADMINISTRATIVE_TYPES = frozenset(
    "https://w3id.org/vn-assistant/ontology#" + kind
    for kind in ("AdministrativeUnit", "Province", "HistoricalProvince", "District", "Ward", "HistoricalAdministrativeUnit")
)


def fold_query(value: str) -> str:
    text = unicodedata.normalize("NFD", clean_text(value).lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn").replace("đ", "d")


_DATE = re.compile(r"\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\b")
_OTHER_IDENTIFIER = re.compile(r"\b(?:ma\s+(?:buu chinh|buu dien|zip|postal|giam gia|dat phong|dat cho|ve|tour|otp|cccd|can cuoc)|zip\s*code|postal\s*code|booking\s*(?:id|code)|so dien thoai|bien so|chuyen bay)\b|\btour\s*[:#]?\s*\d+\b(?!\s*(?:ngay|dem|nguoi)\b)")
_EXPLICIT = re.compile(
    r"\bma\b\s*(?:so\s+)?(?:(?:don vi(?:\s+hanh chinh)?|hanh chinh|dia phuong|tinh(?:\s+thanh)?|thanh pho|phuong|xa|huyen|quan|dvhc)\s+)?"
    r"(?:la\s*)?[:#=]?\s*[\"']?(\d+)\b"
)
_NUMBERS = re.compile(r"(?<![\w])\d+(?![\w])")
_LOCATION = re.compile(r"\b(?:thuoc|dia phuong|don vi|tinh|thanh pho|phuong|xa|huyen|quan|o dau|la gi|la don vi nao)\b")
_DESCRIPTION = re.compile(r"\b(?:gioi thieu|mo ta|lich su|nguon goc|dac sac|dang chu y|gia tri|trai nghiem|du lich|tham quan|sap nhap|sap xep|doi ten|dien tich|dan so|tru so|chu tich|am thuc|khach san|lich trinh|dia chi|quan nao|huyen nao)\b")


@dataclass(frozen=True)
class AdministrativeCodeReference:
    status: str = "none"
    codes: tuple[str, ...] = ()
    reason: str = ""
    descriptive: bool = False

    @property
    def code(self) -> str | None:
        return self.codes[0] if self.status == "lookup" else None

    def to_dict(self) -> dict:
        return {"status": self.status, "code": self.code, "candidates": list(self.codes),
                "reason": self.reason, "descriptive": self.descriptive}


def recognize_administrative_code(question: str) -> AdministrativeCodeReference:
    text = fold_query(question)
    # Prevent a day/month/year, decimal, telephone number or quantity from
    # contributing a fragment that happens to look like a catalogue code.
    masked = _DATE.sub(lambda m: " " * len(m.group()), text)
    masked = re.sub(r"\b\d+[.,]\d+\b", lambda m: " " * len(m.group()), masked)
    explicit = [m.group(1) for m in _EXPLICIT.finditer(masked)]
    numeric = [m for m in _NUMBERS.finditer(masked)
               if 2 <= len(m.group()) <= 6
               and not re.match(r"\s*(?:km|m|met|dong|vnd|trieu|ngay|dem|thang|nam|nguoi|diem|dia diem|tinh|tinh thanh)\b", masked[m.end():])
               and not re.search(r"\b(?:nam|thang|ngay|so nha|quoc lo)\s*$", masked[:m.start()])]
    if _OTHER_IDENTIFIER.search(text):
        if _NUMBERS.search(masked):
            return AdministrativeCodeReference("clarify", tuple(dict.fromkeys(explicit)), "other_identifier")
        return AdministrativeCodeReference()
    codes = list(dict.fromkeys(explicit))
    if codes:
        # A second code must not silently disappear just because only the first
        # one has the word “mã” in front of it.
        codes = list(dict.fromkeys([*codes, *(m.group() for m in numeric)]))
    if not codes and _LOCATION.search(masked):
        codes = list(dict.fromkeys(m.group() for m in numeric
            if not re.search(r"\b(?:phuong|xa|quan|huyen|tinh|thanh pho|thi tran|lich trinh|tour|chuyen|diem du lich)\s*$", masked[:m.start()])
            and ((len(m.group()) == 5 and m.group().startswith("0"))
                 or re.match(r"\s+(?:thuoc|o dau|la\s+(?:don vi|phuong|xa|huyen|quan|tinh|thanh pho))\b", masked[m.end():]))))
    if not codes:
        if re.fullmatch(r"\s*\d{2,6}\s*(?:la gi)?\s*[?!.]?\s*", masked) and numeric:
            return AdministrativeCodeReference("clarify", (numeric[0].group(),), "missing_identifier_context")
        return AdministrativeCodeReference()
    if len(codes) != 1:
        return AdministrativeCodeReference("clarify", tuple(codes), "multiple_codes")
    if len(codes[0]) not in {2, 3, 5}:
        return AdministrativeCodeReference("clarify", tuple(codes), "invalid_code_length")
    return AdministrativeCodeReference("lookup", tuple(codes), descriptive=bool(_DESCRIPTION.search(text)))


def province_key(value: str) -> str:
    value = fold_query(value)
    value = re.sub(r"^(?:tinh|thanh pho|tp\.?)\s+", "", value)
    return re.sub(r"\s+", " ", value).strip(" .?!")


def province_matches(requested: str, actual: str) -> bool:
    return bool(province_key(requested)) and province_key(requested) == province_key(actual)


def code_location_constraint(question: str) -> str:
    values = code_location_constraints(question)
    return values[0] if values else ""


def code_location_constraints(question: str) -> list[str]:
    text = clean_text(question)
    folded = fold_query(text)
    pattern = r"\b(?:thuoc|tai|o|trong)\s+(?:(?:tinh|thanh pho|tp\.?)\s+)?(.+?)(?=\s+(?:vao|ngay|thuoc|tai|o|trong|tu|va|co|la|dung|khong)\b|[?!.,]|$)"
    values = {}
    for match in re.finditer(pattern, folded):
        value = match.group(1).strip()
        if re.match(r"(?:(?:ngay|nam|thang)\s+(?:\d|nao\b|nay\b|qua\b|truoc\b|sau\b)|thoi diem\b|giai doan\b)", value) or _DATE.search(value):
            continue
        if re.match(r"(?:dia phuong|khu vuc|don vi|tinh thanh|tinh|thanh(?: pho)?|phuong|xa|huyen|quan|vung)?\s*(?:nao|gi|dau)\b", value):
            continue
        # Vietnamese accent folding preserves positions after NFC. Stored
        # names are not changed; accent folding is only for matching queries.
        original = text[match.start(1):match.end(1)].strip() if len(text) == len(folded) else value
        values.setdefault(province_key(original), original)
    return list(values.values())


def clarification_for_code(reference: AdministrativeCodeReference) -> str:
    if reference.reason == "multiple_codes":
        return "Bạn đang hỏi nhiều mã. Hãy chọn một mã đơn vị hành chính và nêu ngày cần tra nếu muốn xem danh mục cũ."
    if reference.reason == "invalid_code_length":
        return "Mã hành chính cần được giữ đủ chữ số, kể cả số 0 đầu: mã tỉnh 2 chữ số, mã huyện cũ 3 chữ số hoặc mã xã/phường 5 chữ số. Bạn muốn tra mã nào?"
    if reference.reason == "other_identifier":
        return "Mình chưa có danh mục để xác nhận mã bưu chính, mã đặt chỗ hoặc các loại mã khác. Bạn muốn tra mã đơn vị hành chính hay loại mã nào?"
    return "Bạn muốn tra mã đơn vị hành chính hay một loại mã khác? Hãy thêm loại mã hoặc địa phương cần tra cứu."


def validate_code_facts(facts: dict, params: dict) -> list[str]:
    """Validate the requested key and constraints independently of SPARQL."""
    reasons = []
    if facts.get("type") not in ADMINISTRATIVE_TYPES:
        reasons.append("not_administrative_unit")
    if not isinstance(facts.get("name"), str) or not facts["name"].strip():
        reasons.append("missing_unit_name")
    if params.get("code") is not None and facts.get("code") != params["code"]:
        reasons.append("kg_code_constraint_mismatch")
    if facts.get("type", "").rsplit("#", 1)[-1] in {"Ward", "District"} and not facts.get("provinceName"):
        reasons.append("missing_unit_province")
    province = params.get("province")
    actual_province = facts.get("provinceName", "")
    if not actual_province and facts.get("type", "").rsplit("#", 1)[-1] in {"Province", "HistoricalProvince"}:
        actual_province = facts.get("name", "")
    if province and not province_matches(province, actual_province):
        reasons.append("kg_province_constraint_mismatch")
    if params.get("as_of"):
        try:
            moment = date.fromisoformat(params["as_of"])
            snapshot = date.fromisoformat(facts["snapshotDate"]) if facts.get("snapshotDate") else None
            start = date.fromisoformat(facts["validFrom"]) if facts.get("validFrom") else None
            end = date.fromisoformat(facts["validTo"]) if facts.get("validTo") else None
            if snapshot is not None:
                if moment != snapshot:
                    reasons.append("outside_recorded_snapshot_date")
            elif start is None and end is None:
                reasons.append("missing_temporal_evidence")
            elif start and moment < start or end and moment > end:
                reasons.append("outside_kg_validity_interval")
            elif (start is None or end is None) and moment not in {start, end}:
                reasons.append("unbounded_snapshot_not_valid_for_arbitrary_date")
        except (ValueError, TypeError):
            reasons.append("invalid_temporal_evidence")
    return reasons
