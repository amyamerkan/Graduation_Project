from __future__ import annotations

import json
import math
import socket
import threading
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .runtime import MODEL_EXECUTION_LOCK


class LLMError(RuntimeError):
    pass


class LLMUnavailableError(LLMError):
    pass


class LLMContextError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    backend: str = "transformers"
    model_name: str = "Qwen/Qwen3-0.6B"
    device: str = "auto"
    max_new_tokens: int = 384
    context_window: int = 4096
    timeout_s: float = 60.0
    base_url: str = "http://127.0.0.1:8001/v1"
    api_key: str | None = None
    local_files_only: bool = True
    revision: str | None = None
    trust_remote_code: bool = False

    def __post_init__(self):
        if self.backend not in {"transformers", "vllm"}:
            raise ValueError("Backend LLM phải là transformers hoặc vllm")
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError("Tên mô hình LLM không được để trống")
        if self.device not in {"auto", "cpu", "mps", "cuda"}:
            raise ValueError("Thiết bị LLM phải là auto, cpu, mps hoặc cuda")
        if type(self.max_new_tokens) is not int or self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens phải là số nguyên dương")
        if type(self.context_window) is not int or self.context_window <= self.max_new_tokens:
            raise ValueError("context_window phải lớn hơn max_new_tokens")
        if not isinstance(self.timeout_s, (int, float)) or not math.isfinite(self.timeout_s) or self.timeout_s <= 0:
            raise ValueError("timeout_s phải là số dương hữu hạn")
        if not isinstance(self.local_files_only, bool) or not isinstance(self.trust_remote_code, bool):
            raise ValueError("Cấu hình tải mô hình phải dùng giá trị boolean")
        if self.backend == "vllm":
            parsed = urlsplit(self.base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
                raise ValueError("base_url vLLM không hợp lệ")
            if parsed.username or parsed.password:
                raise ValueError("Thông tin xác thực vLLM phải được đặt trong api_key")


class Generator(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> str: ...

    def status(self) -> dict: ...


def _validate_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("Hội thoại LLM không được để trống")
    prepared = []
    for position, message in enumerate(messages):
        if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant"}:
            raise ValueError("Vai trò hội thoại LLM không hợp lệ")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Nội dung hội thoại LLM phải là văn bản không rỗng")
        if message["role"] == "system" and position != 0:
            raise ValueError("System prompt phải nằm ở đầu hội thoại")
        prepared.append({"role": message["role"], "content": content})
    if prepared[-1]["role"] != "user":
        raise ValueError("Hội thoại LLM phải kết thúc bằng câu hỏi của người dùng")
    return prepared


class TransformerGenerator:
    def __init__(self, config: LLMConfig):
        if config.backend != "transformers":
            raise ValueError("TransformerGenerator cần backend transformers")
        self.config = config
        self._lock = MODEL_EXECUTION_LOCK
        self._model = None
        self._tokenizer = None
        self._torch = None
        self._device = None
        self._context_window = config.context_window
        self._error = None
        self._generation_count = 0
        self._last_latency_ms = None

    def status(self) -> dict:
        return {
            "backend": "transformers",
            "model": self.config.model_name,
            "device": self._device or self.config.device,
            "ready": self._model is not None and self._tokenizer is not None,
            "context_window": self._context_window,
            "max_new_tokens": self.config.max_new_tokens,
            "error": self._error,
            "generation_count": self._generation_count,
            "last_latency_ms": self._last_latency_ms,
        }

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            device = self.config.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
            if device == "mps" and not torch.backends.mps.is_available():
                raise LLMUnavailableError("Thiết bị MPS không khả dụng trên máy này")
            if device == "cuda" and not torch.cuda.is_available():
                raise LLMUnavailableError("Thiết bị CUDA không khả dụng trên máy này")
            kwargs = {
                "local_files_only": self.config.local_files_only,
                "trust_remote_code": self.config.trust_remote_code,
            }
            if self.config.revision is not None:
                kwargs["revision"] = self.config.revision
            tokenizer = AutoTokenizer.from_pretrained(self.config.model_name, **kwargs)
            if not getattr(tokenizer, "chat_template", None):
                raise LLMUnavailableError("Mô hình chưa có chat template; hãy cấu hình mô hình chat/instruct")
            model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=torch.float32 if device == "cpu" else torch.float16,
                **kwargs,
            )
            model = model.to(device)
            model.eval()
            limits = [self.config.context_window]
            for value in [getattr(model.config, "max_position_embeddings", None), getattr(tokenizer, "model_max_length", None)]:
                if isinstance(value, int) and 0 < value < 1_000_000:
                    limits.append(value)
            context_window = min(limits)
            if context_window <= self.config.max_new_tokens:
                raise LLMUnavailableError("Ngữ cảnh của mô hình nhỏ hơn ngân sách sinh câu trả lời")
            self._model = model
            self._tokenizer = tokenizer
            self._torch = torch
            self._device = device
            self._context_window = context_window
            self._error = None
        except LLMError as exc:
            self._error = str(exc)
            raise
        except Exception as exc:
            self._error = f"Không tải được mô hình {self.config.model_name}: {type(exc).__name__}"
            raise LLMUnavailableError(self._error) from exc

    def load(self) -> dict:
        if not self._lock.acquire(timeout=self.config.timeout_s):
            raise LLMTimeoutError("Hết thời gian chờ tải mô hình LLM")
        try:
            self._load()
            return self.status()
        finally:
            self._lock.release()

    def generate(self, messages: list[dict[str, str]]) -> str:
        prepared = _validate_messages(messages)
        started = time.monotonic()
        if not self._lock.acquire(timeout=self.config.timeout_s):
            raise LLMTimeoutError("Hết thời gian chờ lượt sinh câu trả lời LLM")
        try:
            self._load()
            prompt = self._tokenizer.apply_chat_template(prepared, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            inputs = self._tokenizer(prompt, return_tensors="pt", add_special_tokens=False, truncation=False)
            input_tokens = int(inputs["input_ids"].shape[-1])
            if input_tokens + self.config.max_new_tokens > self._context_window:
                raise LLMContextError(f"Ngữ cảnh có {input_tokens} token, vượt ngân sách {self._context_window - self.config.max_new_tokens}")
            remaining = self.config.timeout_s - (time.monotonic() - started)
            if remaining <= 0:
                raise LLMTimeoutError("Hết thời gian chuẩn bị ngữ cảnh LLM")
            inputs = {key: value.to(self._device) for key, value in inputs.items()}
            eos = getattr(self._model.generation_config, "eos_token_id", None)
            if eos is None:
                eos = self._tokenizer.eos_token_id
            pad = self._tokenizer.pad_token_id
            if pad is None:
                pad = eos[0] if isinstance(eos, list) else eos
            kwargs = {
                "max_new_tokens": self.config.max_new_tokens,
                "max_time": remaining,
                "do_sample": False,
                "num_beams": 1,
                "use_cache": True,
                "return_dict_in_generate": False,
            }
            if eos is not None:
                kwargs["eos_token_id"] = eos
            if pad is not None:
                kwargs["pad_token_id"] = pad
            with self._torch.inference_mode():
                output = self._model.generate(**inputs, **kwargs)
            if time.monotonic() - started > self.config.timeout_s:
                raise LLMTimeoutError("Mô hình LLM vượt thời gian sinh câu trả lời")
            new_tokens = output[0, input_tokens:]
            token_ids = new_tokens.tolist()
            stop_ids = set(eos) if isinstance(eos, list) else {eos} if eos is not None else set()
            if len(token_ids) >= self.config.max_new_tokens and (not token_ids or token_ids[-1] not in stop_ids):
                raise LLMError("Câu trả lời LLM bị cắt do hết ngân sách token")
            text = self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            if not text:
                raise LLMError("Mô hình LLM trả về câu trả lời rỗng")
            self._generation_count += 1
            self._last_latency_ms = round((time.monotonic() - started) * 1000, 2)
            self._error = None
            return text
        except LLMError as exc:
            self._error = str(exc)
            raise
        except Exception as exc:
            self._error = f"Sinh câu trả lời LLM thất bại: {type(exc).__name__}"
            raise LLMError(self._error) from exc
        finally:
            self._lock.release()


class VLLMGenerator:
    def __init__(self, config: LLMConfig):
        if config.backend != "vllm":
            raise ValueError("VLLMGenerator cần backend vllm")
        self.config = config
        base = config.base_url.rstrip("/")
        self._api_url = base if base.endswith("/v1") else base + "/v1"
        self._tokenize_url = self._api_url[:-3] + "/tokenize"
        self._ready = False
        self._error = None
        self._generation_count = 0
        self._last_latency_ms = None
        self._lock = threading.Lock()

    def status(self) -> dict:
        return {
            "backend": "vllm",
            "model": self.config.model_name,
            "device": "remote",
            "ready": self._ready,
            "context_window": self.config.context_window,
            "max_new_tokens": self.config.max_new_tokens,
            "error": self._error,
            "generation_count": self._generation_count,
            "last_latency_ms": self._last_latency_ms,
        }

    def _request(self, url: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        request = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=timeout if timeout is not None else self.config.timeout_s) as response:
                raw = response.read(2_097_153)
            if len(raw) > 2_097_152:
                raise LLMError("Phản hồi vLLM vượt giới hạn kích thước")
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get("error"):
                raise LLMError("Phản hồi vLLM không hợp lệ")
            return result
        except HTTPError as exc:
            raise LLMUnavailableError(f"vLLM trả về lỗi HTTP {exc.code}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMTimeoutError("Hết thời gian chờ vLLM") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise LLMTimeoutError("Hết thời gian chờ vLLM") from exc
            raise LLMUnavailableError("Không kết nối được máy chủ vLLM") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise LLMError("Phản hồi vLLM không phải JSON hợp lệ") from exc

    def probe(self) -> dict:
        try:
            result = self._request(self._api_url + "/models")
            models = result.get("data")
            if not isinstance(models, list) or not any(isinstance(model, dict) and model.get("id") == self.config.model_name for model in models):
                raise LLMUnavailableError("Máy chủ vLLM chưa cung cấp mô hình được cấu hình")
            self._ready = True
            self._error = None
            return self.status()
        except LLMError as exc:
            self._ready = False
            self._error = str(exc)
            raise

    def generate(self, messages: list[dict[str, str]]) -> str:
        prepared = _validate_messages(messages)
        started = time.monotonic()
        if not self._lock.acquire(timeout=self.config.timeout_s):
            raise LLMTimeoutError("Hết thời gian chờ lượt sinh câu trả lời vLLM")
        try:
            remaining = self.config.timeout_s - (time.monotonic() - started)
            if remaining <= 0:
                raise LLMTimeoutError("Hết thời gian chờ lượt sinh câu trả lời vLLM")
            tokenized = self._request(self._tokenize_url, {
                "model": self.config.model_name,
                "messages": prepared,
                "add_generation_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False},
            }, remaining)
            count = tokenized.get("count")
            limit = tokenized.get("max_model_len")
            if type(count) is not int or count < 0 or type(limit) is not int or limit <= 0:
                raise LLMError("Phản hồi token hóa vLLM không hợp lệ")
            context_window = min(self.config.context_window, limit)
            if count + self.config.max_new_tokens > context_window:
                raise LLMContextError(f"Ngữ cảnh có {count} token, vượt ngân sách {context_window - self.config.max_new_tokens}")
            remaining = self.config.timeout_s - (time.monotonic() - started)
            if remaining <= 0:
                raise LLMTimeoutError("Hết thời gian token hóa vLLM")
            result = self._request(self._api_url + "/chat/completions", {
                "model": self.config.model_name,
                "messages": prepared,
                "temperature": 0,
                "max_tokens": self.config.max_new_tokens,
                "stream": False,
                "n": 1,
                "seed": 0,
                "chat_template_kwargs": {"enable_thinking": False},
            }, remaining)
            choices = result.get("choices")
            if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
                raise LLMError("Phản hồi vLLM thiếu câu trả lời")
            choice = choices[0]
            if choice.get("finish_reason") != "stop":
                raise LLMError("Câu trả lời vLLM chưa hoàn tất hoặc bị cắt")
            message = choice.get("message")
            text = message.get("content") if isinstance(message, dict) else None
            if not isinstance(text, str) or not text.strip():
                raise LLMError("Câu trả lời vLLM rỗng hoặc không hợp lệ")
            if time.monotonic() - started > self.config.timeout_s:
                raise LLMTimeoutError("vLLM vượt thời gian sinh câu trả lời")
            self._generation_count += 1
            self._last_latency_ms = round((time.monotonic() - started) * 1000, 2)
            self._ready = True
            self._error = None
            return text.strip()
        except LLMError as exc:
            self._ready = False
            self._error = str(exc)
            raise
        finally:
            self._lock.release()


def create_generator(config: LLMConfig) -> Generator:
    if config.backend == "transformers":
        return TransformerGenerator(config)
    return VLLMGenerator(config)
