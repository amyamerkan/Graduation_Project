# Dữ liệu du lịch Việt Nam

> Đối chiếu corpus, collector và KG ngày **25/10/2026**. Đường dẫn dữ liệu tính từ `DATN/`. Các trường đề xuất mở rộng không phải dữ liệu đã có.
> Đợt cập nhật dữ liệu và huấn luyện lại: [DATA_REFRESH_2026-10-25.md](DATA_REFRESH_2026-10-25.md).

## 1. Phạm vi và độ phủ

Miền `tourism` hiện có **453 hồ sơ điểm đến**: 452 từ Cơ sở dữ liệu ngành Du lịch và một hồ sơ bổ sung Vịnh Hạ Long từ trang điểm đến của cơ quan du lịch. Sau chunking có **1.673 đoạn văn**; KG có **453 node `TourismPlace`**.

Tập ban đầu sau lọc có 186 hồ sơ; bước bổ sung 16 đưa tổng lên 202. Lượt crawl tiếp theo lấy 440 hồ sơ, ghép theo URL để thêm 251 điểm đến, tạo tổng 453. Toàn bộ 202 ID điểm đến cũ được giữ; bộ lọc đã loại 52 câu thuộc chủ đề phi vật thể trong 29 hồ sơ sau khi ghép. Các di tích, bảo tàng và nội dung tham quan được giữ lại.

Collector đặt mục tiêu sáu hồ sơ mỗi tỉnh và đã có kết quả ở 34 mã tỉnh trong báo cáo ban đầu, nhưng số hồ sơ thực tế không đều. Đây là mẫu điểm đến để phục vụ hỏi đáp, không phải danh bạ đầy đủ mọi điểm tham quan Việt Nam.

Phạm vi giữ lại gồm thắng cảnh, địa điểm tham quan, di tích, bảo tàng, công trình và không gian văn hóa gắn với địa điểm. Lễ hội độc lập và miền di sản phi vật thể riêng đã được loại khỏi corpus hoạt động. Nội dung văn hóa/lịch sử trong mô tả điểm đến vẫn được giữ.

## 2. Schema hồ sơ

Các trường chung ngoài `data`: `record_id`, `record_type="tourism_place"`, `domain="tourism"`, `source_name`, `source_url`.

| Trường trong `data` | Kiểu | Vai trò và giới hạn |
|---|---|---|
| `name` | string | Tên theo trang nguồn |
| `address` | string | Địa chỉ nguyên văn sau làm sạch; có thể chứa địa danh cũ |
| `description` | string | Mô tả điểm đến, trải nghiệm, văn hóa hoặc lịch sử nếu nguồn cung cấp |
| `province_code`, `province_name` | string | Tỉnh theo bộ lọc danh bạ/ánh xạ mã của collector |
| `province_mapping_basis` | string | Ghi căn cứ ánh xạ tỉnh |
| `address_time_scope` | string | Cảnh báo thời điểm/địa danh của địa chỉ nguồn |
| `retrieved_at` | datetime string | Thời điểm thu thập theo UTC trong JSONL |
| `country` | string | `VN` |
| `section` | string, tùy hồ sơ | Nhánh danh bạ `dest`, `area`, `vcgt`; hồ sơ bổ sung riêng có thể không có |

Ví dụ rút gọn từ hồ sơ đang có; mô tả được thay bằng dấu ba chấm để minh họa schema:

```json
{
  "record_id": "tourism_place_fc44765bd86b7133",
  "record_type": "tourism_place",
  "domain": "tourism",
  "source_name": "Cơ sở dữ liệu ngành Du lịch — TITC",
  "source_url": "https://csdl.vietnamtourism.gov.vn/dest/?item=1",
  "data": {
    "name": "Văn Miếu - Quốc Tử Giám",
    "address": "58 Quốc Tử Giám, Quận Đống Đa, Thành phố Hà Nội",
    "description": "...",
    "province_code": "01",
    "province_name": "Thành phố Hà Nội",
    "country": "VN"
  }
}
```

