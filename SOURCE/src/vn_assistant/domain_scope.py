"""Shared scope rules: retain visitor destinations, exclude intangible-heritage QA."""
from __future__ import annotations

import copy
import re

from .normalization import clean_text


INTANGIBLE_PATTERN = re.compile(
    r"\b(?:ca trù|nhã nhạc|quan họ|đờn ca tài tử|di sản (?:văn hóa )?phi vật thể|phi vật thể|"
    r"tín ngưỡng thờ mẫu|thực hành tín ngưỡng|hát xoan|hát xẩm|chầu văn|bài chòi|"
    r"ví giặm|ví dặm|hát ví|hát then|thực hành then|cồng chiêng|nghệ thuật xo[èe]|nghệ thuật xòe|múa xoè|múa xòe|intangible[- ](?:cultural[- ])?heritage)\b",
    re.IGNORECASE,
)
FOLDED_PATTERN = re.compile(r"\b(?:ca tru|nha nhac|quan ho|don ca tai tu|phi vat the|hat xoan|hat xam|chau van|bai choi|vi giam|vi dam|hat then|cong chieng|mua xoe)\b")


def contains_intangible(value: str) -> bool:
    text = clean_text(value)
    # Match accentless input literally. Accent-folding whole passages would confuse
    # geographical names (Quan Hồ, Châu Văn) and words such as "vị đậm" with art forms.
    return bool(INTANGIBLE_PATTERN.search(text) or FOLDED_PATTERN.search(text.casefold()))


def strip_intangible_sentences(text: str) -> tuple[str, list[str]]:
    """Remove complete source sentences/paragraphs; never rewrite factual content."""
    kept, removed = [], []
    for paragraph in str(text).splitlines():
        for sentence in re.split(r"(?<=[.!?;])\s+", paragraph):
            sentence = clean_text(sentence)
            if sentence:
                (removed if contains_intangible(sentence) else kept).append(sentence)
    return "\n".join(kept), removed


def sanitize_tourism_record(record: dict) -> tuple[dict | None, dict]:
    """Return a sanitized copy and an audit containing IDs/counts, not excluded prose."""
    data = record.get("data", {})
    name = clean_text(data.get("name", record.get("title", "")))
    audit = {"record_id": record.get("record_id", record.get("id")), "removed_sentences": 0}
    if record.get("domain") == "heritage" or contains_intangible(name) or name.casefold().startswith("lễ hội"):
        return None, {**audit, "reason": "excluded_heritage_subject"}
    output = copy.deepcopy(record)
    body = output.get("data", output)
    fields = ("description", "text", "content", "cultural_context")
    for field in fields:
        if isinstance(body.get(field), str):
            cleaned, removed = strip_intangible_sentences(body[field])
            body[field] = cleaned
            audit["removed_sentences"] += len(removed)
    description = body.get("description", body.get("text", body.get("content", "")))
    if len(clean_text(description)) < 60:
        return None, {**audit, "reason": "insufficient_destination_content"}
    if audit["removed_sentences"]:
        body["scope_filter"] = "visitor_destination_only"
    return output, audit
