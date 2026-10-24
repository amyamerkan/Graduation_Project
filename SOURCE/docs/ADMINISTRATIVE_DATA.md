# Dữ liệu địa giới hành chính cũ–mới

> Mô tả dữ liệu và hành vi code ngày **25/10/2026**. Các mốc dưới đây là mốc được collector/dataset ghi nhận; tài liệu không thay thế việc đối chiếu hiệu lực với văn bản gốc.
> Đợt cập nhật dữ liệu và huấn luyện lại: [DATA_REFRESH_2026-10-25.md](DATA_REFRESH_2026-10-25.md).

## 1. Phạm vi

Miền `administration` có **31.496** bản ghi: 17.520 snapshot đơn vị, 10.618 liên kết chuyển đổi, 37 hồ sơ thuộc tính văn bản và 3.321 dòng đối chiếu Cục Thống kê. Danh mục gốc từ `vietnam-provinces==2026.9.0`; đợt bổ sung đã đối chiếu đủ 34 tỉnh và 3.321 đơn vị cấp xã hiện tại với nguồn chính thức, cập nhật 29 tên/cách ghi khác nhau. 34 tên tỉnh ở baseline 2025 được đối chiếu riêng với bảng năm 2025.

Không có dữ liệu polygon ranh giới, tọa độ đầy đủ hoặc hồ sơ pháp lý hoàn chỉnh cho từng sự kiện. Hai tên/mã giống nhau ở hai snapshot không đồng nghĩa đó là cùng thực thể lịch sử liên tục.

## 2. Ba snapshot

| Khóa `snapshot` | `snapshot_date` | Thành phần trong dữ liệu | Cách biểu diễn |
|---|---|---|---|
| `legacy` | `2025-06-30` | 63 tỉnh/thành, 696 huyện/quận, 10.051 xã/phường | `HistoricalProvince`, `District`, `HistoricalAdministrativeUnit`; có `valid_to=2025-06-30` |
| `reorganized2025` | `2025-07-01` | 34 tỉnh/thành, 3.321 xã/phường/đơn vị cấp xã | `Province`, `Ward`; có `valid_from=2025-07-01` |
| `current` | `2026-10-24` | 34 tỉnh/thành, 3.321 đơn vị cấp xã, đã đối chiếu mã/tên với bảng Cục Thống kê | `Province`, `Ward`; `isCurrentSnapshot=true`, không tự gán ngày bắt đầu hiệu lực |

`current` nghĩa là bản danh mục hiện được ứng dụng chọn cho câu hỏi không kèm ngày. Nó không có cơ chế tự tiến theo ngày hệ thống hoặc tự cập nhật khi pháp luật thay đổi.

Số node `Province=68`, `Ward=6.642` trong KG là tổng hai snapshot mới, không được dùng làm số tỉnh/xã hiện hành. Truy vấn danh mục cần lọc đúng snapshot.

## 3. Cấu trúc bản ghi đơn vị

| Trường trong `data` | Ý nghĩa |
|---|---|
| `snapshot`, `snapshot_date` | Phiên bản và ngày chụp danh mục |
| `level` | `province`, `district`, `ward` |
| `name`, `code` | Tên và mã dạng chuỗi |
| `province_code`, `province_name` | Tỉnh/thành tương ứng trong cùng snapshot |
| `district_code`, `district_name` | Có ở đơn vị lịch sử phù hợp |
| `division_type` | Loại đơn vị theo nguồn |
| `catalogue_version` | `2026.9.0` |
| `valid_from`, `valid_to` | Chỉ có khi collector ghi nhận mốc; không đồng nhất với ngày crawl |
| `description`, `country` | Mô tả phục vụ truy xuất, `VN` |

Quy tắc mã: tỉnh 2 chữ số, huyện 3, xã 5 ở collector. Giữ `"00070"` dưới dạng string; đổi sang số nguyên sẽ làm mất số 0 đầu. Trong KG, định danh có context snapshot; index mã có phiên bản để tránh gộp `legacy` với `current`.

