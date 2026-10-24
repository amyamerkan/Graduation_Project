import json
from pathlib import Path
import sqlite3

import numpy as np
import pytest

from vn_assistant.embedding import EmbeddingConfig, HashingEncoder
from vn_assistant.faiss_store import SCHEMA
from vn_assistant.index_recovery import recover_index


def database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?)", [
            (i, f"doc{i}:0", f"doc{i}", f"Văn bản di sản số {i} có thông tin văn hóa và lịch sử.", f"Tài liệu {i}", "heritage", "source", "") for i in range(5)])


def test_recovery_preserves_metadata_and_external_ids(tmp_path):
    import faiss

    metadata = tmp_path / "metadata.sqlite3"
    database(metadata)
    original = metadata.read_bytes()
    index_path = tmp_path / "vn.index"
    result = recover_index(metadata, index_path, EmbeddingConfig(), checkpoint_size=2, backend="hashing")
    assert result["vectors"] == 5
    assert metadata.read_bytes() == original
    index = faiss.read_index(str(index_path))
    assert index.ntotal == 5
    assert np.linalg.norm(index.reconstruct(4)) == pytest.approx(1, abs=1e-6)
    with pytest.raises(ValueError, match="đã tồn tại"):
        recover_index(metadata, index_path, EmbeddingConfig(), backend="hashing")


def test_recovery_resumes_committed_batch_after_encoder_failure(tmp_path, monkeypatch):
    import vn_assistant.index_recovery as module

    metadata = tmp_path / "metadata.sqlite3"
    database(metadata)
    encoder = HashingEncoder()
    encode = encoder.encode_passages
    calls = 0
    def fail(texts):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected_failure")
        return encode(texts)
    encoder.encode_passages = fail
    monkeypatch.setattr(module, "create_encoder", lambda *args, **kwargs: encoder)
    with pytest.raises(RuntimeError, match="injected_failure"):
        recover_index(metadata, tmp_path / "vn.index", EmbeddingConfig(), checkpoint_size=2, backend="hashing")
    assert json.loads((tmp_path / "recovery/state.json").read_text())["completed"] == 2
    encoder.encode_passages = encode
    assert recover_index(metadata, tmp_path / "vn.index", EmbeddingConfig(), checkpoint_size=2, backend="hashing")["vectors"] == 5
