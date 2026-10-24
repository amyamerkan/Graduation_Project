# Báo cáo làm sạch, crawl bổ sung và huấn luyện lại — 25/10/2026

Đợt công việc bắt đầu ngày 24/10 và hoàn tất ngày 25/10/2026 theo giờ Việt Nam. Bản dữ liệu hành chính vẫn ghi mốc quan sát **24/10/2026**; ngày hoàn tất train không được dùng để đổi ngày snapshot.

## 1. Kết quả đã công bố

| Thành phần | Trước | Sau |
|---|---:|---:|
| Tài liệu hoạt động | 28.377 | 31.949 |
| Hành chính | 28.175 | 31.496 |
| Hồ sơ du lịch | 202 | 453 |
| Vector E5 | 28.909 | 33.169 |
| Node KG | 17.722 | 17.973 |
| Quan hệ KG xuất CSV | 28.209 | 28.460 |
| Câu huấn luyện router | 1.902 | 3.402 |

Đã thêm **3.572 tài liệu**: 3.321 dòng đối chiếu hành chính và 251 hồ sơ du lịch. Toàn bộ **202/202 ID điểm đến cũ được giữ**. Corpus và SQLite truy xuất không còn nội dung thuộc nhóm bị loại theo bộ lọc đã kiểm tra.

Dữ liệu/model hoạt động đã được thay tại `DATN/data/` và `DATN/artifacts/{kg,router,faiss}/`. Bản release đầy đủ và báo cáo ở `DATN/artifacts/domain_refresh_2026-10-24/release/`.

## 2. Loại bỏ chủ đề phi vật thể, giữ nội dung tham quan

Bộ lọc loại hồ sơ có chủ đề chính thuộc ca trù, nhã nhạc, quan họ, đờn ca tài tử, bài chòi và nhóm phi vật thể được khai báo. Với điểm đến, chỉ loại câu thuộc nhóm này, không loại toàn bộ di tích, bảo tàng, cảnh quan hoặc lịch sử gắn với nơi tham quan.

Sau ghép, đã loại **52 câu trong 29 hồ sơ điểm đến**, giữ phần nội dung du lịch còn lại. Tên địa lý như **Quan Hồ Thẩn** và **Châu Văn Liêm** có kiểm thử riêng để tránh nhầm với tên loại hình nghệ thuật. Câu hỏi về nhóm bị loại vẫn bị từ chối khi thêm từ “du lịch”; hỗ trợ nhận diện ví dụ không dấu `Ca tru` và tiếng Anh `intangible cultural heritage`.

HTML/DOM gốc được giữ làm bằng chứng nguồn; thư mục raw và bản rollback không tham gia huấn luyện hoặc truy xuất. Các câu hỏi âm trong test vẫn có tên chủ đề bị loại để kiểm tra cơ chế từ chối.

## 3. Nguồn và dữ liệu bổ sung

