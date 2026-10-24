# VN Hybrid Assistant — KG + FAISS RAG + LLM

Ứng dụng Tri Việt phục vụ hỏi đáp về địa giới hành chính cũ–mới và du lịch Việt Nam. Giao diện đàm thoại kết nối trực tiếp backend: phân tích câu hỏi → KG/FAISS → Qwen → cross-check → trả lời kèm nguồn.

Tài liệu lý thuyết, giải thích từng module, cấu hình, cách kiểm thử và giới hạn nằm trong [docs/GIAI_THICH_BACKEND_3_LOP.md](docs/GIAI_THICH_BACKEND_3_LOP.md). Phần giải thích được giữ ngoài code.

Báo cáo Word/PDF được gom tại [DATN/BAO_CAO](../BAO_CAO/). Báo cáo triển khai giai đoạn đầu nằm trong [docs/IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md). Sơ đồ toàn bộ thư mục ở [DATN/README.md](../README.md).

## Bộ tài liệu dự án

Đối chiếu mã nguồn và dữ liệu hiện có ngày 25/10/2026. Tài liệu phân biệt phần đã triển khai, giới hạn hiện tại và đề xuất mở rộng.

| File | Nội dung |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Frontend, Backend, AI, lưu trữ và luồng hỏi đáp |
| [DATABASE.md](docs/DATABASE.md) | Schema JSONL/SQLite, quan hệ KG, FAISS và Neo4j tùy chọn |
| [API.md](docs/API.md) | Endpoint, request, response, trạng thái nghiệp vụ và HTTP errors |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Server/cloud VM, cấu hình, systemd, reverse proxy và rollback |
| [DATA_SOURCES.md](docs/DATA_SOURCES.md) | URL nguồn, xuất xứ, giới hạn tin cậy và thời điểm thu thập |
| [DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | Thu thập, làm sạch, snapshot, chunking, embedding và build artifacts |
| [RAG_DESIGN.md](docs/RAG_DESIGN.md) | Router, retrieval, lựa chọn minh chứng, prompt và cross-check |
| [ADMINISTRATIVE_DATA.md](docs/ADMINISTRATIVE_DATA.md) | Mã đơn vị, địa giới cũ–mới, chuyển một phần và truy vấn thời gian |
| [TOURISM_DATA.md](docs/TOURISM_DATA.md) | Hồ sơ điểm đến, địa chỉ, alias, văn hóa và lịch sử |
| [EVALUATION.md](docs/EVALUATION.md) | Bộ câu hỏi, chỉ số, kết quả đã xác nhận và phạm vi báo cáo cũ |

## Chạy trên Mac hiện tại

Cấu trúc thư mục sử dụng:

```text
DATN/
├── SOURCE/
├── .venv/
├── data/
├── artifacts/
└── models/Qwen3-0.6B/
```

Mở terminal tại `DATN/SOURCE`:

```bash
../.venv/bin/python -m pip install -e '.[dev]'
../.venv/bin/python scripts/download_runtime_models.py --models qwen
bash scripts/run_assistant.sh
```

Mô hình mặc định là Qwen3-0.6B trên Transformers/PyTorch, tự chọn MPS khi có. Settings tự tìm dữ liệu và artifacts trong thư mục `DATN`. Khi cần đổi cấu hình, sao chép `.env.example` thành `.env` và chỉnh giá trị.

Giao diện: [http://127.0.0.1:8001/](http://127.0.0.1:8001/). Swagger: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs). Giao diện tự chuẩn bị mô hình khi cần; lần nạp đầu chậm hơn các lượt sau.

```bash
curl -X POST http://127.0.0.1:8001/v1/system/warmup
curl -X POST http://127.0.0.1:8001/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Đơn vị có mã hành chính 00070 là gì?","top_k":3,"history":[]}'
```

## API

| Endpoint | Chức năng |
|---|---|
| `GET /health` | Tệp dữ liệu hiện có và trạng thái dịch vụ đã nạp |
| `GET /` | Giao diện đàm thoại Tri Việt |
| `POST /v1/classify` | Phân loại route/domain, tạo kế hoạch và ràng buộc |
| `POST /v1/query` | Bước 1–2: truy xuất có bộ lọc, minh chứng, thời gian |
| `POST /v1/rag/search` | Tìm top-k văn bản theo miền |
| `GET /v1/llm/status` | Trạng thái thực tế của mô hình |
| `POST /v1/llm/warmup` | Nạp mô hình local hoặc kiểm tra dịch vụ vLLM |
| `POST /v1/system/warmup` | Chuẩn bị KG, E5, retriever và LLM |
| `POST /v1/answer` | Câu trả lời, nguồn minh chứng và kết quả cross-check |
| `POST /v1/chat` | Hỏi đáp có lịch sử và giải quyết một số câu hỏi nối tiếp |

`/v1/answer` cho LLM chọn tối đa ba mệnh đề đã chuẩn bị từ minh chứng. Backend xác nhận lại mệnh đề, loại nội dung không đạt và định dạng câu trả lời. Đây là chế độ phát sinh có kiểm soát; chưa xác minh được diễn giải ngữ nghĩa tự do hoặc tính đúng đắn tuyệt đối của nguồn.

## Dữ liệu và huấn luyện cập nhật 25/10/2026

Tập đang dùng có 31.949 tài liệu: 28.138 bản ghi danh mục/chuyển đổi hành chính, 37 trang thuộc tính văn bản chính thức, 3.321 dòng đối chiếu Cục Thống kê và 453 hồ sơ điểm du lịch; đợt bổ sung mới thêm 251 điểm đến và 3.321 dòng tham chiếu hành chính chính thức. Chỉ mục hiện có 33.169 vector. Điểm du lịch vẫn bao gồm địa điểm lịch sử, bảo tàng và công trình phục vụ tham quan. Nhánh hỏi đáp di sản phi vật thể đã được bỏ.

- `DATN/data/structured_records.jsonl`: đầu vào KG có cấu trúc, ba snapshot riêng.
- `DATN/data/rag_dataset_final.jsonl`: văn bản dùng để mã hóa E5 và tìm kiếm FAISS.
- `DATN/data/router_training.csv`: 3.402 câu huấn luyện, hai miền và ba hướng truy xuất.
- `DATN/data/raw/2026-10-24/`: dữ liệu thu thập, HTML gốc, URL, checksum và báo cáo crawl.
- `DATN/data/raw/2026-10-24-refresh/`: lượt crawl bổ sung, 440 hồ sơ du lịch và đủ 3.321 dòng đối chiếu hành chính.
- `DATN/artifacts/domain_refresh_2026-10-24/release/`: corpus/model release và báo cáo huấn luyện, truy xuất, 57 ca HTTP thật; [báo cáo cập nhật](docs/DATA_REFRESH_2026-10-25.md).
- `DATN/data/archive/`: archive lịch sử không được ứng dụng đọc/huấn luyện; có [cảnh báo về lượt lọc archive](../data/archive/README.md), cần đối chiếu nguồn trước khi dùng lại.

Danh mục gốc từ `vietnam-provinces==2026.9.0`. Đợt bổ sung đã đối chiếu đủ 34 tỉnh/3.321 đơn vị cấp xã hiện tại với bảng Cục Thống kê, đối chiếu riêng 34 tỉnh năm 2025 và cập nhật 29 tên/cách ghi khác nhau ở snapshot hiện tại. Ba snapshot vẫn được giữ riêng; chưa có xác minh toàn văn mọi văn bản hoặc timeline liên tục. Bảng chuyển đổi giữ riêng trường hợp chuyển một phần địa bàn. Địa chỉ du lịch được giữ theo nguồn và có thể còn địa danh cũ.

Lần cập nhật này huấn luyện lại TF-IDF/Logistic Regression của router, xây lại KG và FAISS; đoạn văn mới/đã sửa được mã hóa E5, đoạn không đổi tái sử dụng vector cùng cấu hình. Trọng số E5 và Qwen vẫn pretrained, không fine-tune hai mô hình này. Kết quả: 264 unit test, 17/17 KG, 26/26 router và 57/57 ca HTTP thật; đây là tập phát triển của dự án.

## Thu thập và xây lại

Chạy từ `DATN/SOURCE`:

```bash
../.venv/bin/python -m pip install -e '.[dev,data]'
../.venv/bin/python scripts/collect_domain_data.py
../.venv/bin/python scripts/collect_official_administration.py
../.venv/bin/python scripts/train_domain_models.py
/usr/bin/caffeinate -i ../.venv/bin/python scripts/build_vectors.py --dataset ../data/rag_dataset_final.jsonl --output ../artifacts/faiss --device mps --batch-size 32
```

Thu thập dùng cache HTTP và giãn lượt truy cập. Hai lệnh thu thập chỉ ghi dữ liệu thô; bước `prepare_domain_corpus.py` đã được chạy một lần để lọc và chuyển tập đang dùng. Script này không cho ghi đè nhật ký chuyển đổi đã hoàn tất. Để cập nhật lần tiếp theo cần kiểm tra dữ liệu thô và chuẩn bị phiên bản tập dữ liệu mới trước khi xây lại.

Chỉ chạy một lượt build FAISS với cùng cấu hình. Tiến độ ở `DATN/artifacts/faiss/build_progress.json`; checkpoint ở `vn.index.build/` cho phép tiếp tục khi dừng giữa chừng. Đợi build hoàn tất rồi khởi động lại API để nạp chỉ mục mới. Kết quả đánh giá router là tập phát triển tự xây, không đại diện độ chính xác thực tế trên toàn bộ người dùng.

## Kiểm thử

```bash
../.venv/bin/python -m pytest -q
../.venv/bin/python -m vn_assistant.cli eval-kg
../.venv/bin/python -m vn_assistant.cli eval-router
../.venv/bin/python scripts/verify_system.py
../.venv/bin/python scripts/verify_ui.py
```

Hai script cuối dùng server đang chạy ở cổng 8001 với KG, E5 và Qwen thật. Kiểm tra UI có mô phỏng lỗi mạng và phản hồi sai định dạng. Báo cáo ghi rõ thời gian, phạm vi, chế độ truy xuất và các tình huống đạt/trượt tại `DATN/artifacts/system_tests/`.

Bộ khóa đồng bộ tải/sử dụng E5 và Qwen giảm lỗi tranh chấp MPS. Chi tiết dấu vết SIGSEGV và cách sửa nằm trong mục 10.6 của file giải thích. Khi thử khởi tạo đồng thời, dùng `scripts/verify_concurrent_startup.py` với một server mới khởi động.

Adapter LLaMA-2 và vLLM có chung hợp đồng sinh câu; việc chạy thật trên môi trường phù hợp vẫn cần kiểm chứng riêng. Chế độ hiện tại dùng Qwen nhỏ trên Mac theo lựa chọn kiểm thử.