## 3. Lịch sử, văn hóa và thông tin thực dụng

Lịch sử xây dựng, nhân vật, kiến trúc, giá trị văn hóa và hoạt động tham quan hiện chủ yếu nằm trong `description` dưới dạng văn bản. Chưa có bảng sự kiện lịch sử, `history[]`, trường niên đại chuẩn hóa, thang độ tin cậy riêng cho từng mệnh đề hoặc ontology chi tiết cho mọi hoạt động.

Schema hoạt động cũng chưa có các trường cấu trúc được kiểm chứng cho giá vé, giờ mở cửa, số điện thoại, tọa độ, thời tiết, phương tiện, dịch vụ đặt chỗ hoặc lịch trình. Một vài thông tin có thể xuất hiện trong mô tả nguồn, nhưng không được xem là dữ liệu thời gian thực.

Tên có chữ “di sản”, “bảo tàng” hoặc “di tích” không tự làm hồ sơ thành lớp `WorldHeritage/Museum/HeritageSite` trong KG mới: nhánh ingest `tourism_place` tạo `TourismPlace`. Không suy ra năm/cấp công nhận từ tên hoặc từ ontology còn khai báo lớp di sản cũ.

## 4. Thu thập và chất lượng trích xuất

`parse_tourism_detail` tìm `main`, tiêu đề `h4`, khối `listing-shot`, dòng địa chỉ `span.d-block` và nội dung `.content-detail`. Parser từ chối trang thiếu cấu trúc, mô tả dưới 60 ký tự hoặc tên bắt đầu bằng “lễ hội”.

Collector duyệt theo bộ lọc tỉnh, chỉ nhận liên kết đúng host và có `item`, tránh trùng URL; ghi lỗi khi bộ lọc tỉnh xung đột. Bộ HTML có thể thay đổi, nên không coi crawl không báo HTTP lỗi là bằng chứng parser đã lấy đủ nội dung.

Script bổ sung tìm các điểm đến được chọn, giới hạn một số kết quả đầu danh bạ. Danh bạ có thể trả hồ sơ liên quan tới từ khóa nhưng không phải đúng điểm đến người dùng định hỏi. Cần kiểm tra tiêu đề và nội dung: ví dụ từ khóa Hạ Long có thể tìm cả cơ sở thương mại mang tên Hạ Long, nên đã có hồ sơ Vịnh Hạ Long riêng từ trang vị trí chính thức.

## 5. Quan hệ với địa giới hành chính

KG tạo `TourismPlace --LOCATED_IN--> Province` bằng `province_code` trong hồ sơ, trỏ tới snapshot hiện tại mà builder đã nạp. Node điểm đến giữ tên, mô tả, địa chỉ, nguồn và ID bản ghi; chưa có liên kết cấp xã được xác nhận hoặc timeline địa chỉ.

Địa chỉ và tỉnh ánh xạ có thể khác cách ghi: địa chỉ nguồn có quận/huyện/tỉnh cũ, trong khi `province_code` dùng bộ lọc nhóm theo danh mục mới. Hai trường phục vụ hai mục đích và phải hiển thị có ngữ cảnh. Không tự thay toàn bộ chuỗi địa chỉ cũ bằng tên mới khi chưa có đối chiếu.

Danh mục tỉnh hiện tại đã được đối chiếu mã/tên với bảng Cục Thống kê như ghi ở [ADMINISTRATIVE_DATA.md](ADMINISTRATIVE_DATA.md). Quan hệ KG xác nhận ánh xạ đã được pipeline ghi, không tự xác minh lại địa chỉ hiện hành của từng điểm đến.

## 6. Tên, alias và hồ sơ trùng

