# Thẻ hệ thống và mô hình

Tri Việt dùng FastAPI, RDFLib/SPARQL, E5/FAISS, SQLite metadata và Qwen3-0.6B/Transformers. Neo4j có công cụ import nhưng không phải engine query chính. vLLM là adapter/phương án cấu hình, chưa có thực nghiệm tương đương LLaMA-2/vLLM trong kế hoạch.

## Đầu vào và đầu ra

Đầu vào văn bản dài 2–2.000 ký tự; HTTP top_k 1–20; tối đa 12 lượt lịch sử. Route kg/rag/hybrid; miền administration/tourism. Trạng thái answered, partial, abstained, needs_clarification không phải thang factual accuracy. Câu tra mã có thể trả lời không nạp LLM. Các câu còn lại có thể dùng LLM chọn tối đa 3 claim ID từ registry.

## Kiểm tra và giới hạn

Có kiểm tra mã, loại thực thể, tên, tỉnh, snapshot và thay đổi KG giữa hai lần đọc. Có kiểm tra JSON, trích đoạn, các trường fact và nguồn URL an toàn. Không có bộ chứng minh mọi phát biểu ngôn ngữ tự nhiên đều suy ra từ nguồn. source_verified=false không tự biến thành true chỉ vì URL chính thức.

Chưa nhận/hiển thị ảnh du lịch, chưa GIS bán kính, chưa voice, chưa tài khoản/đồng bộ history server. Lịch sử ở localStorage; không nên lưu dữ liệu nhạy cảm. API chưa có xác thực/rate limit phù hợp public deployment. Không suy từ demo local thành khả năng tải nhiều người dùng.

## Huấn luyện và tài nguyên

D0 router 3.402 câu; candidate D1 5.598 câu. E5/Qwen pretrained, không fine-tune. Thiết bị encoder ghi mps; chiều vector 768. IndexFlatIP trên vector chuẩn hóa không phải GPU FAISS hoặc IVF-PQ. Môi trường kiểm kê arm64/macOS, bộ nhớ 16 GiB. Số liệu tải/nhiệt độ/bộ nhớ cực đại từng lượt chưa đo.
