# Công việc cần thực hiện và tiêu chí nghiệm thu

| Mã | Ưu tiên | Công việc | Tiêu chí | Sản phẩm cần có |
|---|---|---|---|---|
| G01 | P0 | Duyệt gold và tạo test kín | Hai người chấm; xác nhận đáp án/nguồn; lưu bất đồng và quy tắc giải quyết | annotation_review.csv và tập test mới đóng băng |
| G02 | P0 | Đánh giá câu trả lời | Chấm factuality, faithfulness, completeness, citation và từ chối theo rubric | Phiếu chấm; số mẫu; thống kê theo nhóm |
| G03 | P0 | Chọn benchmark ngoài phù hợp | Đúng phiên bản, giấy phép, adapter và task; không coi câu tự sinh là GS-QA | Manifest dữ liệu và output công khai phù hợp |
| G04 | P0 | Xác nhận phạm vi với GVHD | Người dùng đã xác nhận bìa; còn chấp thuận đổi runtime và thu hẹp miền | Bìa đã đồng bộ TS.; biên bản phạm vi cần GVHD |
| G05 | P1 | Đối chứng cross-check | Cùng câu, nguồn, mô hình; bật/tắt kiểm tra; chấm mệnh đề và coverage | Kết quả A/B, không chỉ unit test |
| G06 | P1 | Mở rộng đo độ trễ | Đã đo 3 câu x 5 lần và từng pha thô; còn tách encode/search và tăng mẫu, tải | artifacts/research_validation_2026-11-18/latency_report.json |
| G07 | P1 | Tối ưu trên dev | Chọn k, RRF, ngưỡng, prompt trên dev rồi khóa cấu hình | Config và hash trước test kín |
| G08 | P1 | Nghiệm thu phát hành D1 | Đã đạt 353 unit, 65 HTTP, 33 UI trên D1 cô lập; còn duyệt nội dung và phát hành | artifacts/research_validation_2026-11-18/validation_manifest.json |
| G09 | P1 | Căn cứ hiệu lực và chuyển một phần | Gắn văn bản/khoản cho sự kiện; không nội suy các ngày còn thiếu | Bảng sự kiện được thẩm định |
| G10 | P1 | Tăng độ phủ du lịch | Ưu tiên tỉnh ít bản ghi, nhiều cách hỏi tên cũ/mới; audit địa chỉ | Coverage theo tỉnh và nguồn |
| G11 | P2 | Truy vấn bán kính/hình học | Tọa độ có nguồn, mốc gốc, hệ quy chiếu, khoảng cách; test điểm chuẩn | Dữ liệu GIS và engine; chưa có hiện tại |
| G12 | P1 | Đóng gói cài mới | Dùng môi trường sạch trên máy khác; kiểm soát phiên bản và tài nguyên | Log cài/khởi chạy và quickstart |
| G13 | P1 | Slide và video | Demo mã/ngày, mô tả, ca không có dữ liệu, giới hạn phương pháp | Slide và video thực tế |
| G14 | P1 | Người viết và GVHD rà báo cáo | Đã xuất và kiểm tra bố cục/mục lục; cần tác giả duyệt nội dung, giấy phép và ký | qa_manifest.json; checklist tác giả/GVHD |

P0 là điều kiện để đưa ra kết luận nghiên cứu mạnh hoặc nộp bản chính thức; P1 phục vụ hoàn thiện và bàn giao; P2 là mở rộng nếu phạm vi được duyệt. Thứ tự đề xuất: G01–G04 trước, sau đó G05–G10 và G12, cuối cùng G13–G14. G11 cần nguồn lực riêng và không thể thay bằng crawl thêm văn bản.

Nếu giữ giới hạn hình học hoặc không chạy được một benchmark, cần ghi rõ điều chỉnh phạm vi và thống nhất với GVHD; không tạo số liệu để lấp chỗ thiếu. Không có phân công thời lượng thực tế hoặc chữ ký tác giả trong bằng chứng nên tài liệu không tự gán người chịu trách nhiệm và ngày hoàn tất.
