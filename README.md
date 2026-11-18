# Đồ án — Trợ lý hỏi đáp kiến trúc ba lớp

```text
DATN/
├── BAO_CAO/       Báo cáo Word và tài liệu PDF
├── SOURCE/        Mã nguồn, giao diện, truy vấn và kiểm thử
├── data/          Dữ liệu hành chính, RAG và tập huấn luyện router
├── artifacts/     KG, chỉ mục, router, checkpoint và kết quả đánh giá
├── models/        Trọng số Qwen dùng cục bộ
├── .venv/         Môi trường Python của ứng dụng
└── README.md      Hướng dẫn thư mục này
```

Ứng dụng đọc trực tiếp `data/`, `artifacts/`, `models/` và `.venv/` tại các vị trí trên. Dữ liệu đang dùng gồm địa giới hành chính cũ–mới và du lịch Việt Nam. Tiến độ mã hóa lại nằm trong `artifacts/faiss/build_progress.json`; dữ liệu cũ không thuộc di sản được nén tại `data/archive/` và không tham gia truy xuất.

## Mở ứng dụng

Từ thư mục `DATN`, chạy:

```bash
bash SOURCE/scripts/run_assistant.sh
```

Giao diện tại [http://127.0.0.1:8001/](http://127.0.0.1:8001/). Nếu server đã chạy, chỉ cần mở địa chỉ này.

## Các tài liệu chính

- [Báo cáo tốt nghiệp đầy đủ và hồ sơ đối chứng](BAO_CAO/THESIS_2026/README.md): sáu chương, Word/PDF, kết quả, protocol và backlog; cập nhật kiểm thử D1 ngày 18/11/2026.
- [Kết quả nghiệm thu kỹ thuật D1](artifacts/research_validation_2026-11-18/README.md): 353 unit, 65 HTTP, 33 UI và đo độ trễ sơ bộ; mặc định app vẫn dùng D0.
- [Báo cáo Chương 2](BAO_CAO/Chuong_2_Thiet_ke_he_thong_KG_RAG_LLM.docx).
- [Báo cáo đồ án gốc](BAO_CAO/Đồ%20Án.pdf).
- [Phân tích kiến trúc](BAO_CAO/Phân%20tích%20kiến%20trúc.pdf).
- [Giải thích code, lý thuyết và giới hạn](SOURCE/docs/GIAI_THICH_BACKEND_3_LOP.md).
- [Hướng dẫn kỹ thuật và kiểm thử](SOURCE/README.md).
- [Báo cáo triển khai giai đoạn đầu](SOURCE/docs/IMPLEMENTATION_REPORT.md).
- [Kết quả kiểm thử hệ thống](artifacts/system_tests/).
- [Nhật ký dọn dẹp ngày 24/10/2026](artifacts/maintenance/cleanup_2026-10-24.json).

Ngày 24/10/2026 đã gom các báo cáo về `BAO_CAO/`, giữ một bản Word duy nhất và dọn cache Python, metadata Finder, liên kết hỏng cùng bản ZIP đã xác nhận không chứa mã nguồn riêng. Các đường dẫn của dữ liệu, mô hình và chương trình đang chạy được giữ nguyên.
