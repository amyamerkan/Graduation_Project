# Thẻ dữ liệu D0 và D1

Mục đích: hỏi đáp văn bản địa giới cũ–mới và điểm tham quan Việt Nam. Ngôn ngữ chủ yếu tiếng Việt. D0 là dữ liệu ứng dụng, D1 là release nghiên cứu riêng. Không phải tổng điều tra địa điểm du lịch hoặc timeline pháp lý liên tục.

| Loại bản ghi | D0 | D1 |
|---|---|---|
| Snapshot hành chính | 17520 | 17520 |
| Liên kết chuyển đổi | 10618 | 10618 |
| Hồ sơ thuộc tính văn bản | 37 | 37 |
| Dòng quan sát đối chiếu | 3321 | 6642 |
| Đoạn hành chính riêng biệt | 0 | 3351 |
| Điểm du lịch | 453 | 825 |
| Tổng tài liệu | 31949 | 38993 |

## Nguồn và quyền sử dụng

Danh mục nền vietnam-provinces 2026.9.0, nguồn cộng đồng có điều kiện GPL-3.0-or-later cần xem xét khi phân phối. Bảng NSO và bài Chính phủ là nguồn hành chính có thẩm quyền; thời điểm bảng hiển thị và hiệu lực cần được phân biệt. TITC cung cấp các điểm được lấy theo bộ lọc tỉnh và phân trang. Truy cập công khai không tự động đồng nghĩa mọi bài và ảnh có giấy phép mở; đợt này không thu ảnh.

## Đơn vị dữ liệu và thời gian

Code là string có số 0 đầu. Snapshot 2025-06-30, 2025-07-01, 2026-10-24 được giữ riêng. 3.321 quan sát mới ngày 30/10/2026 so với cột tham chiếu 31/10/2025; cột tham chiếu này không phải trước sắp xếp tháng 7. Không có thay đổi ở các trường được script đối chiếu giữa hai lần quan sát. Không đếm dòng quan sát thành sự kiện sáp nhập mới.

Đoạn pháp lý khử trùng theo biến thể số thứ tự/dấu câu, giữ nguyên văn và URL bổ sung. Có 2.757 biến thể trùng được gộp. Điểm du lịch mới: 372; tổng 825, thuộc 34 tỉnh theo nguồn. Audit mới loại 38 câu chủ đề phi vật thể. Tỉnh ít dữ liệu vẫn có thể có nhiều điểm thực tế chưa được crawl.

## Giới hạn và rủi ro

Nguồn có thể đổi nội dung; cache và SHA256 giúp truy nguyên nhưng không chứng minh sự thật. Địa chỉ có thể còn huyện/tỉnh cũ; không tự gán xã mới. Chuyển một phần không phải nhập toàn bộ. Corpus cũ và mới có tài liệu tương đương chưa được gán đầy đủ positive IDs. Những archives không hoạt động không phải input của D1; ghi chú sự cố vệ sinh archive trước đây được giữ ở hồ sơ bảo trì.