Cha/con phải tồn tại cùng snapshot. Cấu trúc lịch sử: xã → huyện → tỉnh; cấu trúc mới trong dữ liệu: xã → tỉnh. Builder báo lỗi nếu thiếu cha hoặc chuyển đổi tham chiếu một snapshot không có.

## 4. Chuyển đổi cũ–mới

`administrative_conversion.data` gồm:

```json
{
  "level": "ward",
  "old_code": "00001",
  "old_name": "Tên đơn vị cũ",
  "new_code": "00002",
  "new_name": "Tên đơn vị sau sắp xếp",
  "is_partial": true,
  "valid_from": "2025-07-01",
  "catalogue_version": "2026.9.0"
}
```

Đây là ví dụ cấu trúc với mã/tên minh họa. Một đơn vị cũ có thể có nhiều dòng đích; không ép quan hệ thành một-một.

| Điều kiện | Quan hệ KG | Cách diễn đạt |
|---|---|---|
| `is_partial=false` | `REORGANIZED_INTO` | Liên kết chuyển đổi sau sắp xếp |
| `is_partial=true` | `PARTLY_MERGED_INTO` | Chuyển một phần địa bàn; không kết luận nhập toàn bộ |

Builder nối từ node `legacy` tới node `reorganized2025`. Tên đích dùng baseline 2025, không lấy tên cập nhật 2026 thay vào. Dữ liệu có 9.513 quan hệ chuyển đổi thông thường và 1.105 quan hệ chuyển một phần. Báo cáo collector còn lưu 10 mục chuyển đổi bị bỏ qua do không khớp đơn vị tham chiếu; không được tự tạo cạnh để bù.

Một liên kết có thể giữ cùng mã/tên qua hai snapshot; quan hệ đó chưa đủ để khẳng định có một vụ sáp nhập thực địa. Nên trình bày là chuyển đổi danh mục theo nguồn, giữ trường `transitionType` và dẫn nguồn.

## 5. Quy tắc hiệu lực và truy vấn theo ngày

1. Phân biệt `retrieved_at` (ngày lấy dữ liệu), `snapshot_date` (ngày mô tả danh mục), `valid_from/valid_to` (mốc hiệu lực được ghi) và ngày ban hành văn bản.
2. Câu hỏi có mã + một ngày hợp lệ định dạng ISO hoặc `dd/mm/yyyy` có thể tạo kế hoạch `09_unit_at_time`.
3. Nếu node có `snapshotDate`, ngày yêu cầu phải **đúng ngày snapshot**, không tự coi snapshot có hiệu lực tới ngày kế tiếp hoặc tới hiện tại.
4. Với dữ liệu không có snapshot nhưng có khoảng hiệu lực đủ căn cứ, query/checker có logic kiểm tra khoảng; corpus hiện tại chủ yếu dùng snapshot. Khoảng mở một đầu không tự chứng minh mọi ngày ngoài mốc đã biết.
5. Điều kiện tỉnh nếu có phải khớp quan hệ KG; sau khi LLM chọn, CrossChecker kiểm tra lại ngày và tỉnh.
6. Nếu không có bản ghi phù hợp, không dùng văn bản RAG để tự xác nhận điều kiện ngày bị thiếu.

Ví dụ hành vi kỳ vọng theo dữ liệu/test hiện tại:

| Câu hỏi | Kỳ vọng |
|---|---|
| “Ngày 30/06/2025, mã 00070 thuộc thành phố Hà Nội không?” | Snapshot cũ; tên ghi trong dữ liệu là Phường Hàng Trống |
| “Ngày 01/07/2025, đơn vị có mã 00070 là gì?” | Snapshot sau sắp xếp; tên ghi trong dữ liệu là Phường Hoàn Kiếm |
| “Ngày 24/10/2026, mã 00070 là đơn vị nào?” | Tra snapshot thu thập hiện tại |
| “Ngày 01/08/2025, mã 00070 là đơn vị nào?” | Không nội suy từ hai snapshot; từ chối khi không có căn cứ |
| “Ngày 01/07/2025, mã 00070 thuộc tỉnh Quảng Ninh không?” | Không có dòng khớp đồng thời mã–ngày–tỉnh; từ chối xác nhận |
| “Hôm nay mã 00070 thuộc tỉnh nào?” | Thời gian tương đối chưa được xác nhận; từ chối |

