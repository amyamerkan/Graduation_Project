# Mở rộng dữ liệu và thực nghiệm phục vụ đồ án

Ngày 18/11/2026 đã kiểm thử D1 riêng trên cổng 8011: 353/353 unit test, 65/65 ca HTTP và 33/33 kiểm tra UI đạt; có đo độ trễ tuần tự 3 câu × 5 lần. Xem [bằng chứng nghiệm thu kỹ thuật](../../artifacts/research_validation_2026-11-18/README.md) và [hồ sơ báo cáo tốt nghiệp](../../BAO_CAO/THESIS_2026/README.md). Dữ liệu mặc định D0 vẫn được giữ; đây chưa phải chấm chất lượng câu trả lời độc lập.

Đợt 30–31/10/2026 tạo một **release nghiên cứu riêng** tại `DATN/artifacts/research_expansion_2026-10-30/`. Dữ liệu/app đang hoạt động không bị thay thế. Báo cáo kết quả được sinh từ số đo, không điền chỉ số dự kiến:

- [Báo cáo dữ liệu, phương pháp và kết quả](../../artifacts/research_expansion_2026-10-30/RESEARCH_REPORT.md).
- [Kiểm kê và kiểm tra bảo toàn dữ liệu](../../artifacts/research_expansion_2026-10-30/corpus_audit.json).
- [Kết quả thực nghiệm đầy đủ](../../artifacts/research_expansion_2026-10-30/experiment_report.json).
- [Bảng đối chiếu hành chính cũ–mới](../../artifacts/research_expansion_2026-10-30/administrative_crosswalk.csv).
- [Điểm đến theo tỉnh/thành](../../artifacts/research_expansion_2026-10-30/tourism_by_province.csv).
- [Phiếu duyệt nhãn thủ công](../../artifacts/research_expansion_2026-10-30/annotation_review.csv).

## Đối chiếu yêu cầu giảng viên

| Yêu cầu | Phần thực hiện |
|---|---|
| Dữ liệu và phương pháp có sẵn, thực nghiệm sơ bộ | D0 là bộ dự án đã có, gồm danh mục cộng đồng và dữ liệu đã thu thập; so sánh TF-IDF, BM25, E5 và RRF. Nêu rõ dữ liệu/thuật toán có sẵn, trích dẫn công trình gốc. |
| Xây dựng dữ liệu mới, thử nhiều phương pháp | D1 giữ toàn bộ D0, thêm đoạn sắp xếp có nguồn, điểm đến mới và dòng quan sát bảng NSO có ngày; cùng giao thức chạy trên D0/D1. |
| Đề xuất phương pháp lai và thực nghiệm | Kết hợp phân miền, từ khóa tỉnh cũ/mới, điều kiện mã/ngày và RRF; ablation bỏ điều kiện tỉnh/thời gian; đánh giá riêng dữ liệu cũ và mở rộng. Đây là đóng góp tích hợp, chưa tuyên bố tính mới thuật toán toàn cầu. |

## Quy tắc dữ liệu

- Giữ số 0 đầu, phân biệt mã tái sử dụng qua các snapshot.
- Tách `retrieved_at`, ngày quan sát của bảng, ngày snapshot và hiệu lực pháp lý. Không biến ngày cào thành ngày hiệu lực.
- Giữ nguyên địa chỉ du lịch từ nguồn; không suy ra xã mới khi địa chỉ chỉ có huyện/tỉnh cũ.
- Giữ chuyển đổi một phần; không nối hai thực thể lịch sử chỉ vì cùng mã/tên.
- Giữ raw, URL, SHA256, trạng thái cache và audit khử trùng. Không xóa hoặc chuẩn hóa lại văn bản trong archives.
- Tiếp tục loại chủ đề di sản phi vật thể khỏi dữ liệu du lịch; giữ các điểm tham quan vật thể phù hợp.

## Phạm vi kết quả

Các câu silver được sinh từ dữ liệu nguồn để phát triển phương pháp; chúng không thay benchmark được người gán nhãn độc lập. Tách dev/test theo thực thể và giữ riêng bộ phát triển thủ công cũ. Chỉ số truy xuất không đồng nghĩa factual accuracy của câu trả lời; ca không có snapshot được đo khả năng từ chối riêng. Chưa có thực nghiệm GIS/polygon, cross-encoder hoặc benchmark BEIR công khai trong đợt này.

Pipeline chạy lại bằng các script `collect_research_expansion.py`, `finalize_research_corpus.py`, `retrain_domain_refresh.py`, `refresh_vectors.py`, `run_research_experiments.py`, `write_research_report.py`. Lệnh và giới hạn tái lập nằm trong báo cáo kết quả. Router có được train lại; E5/Qwen vẫn là pretrained, không gọi việc tạo embedding là fine-tune.
