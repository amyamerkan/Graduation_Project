# Nghiệm thu kỹ thuật D1 ngày 18/11/2026

D1 đã được khởi chạy riêng tại cổng 8011 với corpus, graph, router và FAISS của release research_expansion_2026-10-30. Không thay dữ liệu mặc định D0. Cùng bộ ca phát triển được dùng để kiểm tra tương thích; đây chưa phải benchmark QA độc lập.

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Unit toàn bộ | 353/353 | unit_audit.xml trong bộ báo cáo |
| HTTP với E5/Qwen thật | 65/65 | backend_report.json |
| Chromium desktop/mobile | 33/33 kiểm tra; 2 trao đổi backend thật, các lỗi còn lại có mô phỏng | ui/ui_report.json |
| SQLite integrity | ok | validation_manifest.json |
| Metadata D1 | 41,280 vectors; 38,993 tài liệu | validation_manifest.json |
| Runtime health | full_faiss; LLM sẵn sàng | backend_report.json |

## Độ trễ sơ bộ

Mỗi câu bỏ một lượt warmup, sau đó gửi tuần tự năm yêu cầu. Phép đo chính được thực hiện sau khi bộ UI đã kết thúc. Đơn vị mili giây; p95 theo nearest rank với n = 5 gần như giá trị lớn nhất, không phải ước lượng vững cho sản phẩm. Khởi tạo mô hình được ghi riêng. Các pha question_processing, generation, kg_refresh, cross_check và total nằm trong JSON; encode/search chưa được tách. Thiết bị mô hình: mps; máy arm64.

| Ca phát triển | Số lượt | HTTP p50 ms | HTTP p95 ms |
|---|---|---|---|
| bare_00008 | 5 | 10.499 | 12.947 |
| rag_tourism | 5 | 2432.059 | 2499.195 |
| hybrid_tourism | 5 | 3149.763 | 3382.351 |

Không so sánh độ trễ này với ranking_ms trong harness truy xuất. Không có tải đồng thời, máy độc lập hoặc triển khai cloud trong phép đo.

## Tái lập

Từ SOURCE, đặt các biến môi trường tương ứng manifest trước khi chạy server. Các đường dẫn bên dưới được tính từ SOURCE:

```bash
export DATASET_PATH=../artifacts/research_expansion_2026-10-30/data/structured_records.jsonl
export KG_TTL_PATH=../artifacts/research_expansion_2026-10-30/artifacts/kg/vn_knowledge_graph.ttl
export ROUTER_MODEL_PATH=../artifacts/research_expansion_2026-10-30/artifacts/router/router.joblib
export FAISS_INDEX_PATH=../artifacts/research_expansion_2026-10-30/artifacts/faiss/vn.index
export FAISS_METADATA_PATH=../artifacts/research_expansion_2026-10-30/artifacts/faiss/metadata.sqlite3
../.venv/bin/python -m vn_assistant.cli serve --port 8011
```

Terminal khác, cũng từ SOURCE, chạy lần lượt để không gây nhiễu phép đo:

```bash
../.venv/bin/python scripts/verify_system.py --url http://127.0.0.1:8011 --output ../artifacts/new_validation/backend_report.json
../.venv/bin/python scripts/verify_ui.py --url http://127.0.0.1:8011 --output ../artifacts/new_validation/ui
../.venv/bin/python scripts/measure_runtime.py --url http://127.0.0.1:8011 --output ../artifacts/new_validation/latency_report.json
```

Không khởi động mặc định D0 trong shell còn các biến D1. Chọn thư mục output mới để bảo toàn kết quả lịch sử.

## Phần cần người đánh giá

answer_review.csv chứa câu hỏi, câu trả lời và URL thật của lần chạy, các cột điểm để trống. Hai người chấm cần sao chép phiếu riêng, kiểm tra nguồn, ghi bất đồng và tổng hợp theo rubric phụ lục C. Chưa có điểm Faithfulness/factuality nào được suy ra từ 65 ca HTTP. G01, G02, G03, G05 và các phần pháp lý/GIS/triển khai độc lập còn cần thực hiện đúng tiêu chí trong backlog.