`train_domain_models.py` lưu `tourism_entities` và `tourism_aliases` trong router artifact. Có alias theo tên nhóm như Hội An, Mỹ Sơn, Hạ Long, Sa Pa, Phú Quốc, Nha Trang, Đà Lạt, Phong Nha, Cát Bà, Côn Đảo; có ánh xạ `Hồ Gươm → Hồ Hoàn Kiếm`.

Nhận diện hiện dựa trên chuỗi/alias, chưa phải entity linking học sâu. Alias có thể dẫn tới nhiều hồ sơ. “Thành phố Hội An” và “Khu phố cổ Hội An” có thể là các hồ sơ khác nhau được giữ từ nguồn; không tự xem chúng là một node duy nhất. Khi nhiều thực thể khớp, cần cảnh báo mơ hồ hoặc yêu cầu địa danh đầy đủ.

## 7. Từ hồ sơ tới câu trả lời

1. Tài liệu RAG dùng cùng ID với record, văn bản ghép tên, địa chỉ nguồn và mô tả.
2. Chia chunk 900 ký tự, overlap 150; giữ tiêu đề và URL trong SQLite.
3. Câu hỏi “ở đâu/địa chỉ/thuộc tỉnh nào” ưu tiên KG; câu hỏi giới thiệu/đặc sắc ưu tiên RAG; câu hỏi có cả hai dùng hybrid khi router nhận diện được.
4. Bộ lọc miền và tên/alias giới hạn ứng viên; các chunk đủ điểm tạo câu trích xuất.
5. LLM chọn mệnh đề, cross-check kiểm tra và backend gắn nguồn.

| Câu hỏi mẫu | Kỳ vọng theo thiết kế |
|---|---|
| “Hồ Gươm ở đâu?” | Dùng alias, tìm Hồ Hoàn Kiếm, dẫn dữ kiện KG |
| “Giới thiệu hoạt động tham quan tại Hội An.” | Truy xuất mô tả du lịch có nguồn |
| “Hồ Hoàn Kiếm ở đâu và có gì đáng chú ý?” | Kết hợp KG và văn bản khi đủ minh chứng |
| “Vịnh Hạ Long ở đâu?” | Tìm đúng hồ sơ Vịnh, tránh lấy cơ sở mang tên Hạ Long thay thế |
| “Điểm du lịch nào trong bán kính 5 km quanh Hồ Hoàn Kiếm?” | Từ chối điều kiện không gian chưa hỗ trợ |
| “Giá vé hôm nay là bao nhiêu?” | Không tự tạo dữ kiện thời gian thực; xem điều kiện và minh chứng hiện có |

Các câu về alias, Hội An, Hạ Long, hybrid Hồ Hoàn Kiếm và từ chối điều kiện bán kính đã chạy trong bộ HTTP 57 ca của đợt cập nhật. Khi không có minh chứng qua ngưỡng, hệ thống vẫn có thể từ chối; không nên ép mọi câu hỏi phải có câu trả lời.

## 8. Hướng mở rộng

**Đề xuất:** tách `address_original/address_normalized`, lịch sử địa chỉ và căn cứ ánh xạ; thêm tọa độ có nguồn, loại hình điểm đến, sự kiện lịch sử có thời gian, giá vé/giờ mở cửa có ngày kiểm chứng và alias đã duyệt. Chỉ thêm tìm bán kính khi có dữ liệu tọa độ đủ tin cậy và truy vấn không gian thật.

Đánh giá riêng khả năng phân biệt tên gần nhau, alias, hồ sơ rộng–hẹp, địa chỉ cũ–mới và câu hỏi nhiều điểm đến; đo cả độ phủ truy xuất và tỷ lệ trả lời sai thực thể. Xem [EVALUATION.md](EVALUATION.md) và [DATA_SOURCES.md](DATA_SOURCES.md).

Mã đối chiếu: [corpus_update.py](../src/vn_assistant/corpus_update.py), [append_selected_destinations.py](../scripts/append_selected_destinations.py), [train_domain_models.py](../scripts/train_domain_models.py), [kg_builder.py](../src/vn_assistant/kg_builder.py).
