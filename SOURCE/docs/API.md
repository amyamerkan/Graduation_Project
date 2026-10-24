# Đặc tả API

> Đối chiếu `api.py`, `question_processing.py` và `generation.py` ngày **25/10/2026**, phiên bản API `1.2.0`. Ví dụ có ghi “rút gọn” không đại diện đầy đủ JSON trả về.
> Đợt cập nhật dữ liệu và huấn luyện lại: [DATA_REFRESH_2026-10-25.md](DATA_REFRESH_2026-10-25.md).

## 1. Quy ước

- Base URL cục bộ: `http://127.0.0.1:8001`.
- Request/response nghiệp vụ dùng JSON UTF-8; POST có `Content-Type: application/json`.
- Swagger: `/docs`; ReDoc: `/redoc`; schema: `/openapi.json`.
- Hiện chưa có xác thực, phân quyền, rate limit hoặc streaming. `LLM_API_KEY` là khóa gọi dịch vụ LLM phía sau, không bảo vệ API Tri Việt.
- Các endpoint trả `dict`, chưa khai báo response model Pydantic chi tiết; code và tài liệu này bổ sung cấu trúc mà OpenAPI chưa thể hiện đầy đủ.

## 2. Request dùng chung

### `QuestionRequest`

```json
{"question": "Đơn vị có mã 00070 là gì?", "top_k": 3}
```

| Trường | Kiểu | Bắt buộc | Ràng buộc |
|---|---|---|---|
| `question` | string | Có | 2–2.000 ký tự; chuẩn hóa Unicode NFC, khoảng trắng, bỏ NUL; ít nhất 2 ký tự sau chuẩn hóa |
| `top_k` | integer | Không | Mặc định 5; từ 1 đến 20 ở HTTP API |

`top_k` giới hạn số kết quả RAG, không phải số dòng SPARQL hay số mệnh đề trả lời. Biến môi trường `TOP_K` được CLI sử dụng; mặc định request HTTP vẫn là 5 theo Pydantic.

### `RagRequest`

Kế thừa `QuestionRequest`, thêm `domain: string | null`. Schema hiện nhận `law`, `administration`, `heritage`, `tourism`; corpus hoạt động chỉ có `administration` và `tourism`. `domain=null` tìm xuyên miền, miền không có dữ liệu có thể trả `results=[]`.

### `ChatRequest`

```json
{
  "question": "Đơn vị đó thuộc tỉnh nào?",
  "top_k": 3,
  "history": [
    {"role": "user", "content": "Đơn vị mã 00070 là gì?"},
    {"role": "assistant", "content": "Thông tin đã trả lời ở lượt trước."}
  ]
}
```

`history` mặc định `[]`, tối đa 12 phần tử; `role` chỉ nhận `user` hoặc `assistant`, `content` dài 1–12.000 ký tự. Bộ giải quyết tham chiếu dùng câu hỏi `user` gần nhất; không coi câu trả lời cũ của assistant là chứng cứ thay cho KG/RAG.

## 3. Danh sách endpoint

| Method | Endpoint | Request | Response chính |
|---|---|---|---|
| GET | `/` | Không | HTML giao diện |
| GET | `/assets/{path}` | Không | Tài nguyên tĩnh |
| GET | `/health` | Không | Trạng thái dịch vụ và tệp artifacts |
| POST | `/v1/classify` | `QuestionRequest` | `classification`, `plan` |
| POST | `/v1/query` | `QuestionRequest` | Kế hoạch, kết quả KG/RAG, cảnh báo, thời gian |
| POST | `/v1/rag/search` | `RagRequest` | `results` chứa các chunk có điểm |
| GET | `/v1/llm/status` | Không | Trạng thái LLM, không tự warmup |
| POST | `/v1/llm/warmup` | Không cần body | Nạp LLM hoặc probe vLLM |
| POST | `/v1/system/warmup` | Không cần body | Chuẩn bị KG, retriever/E5 và LLM |
| POST | `/v1/answer` | `QuestionRequest` | Trả lời có minh chứng, không có giải quyết lịch sử |
| POST | `/v1/chat` | `ChatRequest` | Trả lời kèm xử lý tham chiếu hội thoại |

Không có endpoint cập nhật dữ liệu, nạp file, xóa hội thoại, SPARQL tự do hoặc quản lý tài khoản.

## 4. Phân loại và kế hoạch

`POST /v1/classify` trả cấu trúc:

```json
{
  "classification": {
    "question": "Đơn vị có mã 00070 là gì?",
    "route": "kg",
    "domain": "administration",
    "route_confidence": 0.7,
    "domain_confidence": 0.7,
    "method": "tfidf_logistic_regression"
  },
  "plan": {
    "route": "kg",
    "kg": {"query": "03_unit_by_code", "params": {"code": "00070"}},
    "rag": null,
    "intent": "logical",
    "constraints": {"temporal": [], "spatial": [], "unsupported": []},
    "warnings": [],
    "scope": "supported"
  }
}
```

