# Báo cáo tốt nghiệp Tri Việt và hồ sơ đối chứng

Bản bàn giao ngày 18/11/2026 dựa trên hai PDF người dùng cung cấp, mã nguồn thực tế và artifacts nghiên cứu ngày 30–31/10. Tên đề tài, Nguyễn Anh Kiệt — 52300123, Trần Cao Phong — 52300144 và GVHD **TS. Trần Thanh Phước** đã được người dùng xác nhận.

- [Bản Word để chỉnh sửa](output/docx/Bao_cao_Do_an_Tot_nghiep_Tri_Viet_2026.docx).
- [Bản PDF để đọc và in](output/pdf/Bao_cao_Do_an_Tot_nghiep_Tri_Viet_2026.pdf).
- [Toàn văn Markdown](markdown/BAO_CAO_DO_AN_TOT_NGHIEP.md).
- [Mục lục bộ hồ sơ Markdown](markdown/00_BAT_DAU.md): đối chiếu 19 tuần, công việc/tiêu chí nghiệm thu, giao thức, kết quả, thẻ dữ liệu/hệ thống và công trình liên quan.
- [Nghiệm thu D1 và độ trễ](markdown/11_NGHIEM_THU_D1.md).
- [Bằng chứng chạy D1](../../artifacts/research_validation_2026-11-18/README.md) và [phiếu chấm câu trả lời](../../artifacts/research_validation_2026-11-18/answer_review.csv).

Bản xuất đã kiểm tra có **56 trang**, sáu chương; mỗi chương gồm giới thiệu, công trình liên quan, phương pháp/dữ liệu, thực nghiệm và kết luận. Các chương nguồn ở markdown/CHUONG_01.md đến CHUONG_06.md. Có tóm tắt Việt/Anh, mục lục, danh mục hình/bảng/ký hiệu, tài liệu tham khảo và phụ lục. Word và PDF dùng cùng bản bố cục; qa_manifest.json lưu số trang, hash và kết quả rà soát.

## Phạm vi kết quả

D0 có 31.949 tài liệu, D1 có 38.993; bảy cấu hình được so sánh trên cùng giao thức. Phương án lai đạt MRR@10 0,9297 trên silver test D1, nhưng thấp hơn RRF thường trên 16 câu phát triển thủ công. Đây là kết quả truy xuất sơ bộ, chưa phải độ chính xác trả lời độc lập.

Ngày 18/11, kiểm tra lại đạt 353 unit test, D1 đạt 65 ca HTTP và 33 kiểm tra UI trên cấu hình cô lập. Có số đo tuần tự ba câu, mỗi câu năm lần sau warmup. Những số này không chứng minh Faithfulness, chất lượng mọi dữ kiện hoặc khả năng tải đồng thời. D1 chưa thay mặc định D0 trong ứng dụng.

Phần cần tiếp tục được giữ rõ trong [backlog](markdown/02_CONG_VIEC_CAN_THUC_HIEN.md): duyệt nhãn và chấm độc lập, benchmark ngoài phù hợp, đối chứng cross-check, nguồn hiệu lực pháp lý, GIS nếu giữ trong phạm vi, cài mới trên máy độc lập và sản phẩm bảo vệ. Phiếu đánh giá đã được chuẩn bị; không tự điền điểm, chữ ký hoặc sự chấp thuận của GVHD. Tác giả cần đọc và duyệt lời cảm ơn, cam đoan, nội dung trước khi nộp.

## Các tệp đưa lên Git

Code, dữ liệu corpus/raw, graph/router, cấu hình, kết quả thí nghiệm, ảnh minh họa và bản báo cáo được lưu cùng repo. Không đưa thư viện tạm, ảnh render QA và hai bộ chỉ mục FAISS/SQLite nghiên cứu có thể tạo lại vào Git. Không xóa các tệp này trên máy hiện tại. Thư mục tmp/ chỉ phục vụ dựng/kiểm tra tài liệu.

Sau khi clone, cần tạo môi trường và tải trọng số theo [hướng dẫn kỹ thuật](../../SOURCE/README.md) và [triển khai](../../SOURCE/docs/DEPLOYMENT.md). Để tái tạo chỉ mục D1 từ corpus đã lưu, chạy từ SOURCE, dùng output riêng:

```bash
export FAISS_INDEX_PATH=../artifacts/research_expansion_2026-10-30/artifacts/faiss_rebuilt/vn.index
export FAISS_METADATA_PATH=../artifacts/research_expansion_2026-10-30/artifacts/faiss_rebuilt/metadata.sqlite3
../.venv/bin/python -m vn_assistant.cli build-faiss \
  --dataset ../artifacts/research_expansion_2026-10-30/data/rag_dataset_final.jsonl \
  --model intfloat/multilingual-e5-base --device cpu --batch-size 16 \
  --chunk-size 900 --overlap 150
```

Dùng mps/cuda chỉ khi máy hỗ trợ. Không thay output vào server đang hoạt động. Chạy lại benchmark có thể khác nhỏ theo phần cứng và phiên bản; giữ config/hash và báo cáo mới riêng. Hướng dẫn này chưa thay bằng chứng cài mới trên một máy độc lập.

## Dựng lại báo cáo

Phụ thuộc Python: python-docx, pypdf, pdfplumber, Pillow; matplotlib nếu dựng lại biểu đồ. Chạy từ gốc DATN:

```bash
python BAO_CAO/THESIS_2026/complete_handover.py
python BAO_CAO/THESIS_2026/build_pack.py
python BAO_CAO/THESIS_2026/make_figures.py
python BAO_CAO/THESIS_2026/build_document.py
```

Trong phiên tạo tài liệu này, Python/LibreOffice/Poppler bundled của Codex được dùng để dựng và kiểm tra. Khi dựng ở môi trường khác, cài các phụ thuộc tương ứng. make_figures.py ưu tiên gói bổ sung cục bộ nếu có, nhưng dùng matplotlib đã cài khi tmp/ không tồn tại.

Sau khi render Word ra PDF/PNG bằng render_docx.py, chạy update_pagination.py với đường dẫn PDF, dựng Word và render lại cho tới khi mapping_stable là true. Chạy qa_document.py --render-dir <thư_mục_render>, kiểm tra từng trang và sao chép đúng PDF đã kiểm tra sang output/pdf/. Mục lục hiện là bản đã đối chiếu số trang; sửa Word cần cập nhật lại. Không chỉ sửa PDF hoặc sửa bảng số đo mà không thay bằng chứng gốc.

input_manifest.json ghi đường dẫn/hash PDF nguồn trên máy tác giả; các PDF nguồn cá nhân không được sao chép vào bộ THESIS_2026. evidence_manifest.json và validation_manifest.json giúp truy nguyên các kết quả được trích dẫn. Báo cáo chưa có chữ ký hay xác nhận nghiệm thu của nhà trường.
