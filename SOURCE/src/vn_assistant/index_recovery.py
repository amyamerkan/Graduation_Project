from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

import numpy as np

from .embedding import EmbeddingConfig, create_encoder


def recover_index(metadata_path, index_path, embedding_config, *, checkpoint_size=256, backend="transformer"):
    import faiss

    metadata_path, index_path = Path(metadata_path).resolve(), Path(index_path).resolve()
    work = index_path.parent / "recovery"
    work.mkdir(exist_ok=True)
    with (work / "process.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if index_path.exists():
            raise ValueError("Chỉ mục đã tồn tại; không ghi đè")
        digest = hashlib.sha256()
        with metadata_path.open("rb") as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(block)
        signature = {"metadata_sha256": digest.hexdigest(), "embedding": asdict(embedding_config), "backend": backend}
        state_path = work / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {"signature": signature, "completed": 0}
        if state.get("signature") != signature:
            raise ValueError("Checkpoint không khớp metadata hoặc mô hình")
        with sqlite3.connect(metadata_path.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
            total, low, high = connection.execute("SELECT COUNT(*),MIN(vector_id),MAX(vector_id) FROM chunks").fetchone()
            if not total or low != 0 or high != total - 1:
                raise ValueError("Recovery yêu cầu vector_id liên tục từ 0")
            encoder = create_encoder(embedding_config, backend=backend)
            dimension = encoder.dimension
            vector_path = work / "vectors.f32"
            if state["completed"] and (not vector_path.is_file() or vector_path.stat().st_size != total * dimension * 4):
                raise ValueError("Checkpoint vector không đầy đủ")
            vectors = np.memmap(vector_path, dtype="float32", mode="r+" if vector_path.exists() else "w+", shape=(total, dimension))
            initial = completed = state["completed"]
            start = time.monotonic()
            progress_path = index_path.parent / "recovery_progress.json"
            def save(status):
                elapsed = time.monotonic() - start
                rate = (completed - initial) / max(elapsed, .001)
                payload = {"status": status, "pid": os.getpid(), "vectors": completed, "total": total,
                           "percent": round(completed * 100 / total, 2), "vectors_per_second": round(rate, 2),
                           "estimated_remaining_seconds": round((total - completed) / rate) if rate > 0 else None,
                           "device": embedding_config.device, "updated_at": datetime.now(timezone.utc).isoformat()}
                temporary = progress_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(payload, indent=2))
                os.replace(temporary, progress_path)
                print(json.dumps(payload), flush=True)
            save("encoding")
            try:
                cursor = connection.execute("SELECT vector_id,text FROM chunks WHERE vector_id>=? ORDER BY vector_id", (completed,))
                while rows := cursor.fetchmany(checkpoint_size):
                    values = np.asarray(encoder.encode_passages([row[1] for row in rows]), dtype="float32")
                    if values.shape != (len(rows), dimension) or not np.isfinite(values).all():
                        raise ValueError("Embedding không hợp lệ")
                    faiss.normalize_L2(values)
                    vectors[completed:completed + len(rows)] = values
                    vectors.flush()
                    completed += len(rows)
                    state["completed"] = completed
                    temporary = state_path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(state, indent=2))
                    os.replace(temporary, state_path)
                    save("encoding")
                save("publishing")
                index = faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))
                for offset in range(0, total, 8192):
                    end = min(offset + 8192, total)
                    index.add_with_ids(np.asarray(vectors[offset:end]), np.arange(offset, end, dtype="int64"))
                temporary = work / "vn.index.tmp"
                faiss.write_index(index, str(temporary))
                checked = faiss.read_index(str(temporary))
                if checked.ntotal != total or checked.d != dimension:
                    raise ValueError("Chỉ mục khôi phục không khớp metadata")
                os.replace(temporary, index_path)
                save("complete")
                return {"vectors": total, "dimension": dimension, "metadata_sha256": signature["metadata_sha256"],
                        "embedding": asdict(embedding_config), "elapsed_seconds": round(time.monotonic() - start, 3)}
            except BaseException:
                save("interrupted")
                raise

