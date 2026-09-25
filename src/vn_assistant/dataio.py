from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from .normalization import clean_text, stable_id


TECHNICAL_KEYS = {"ddd", "fr", "ip", "op", "shapes", "meta.g", "rules.@nx/enforce-module-boundaries"}
DROP_SOURCES = {"taidng/UIT-ViQuAD2.0", "excel_source_manifest", "vietnam-travel-rcm-sys"}


@dataclass
class Document:
    doc_id: str
    text: str
    title: str = ""
    domain: str = "unknown"
    source: str = ""
    source_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _first_non_space(path: Path) -> str:
    with path.open("r", encoding="utf-8") as stream:
        while True:
            char = stream.read(1)
            if not char or not char.isspace():
                return char


def iter_records(path: str | Path) -> Iterator[dict[str, Any]]:
    """Stream a top-level array, {records:[...]}, or JSONL file."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() in {".jsonl", ".ndjson"}:
        with source.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"JSONL lỗi tại dòng {line_number}: {exc}") from exc
        return
    first = _first_non_space(source)
    if first in "[{":
        try:
            import ijson
        except ImportError as exc:
            raise RuntimeError("Thiếu ijson. Chạy: pip install -r requirements.txt") from exc
        with source.open("rb") as stream:
            prefix = "item" if first == "[" else "records.item"
            yield from ijson.items(stream, prefix)
        return
    raise ValueError(f"Không nhận diện được định dạng JSON/JSONL: {source}")


def source_name(record: dict[str, Any]) -> str:
    provenance = record.get("provenance") or {}
    source = record.get("source")
    if isinstance(source, dict):
        source = source.get("name")
    return clean_text(
        record.get("source_name")
        or source
        or provenance.get("source_name")
        or provenance.get("dataset")
        or (record.get("data") or {}).get("dataset")
    )


def unwrap_data(record: dict[str, Any]) -> dict[str, Any]:
    data = record.get("data")
    if not isinstance(data, dict):
        return record
    nested = data.get("data")
    return nested if isinstance(nested, dict) else data


def infer_domain(record: dict[str, Any]) -> str:
    explicit = clean_text(record.get("domain") or unwrap_data(record).get("domain")).lower()
    if explicit in {"law", "administration", "heritage", "tourism"}:
        return explicit
    source = source_name(record).lower()
    if any(key in source for key in ("phapdien", "legal", "law", "vibidlqa")):
        return "law"
    if any(key in source for key in ("province", "administrative", "sap-nhap", "sáp nhập")):
        return "administration"
    if any(key in source for key in ("museum", "cultural", "heritage")):
        return "heritage"
    if any(key in source for key in ("tourism", "travel", "destination")):
        return "tourism"
    return "unknown"


def is_technical(record: dict[str, Any]) -> bool:
    if source_name(record) in DROP_SOURCES:
        return True
    if record.get("record_type") == "excel_source_manifest":
        return True
    data = unwrap_data(record)
    keys = set(data)
    if len(keys & TECHNICAL_KEYS) >= 2:
        return True
    provenance = record.get("provenance") or {}
    path = clean_text(provenance.get("source_file")).lower()
    return any(token in path for token in ("lottie", "package-lock", "node_modules", ".eslint", "manifest"))


def _texts_from_messages(messages: Any) -> list[str]:
    values: list[str] = []
    if not isinstance(messages, list):
        return values
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            values.append(content)
        elif isinstance(content, list):
            values.extend(str(item.get("text")) for item in content if isinstance(item, dict) and item.get("text"))
    return values


def _texts_from_paragraphs(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
    output: list[str] = []
    if not isinstance(value, list):
        return output
    for paragraph in value:
        if not isinstance(paragraph, dict):
            continue
        output.append(clean_text(paragraph.get("context")))
        for qa in paragraph.get("qas") or []:
            if not isinstance(qa, dict):
                continue
            output.append(clean_text(qa.get("question")))
            answers = qa.get("answers") or []
            output.extend(clean_text(item.get("text")) for item in answers if isinstance(item, dict))
    return output


def record_to_document(record: dict[str, Any]) -> Document | None:
    if is_technical(record):
        return None
    data = unwrap_data(record)
    source = source_name(record)
    domain = infer_domain(record)
    title = clean_text(record.get("title") or data.get("title") or data.get("name"))
    source_url = clean_text(record.get("source_url") or data.get("url"))
    if isinstance(record.get("source"), dict):
        source_url = source_url or clean_text(record["source"].get("url"))
    if isinstance(data.get("source"), dict):
        source_url = source_url or clean_text(data["source"].get("url"))

    fields = (
        "text", "content", "context", "description", "reference_answer", "answer",
        "question", "query", "Question", "Response", "cultural_context", "procedure",
        "article_text", "law_text", "overall_description",
    )
    values = [title]
    values.extend(clean_text(data.get(field)) for field in fields)
    values.extend(_texts_from_messages(data.get("messages") or data.get("conversations")))
    values.extend(_texts_from_paragraphs(data.get("paragraphs")))
    # Cleaned JSONL often already starts its text with the title.
    values = list(dict.fromkeys(value for value in values if value))
    if title and any(value != title and value.startswith(title) for value in values):
        values.remove(title)
    text = clean_text("\n".join(values))
    if len(text) < 40:
        return None
    record_id = clean_text(record.get("record_id") or record.get("doc_id") or record.get("id"))
    doc_id = record_id or stable_id("doc", source, title, text[:500])
    return Document(
        doc_id=doc_id,
        text=text,
        title=title,
        domain=domain,
        source=source,
        source_url=source_url,
        metadata={"record_type": clean_text(record.get("record_type"))},
    )


def iter_documents(path: str | Path, allowed_domains: Iterable[str] | None = None) -> Iterator[Document]:
    allowed = set(allowed_domains or ("law", "administration", "heritage", "tourism"))
    for record in iter_records(path):
        document = record_to_document(record)
        if document and document.domain in allowed:
            yield document


def chunk_document(document: Document, size: int = 900, overlap: int = 150) -> Iterator[dict[str, Any]]:
    if size <= overlap or overlap < 0:
        raise ValueError("Cần size > overlap >= 0")
    text = document.text
    start = 0
    chunk_number = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if boundary > start + size // 2:
                end = boundary + 1
        chunk = clean_text(text[start:end])
        if chunk:
            yield {
                "chunk_id": f"{document.doc_id}:{chunk_number}",
                "doc_id": document.doc_id,
                "text": chunk,
                "title": document.title,
                "domain": document.domain,
                "source": document.source,
                "source_url": document.source_url,
            }
            chunk_number += 1
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
