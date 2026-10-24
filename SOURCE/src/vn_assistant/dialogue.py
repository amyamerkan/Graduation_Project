from __future__ import annotations

import re

from .normalization import clean_text


def resolve_question(question: str, history: list[dict]) -> dict:
    question = clean_text(question)
    reference = re.compile(r"\b(?:đơn vị đó|phường đó|xã đó|mã đó|nơi đó|ở đó|di sản đó|địa điểm đó|nó)\b", re.I)
    short = question.casefold().strip(" ?.!") in {"ở đâu", "thuộc tỉnh nào", "có giá trị gì", "còn lịch sử thì sao"}
    if not reference.search(question) and not short:
        return {"question": question, "resolved": False, "needs_context": False}
    previous = next((clean_text(item.get("content")) for item in reversed(history) if item.get("role") == "user"), "")
    if not previous:
        return {"question": question, "resolved": False, "needs_context": True}
    code = re.search(r"\bmã(?:\s+(?:số|hành chính))?\s*[:#]?\s*(\d{2,6})\b", previous, re.I)
    quoted = re.search(r'[“"]([^”"]+)[”"]', previous)
    if code:
        topic = "đơn vị có mã " + code.group(1)
    elif quoted:
        topic = quoted.group(1)
    else:
        from .router import _extract_entity_keyword

        topic = _extract_entity_keyword(previous)
    if not topic or len(topic) > 120:
        return {"question": question, "resolved": False, "needs_context": True}
    resolved = f"{topic} {question}" if short else reference.sub(lambda _: topic, question)
    return {"question": resolved, "resolved": True, "needs_context": False}
