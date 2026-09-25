# VN Hybrid Assistant - KG + RAG + Question Processing

Project cho đề tài **“Ứng dụng kiến trúc 3 lớp trong xây dựng trợ lý ảo thông minh cho lĩnh vực di sản du lịch và hành chính Việt Nam”**.

Hệ thống triển khai đúng hai bước đầu của execution pipeline trong tài liệu kiến trúc:

1. **Question Processing:** TF-IDF (word + character n-gram) và Logistic Regression phân loại `kg`, `rag`, `hybrid`, đồng thời nhận diện domain.
2. **Physical Retrieval:** SPARQL lấy sự thật cứng từ KG; nếu KG thiếu, FAISS tìm top-k đoạn văn bằng cosine similarity.

Phần sinh câu trả lời bằng LLM được đặt sau API này. API cố ý trả evidence có nguồn để tầng LLM không tự thêm dữ kiện.

## Deliverables

| Yêu cầu | Thành phần trong project |
|---|---|
| Schema Ontology OWL/RDF | `ontology/vn_heritage_admin.ttl` và file `.owl` sinh tự động |
| KG ban đầu | `artifacts/kg/vn_knowledge_graph.ttl`, `nodes.csv`, `relationships.csv` |
| CSDL đồ thị Neo4j | `docker-compose.yml` + lệnh `load-neo4j` |
| SPARQL chuẩn | 8 query trong `queries/` |
| Test SPARQL | `evaluation/kg_gold.jsonl` + `artifacts/kg/evaluation_report.json` |
| Transformer Embedding | multilingual E5, prefix `query:`/`passage:`, vector L2-normalized |
| FAISS cosine | `IndexFlatIP` trên vector chuẩn hóa + metadata SQLite |
| API RAG | `/v1/rag/search` và `/v1/query` |
| Phân loại câu hỏi | `router.py`, tập train/test CSV và report |

## 1. Cài đặt trên VS Code (macOS/Windows/Linux)

Mở Terminal tại thư mục project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -e .
```

Windows PowerShell dùng:

```powershell
.venv\Scripts\Activate.ps1
```

Đặt một trong các file sau vào thư mục `data/`:

- `vn_complete_dataset_v2.json` (khuyến nghị, 193.708 records theo report), hoặc
- `rag_dataset_final.jsonl` cho nhánh FAISS và dataset JSON gốc cho nhánh KG, hoặc
- `vn_complete_dataset.json` để chạy thử project hiện tại.

Không đưa file data lớn vào Git.

## 2. Phase 1 - dựng Ontology và Knowledge Graph

```bash
vn-assistant build-kg --dataset data/vn_complete_dataset_v2.json
```

Kết quả:

```text
artifacts/kg/
├── vn_knowledge_graph.ttl
├── vn_knowledge_graph.owl
├── nodes.csv
├── relationships.csv
└── build_report.json
```

Builder đọc streaming bằng `ijson`, không nạp toàn bộ file vào RAM. Các quan hệ địa giới được tạo trực tiếp từ field có cấu trúc:

- `Ward - LOCATED_IN -> Province`
- `HistoricalAdministrativeUnit - LOCATED_IN -> District`
- `HistoricalAdministrativeUnit - MERGED_INTO -> Ward`
- `HistoricalAdministrativeUnit - REPLACED_BY -> Ward`

Dữ liệu cũ có `validTo=2025-06-30`; dữ liệu sau sáp nhập có `validFrom=2025-07-01`.

### Nạp Neo4j

```bash
docker compose up -d
vn-assistant load-neo4j --password change-me-now
```

Neo4j Browser: `http://localhost:7474`.

Ví dụ Cypher:

```cypher
MATCH (old:HistoricalAdministrativeUnit)-[:MERGED_INTO]->(new:Ward)
RETURN old.name, new.name, new.code
LIMIT 20;
```

## 3. Phase 2 - SPARQL và đánh giá KG

```bash
vn-assistant eval-kg
```

Report gồm accuracy theo test case và Precision/Recall/F1 của các binding bắt buộc. Query sử dụng tham số đã escape; tên file query không được nhận tùy ý từ HTTP.

Ví dụ chạy bằng Python:

```python
from vn_assistant.sparql_service import SparqlService

service = SparqlService("artifacts/kg/vn_knowledge_graph.ttl", "queries")
rows = service.execute("04_merger_history", {"old_name": "Thị trấn Cờ Đỏ"})
print(rows)
```

## 4. RAG - Transformer, FAISS và cosine top-k

Train ở đây nghĩa là **cấu hình/encode bằng mô hình embedding**, không train LLM từ đầu.

```bash
vn-assistant build-faiss \
  --dataset data/rag_dataset_final.jsonl \
  --model intfloat/multilingual-e5-base \
  --device cpu \
  --batch-size 16
```

Nếu chạy từ file v2:

```bash
vn-assistant build-faiss --dataset data/vn_complete_dataset_v2.json
```

Tối ưu lexical gap gồm:

- multilingual E5 phù hợp truy vấn tiếng Việt;
- prefix riêng cho query và passage;
- word expansion cho thuật ngữ miền (`TTHC`, `CCCD`, `UBND`, tên di sản);
- Unicode NFC;
- vector L2-normalized và inner product, tương đương cosine similarity.

Chế độ `--backend hashing` chỉ dành cho smoke test offline, không dùng làm kết quả đồ án.

## 5. Train và test Question Router

```bash
vn-assistant train-router
vn-assistant eval-router
```

