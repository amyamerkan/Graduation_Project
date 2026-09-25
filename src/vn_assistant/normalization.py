from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


SPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^0-9a-zA-ZÀ-ỹ]+", re.UNICODE)

DOMAIN_EXPANSIONS = {
    "ubnd": "ủy ban nhân dân",
    "tthc": "thủ tục hành chính",
    "cccd": "căn cước công dân",
    "bhxh": "bảo hiểm xã hội",
    "bhyt": "bảo hiểm y tế",
    "vịnh hạ long": "di sản thiên nhiên thế giới vịnh hạ long",
    "phố cổ hội an": "di sản văn hóa thế giới phố cổ hội an",
    "cố đô huế": "quần thể di tích cố đô huế",
    "kg": "đồ thị tri thức",
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = text.replace("\x00", " ")
    return SPACE_RE.sub(" ", text).strip()


def normalized_key(value: Any) -> str:
    text = unicodedata.normalize("NFD", clean_text(value).lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return SPACE_RE.sub(" ", NON_WORD_RE.sub(" ", text)).strip()


def expand_domain_terms(text: str) -> str:
    original = clean_text(text)
    lowered = original.lower()
    additions = [expanded for term, expanded in DOMAIN_EXPANSIONS.items() if term in lowered]
    return clean_text(" ".join([original, *additions]))


def stable_id(kind: str, *parts: Any) -> str:
    raw = "|".join(normalized_key(part) for part in parts if clean_text(part))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{kind.lower()}_{digest}"


def safe_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return label if label and label[0].isalpha() else f"Entity_{label}"

