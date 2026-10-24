# Nguồn dữ liệu, độ tin cậy và thời điểm cập nhật

> Kiểm kê dữ liệu cục bộ ngày **25/10/2026**. URL, thời điểm thu thập và phạm vi trích xuất được đọc từ code, JSONL và manifest đã lưu; tài liệu này không xác nhận các website vẫn giữ nguyên nội dung tại thời điểm người đọc mở liên kết.
> Đợt cập nhật dữ liệu và huấn luyện lại: [DATA_REFRESH_2026-10-25.md](DATA_REFRESH_2026-10-25.md).

## 1. Danh mục nguồn đang hoạt động

| Nguồn và URL | Miền / số bản ghi trong corpus hiện tại | Độ tin cậy và giới hạn | Thời điểm của bản đang lưu |
|---|---|---|---|
| [vietnam-provinces 2026.9.0](https://pypi.org/project/vietnam-provinces/2026.9.0/) | 24.749 bản ghi còn dùng nguồn chính là package; danh mục/chuyển đổi ban đầu có 28.138 bản ghi | Giữ nguồn cộng đồng cho dữ liệu chưa đối chiếu; snapshot hiện tại và 34 tỉnh baseline 2025 đã được cập nhật nguồn sau kiểm tra bảng chính thức | Thu thập 24/10/2026; snapshot 30/06/2025, 01/07/2025, 24/10/2026 |
| [Danh mục Cục Thống kê](https://danhmuchanhchinh.nso.gov.vn/) và [bảng đối chiếu](https://danhmuchanhchinh.nso.gov.vn/Doi_Chieu_Moi.aspx) | 3.355 snapshot hiện tại được đối chiếu/cập nhật nguồn và 3.321 bản ghi tham chiếu mới | Đối chiếu mã/tên/tỉnh, giữ ghi chú và tham chiếu văn bản; chưa xác minh toàn văn mọi thay đổi | Thu thập 24/10/2026; ngày tra cứu 24/10/2026, cột đối chiếu 31/10/2025 |
| [Bảng danh mục 2025 của Báo Chính phủ](https://baochinhphu.vn/bang-danh-muc-va-ma-so-cua-34-tinh-thanh-moi-3321-don-vi-hanh-chinh-cap-xa-moi-102250704153652947.htm) | 34 snapshot tỉnh baseline 2025 được đối chiếu/cập nhật nguồn | Dùng bảng năm 2025, không lấy tên tỉnh cập nhật 2026 áp ngược | Thu thập 24/10/2026, nội dung danh mục năm 2025 |
| [Cơ sở dữ liệu ngành Du lịch](https://csdl.vietnamtourism.gov.vn/) | Du lịch: 452 hồ sơ | Nguồn ngành chính thức theo manifest; tên, địa chỉ và mô tả được trích từ trang. Địa chỉ có thể giữ tên cũ, độ đầy đủ giữa tỉnh khác nhau | Thu thập và bổ sung 24/10/2026 |
| [Trang điểm đến Vịnh Hạ Long](https://vietnamtourism.vn/index.php/tourism/items/1627/6) | Du lịch: 1 hồ sơ bổ sung | Trang cơ quan du lịch theo code; chỉ trích phần giới thiệu vị trí. Không suy ra đã có mọi thuộc tính du lịch | `retrieved_at` 24/10/2026, khoảng 20:27 giờ Việt Nam |
| [Trang tổng hợp nghị quyết sắp xếp cấp xã](https://baochinhphu.vn/34-nghi-quyet-cua-ubtvqh-ve-sap-xep-cac-don-vi-hanh-chinh-cap-xa-102250618163209716.htm) và các trang văn bản Chính phủ | Hành chính: 37 hồ sơ thuộc tính văn bản | Nguồn gốc chính thức; mới lấy metadata, chưa đọc/OCR đầy đủ phụ lục ký số; chưa chứng minh từng cạnh chuyển đổi | 24/10/2026, khoảng 01:43–01:44 giờ Việt Nam |

Tổng **31.949 bản ghi**: **31.496 hành chính** và **453 du lịch**. Số 186 hồ sơ du lịch trong manifest ban đầu và 202 sau đợt bổ sung 16 hồ sơ là các mốc lịch sử. Lượt crawl mới lấy 440 hồ sơ, ghép theo URL với dữ liệu cũ tạo 453 hồ sơ duy nhất, thêm 251 điểm đến. Báo cáo mới ở `data/raw/2026-10-24-refresh/` và `artifacts/domain_refresh_2026-10-24/release/`.

## 2. Phạm vi URL và nội dung

Danh bạ du lịch được đọc ở `/dest/`, `/area/`, `/vcgt/`; các hồ sơ có tham số `item`. Ví dụ URL có trong corpus: [Văn Miếu – Quốc Tử Giám](https://csdl.vietnamtourism.gov.vn/dest/?item=1). Bộ lọc tỉnh của danh bạ là căn cứ ánh xạ `province_code`, không phải phép xác nhận lại mọi địa chỉ đến cấp xã.

Nguồn văn bản gồm 34 liên kết nghị quyết cấp xã được trích từ trang tổng hợp và ba URL bổ sung cố định trong `collect_official_administration`:

- [Văn bản docid 214409](https://vanban.chinhphu.vn/?classid=1&docid=214409&orggroupid=3&pageid=27160).
- [Văn bản docid 213930](https://vanban.chinhphu.vn/?classid=1&docid=213930&orggroupid=1&pageid=27160).
- [Văn bản docid 219325](https://chinhphu.vn/?classid=0&docid=219325&pageid=27160).

Trường được lấy: số ký hiệu, ngày ban hành, ngày hiệu lực nếu có trên trang, loại văn bản, cơ quan ban hành, người ký và trích yếu. Ngày thu thập không thay cho ngày ban hành hoặc ngày hiệu lực.

## 3. Bằng chứng lưu tại dự án

Tất cả đường dẫn sau tính từ `DATN/`:

| Tệp / thư mục | Giá trị kiểm chứng |
|---|---|
| `data/raw/2026-10-24/administration.jsonl` | Bản ghi danh mục và liên kết chuyển đổi trước khi đưa vào corpus |
| `tourism.jsonl`, `selected_destinations.jsonl`, `halong_destination.jsonl` trong cùng thư mục raw | Hồ sơ du lịch ban đầu và bổ sung |
| `official_administration.jsonl` trong raw | 37 hồ sơ thuộc tính văn bản |
| `http_cache/` trong raw | HTML lưu theo SHA-256 của URL |
| `http_manifest.jsonl`, `official_http_manifest.jsonl`, `halong_http_manifest.jsonl` trong raw | URL, tên tệp, trạng thái, số byte, SHA-256 nội dung, `retrieved_at` |
| `source_manifest.json`, `collection_report.json`, `official_administration_report.json` trong raw | Phiên bản nguồn, phạm vi, lỗi thu thập và giới hạn |
| `artifacts/maintenance/destination_enrichment_2026-10-24.json` | 16 hồ sơ thêm sau kiểm kê ban đầu |

`PublicCrawler` kiểm tra robots.txt, giãn lượt theo host với độ trễ mặc định 0,8 giây, dùng cache và User-Agent `VN-Admin-Tourism-Thesis/1.0`. Khi đọc cache, `retrieved_at` mới phản ánh lần đọc cache, chưa chắc là lần tải HTML đầu tiên; manifest không cung cấp xác minh nội dung còn mới trên server nguồn.

Gói wheel danh mục được lưu tại raw, phiên bản `2026.9.0`; `source_manifest.json` ghi checksum `b5f3540a98937d38b9bebcbdb792fa4f5b9712737d41b05c7254beb2308ebcd1`. Nhãn giấy phép `GPL-3.0-or-later` là giá trị manifest ghi cho dependency; cần giữ thông tin nguồn và rà soát điều kiện sử dụng khi phân phối dữ liệu/sản phẩm.

## 4. Cách diễn giải độ tin cậy

Phân biệt ba mức đánh giá, không chuyển chúng thành một điểm số chưa được kiểm chứng:

1. **Xuất xứ:** trang cơ quan chính thức hoặc bộ dữ liệu cộng đồng có phiên bản.
2. **Độ đúng của trích xuất:** parser có lấy đúng trường, có thiếu phần ký số/địa chỉ hay sai ánh xạ không.
3. **Xác minh thực tế:** dữ kiện đã được đối chiếu với tài liệu gốc có hiệu lực và các nguồn thích hợp chưa.

Hiện tại `document_from_record`, `build_evidence` và citations giữ `source_verified=false`. Cross-check khẳng định mệnh đề khớp nội dung truy xuất/KG trong phạm vi được kiểm tra; không tự chứng minh nguồn đúng hoặc còn hiệu lực.

Các chuỗi “Thành phố Quảng Ninh”, “Thành phố Bắc Ninh” và “Thành phố Đồng Nai” hiện đã được đối chiếu với bảng Cục Thống kê, nơi có ghi tham chiếu văn bản. Đây là bước kiểm tra nguồn chính thức bổ sung cho dữ liệu cộng đồng. Nó không đồng nghĩa toàn văn mọi nghị quyết đã được đọc và xác minh; snapshot 2025 vẫn giữ riêng theo bảng năm 2025.

## 5. Dữ liệu ngoài corpus hoạt động

- `data/archive/` giữ dữ liệu cũ đã lọc và nén; API không đọc các archive trong cấu hình hiện hành.
- Miền riêng `heritage` và `law` còn dấu vết trong ontology/schema/test cũ, nhưng corpus hoạt động chỉ có hai miền đã nêu. Di tích, bảo tàng, lịch sử và văn hóa vẫn có thể xuất hiện dưới hồ sơ điểm đến du lịch.
- Theo manifest đã lưu, [vietnam.travel](https://vietnam.travel/term-conditions) bị loại khỏi lần crawl này vì điều kiện lưu nội dung cần cho phép; không phải nguồn đang dùng.
- Trọng số [multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base) và [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) là tài nguyên mô hình, không phải nguồn xác thực hành chính hoặc du lịch.

## 6. Quy trình cập nhật đề xuất

Chưa có scheduler tự động cập nhật. Các collector và một số hằng số đang gắn ngày `2026-10-24`; muốn cập nhật cần tạo phiên bản raw mới, sửa tham số/hằng số liên quan có kiểm soát và kiểm tra dữ liệu trước khi công bố corpus mới.

Nên rà soát hành chính khi có thông báo/văn bản thay đổi; rà soát địa chỉ điểm đến khi danh mục hoặc nguồn đổi. Mỗi lần cập nhật cần ghi thời gian tải thật, thời gian nội dung nguồn nếu có, mốc hiệu lực, checksum, phạm vi trích xuất, lỗi và quyết định giữ/loại. Chu kỳ cụ thể phải được vận hành lựa chọn; hiện chưa có SLA độ mới.

Mã đối chiếu: [corpus_update.py](../src/vn_assistant/corpus_update.py), [collect_official_administration.py](../scripts/collect_official_administration.py), [append_selected_destinations.py](../scripts/append_selected_destinations.py). Xem thêm [DATA_PIPELINE.md](DATA_PIPELINE.md).