Router xuất:

- `route`: `kg`, `rag`, hoặc `hybrid`;
- `domain`: `law`, `administration`, `heritage`, `tourism`;
- confidence của từng nhãn;
- physical plan cho SPARQL hoặc FAISS.

Tập CSV đi kèm là seed set để pipeline chạy được. Khi báo cáo kết quả chính thức, nên thay bằng 500-1.000 câu gán nhãn thủ công và tách train/test theo câu hỏi, không đánh giá trên chính tập train.

## 6. Chạy API

```bash
vn-assistant serve --host 127.0.0.1 --port 8000
```

Swagger UI: `http://127.0.0.1:8000/docs`.

Ví dụ:

```bash
curl -X POST http://127.0.0.1:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Thị trấn Cờ Đỏ sau sáp nhập thành đơn vị nào?","top_k":5}'
```

Endpoints:

| Endpoint | Chức năng |
|---|---|
| `GET /health` | Kiểm tra router, KG và FAISS |
| `POST /v1/classify` | Bước 1: phân loại và lập physical plan |
| `POST /v1/rag/search` | Cosine top-k, có filter domain |
| `POST /v1/query` | Bước 1 + Bước 2, KG miss thì fallback sang RAG |

## 7. Chạy toàn pipeline

```bash
PYTHONPATH=src python3 scripts/run_pipeline.py \
  --dataset data/vn_complete_dataset_v2.json \
  --skip-faiss
```

Bỏ `--skip-faiss` khi muốn tạo index Transformer đầy đủ. Lần đầu sẽ tải model embedding; với 130.999 records, nên cắm sạc và bảo đảm còn vài GB trống.

## 8. Kiểm thử code

```bash
pytest -q
```

## Lưu ý dữ liệu đính kèm

File `vn_complete_dataset.json` được cung cấp trong phiên này có **81.090 records**, trong khi `vn_dataset_expander_report.json` xác nhận bản v2 trên máy của bạn có **193.708 records** và `prepare_report.json` xác nhận RAG final có **130.999 records**. Vì file v2/final không được đính kèm, KG mẫu trong gói được build từ file 81.090 records; toàn bộ code vẫn tương thích với bản v2 và JSONL final để bạn chạy local.


## Kiểm tra và build có thể chạy tiếp (24/09/2026)

Chạy tại thư mục gốc dự án. Các lệnh dưới đây dùng Python đã có các dependency trong `requirements.txt`.

```bash
python3 -m pytest -q
PYTHONPATH=src python3 -m vn_assistant.cli eval-kg
PYTHONPATH=src python3 -m vn_assistant.cli eval-router
python3 scripts/benchmark_sparql.py
python3 scripts/build_vectors.py
```

`build_vectors.py` mặc định dùng GPU Metal (`mps`), batch 16 và model E5 đã có trong cache. Máy không có Metal dùng `--device cpu`. Script này chạy offline mặc định; nếu chưa có model, dùng CLI `build-faiss` bên trên để tải model trước. Không chạy đồng thời hai lượt build vào cùng thư mục output.

Tiến độ lưu ở `artifacts/faiss/build_progress.json`. Vector và metadata được checkpoint theo batch trong `artifacts/faiss/vn.index.build/`. Nếu bị ngắt, chạy lại **cùng lệnh, cùng dữ liệu và cấu hình** để tiếp tục; không xóa checkpoint. Index chính thức chỉ được ghi sau khi encode xong.

Chạy trong terminal thứ hai để tự kiểm tra ngay sau khi lượt build đang chạy hoàn tất:

```bash
python3 scripts/finalize_index.py
```

Trạng thái kiểm tra nằm trong `artifacts/faiss/validation_status.json`. Nếu build bị ngắt, chạy lại lệnh build và lệnh finalize. Để chạy từng phép đo riêng:

```bash
python3 scripts/evaluate_retrieval.py --device mps
python3 scripts/verify_pipeline.py --index-dir artifacts/evaluation/sample_index
python3 scripts/evaluate_retrieval.py --full-index artifacts/faiss
python3 scripts/verify_pipeline.py --index-dir artifacts/faiss
```

- KG: `expected_rows` là danh sách đáp án đầy đủ và dùng tính TP/FP/FN. `must_contain` chỉ kiểm tra độ bao phủ; không được dùng để suy ra precision. Các ca âm tính kiểm tra kết quả rỗng và tham số chứa ký tự đặc biệt.
- SPARQL: `03_unit_by_code` dùng `VALUES` để tra mã trực tiếp. Benchmark xác nhận cùng tập kết quả với truy vấn cũ.
- FAISS: lọc domain ngay trong search bằng ID selector, tránh thiếu top-k do các miền khác chiếm danh sách ứng viên. Retriever đọc cấu hình encoder đã lưu cùng index.
- Embedding: ablation so sánh E5 với/không mở rộng thuật ngữ trên 16 câu diễn đạt lại, cộng 50 tài liệu nhiễu lấy mẫu mỗi miền. Đây là tập phát triển nhỏ, không phải benchmark độc lập, cũng không phải fine-tuning trọng số mô hình. Các tài liệu đúng đã biết chưa bao phủ mọi tài liệu liên quan trong corpus.
- Các kiểm thử tích hợp xác nhận luồng và cosine; không chứng minh nội dung dữ liệu đầu vào đúng hoặc hệ thống không còn ảo giác. Pipeline hiện trả bằng chứng truy xuất, chưa có bước sinh câu trả lời bằng LLM.
