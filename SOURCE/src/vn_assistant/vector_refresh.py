"""Rebuild a versioned index, retaining only identical pretrained passage vectors."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

import numpy as np

from .embedding import EmbeddingConfig, create_encoder
from .faiss_store import SCHEMA, iter_chunks


def refresh_vectors(dataset, seed_dir, output_dir, *, device="cpu", batch_size=32, backend="transformer"):
    import faiss

    dataset, seed_dir, output_dir = map(lambda p: Path(p).resolve(), (dataset, seed_dir, output_dir))
    if seed_dir == output_dir:
        raise ValueError("Refresh output must differ from the active index directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any((output_dir / name).exists() for name in ("vn.index", "metadata.sqlite3", "index_config.json")):
        raise ValueError("Refresh output already contains an index; select a new version")
    saved = json.loads((seed_dir / "index_config.json").read_text())
    if saved.get("backend") != backend:
        raise ValueError("Embedding backend differs from seed index")
    config = replace(EmbeddingConfig(**saved["embedding"]), device=device, batch_size=batch_size)
    seed = faiss.read_index(str(seed_dir / "vn.index"))
    with sqlite3.connect((seed_dir / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True) as connection:
        old = connection.execute("SELECT vector_id,text FROM chunks ORDER BY vector_id").fetchall()
    if len(old) != seed.ntotal:
        raise ValueError("Seed index and metadata counts differ")
    # Passage encoding depends on text and the unchanged saved embedding preprocessing.
    by_text = {text: vector_id for vector_id, text in old}
    chunks = list(iter_chunks(dataset, saved["chunk_size"], saved["overlap"]))
    if not chunks or len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("Empty corpus or duplicate chunk identities")
    vectors = np.empty((len(chunks), seed.d), dtype="float32")
    missing, reused = [], 0
    for position, chunk in enumerate(chunks):
        previous = by_text.get(chunk["text"])
        if previous is None:
            missing.append(position)
        else:
            vectors[position] = seed.reconstruct(int(previous))
            reused += 1
    start = time.monotonic()
    encoded = 0

    def progress(status):
        value = {"status": status, "vectors": reused + encoded, "total": len(chunks),
                 "reused_vectors": reused, "encoded_vectors": encoded, "new_vectors_total": len(missing),
                 "elapsed_seconds": round(time.monotonic() - start, 3), "device": device,
                 "dataset": str(dataset), "updated_at": datetime.now(timezone.utc).isoformat()}
        temporary = output_dir / "build_progress.tmp"
        temporary.write_text(json.dumps(value, indent=2))
        os.replace(temporary, output_dir / "build_progress.json")
        print(json.dumps(value), flush=True)

    progress("encoding")
    if missing:
        encoder = create_encoder(config, backend=backend)
        if encoder.dimension != seed.d:
            raise ValueError("Embedding dimension differs from seed index")
        last = time.monotonic()
        for offset in range(0, len(missing), batch_size):
            positions = missing[offset:offset + batch_size]
            values = encoder.encode_passages([chunks[i]["text"] for i in positions])
            if values.shape != (len(positions), seed.d) or not np.isfinite(values).all():
                raise ValueError("Invalid refreshed embeddings")
            vectors[positions] = values
            encoded += len(positions)
            if time.monotonic() - last > 20:
                progress("encoding")
                last = time.monotonic()
    if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
        raise ValueError("Refresh requires finite normalized passage vectors")
    progress("writing_index")
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(seed.d))
    index.add_with_ids(vectors, np.arange(len(chunks), dtype="int64"))
    with sqlite3.connect(output_dir / "metadata.sqlite3") as connection:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)", [
            (i, c["chunk_id"], c["doc_id"], c["text"], c["title"], c["domain"], c["source"], c["source_url"])
            for i, c in enumerate(chunks)])
        domains = dict(connection.execute("SELECT domain,COUNT(*) FROM chunks GROUP BY domain"))
        documents = connection.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks").fetchone()[0]
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Refreshed metadata integrity check failed")
    faiss.write_index(index, str(output_dir / "vn.index"))
    report = {"backend": backend, "production_ready": backend == "transformer", "embedding": asdict(config),
              "metric": saved["metric"], "documents": documents, "vectors": len(chunks), "dimension": seed.d,
              "chunks_by_domain": domains, "chunk_size": saved["chunk_size"], "overlap": saved["overlap"],
              "reused_vectors": reused, "encoded_vectors": encoded,
              "build_signature": {"dataset": str(dataset), "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                                  "seed_config_sha256": hashlib.sha256((seed_dir / "index_config.json").read_bytes()).hexdigest(),
                                  "embedding": asdict(config), "backend": backend, "format_version": 3},
              "refresh_scope": "Identical passage text reuses vectors with saved encoder settings; changed/new passages re-encoded. No E5 fine-tuning."}
    (output_dir / "index_config.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    checked = faiss.read_index(str(output_dir / "vn.index"))
    if checked.ntotal != len(chunks):
        raise ValueError("Refreshed index count mismatch")
    progress("complete")
    return report
