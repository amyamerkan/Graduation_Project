# Sửa luồng tra cứu mã hành chính — 25/10/2026

## Vấn đề và hành vi sau sửa

Hai câu “00008 thuộc địa phương nào” và “mã địa phương 00008 thuộc địa phương nào” trước đây có thể bị phân loại sang du lịch, lấy địa chỉ không liên quan và hiển thị nhãn đã đối chiếu. Sau sửa, cả hai đi qua nhận diện mã dùng chung, tra KG và dựng câu trực tiếp:

> Mã hành chính 00008 là Phường Ngọc Hà, thuộc Thành phố Hà Nội. Thông tin theo bản chụp danh mục ngày 2026-10-24.

Đây là dữ kiện của snapshot đang lưu, không phải xác nhận tự động mọi ngày sau snapshot.

## Thay đổi

- `administrative_codes.py`: nhận diện mã có/không dấu, giữ số 0 đầu; phân biệt mã khác, nhiều mã, ngày/số lượng và số trong tên đơn vị. Chỉ chuẩn hóa câu hỏi, không sửa văn bản nguồn.
- Router/planner ưu tiên tra mã trước dự đoán thống kê. `03_unit_by_code` và `09_unit_at_time` không dùng RAG fallback khi thiếu/lỗi KG.
- Processor kiểm tra mã, loại đơn vị, tên, tỉnh và ngày trước khi dùng dữ kiện. Điều kiện tỉnh khớp toàn tên sau chuẩn hóa dấu/tiền tố.
- `AnswerService` dùng `structured_kg` cho tra mã: không gọi E5/Qwen; nhiều bản ghi yêu cầu làm rõ. Câu kèm nội dung mô tả chưa đủ căn cứ được đánh dấu `partial`.
- CrossChecker dựng lại kế hoạch từ câu hỏi, truy vấn lại KG và đối chiếu các trường trước khi xuất câu trả lời.
- Hội thoại tiếp nối giữ mã/ngày từ các lượt user; mã mới ghi rõ được ưu tiên. Nội dung assistant không được dùng làm bằng chứng.
- UI phân biệt “Đã kiểm tra mã và điều kiện tra cứu” với “Có minh chứng trích dẫn”; lưu cờ này cùng lịch sử. Câu trả lời sai đã lưu không được tự viết lại: tải lại trang rồi gửi lại câu hỏi.

## Kiểm chứng

Artifacts nằm tại `DATN/artifacts/admin_code_fix_2026-10-25/`:

- `unit_report.xml`: 350 kiểm thử, gồm 86 ca hồi quy mới.
- `backend_report.json`: kết quả bộ HTTP 65 ca; KG thật, nhánh du lịch dùng E5/Qwen, nhánh mã dựng câu trực tiếp.
- `ui/ui_report.json`: 33 kiểm tra Chromium, gồm câu lỗi trong ảnh, hội thoại, nhãn sau tải lại lịch sử, desktop/mobile và mô phỏng lỗi mạng/JSON.
- `ui/screenshots/desktop-answer.png`: giao diện sau khi tra mã và hỏi tiếp nối.

Không huấn luyện lại router, E5 hoặc Qwen trong thay đổi này; không sửa corpus hay archives. Lỗi được xử lý ở nhận diện, truy xuất và kiểm tra câu trả lời. Quy tắc vẫn cần mở rộng và thêm kiểm thử khi gặp cách hỏi mới; thiếu dữ liệu lịch sử hoặc ngày ngoài snapshot vẫn cần bổ sung nguồn phù hợp.