`abstained` là thiếu khả năng xác nhận bằng dữ liệu/phạm vi hiện có, không phải bằng chứng mệnh đề người dùng hỏi là sai. Các kỳ vọng trên kiểm tra dữ liệu ứng dụng, chưa phải kiểm chứng pháp lý độc lập.

## 6. Tên, địa danh trùng và chất lượng nguồn

Không gộp theo tên khi có thể dùng mã/snapshot. Khi hỏi tên không có mã, truy vấn theo chuỗi có thể khớp nhiều đơn vị; dịch vụ trả lời gắn cảnh báo mơ hồ thay vì coi một bản ghi tùy ý là duy nhất. Người dùng cần bổ sung địa phương hoặc mã.

Tên “Thành phố Quảng Ninh” ở snapshot thu thập 2026 đã được đối chiếu với bảng Cục Thống kê; baseline 2025 vẫn giữ “Tỉnh Quảng Ninh” theo bảng năm 2025. Bảng hiện tại cũng ghi số/ngày văn bản tham chiếu. Đây là đối chiếu các trường được trang nguồn hiển thị, chưa thay thế việc đọc và xác minh toàn văn văn bản tương ứng.

`administrative_reference.data` giữ `observed_date=24/10/2026`, `reference_date=31/10/2025`, tên/mã/tỉnh của hai cột, `legal_reference`, `recorded_date`, `change_note`, `retrieved_at` và mô tả trích xuất. Không gọi cột đối chiếu 31/10/2025 là snapshot trước tháng 7/2025, không tự chuyển câu ghi chú thành các cạnh sáp nhập suy diễn.

37 trang văn bản mới có metadata. Code chưa trích xuất đầy đủ phụ lục, chưa gắn văn bản căn cứ riêng cho từng cạnh chuyển đổi, chưa duy trì timeline đầy đủ giữa 2025 và 2026. RDF cũng chưa lưu ngày hiệu lực/provenance dưới dạng thuộc tính của từng sự kiện chuyển đổi độc lập.

## 7. Các điều kiện chưa hỗ trợ

- Khoảng năm, khoảng ngày, “trước/sau/từ ngày” và thời gian tương đối nói chung.
- Xác nhận ngày ngoài snapshot hoặc tự cập nhật theo “hiện nay”.
- Biên giới polygon, giáp ranh, bán kính, gần nhất, khoảng cách và định vị tọa độ.
- Tự quy đổi địa chỉ du lịch xuống xã mới khi nguồn chỉ ghi quận/huyện/tỉnh cũ.

Các điều kiện này được phát hiện bằng regex/quy tắc, chưa phải bộ phân tích ngôn ngữ bao phủ mọi cách diễn đạt. Khi mở rộng cần thêm dữ liệu và kiểm thử âm để tránh xác nhận quá phạm vi.

## 8. Cập nhật và hướng phát triển

Quy trình hiện tại giữ riêng snapshot và kiểm tra cha/con/mã trước build. Hướng mở rộng là tạo thực thể sự kiện có `effective_from/effective_to`, văn bản căn cứ, phạm vi chuyển đổi, nguồn và mức xác minh; thêm ánh xạ hình học khi cần xử lý địa giới thực sự. Đây là đề xuất, chưa có bảng sự kiện hoặc truy vấn GIS trong hệ thống.

Mã đối chiếu: [corpus_update.py](../src/vn_assistant/corpus_update.py), [kg_builder.py](../src/vn_assistant/kg_builder.py), [router.py](../src/vn_assistant/router.py), [09_unit_at_time.rq](../queries/09_unit_at_time.rq), [cross_check.py](../src/vn_assistant/cross_check.py). Nguồn: [DATA_SOURCES.md](DATA_SOURCES.md).
