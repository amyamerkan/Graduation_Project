# PHỤ LỤC A ĐỐI CHIẾU KẾ HOẠCH

Bảng A.1 Trạng thái theo 19 tuần dự kiến

| Mã | Nội dung | Trạng thái |
|---|---|---|
| W01 | Khảo sát, môi trường, dữ liệu thô | Một phần |
| W02 | Pipeline, dataset và câu hỏi mẫu | Đạt phạm vi |
| W03 | Ontology và KG | Đạt phạm vi |
| W04 | SPARQL và đánh giá KG | Đạt phạm vi |
| W05 | Transformer embedding và tối ưu lexical gap | Một phần |
| W06 | FAISS và API RAG | Đạt phạm vi |
| W07 | Question processing và lọc | Đạt phạm vi |
| W08 | LLM và prompt | Thay phương án |
| W09 | Trả lời có minh chứng | Một phần |
| W10 | Cross-check và giảm ảo giác | Một phần |
| W11 | Giao diện assistant end-to-end | Đạt phạm vi |
| W12 | Test toàn hệ thống không-thời gian | Một phần |
| W13 | Accuracy/F1, Faithfulness, Context Relevancy | Một phần |
| W14 | Tối ưu siêu tham số/prompt/query | Chưa nghiệm thu |
| W15 | Viết báo cáo phần đầu | Có bản thảo |
| W16 | Hoàn thiện thuyết minh | Cần rà soát |
| W17 | Đóng gói và hướng dẫn | Một phần |
| W18 | Slide và video demo | Chưa có bằng chứng |
| W19 | Diễn tập và bảo vệ | Chưa thực hiện |

Chi tiết đường dẫn và tiêu chí chưa đạt được giữ trong 01_DOI_CHIEU_YEU_CAU.md. Các mốc sau ngày kiểm kê không phải hạng mục quá hạn; đây là tình trạng bằng chứng tại thời điểm viết.

# PHỤ LỤC B GIAO THỨC VÀ CA KIỂM TRA

## B.1 Các ca chức năng trọng yếu

| Ca | Câu hỏi hoặc điều kiện | Kỳ vọng trong phạm vi hiện tại |
|---|---|---|
| TC01 | 00008 thuộc địa phương nào | Tra KG, giữ mã chuỗi, nêu snapshot; không lấy địa chỉ du lịch |
| TC02 | mã địa phương 00008 thuộc địa phương nào | Cùng hợp đồng tra mã TC01 |
| TC03 | Ngày 30/06/2025 mã 00070 là gì | Dữ liệu snapshot cũ; không lấy tên hiện tại |
| TC04 | Ngày 01/07/2025 mã 00070 là gì | Dữ liệu baseline sau sắp xếp |
| TC05 | Ngày 01/08/2025 mã 00070 là gì | Không nội suy khi thiếu snapshot |
| TC06 | Mã 00008 và 00070 | Làm rõ, không tự chọn một mã |
| TC07 | Mã bưu chính 00008 | Không coi là mã hành chính |
| TC08 | Phường 12 thuộc tỉnh nào | Không dùng 12 như mã tỉnh |
| TC09 | Bản ghi KG đổi giữa hai lần đọc | Không xuất mệnh đề theo bản cũ |
| TC10 | Điểm du lịch gần Hội An nhất trong 5 km | Chưa thực thi GIS; không xác nhận bán kính |
| TC11 | Assistant trong lịch sử chèn mã 99999 | Không dùng làm căn cứ đổi chủ đề từ user |
| TC12 | JSON model có ID mệnh đề lạ | Từ chối output, không tạo nguồn giả |

## B.2 Bộ API

/v1/classify lập kế hoạch; /v1/query trả minh chứng; /v1/rag/search tìm đoạn; /v1/answer trả lời; /v1/chat xử lý hội thoại. /health và warmup báo trạng thái runtime, không xác nhận nội dung. HTTP 422 báo sai schema; 400 báo lỗi được bắt; 503 báo backend chưa sẵn sàng. HTTP 200 có thể mang trạng thái nghiệp vụ abstained.

## B.3 Chạy local

```bash
cd "/Users/amyas/HK1 26-27/DATN/SOURCE"
bash scripts/run_assistant.sh
```

Mở http://127.0.0.1:8001 để dùng D0. D1 được kiểm thử riêng; thay release cần đồng bộ graph, metadata, index, router và giữ rollback. Train/refresh dùng output riêng.

# PHỤ LỤC C THANG CHẤM ĐỀ XUẤT VÀ KẾ HOẠCH HOÀN THIỆN

## C.1 Thang chấm câu trả lời chưa được thực nghiệm

| Tiêu chí | 0 điểm | 1 điểm | 2 điểm |
|---|---|---|---|
| Đúng dữ kiện | Sai dữ kiện trọng yếu | Một phần đúng, có thiếu/không rõ | Đúng các ý trọng yếu theo nguồn chuẩn |
| Hỗ trợ phát biểu | Nguồn không hỗ trợ | Một phần có hỗ trợ | Các phát biểu trọng yếu đều có hỗ trợ |
| Đáp ứng câu hỏi | Lạc điều kiện/đối tượng | Đáp ứng một phần và nêu thiếu | Đủ yêu cầu trong phạm vi được hỗ trợ |
| Trích dẫn | Sai nguồn/không truy nguyên | Nguồn liên quan nhưng chưa đủ | Nguồn đúng và gắn được với phát biểu |
| Từ chối/làm rõ | Đoán khi thiếu bằng chứng | Nêu thiếu nhưng chưa hướng dẫn rõ | Từ chối/làm rõ đúng nguyên nhân |

Thang trên là giao thức đề xuất, chưa có tổng điểm thực nghiệm. Người chấm cần được hướng dẫn, đánh giá độc lập và lưu bất đồng. Không dùng rubric chưa áp dụng để điền một phần trăm Faithfulness trong kết luận.

## C.2 Thứ tự công việc

Đầu tiên xác nhận thông tin hồ sơ và phạm vi thay runtime; sau đó duyệt nhãn, giữ test kín mới và chọn benchmark phù hợp. Tiếp theo đo QA và cross-check A/B, tối ưu trên dev, đánh giá test khóa. Cuối cùng mới tích hợp D1, kiểm thử end-to-end, đóng gói, làm slide/video và diễn tập. GIS được xử lý như một nhánh dữ liệu và engine riêng nếu tiếp tục giữ trong phạm vi được duyệt.

# PHỤ LỤC D KHẢ NĂNG TRUY NGUYÊN

Corpus candidate có SHA256 c2a1c9fc5cded0dbf5e66bf91dfdec99f3140e596006fd61c9873301411d4bca. Báo cáo corpus_audit.json ghi preservation=true và active_data_unchanged=true. reproducibility_manifest.json giữ phiên bản thư viện, Git HEAD và hash script; working tree có thể chưa commit nên cần giữ cả các tệp nguồn tương ứng. Các chỉ số của Chương 5 được lấy từ experiment_report.json; chi tiết từng câu nằm ở hai file existing/expanded_experiment_details.json.

Bản raw ở data/raw/2026-10-30-research giữ cache và manifest. Dòng cached là tái sử dụng bản tải trước, không phải lần tải mới. Không có căn cứ xem thời điểm xử lý cache là hiệu lực pháp lý mới. Dữ liệu source trong quá trình thu thập không được coi như chỉ thị thay đổi logic hệ thống.