Ví dụ theo nhánh mã đơn vị trong code; confidence có thể đổi theo mô hình/quy tắc. Khi quy tắc ghi đè dự đoán, confidence được gán 0,70, không phải xác suất đúng thực tế được hiệu chuẩn. `route` là `kg/rag/hybrid`; `intent` là `logical/textual/hybrid`; `scope` là `supported/out_of_scope`.

`/v1/classify` chỉ lập kế hoạch. `scope=supported` chưa chứng minh dữ liệu có câu trả lời.

## 5. Truy xuất

### `POST /v1/query`

Trả các trường sau:

| Trường | Nội dung |
|---|---|
| `question`, `classification`, `plan` | Câu hỏi chuẩn hóa và kế hoạch |
| `effective_route` | Route thực thi; có thể là `rag_fallback` |
| `kg_results` | Mảng binding SPARQL; trường phụ thuộc mẫu query, giá trị RDF thường chuyển thành string |
| `rag_results` | Mảng chunk theo schema bên dưới |
| `evidence_count` | Tổng số dòng KG và kết quả RAG, trước khi lọc minh chứng sinh câu |
| `status` | `ready`, `partial`, `no_evidence`, `unsupported_constraints`, `out_of_scope` |
| `physical_filters` | `domain`, `doc_ids`, `entity_terms` thực sự áp cho nhánh RAG |
| `warnings` | Mảng chuỗi cảnh báo |
| `timings_ms` | `classification`, `kg`, `rag`, `total` |

Kết quả KG có thể được bổ sung `source_record_ids`, `source_names`, `source_urls`. Lỗi KG/RAG bên trong processor thường được đưa vào `warnings`; endpoint có thể trả HTTP 200 cùng kết quả một phần hoặc không có minh chứng.

### `POST /v1/rag/search`

```bash
curl http://127.0.0.1:8001/v1/rag/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"Giới thiệu Hồ Hoàn Kiếm.","top_k":3,"domain":"tourism"}'
```

Response minh họa cấu trúc; ID, nội dung và điểm bên dưới là giá trị ví dụ:

```json
{
  "results": [{
    "vector_id": 100,
    "chunk_id": "tourism_place_example:0",
    "doc_id": "tourism_place_example",
    "text": "Nội dung đoạn văn tìm được...",
    "title": "Hồ Hoàn Kiếm",
    "domain": "tourism",
    "source": "Tên nguồn",
    "source_url": "https://example.org/place",
    "score": 0.82
  }]
}
```

Chế độ dự phòng thêm `retrieval_mode="lexical_candidates_faiss"`, `candidate_count`. Điểm là độ tương tự, không phải xác suất đúng. Endpoint này không lọc bằng `ANSWER_MIN_RAG_SCORE`, không gọi LLM hoặc cross-check. Bộ lọc `doc_ids/entity_terms` có trong API Python nội bộ, chưa được nhận trực tiếp từ `RagRequest`.

## 6. Trả lời và hội thoại

```bash
curl http://127.0.0.1:8001/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Đơn vị có mã 00070 là gì?","top_k":3,"history":[]}'
```

Các trường của `/v1/answer` và nhánh trả lời thông thường của `/v1/chat`:

| Trường | Kiểu / ý nghĩa |
|---|---|
| `question` | Câu hỏi đã xử lý |
| `classification`, `plan` | Phân loại và kế hoạch |
| `effective_route`, `retrieval_status` | Cách truy xuất và trạng thái trước sinh |
| `status` | `answered`, `partial`, `abstained` |
| `answer` | Chuỗi tiếng Việt, gồm ký hiệu nguồn và phần nguồn |
| `claims` | Mệnh đề đã qua kiểm tra: `claim_id`, `mode`, `text`, `evidence_ids`; mệnh đề fact có `fields`, `fact_checks` |
| `citations` | Nguồn tương ứng với mệnh đề được giữ |
| `cross_check` | Kết quả kiểm tra, số lượng supported/rejected và phạm vi xác minh |
| `warnings` | Cảnh báo dữ liệu, mệnh đề bị loại, nội dung thiếu hoặc từ chối |
| `llm` | Trạng thái LLM |
| `timings_ms` | `question_processing`, `generation`, `kg_refresh`, `cross_check`, `total` |

Mỗi citation có `number`, `evidence_id`, `kind` (`kg/rag`), `title`, `source`, `source_url` (có thể null), `source_record_ids`, `source_verified`. Mã minh chứng và số thứ tự chỉ có ý nghĩa trong một response. `source_verified=false` trong pipeline hiện tại, kể cả khi URL thuộc cơ quan chính thức.

