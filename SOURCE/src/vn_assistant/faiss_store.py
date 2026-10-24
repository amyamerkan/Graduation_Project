from __future__ import annotations

import json
import os
import sqlite3
import time
import sys
import threading
from functools import lru_cache
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np

from .dataio import chunk_document, iter_documents
from .embedding import EmbeddingConfig, create_encoder


SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    vector_id INTEGER PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    doc_id TEXT NOT NULL,
    text TEXT NOT NULL,
    title TEXT NOT NULL,
    domain TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_domain ON chunks(domain);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
"""


def _batched(items: Iterable[dict[str, Any]], batch_size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def iter_chunks(dataset_path: str | Path, chunk_size: int, overlap: int, limit_documents: int = 0) -> Iterator[dict[str, Any]]:
    for index, document in enumerate(iter_documents(dataset_path), 1):
        yield from chunk_document(document, size=chunk_size, overlap=overlap)
        if limit_documents and index >= limit_documents:
            break


def _validate_checkpoint_prefix(work: Path, signature: dict, previous: dict) -> None:
    changed = {key for key in signature.keys() | previous.keys() if signature.get(key) != previous.get(key)}
    if not changed.issubset({"dataset_size", "dataset_mtime_ns"}) or not (work / "metadata.sqlite3").exists():
        raise ValueError(f"Build checkpoint differs from requested configuration: {work}")
    chunks = iter_chunks(signature["dataset"], signature["chunk_size"], signature["overlap"], signature["limit_documents"])
    with sqlite3.connect((work / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        for row in connection.execute("SELECT vector_id, chunk_id, doc_id, text, title, domain, source, source_url FROM chunks ORDER BY vector_id"):
            chunk = next(chunks, None)
            if chunk is None or tuple(row[1:]) != tuple(chunk[key] for key in ("chunk_id", "doc_id", "text", "title", "domain", "source", "source_url")):
                raise ValueError(f"Dataset changes an encoded checkpoint prefix at vector {row[0]}; use a new output directory")


def build_faiss_index(
    dataset_path: str | Path,
    index_path: str | Path,
    metadata_path: str | Path,
    config_path: str | Path,
    embedding_config: EmbeddingConfig,
    *,
    backend: str = "transformer",
    chunk_size: int = 900,
    overlap: int = 150,
    limit_documents: int = 0,
) -> dict[str, Any]:
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("Thiếu faiss-cpu. Chạy pip install -r requirements.txt") from exc

    index_path, metadata_path, config_path = map(Path, (index_path, metadata_path, config_path))
    for path in (index_path, metadata_path, config_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    source = Path(dataset_path).resolve()
    signature = {
        "dataset": str(source), "dataset_size": source.stat().st_size,
        "dataset_mtime_ns": source.stat().st_mtime_ns, "backend": backend,
        "embedding": asdict(embedding_config), "chunk_size": chunk_size,
        "overlap": overlap, "limit_documents": limit_documents, "format_version": 2,
    }
    if config_path.exists() and index_path.exists() and metadata_path.exists():
        existing = json.loads(config_path.read_text())
        if existing.get("build_signature") == signature:
            return existing
    work = index_path.parent / (index_path.name + ".build")
    work.mkdir(exist_ok=True)
    manifest = work / "signature.json"
    if manifest.exists() and json.loads(manifest.read_text()) != signature:
        _validate_checkpoint_prefix(work.resolve(), signature, json.loads(manifest.read_text()))
    manifest.write_text(json.dumps(signature, ensure_ascii=False, indent=2))
    encoder = create_encoder(embedding_config, backend=backend)
    temp_db = work / "metadata.sqlite3"
    vector_path = work / "vectors.f32"
    connection = sqlite3.connect(temp_db)
    connection.executescript(SCHEMA)
    vector_id = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    completed = {row[0] for row in connection.execute("SELECT chunk_id FROM chunks")}
    expected_bytes = vector_id * encoder.dimension * 4
    if vector_id and (not vector_path.exists() or vector_path.stat().st_size < expected_bytes):
        connection.close()
        raise ValueError("Checkpoint vectors are shorter than committed metadata")
    start = time.monotonic()
    initial_count = vector_id
    last_progress = 0.0
    progress_path = index_path.parent / "build_progress.json"
    def progress(status: str) -> None:
        elapsed = time.monotonic() - start
        payload = {"status": status, "vectors": vector_id, "resumed_vectors": initial_count,
                   "elapsed_seconds": elapsed, "vectors_per_second": (vector_id - initial_count) / max(elapsed, .001),
                   "device": embedding_config.device, "dataset": str(source)}
        temp_progress = progress_path.with_suffix(".tmp")
        temp_progress.write_text(json.dumps(payload, indent=2))
        os.replace(temp_progress, progress_path)
        print(json.dumps(payload), file=sys.stderr, flush=True)
    try:
        with vector_path.open("r+b" if vector_path.exists() else "w+b") as stream:
            # A crash may leave uncommitted vectors; SQLite is the checkpoint authority.
            stream.truncate(expected_bytes)
            stream.seek(expected_bytes)
            pending = (item for item in iter_chunks(dataset_path, chunk_size, overlap, limit_documents)
                       if item["chunk_id"] not in completed)
            progress("encoding")
            for batch in _batched(pending, embedding_config.batch_size):
                vectors = encoder.encode_passages([item["text"] for item in batch])
                if vectors.shape != (len(batch), encoder.dimension) or not np.isfinite(vectors).all():
                    raise ValueError("Invalid embedding batch")
                stream.write(vectors.astype("float32").tobytes())
                stream.flush()
                os.fsync(stream.fileno())
                rows = [(vector_id + offset, item["chunk_id"], item["doc_id"], item["text"], item["title"],
                         item["domain"], item["source"], item["source_url"]) for offset, item in enumerate(batch)]
                connection.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
                connection.commit()
                vector_id += len(batch)
                completed.update(item["chunk_id"] for item in batch)
                if time.monotonic() - last_progress >= 30:
                    progress("encoding")
                    last_progress = time.monotonic()
        if not vector_id:
            raise ValueError("Không có văn bản hợp lệ để lập chỉ mục")
        documents = connection.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks").fetchone()[0]
        domain_counts = dict(connection.execute("SELECT domain, COUNT(*) FROM chunks GROUP BY domain"))
        progress("writing_index")
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(encoder.dimension))
        vectors = np.memmap(vector_path, dtype="float32", mode="r", shape=(vector_id, encoder.dimension))
        for offset in range(0, vector_id, 8192):
            end = min(offset + 8192, vector_id)
            index.add_with_ids(np.asarray(vectors[offset:end]), np.arange(offset, end, dtype="int64"))
        temp_index = work / "index.tmp"
        faiss.write_index(index, str(temp_index))
        # Copy via SQLite backup so the checkpoint remains available until publication finishes.
        published_db = metadata_path.with_suffix(".publishing")
        with sqlite3.connect(published_db) as destination:
            connection.backup(destination)
        os.replace(temp_index, index_path)
        os.replace(published_db, metadata_path)
        report = {"backend": backend, "production_ready": backend == "transformer" and limit_documents == 0,
                  "embedding": asdict(embedding_config), "metric": "cosine_via_normalized_inner_product",
                  "documents": documents, "vectors": vector_id, "dimension": encoder.dimension,
                  "resumed_vectors": initial_count,
                  "chunks_by_domain": domain_counts, "chunk_size": chunk_size, "overlap": overlap,
                  "build_signature": signature}
        temp_config = config_path.with_suffix(".tmp")
        temp_config.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        os.replace(temp_config, config_path)
        progress("complete")
        return report
    except BaseException:
        progress("interrupted")
        raise
    finally:
        connection.close()


class FaissRetriever:
    def __init__(self, index_path: str | Path, metadata_path: str | Path, embedding_config: EmbeddingConfig, backend: str = "transformer"):
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("Thiếu faiss-cpu") from exc
        config_path = Path(index_path).parent / "index_config.json"
        if config_path.exists():
            saved = json.loads(config_path.read_text())
            if saved["backend"] != backend:
                raise ValueError("Embedding backend differs from index backend")
            # Preserve trained/indexed preprocessing; only runtime device/batch size may change.
            embedding_config = EmbeddingConfig(**{**saved["embedding"], "device": embedding_config.device,
                                                    "batch_size": embedding_config.batch_size})
        self._search_lock = threading.RLock()
        self.index = faiss.read_index(str(index_path))
        self.metadata_path = Path(metadata_path)
        self.encoder = create_encoder(embedding_config, backend=backend)
        if self.index.d != self.encoder.dimension:
            raise ValueError("Embedding dimension differs from index")
        with sqlite3.connect(self.metadata_path) as connection:
            if connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] != self.index.ntotal:
                raise ValueError("Index and metadata counts differ")

    @lru_cache(maxsize=32)
    def _allowed_ids(self, domain: str | None, doc_ids: tuple[str, ...] | None, entity_terms: tuple[str, ...] | None) -> np.ndarray:
        conditions = []
        values = []
        if domain:
            conditions.append("domain = ?")
            values.append(domain)
        extra = []
        if doc_ids:
            extra.append("doc_id IN (" + ",".join("?" for _ in doc_ids) + ")")
            values.extend(doc_ids)
        if entity_terms:
            for term in entity_terms:
                extra.append("(instr(unicode_fold(title), ?) > 0 OR instr(unicode_fold(text), ?) > 0)")
                values.extend([term.casefold(), term.casefold()])
        if extra:
            conditions.append("(" + " OR ".join(extra) + ")")
        elif doc_ids is not None or entity_terms is not None:
            return np.asarray([], dtype="int64")
        sql = "SELECT vector_id FROM chunks"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        with sqlite3.connect(self.metadata_path) as connection:
            connection.create_function("unicode_fold", 1, lambda value: (value or "").casefold(), deterministic=True)
            return np.asarray([row[0] for row in connection.execute(sql, values)], dtype="int64")

    def search(self, query: str, top_k: int = 5, domain: str | None = None, *,
               doc_ids: list[str] | None = None, entity_terms: list[str] | None = None) -> list[dict[str, Any]]:
        if top_k < 1 or top_k > 100:
            raise ValueError("top_k phải nằm trong [1, 100]")
        import faiss
        docs = None if doc_ids is None else tuple(dict.fromkeys(str(item) for item in doc_ids))
        terms = None if entity_terms is None else tuple(dict.fromkeys(str(item).strip() for item in entity_terms if str(item).strip()))
        if docs is not None and len(docs) > 1000 or terms is not None and len(terms) > 100:
            raise ValueError("Bộ lọc thực thể vượt giới hạn")
        allowed = self._allowed_ids(domain, docs, terms) if domain or docs is not None or terms is not None else None
        if allowed is not None and not len(allowed):
            return []
        with self._search_lock:
            vector = self.encoder.encode_queries([query])
            if allowed is not None:
                selector = faiss.IDSelectorBatch(allowed)
                parameters = faiss.SearchParameters(sel=selector)
                scores, ids = self.index.search(vector, top_k, params=parameters)
            else:
                scores, ids = self.index.search(vector, top_k)
        pairs = [(int(vector_id), float(score)) for vector_id, score in zip(ids[0], scores[0]) if vector_id >= 0]
        if not pairs:
            return []
        placeholders = ",".join("?" for _ in pairs)
        with sqlite3.connect(self.metadata_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(f"SELECT * FROM chunks WHERE vector_id IN ({placeholders})", [item[0] for item in pairs]).fetchall()
        by_id = {int(row["vector_id"]): dict(row) for row in rows}
        output = []
        for vector_id, score in pairs:
            row = by_id.get(vector_id)
            if row and (not domain or row["domain"] == domain):
                output.append({**row, "score": score})
                if len(output) >= top_k:
                    break
        return output

