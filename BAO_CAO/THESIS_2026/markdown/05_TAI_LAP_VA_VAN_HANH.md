# Tái lập và vận hành

## App đang dùng

```bash
cd "/Users/amyas/HK1 26-27/DATN/SOURCE"
bash scripts/run_assistant.sh
```

Mở http://127.0.0.1:8001. Dữ liệu mặc định vẫn là D0. Không cần train hoặc tạo embedding lại mỗi lần khởi động. Lần tải trọng số đầu có thể chậm hơn. Hướng dẫn này giả định môi trường và trọng số hiện có, không thay log cài mới trên máy khác.

## Bản nghiên cứu

```bash
../.venv/bin/python scripts/collect_research_expansion.py --output ../artifacts/research_expansion_2026-10-30 --tourism-pages 4
../.venv/bin/python scripts/finalize_research_corpus.py --release ../artifacts/research_expansion_2026-10-30
../.venv/bin/python scripts/retrain_domain_refresh.py --release ../artifacts/research_expansion_2026-10-30
../.venv/bin/python scripts/run_research_experiments.py --release ../artifacts/research_expansion_2026-10-30 --device mps
```

Các lệnh chạy từ SOURCE; raw cache có thể được tái sử dụng. Để build FAISS lại, dùng refresh_vectors.py với dataset candidate, thư mục seed hợp lệ và output **mới chưa có index**. Release hiện đã có chỉ mục, không chạy lệnh ghi đè tùy tiện. Vector chỉ tái sử dụng nếu nội dung passage và cấu hình encoder phù hợp; không gọi đó là fine-tune.

## Kiểm thử và version

```bash
../.venv/bin/python -m pytest -q
../.venv/bin/python scripts/verify_system.py
../.venv/bin/python scripts/verify_ui.py
```

Hai lệnh cuối cần server đúng phiên bản. Chỉ định output riêng để không mất báo cáo lịch sử. Trước khi công bố release mới: kiểm tra toàn bộ ID/nguồn, SQLite integrity, số vector, graph, alias, HTTP/UI và rollback. Không thay index khi server đang giữ metadata/graph của bản khác. Code hiện có một process và lock nội bộ, không mặc nhiên dùng nhiều worker trên cùng máy 16 GiB.

## Build báo cáo

Chạy build_pack.py để cập nhật bảng số đo và Markdown từ artifacts. Chạy build_document.py bằng Python bundled để xuất Word, sau đó render_docx.py của runtime để chuyển PDF và PNG kiểm tra. File qa_manifest.json ghi số trang, kiểm tra liên kết và audit số liệu của lần xuất. Sửa nội dung chương trong markdown/ rồi build lại; không sửa bảng kết quả bằng tay nếu JSON gốc chưa thay.
