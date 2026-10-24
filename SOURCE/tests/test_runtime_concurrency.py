from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import time

from vn_assistant import api, metadata_retriever
from vn_assistant.embedding import EmbeddingConfig, TransformerEncoder
from vn_assistant.llm import LLMConfig, TransformerGenerator
from vn_assistant.metadata_retriever import MetadataFaissRetriever
from vn_assistant.runtime import MODEL_EXECUTION_LOCK


def test_api_constructs_one_retriever_during_concurrent_cold_start(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata.sqlite3"
    metadata.touch()
    monkeypatch.setattr(api, "SETTINGS", replace(api.SETTINGS, faiss_index_path=tmp_path / "missing.index", faiss_metadata_path=metadata))
    monkeypatch.setattr(api, "_runtime_state", {"faiss_ready": False})
    calls = []
    class Retriever:
        def __init__(self, *args):
            calls.append(1)
            time.sleep(.02)
    monkeypatch.setattr(api, "MetadataFaissRetriever", Retriever)
    api.get_faiss.cache_clear()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            instances = list(pool.map(lambda _: api.get_faiss(), range(8)))
        assert len(calls) == 1
        assert all(item is instances[0] for item in instances)
    finally:
        api.get_faiss.cache_clear()


def test_lazy_encoder_is_shared_during_simultaneous_requests(tmp_path, monkeypatch):
    calls = []
    def create(*args, **kwargs):
        calls.append(1)
        time.sleep(.02)
        return object()
    monkeypatch.setattr(metadata_retriever, "create_encoder", create)
    retriever = MetadataFaissRetriever(tmp_path / "metadata.sqlite3", EmbeddingConfig())
    with ThreadPoolExecutor(max_workers=8) as pool:
        encoders = list(pool.map(lambda _: retriever.encoder, range(8)))
    assert len(calls) == 1
    assert all(item is encoders[0] for item in encoders)


def test_embedding_and_llm_share_model_execution_gate():
    generator = TransformerGenerator(LLMConfig())
    encoder = TransformerEncoder.__new__(TransformerEncoder)
    entered, release = threading.Event(), threading.Event()
    class Model:
        def encode(self, *args, **kwargs):
            entered.set()
            assert release.wait(2)
            return [[1.0, 0.0]]
    encoder.config = EmbeddingConfig()
    encoder.model = Model()
    assert generator._lock is MODEL_EXECUTION_LOCK
    with ThreadPoolExecutor(max_workers=1) as pool:
        work = pool.submit(encoder.encode_queries, ["Ca trù"])
        assert entered.wait(1)
        acquired = generator._lock.acquire(timeout=.01)
        try:
            assert not acquired
        finally:
            if acquired:
                generator._lock.release()
            release.set()
        assert work.result(timeout=2).shape == (1, 2)


def test_parallel_system_warmup_initializes_embedding_once(monkeypatch):
    monkeypatch.setattr(api, "_runtime_state", {"faiss_ready": False})
    calls = {"prepare": 0, "encode": 0}
    class Encoder:
        def encode_queries(self, *args):
            calls["encode"] += 1
            time.sleep(.02)
    class Retriever:
        encoder = Encoder()
        def warmup(self):
            calls["prepare"] += 1
    class Generator:
        def load(self):
            return {"ready": True}
    monkeypatch.setattr(api, "get_kg", lambda: object())
    monkeypatch.setattr(api, "get_faiss", lambda: Retriever())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: api.system_warmup(Generator()), range(8)))
    assert calls == {"prepare": 1, "encode": 1}
    assert all(item["status"] == "ready" for item in results)
