import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import threading
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from vn_assistant import llm
from vn_assistant.llm import (
    LLMConfig,
    LLMContextError,
    LLMError,
    LLMTimeoutError,
    LLMUnavailableError,
    TransformerGenerator,
    VLLMGenerator,
    create_generator,
)


MESSAGES = [{"role": "system", "content": "Chỉ dùng minh chứng."}, {"role": "user", "content": "Tên đơn vị là gì?"}]


class FakeTensor:
    def __init__(self, values):
        self.values = values
        self.shape = (len(values), len(values[0])) if values and isinstance(values[0], list) else (len(values),)

    def to(self, device):
        return self

    def __getitem__(self, key):
        if isinstance(key, tuple):
            row, selection = key
            return FakeTensor(self.values[row][selection])
        return self.values[key]

    def tolist(self):
        return self.values


class FakeTokenizer:
    chat_template = "available"
    model_max_length = 4096
    eos_token_id = 2
    pad_token_id = None

    def __init__(self, token_count=2, text='{"claims": []}'):
        self.token_count = token_count
        self.text = text
        self.template_kwargs = None
        self.tokenize_kwargs = None

    def apply_chat_template(self, messages, **kwargs):
        self.template_kwargs = kwargs
        return "complete evidence prompt"

    def __call__(self, prompt, **kwargs):
        self.tokenize_kwargs = kwargs
        return {"input_ids": FakeTensor([[1] * self.token_count]), "attention_mask": FakeTensor([[1] * self.token_count])}

    def decode(self, tokens, **kwargs):
        return self.text


class FakeModel:
    config = SimpleNamespace(max_position_embeddings=4096)
    generation_config = SimpleNamespace(eos_token_id=2)

    def __init__(self, token_count=2, suffix=None):
        self.token_count = token_count
        self.suffix = suffix or [7, 2]
        self.kwargs = None
        self.device = None
        self.evaluated = False

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        self.evaluated = True

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return FakeTensor([[1] * self.token_count + self.suffix])


def fake_generator(token_count=2, text='{"claims": []}', suffix=None, **config):
    generator = TransformerGenerator(LLMConfig(**config))
    generator._model = FakeModel(token_count, suffix)
    generator._tokenizer = FakeTokenizer(token_count, text)
    generator._torch = SimpleNamespace(inference_mode=nullcontext)
    generator._device = "cpu"
    return generator


@pytest.mark.parametrize("changes", [
    {"backend": "unknown"},
    {"model_name": ""},
    {"device": "metal"},
    {"max_new_tokens": 0},
    {"max_new_tokens": True},
    {"context_window": 384},
    {"timeout_s": float("inf")},
    {"timeout_s": 0},
    {"local_files_only": "true"},
    {"backend": "vllm", "base_url": "file:///tmp/model"},
    {"backend": "vllm", "base_url": "https://key:secret@example.com/v1"},
])
def test_config_rejects_invalid_values(changes):
    with pytest.raises(ValueError):
        LLMConfig(**changes)


def test_factory_is_lazy_and_reports_not_ready():
    generator = create_generator(LLMConfig())
    assert isinstance(generator, TransformerGenerator)
    assert generator.status()["ready"] is False
    assert generator._model is None
    assert isinstance(create_generator(LLMConfig(backend="vllm")), VLLMGenerator)


def test_load_selects_mps_and_disables_remote_code(monkeypatch):
    tokenizer = FakeTokenizer()
    model = FakeModel()
    calls = []
    fake_torch = SimpleNamespace(
        float32="float32", float16="float16",
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)),
    )

    def load_tokenizer(name, **kwargs):
        calls.append(("tokenizer", name, kwargs))
        return tokenizer

    def load_model(name, **kwargs):
        calls.append(("model", name, kwargs))
        return model

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=load_tokenizer),
        AutoModelForCausalLM=SimpleNamespace(from_pretrained=load_model),
    ))
    generator = TransformerGenerator(LLMConfig())
    assert calls == []
    assert generator.load()["ready"]
    assert generator.status()["device"] == "mps"
    assert model.evaluated
    assert calls[1][2]["torch_dtype"] == "float16"
    assert calls[0][2]["local_files_only"] is True
    assert calls[0][2]["trust_remote_code"] is False
    generator.load()
    assert len(calls) == 2


def test_unavailable_explicit_device_does_not_fall_back(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
    ))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoTokenizer=None, AutoModelForCausalLM=None))
    generator = TransformerGenerator(LLMConfig(device="mps"))
    with pytest.raises(LLMUnavailableError, match="MPS"):
        generator.load()
    assert not generator.status()["ready"]


def test_transformer_generation_is_bounded_greedy_and_only_decodes_new_tokens():
    generator = fake_generator()
    assert generator.generate(MESSAGES) == '{"claims": []}'
    assert generator._model.kwargs["do_sample"] is False
    assert generator._model.kwargs["max_new_tokens"] == 384
    assert 0 < generator._model.kwargs["max_time"] <= 60
    assert generator._tokenizer.template_kwargs["enable_thinking"] is False
    assert generator._tokenizer.tokenize_kwargs["truncation"] is False
    assert generator._tokenizer.tokenize_kwargs["add_special_tokens"] is False
    assert generator.status()["generation_count"] == 1


