import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from vn_assistant import api, cli
from vn_assistant.llm import LLMContextError, LLMError, LLMUnavailableError
from vn_assistant.router import QuestionRouter


class FakeGenerator:
    def __init__(self):
        self.ready = False
        self.loads = 0

    def status(self):
        return {"backend": "transformers", "model": "test-only", "ready": self.ready}

    def load(self):
        self.loads += 1
        self.ready = True
        return self.status()


class FakeAnswerService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def answer(self, question, top_k=5):
        self.calls.append((question, top_k))
        if self.error:
            raise self.error
        return {"answer": "Phản hồi có nguồn [E1]", "status": "verified", "citations": [{"id": "E1"}], "cross_check": {"passed": True}}


@pytest.fixture
def client():
    generator = FakeGenerator()
    api.app.dependency_overrides[api.get_generator] = lambda: generator
    with TestClient(api.app) as test_client:
        yield test_client
    api.app.dependency_overrides.clear()


def test_answer_endpoint_preserves_answer_and_citations(client):
    service = FakeAnswerService()
    api.app.dependency_overrides[api.get_answer_service] = lambda: service

    response = client.post("/v1/answer", json={"question": "  Mỹ Sơn ở đâu?  ", "top_k": 3})

    assert response.status_code == 200
    assert service.calls == [("Mỹ Sơn ở đâu?", 3)]
    assert response.json()["citations"] == [{"id": "E1"}]
    assert response.json()["cross_check"] == {"passed": True}


@pytest.mark.parametrize("error,status_code", [
    (LLMUnavailableError("model unavailable"), 503),
    (LLMError("generation failed"), 503),
    (LLMContextError("context too long"), 400),
    (ValueError("bad input"), 400),
])
def test_answer_errors_map_to_service_or_input_status(client, error, status_code):
    api.app.dependency_overrides[api.get_answer_service] = lambda: FakeAnswerService(error)

    response = client.post("/v1/answer", json={"question": "Mỹ Sơn ở đâu?"})

    assert response.status_code == status_code
    assert response.json()["detail"] == str(error)


@pytest.mark.parametrize("body", [
    {"question": "   "},
    {"question": "A"},
    {"question": "Mỹ Sơn?", "top_k": 0},
    {"question": "Mỹ Sơn?", "top_k": 21},
    {"question": "a" * 2001},
])
def test_answer_request_validation_does_not_invoke_model(client, body):
    service = FakeAnswerService()
    api.app.dependency_overrides[api.get_answer_service] = lambda: service

    response = client.post("/v1/answer", json=body)

    assert response.status_code == 422
    assert service.calls == []


def test_status_and_health_do_not_warm_up_model(client, tmp_path, monkeypatch):
    for filename in ("router.joblib", "kg.ttl", "vn.index", "metadata.sqlite3"):
        (tmp_path / filename).touch()
    settings = replace(api.SETTINGS, router_model_path=tmp_path / "router.joblib", kg_ttl_path=tmp_path / "kg.ttl", faiss_index_path=tmp_path / "vn.index", faiss_metadata_path=tmp_path / "metadata.sqlite3")
    monkeypatch.setattr(api, "SETTINGS", settings)
    monkeypatch.setattr(api, "_runtime_state", {"router_ready": False, "kg_ready": False, "faiss_ready": False})

    status = client.get("/v1/llm/status")
    health = client.get("/health")

    assert status.status_code == 200 and status.json()["ready"] is False
    assert health.json()["artifacts_present"] == {"router": True, "kg": True, "faiss": True}
    assert health.json()["kg_ready"] is False
    assert health.json()["faiss_ready"] is False
    assert health.json()["llm"]["ready"] is False
    warmup = client.post("/v1/llm/warmup")
    assert warmup.status_code == 200 and warmup.json()["ready"] is True
    assert client.get("/v1/llm/status").json()["ready"] is True


def test_vllm_warmup_probes_remote_backend(client):
    class RemoteGenerator:
        def __init__(self):
            self.probes = 0

        def probe(self):
            self.probes += 1
            return {"backend": "vllm", "ready": True}

    generator = RemoteGenerator()
    api.app.dependency_overrides[api.get_generator] = lambda: generator

    response = client.post("/v1/llm/warmup")

    assert response.status_code == 200 and response.json()["ready"] is True
    assert generator.probes == 1


def test_unavailable_warmup_returns_503(client):
    class BrokenGenerator:
        def load(self):
            raise LLMUnavailableError("model files missing")

    api.app.dependency_overrides[api.get_generator] = lambda: BrokenGenerator()

    response = client.post("/v1/llm/warmup")

    assert response.status_code == 503
    assert response.json()["detail"] == "model files missing"


