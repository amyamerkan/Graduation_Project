from __future__ import annotations

import re

from .normalization import clean_text
from .administrative_codes import recognize_administrative_code, fold_query


def resolve_question(question: str, history: list[dict]) -> dict:
    question = clean_text(question)
    if recognize_administrative_code(question).status != "none":
        return {"question": question, "resolved": False, "needs_context": False}
    reference = re.compile(r"\b(?:don vi do|phuong do|xa do|ma do|noi do|o do|di san do|dia diem do|no)\b")
    short = fold_query(question).strip(" ?.!") in {"o dau", "thuoc tinh nao", "co gia tri gi", "con lich su thi sao"}
    if not reference.search(fold_query(question)) and not short:
        return {"question": question, "resolved": False, "needs_context": False}
    previous_index = next((index for index in range(len(history) - 1, -1, -1) if history[index].get("role") == "user"), None)
    previous = clean_text(history[previous_index].get("content")) if previous_index is not None else ""
    if not previous:
        return {"question": question, "resolved": False, "needs_context": True}
    # Resolve a chain of user follow-ups without borrowing any entity or code
    # from assistant answers. Stop at an unresolved/ambiguous user turn.
    prior_resolution = resolve_question(previous, history[:previous_index])
    if prior_resolution["needs_context"]:
        return {"question": question, "resolved": False, "needs_context": True}
    previous = prior_resolution["question"]
    code = recognize_administrative_code(previous)
    quoted = re.search(r'[“"]([^”"]+)[”"]', previous)
    if code.status == "clarify":
        return {"question": question, "resolved": False, "needs_context": True}
    if code.code:
        topic = "đơn vị có mã " + code.code
        from .router import _dated_unit_plan, _extract_constraints
        if _extract_constraints(previous)["temporal"] and not _extract_constraints(question)["temporal"]:
            dated = _dated_unit_plan(previous, code.code)
            if not dated or not dated["params"].get("as_of"):
                return {"question": question, "resolved": False, "needs_context": True}
            topic += " ngày " + dated["params"]["as_of"]
    elif quoted:
        topic = quoted.group(1)
    else:
        from .router import _extract_entity_keyword

        topic = _extract_entity_keyword(previous)
    if not topic or len(topic) > 120:
        return {"question": question, "resolved": False, "needs_context": True}
    resolved = f"{topic} {question}" if short else question
    if not short:
        for match in reversed(list(reference.finditer(fold_query(question)))):
            resolved = resolved[:match.start()] + topic + resolved[match.end():]
    return {"question": resolved, "resolved": True, "needs_context": False}