Response từ chối rút gọn:

```json
{
  "question": "Đơn vị có mã 99999 là gì?",
  "status": "abstained",
  "answer": "Mình chưa tìm được bản ghi KG khớp mã đơn vị và các điều kiện bạn yêu cầu. Bạn kiểm tra lại mã hoặc thay đổi ngày, địa phương cần tra cứu nhé.",
  "claims": [],
  "citations": [],
  "warnings": ["missing_verified_code"],
  "cross_check": {
    "status": "insufficient_evidence",
    "supported_count": 0,
    "reason": "missing_verified_code"
  }
}
```

`/v1/chat` thường thêm `original_question`, `context_resolution` (`question`, `resolved`, `needs_context`) và `retrieval_mode`. Nếu không có lịch sử để giải quyết đại từ, endpoint trả `status="needs_clarification"`, `claims=[]`, `citations=[]`, `warnings=["missing_conversation_context"]`. Nhánh này có response tối giản, không có đủ các trường phân loại/LLM như nhánh trả lời thường.

`partial` có thể do tên khớp nhiều thực thể (`ambiguous_entity`), thiếu trường được hỏi, mệnh đề bị loại hoặc danh sách bị rút gọn (`evidence_truncated`). Client cần hiển thị cảnh báo, không chỉ đọc `answer`.

## 7. Health và warmup

`GET /health` trả `status`, `router_ready`, `kg_ready`, `faiss_ready`, `artifacts_present`, `llm`, `retrieval_mode`, `capabilities`. Tên mode là `full_faiss`, `lexical_candidates_faiss` hoặc `unavailable`.

`status="ok"` phản ánh endpoint hoạt động, chưa phải readiness toàn hệ thống. Cờ runtime là dấu vết dịch vụ đã được chuẩn bị; `faiss_ready=true` cũng có thể xuất hiện ở chế độ dự phòng. Muốn xác nhận chỉ mục đầy đủ phải đọc thêm `retrieval_mode` và `artifacts_present.faiss`.

`GET /v1/llm/status` trả `backend`, `model`, `device`, `ready`, `context_window`, `max_new_tokens`, `error`, `generation_count`, `last_latency_ms`. Status không gọi tải trọng số. `POST /v1/llm/warmup` trả cùng cấu trúc sau nạp/probe.

`POST /v1/system/warmup` trả `status="ready"`, `llm`, `kg_ready=true`, `rag_ready=true`, `elapsed_ms`. Lần chạy đầu có thể tốn thời gian; kiểm tra mode bằng `/health` sau warmup. Warmup không chứng minh tất cả câu hỏi sẽ được trả lời đúng.

## 8. HTTP errors và trạng thái nghiệp vụ

| HTTP | Trường hợp trong code |
|---|---|
| 200 | Thành công xử lý; vẫn có thể `abstained`, `needs_clarification`, `no_evidence` hoặc `partial` |
| 400 | `ValueError` được endpoint bắt; `LLMContextError` ở answer/chat/warmup LLM |
| 422 | Sai schema Pydantic: thiếu question, quá ngắn/dài, top_k ngoài giới hạn, role/history/domain sai |
| 503 | LLM lỗi/timeout/không khả dụng; cấu hình LLM/answer không hợp lệ; thiếu retriever ở RAG search; thiếu KG/retriever hoặc lỗi chuẩn bị ở system warmup |
| 404 / 405 | Route/tài nguyên không tồn tại hoặc sai HTTP method, theo framework |
| 500 | Ngoại lệ chưa được xử lý, ví dụ lỗi nạp tệp ở dependency; chưa có exception handler chung cho mọi lỗi |

Lỗi do code chủ động trả:

```json
{"detail": "FAISS index chưa sẵn sàng"}
```

Lỗi validation có dạng `{"detail":[{"loc":["body","top_k"],"msg":"...","type":"..."}]}`; các khóa khác tùy phiên bản Pydantic. Chưa có envelope `error.code` ổn định, chưa ánh xạ timeout thành 504 hoặc rate limit thành 429 trong ứng dụng.

Một số lý do nghiệp vụ trong `warnings/cross_check.reason`: `out_of_scope`, `unsupported_constraints`, `no_eligible_evidence`, `missing_verified_code`, `missing_verified_count`, `invalid_output_schema`, `unknown_claim_id`, `model_selected_no_claims`, `cross_check_rejected_all_claims`. Đây không phải HTTP error codes và danh sách có thể được mở rộng theo code.

Mã đối chiếu: [api.py](../src/vn_assistant/api.py), [generation.py](../src/vn_assistant/generation.py), [dialogue.py](../src/vn_assistant/dialogue.py), [test_api.py](../tests/test_api.py).