def test_retrieval_routes_remain_available_without_llm(client, tmp_path):
    api.app.dependency_overrides[api.get_router] = lambda: QuestionRouter(tmp_path / "missing")

    class Processor:
        def process(self, question, top_k):
            return {"question": question, "kg_results": [{"code": "00070"}], "rag_results": [], "effective_route": "kg"}

    class Retriever:
        def search(self, question, top_k, domain):
            return [{"text": "evidence", "domain": domain, "score": 0.9}]

    api.app.dependency_overrides[api.get_processor] = lambda: Processor()
    api.app.dependency_overrides[api.get_faiss] = lambda: Retriever()

    classification = client.post("/v1/classify", json={"question": "Đơn vị có mã 00070 là gì?"})
    query = client.post("/v1/query", json={"question": "Đơn vị có mã 00070 là gì?"})
    rag = client.post("/v1/rag/search", json={"question": "Mỹ Sơn có giá trị gì?", "domain": "heritage"})

    assert classification.status_code == 200 and classification.json()["plan"]["kg"]["query"] == "03_unit_by_code"
    assert query.status_code == 200 and query.json()["effective_route"] == "kg"
    assert rag.status_code == 200 and rag.json()["results"][0]["domain"] == "heritage"


def test_lazy_processor_does_not_load_faiss_for_successful_kg(tmp_path, monkeypatch):
    class KG:
        def execute(self, query, params):
            return [{"code": "00070", "name": "Phường X"}]

    calls = []
    monkeypatch.setattr(api, "get_router", lambda: QuestionRouter(tmp_path / "missing"))
    monkeypatch.setattr(api, "get_kg", lambda: KG())
    monkeypatch.setattr(api, "get_faiss", lambda: calls.append("FAISS loaded"))
    api.get_processor.cache_clear()
    try:
        result = api.get_processor().process("Đơn vị có mã 00070 là gì?")
    finally:
        api.get_processor.cache_clear()

    assert result["effective_route"] == "kg"
    assert calls == []


def test_generator_factory_maps_settings_without_loading(monkeypatch):
    captured = []
    generator = FakeGenerator()
    monkeypatch.setattr(api, "create_generator", lambda config: captured.append(config) or generator)
    api.get_generator.cache_clear()
    try:
        assert api.get_generator() is generator
        assert api.get_generator() is generator
    finally:
        api.get_generator.cache_clear()

    assert len(captured) == 1
    assert captured[0].model_name == api.SETTINGS.llm_model
    assert captured[0].base_url == api.SETTINGS.llm_base_url
    assert captured[0].local_files_only == api.SETTINGS.llm_local_files_only
    assert generator.loads == 0


def test_cli_answer_and_warmup_use_shared_factories(monkeypatch, capsys):
    service = FakeAnswerService()
    generator = FakeGenerator()
    monkeypatch.setattr(api, "get_answer_service", lambda: service)
    monkeypatch.setattr(api, "get_generator", lambda: generator)
    monkeypatch.setattr("sys.argv", ["vn-assistant", "answer", "Mỹ Sơn ở đâu?", "--top-k", "2"])
    cli.main()
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
    assert service.calls == [("Mỹ Sơn ở đâu?", 2)]

    monkeypatch.setattr("sys.argv", ["vn-assistant", "warmup-llm"])
    cli.main()
    assert json.loads(capsys.readouterr().out)["ready"] is True
    assert generator.loads == 1


def test_cli_serve_default_port_is_8001(monkeypatch):
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr("sys.argv", ["vn-assistant", "serve"])

    cli.main()

    assert calls[0][1]["port"] == 8001


def test_cli_query_uses_lazy_shared_processor(monkeypatch, capsys):
    class Processor:
        def process(self, question, top_k):
            return {"question": question, "top_k": top_k, "effective_route": "kg"}

    monkeypatch.setattr(api, "get_processor", lambda: Processor())
    monkeypatch.setattr("sys.argv", ["vn-assistant", "query", "Đơn vị mã 00070?", "--top-k", "2"])

    cli.main()

    output = json.loads(capsys.readouterr().out)
    assert output["effective_route"] == "kg"
    assert output["top_k"] == 2


def test_invalid_answer_configuration_returns_service_unavailable(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException

    api.get_answer_service.cache_clear()
    monkeypatch.setattr(api, "SETTINGS", SimpleNamespace(answer_max_evidence=0, answer_min_rag_score=.70))
    monkeypatch.setattr(api, "get_processor", lambda: object())
    monkeypatch.setattr(api, "get_generator", lambda: object())
    with pytest.raises(HTTPException) as caught:
        api.get_answer_service()
    assert caught.value.status_code == 503