def test_transformer_rejects_overflow_without_truncating_evidence():
    generator = fake_generator(token_count=15, context_window=20, max_new_tokens=6)
    with pytest.raises(LLMContextError):
        generator.generate(MESSAGES)
    assert generator._model.kwargs is None
    assert generator.status()["generation_count"] == 0


def test_transformer_rejects_token_limited_partial_reply():
    generator = fake_generator(max_new_tokens=2, suffix=[7, 8])
    with pytest.raises(LLMError, match="ngân sách token"):
        generator.generate(MESSAGES)


def test_transformer_rejects_empty_reply():
    generator = fake_generator(text=" ")
    with pytest.raises(LLMError, match="rỗng"):
        generator.generate(MESSAGES)


def test_transformer_admission_timeout():
    generator = fake_generator(timeout_s=0.001)
    entered, release = threading.Event(), threading.Event()
    def hold_model():
        with generator._lock:
            entered.set()
            assert release.wait(2)
    with ThreadPoolExecutor(max_workers=1) as pool:
        held = pool.submit(hold_model)
        assert entered.wait(1)
        try:
            with pytest.raises(LLMTimeoutError):
                generator.generate(MESSAGES)
        finally:
            release.set()
        held.result(timeout=2)


@pytest.mark.parametrize("messages", [[], [{"role": "tool", "content": "x"}], [{"role": "user", "content": ""}], [{"role": "assistant", "content": "x"}]])
def test_invalid_messages_rejected_before_model_load(messages):
    generator = create_generator(LLMConfig())
    with pytest.raises(ValueError):
        generator.generate(messages)
    assert not generator.status()["ready"]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.payload[:size]


def test_vllm_auth_token_budget_and_completion_contract(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data) if request.data else None
        calls.append((request.full_url, request.get_header("Authorization"), payload, timeout))
        if request.full_url.endswith("/tokenize"):
            return FakeResponse({"count": 10, "max_model_len": 4096})
        return FakeResponse({"choices": [{"finish_reason": "stop", "message": {"content": " Phản hồi [E1]. "}}]})

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)
    generator = VLLMGenerator(LLMConfig(backend="vllm", api_key="private-key"))
    assert generator.generate(MESSAGES) == "Phản hồi [E1]."
    assert calls[0][0] == "http://127.0.0.1:8001/tokenize"
    assert calls[1][0] == "http://127.0.0.1:8001/v1/chat/completions"
    assert calls[0][1] == "Bearer private-key"
    assert calls[1][2]["temperature"] == 0
    assert calls[1][2]["max_tokens"] == 384
    assert calls[1][2]["chat_template_kwargs"] == calls[0][2]["chat_template_kwargs"]
    assert generator.status()["ready"]
    assert "private-key" not in str(generator.status())


def test_vllm_context_error_never_calls_generation(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse({"count": 4000, "max_model_len": 4096})

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)
    generator = VLLMGenerator(LLMConfig(backend="vllm"))
    with pytest.raises(LLMContextError):
        generator.generate(MESSAGES)
    assert calls == ["http://127.0.0.1:8001/tokenize"]


@pytest.mark.parametrize("reply", [
    {"choices": []},
    {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": None}}]},
    b"not-json",
    {"error": "server failure"},
])
def test_vllm_rejects_invalid_or_truncated_completions(monkeypatch, reply):
    responses = [FakeResponse({"count": 10, "max_model_len": 4096}), FakeResponse(reply)]
    monkeypatch.setattr(llm, "urlopen", lambda request, timeout: responses.pop(0))
    generator = VLLMGenerator(LLMConfig(backend="vllm"))
    with pytest.raises(LLMError):
        generator.generate(MESSAGES)
    assert generator.status()["generation_count"] == 0


def test_vllm_probe_checks_configured_model(monkeypatch):
    generator = VLLMGenerator(LLMConfig(backend="vllm", model_name="local-model"))
    monkeypatch.setattr(llm, "urlopen", lambda request, timeout: FakeResponse({"data": [{"id": "other-model"}]}))
    with pytest.raises(LLMUnavailableError):
        generator.probe()
    monkeypatch.setattr(llm, "urlopen", lambda request, timeout: FakeResponse({"data": [{"id": "local-model"}]}))
    assert generator.probe()["ready"]


@pytest.mark.parametrize("error, expected", [
    (socket.timeout(), LLMTimeoutError),
    (URLError(socket.timeout()), LLMTimeoutError),
    (URLError("unreachable"), LLMUnavailableError),
    (HTTPError("http://127.0.0.1:8001/v1/models", 503, "busy", {}, None), LLMUnavailableError),
])
def test_vllm_transport_errors_are_explicit(monkeypatch, error, expected):
    def fail(request, timeout):
        raise error

    monkeypatch.setattr(llm, "urlopen", fail)
    generator = VLLMGenerator(LLMConfig(backend="vllm"))
    with pytest.raises(expected):
        generator.probe()
    assert not generator.status()["ready"]