- [Cục Thống kê — danh mục hành chính](https://danhmuchanhchinh.nso.gov.vn/): đối chiếu 34 tỉnh/thành hiện tại.
- [Cục Thống kê — bảng đối chiếu](https://danhmuchanhchinh.nso.gov.vn/Doi_Chieu_Moi.aspx): lấy đủ **3.321 dòng qua 5 trang**; giữ ngày tra cứu 24/10/2026, ngày cột đối chiếu 31/10/2025, ghi chú và tham chiếu văn bản. Không gọi cột 31/10/2025 là dữ liệu trước sắp xếp tháng 7/2025.
- [Báo Chính phủ — danh mục năm 2025](https://baochinhphu.vn/bang-danh-muc-va-ma-so-cua-34-tinh-thanh-moi-3321-don-vi-hanh-chinh-cap-xa-moi-102250704153652947.htm): kiểm tra riêng 34 tỉnh ở baseline 2025.
- [Cơ sở dữ liệu ngành Du lịch](https://csdl.vietnamtourism.gov.vn/): crawl theo bộ lọc tỉnh, thu được **440 hồ sơ**, không có lỗi crawl được ghi nhận. Sau ghép với hồ sơ cũ theo URL có 453 hồ sơ duy nhất; độ phủ giữa tỉnh vẫn không đều, chưa phải toàn bộ điểm đến Việt Nam.

Đã đối chiếu mã/tên của đủ **34 tỉnh + 3.321 đơn vị cấp xã hiện tại**, cập nhật **29 tên/cách ghi khác nguồn cộng đồng**. Ví dụ mã `07294` cập nhật tên hiện tại thành Phường Bố Hạ; bản năm 2025 vẫn giữ Xã Bố Hạ. Thay đổi không được áp ngược vào snapshot cũ.

Dữ liệu cũ 63 tỉnh, 696 huyện, 10.051 xã/phường và 10.618 liên kết chuyển đổi vẫn được giữ. Bảng mới bổ sung căn cứ tra cứu, chưa xác minh toàn văn mọi văn bản hoặc tự tạo timeline liên tục. Trường `source_verified` của evidence vẫn `false`, phân biệt đối chiếu trường nguồn với xác minh sự thật độc lập.

Nguồn thô, checksum, thời gian lấy và báo cáo nằm trong `DATN/data/raw/2026-10-24-refresh/`.

## 4. Huấn luyện và chỉ mục

- Huấn luyện lại hai pipeline TF-IDF từ/ký tự + Logistic Regression, với 3.402 câu thuộc hai miền và ba route.
- Xây lại KG, metadata SQLite và FAISS cho toàn bộ corpus mới.
- E5 vẫn dùng pretrained `intfloat/multilingual-e5-base`; đoạn thay đổi/mới được mã hóa, đoạn có text giữ nguyên được tái sử dụng vector với cấu hình encoder của seed. Hai lượt build mã hóa 4.056 và 262 chunk; chỉ mục cuối có 33.169 vector.
- Qwen3-0.6B tiếp tục dùng trọng số đã tải. **Không fine-tune trọng số E5 hoặc Qwen** trong đợt này.

Sửa hai lỗi phát hiện qua API thật: alias du lịch duy nhất được chuyển thành tên đầy đủ để tránh lẫn xã cùng tên; parser cho phép đúng một dấu chấm sau object JSON hợp lệ do Qwen nhỏ sinh ra. Không chấp nhận lời giải thích tùy ý, đối tượng JSON thứ hai hoặc claim ID không có; cross-check vẫn kiểm tra mệnh đề như trước.

## 5. Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Unit tests | **264/264** |
| KG gold hiện có | **17/17** |
| Router development set sau quy tắc | **26/26** |
| HTTP thực với E5/Qwen, mode full FAISS | **57/57** |
| Retrieval hai miền | 16 câu; Hit@1 **0,75**, known-positive Hit@5 **0,9375**, MRR@5 **0,828125** |
| Kiểm tra toàn bộ corpus/metadata | Không còn chủ đề bị loại theo bộ lọc; SQLite integrity `ok`; số vector khớp metadata |
| Giữ dữ liệu du lịch cũ | **202/202 ID** còn trong corpus mới |

Các tập trên là tập phát triển/kiểm thử của dự án, không phải benchmark độc lập về độ đúng pháp lý hoặc khả năng trả lời mọi câu hỏi. Một câu hỏi mã tỉnh ngắn chưa tìm được tài liệu dương bằng dense retrieval trong top-5; câu hỏi mã số nên đi qua KG, nhánh này đã được kiểm thử. Không lấy 57/57 để tuyên bố độ chính xác tổng quát 100%.

Báo cáo chi tiết trong release: [huấn luyện](../../artifacts/domain_refresh_2026-10-24/release/training_report.json), [HTTP cuối](../../artifacts/domain_refresh_2026-10-24/release/backend_evaluation_final.json), [retrieval](../../artifacts/domain_refresh_2026-10-24/release/retrieval_evaluation.json), [corpus](../../artifacts/domain_refresh_2026-10-24/release/corpus_refresh_report.json), [manifest](../../artifacts/domain_refresh_2026-10-24/release/release_manifest.json), [công bố](../../artifacts/domain_refresh_2026-10-24/release/publication_report.json).

## 6. Lưu ý về archive cũ

Một lượt lọc **hai file archive không hoạt động** đã dùng quy tắc bỏ dấu quá rộng, có thể loại nhầm một số câu du lịch/địa lý. Quy tắc này đã được sửa trước khi tạo corpus/model cuối; dữ liệu hoạt động gốc và toàn bộ 202 ID điểm đến cũ được kiểm tra riêng và vẫn giữ.

**Chưa phục hồi nguyên văn được phần archive đã thay đổi**; cần đối chiếu nguồn gốc trước khi dùng lại các archive cho công việc khác. Hai archive không được dùng để huấn luyện đợt này. Chi tiết: [cảnh báo archive](../../artifacts/maintenance/archive_scope_refresh_extended_2026-10-24.json). Script archive hiện yêu cầu thư mục backup trước khi sửa.

Bản dữ liệu/model hoạt động trước công bố được giữ riêng ở `DATN/artifacts/domain_refresh_2026-10-24/previous/` để rollback; đường đọc của API vẫn chỉ trỏ tới bộ dữ liệu/model hoạt động mới.

## 7. Các script của lượt cập nhật

`crawl_domain_refresh.py`, `crawl_official_admin_refresh.py`, `prepare_corpus_refresh.py`, `retrain_domain_refresh.py`, `refresh_vectors.py`, `evaluate_domain_retrieval.py`, `publish_domain_refresh.py` trong `SOURCE/scripts/`. Chọn raw/release mới cho lượt sau, kiểm tra mốc ngày và nguồn trước khi ghép; không chạy lại migration dọn dữ liệu ban đầu.
