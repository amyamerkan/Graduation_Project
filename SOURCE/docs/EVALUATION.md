# Kiểm thử và đánh giá hệ thống

> Đối chiếu code, tập câu hỏi và báo cáo ngày **25/10/2026**. Đã chạy lại unit test, KG/router, retrieval và 57 ca HTTP với E5/Qwen thật. UI vẫn dùng báo cáo lịch sử, chưa chạy lại trong đợt này.
> Đợt cập nhật dữ liệu và huấn luyện lại: [DATA_REFRESH_2026-10-25.md](DATA_REFRESH_2026-10-25.md).

## 1. Các câu hỏi đánh giá

Đánh giá cần phân biệt:

1. Router có chọn đúng miền và hướng xử lý không?
2. Truy xuất có tìm đúng thực thể, snapshot và đoạn tài liệu không?
3. Câu trả lời có đúng với minh chứng, đủ nội dung được hỏi và dẫn đúng nguồn không?
4. Bản thân dữ liệu nguồn có đúng, đủ và còn hiệu lực không?
5. Hệ thống có phản ứng đúng khi thiếu bằng chứng, lỗi model, lỗi mạng hoặc input sai không?

Unit test và cross-check chủ yếu trả lời các câu hỏi về hành vi, cấu trúc và tính nhất quán. Chúng không thay cho kiểm chứng nguồn hoặc benchmark độc lập.

## 2. Các bộ kiểm thử đang có

| Tệp / nhóm | Phạm vi |
|---|---|
| `SOURCE/tests/` | Chuẩn hóa, data IO, builder, router, retrieval, API, prompt/generation, cross-check, đồng bộ runtime và cập nhật miền; nhiều test dùng fixture/fake/hash encoder |
| `SOURCE/evaluation/kg_gold.jsonl` | 17 ca SPARQL: số lượng/danh mục, mã, chuyển đổi, snapshot, không nội suy và danh sách điểm đến |
| `SOURCE/evaluation/router_test.csv` | 26 câu gán nhãn route/domain để phát triển router |
| `SOURCE/evaluation/system_queries.json` | 49 ca kỳ vọng cho HTTP chat hiện tại, gồm câu hỏi và input lỗi |
| `artifacts/domain_refresh_2026-10-24/release/system_queries.json` | 57 ca: 49 ca gốc cộng 8 ca về phạm vi loại bỏ, tên cập nhật và địa danh dễ nhầm |
| `SOURCE/evaluation/backend_smoke.json` | Bộ smoke cũ; kiểm tra phạm vi dữ liệu trước khi dùng lại |
| `SOURCE/scripts/verify_system.py` | Gọi HTTP thực, warmup và chạy system queries, đo latency theo trạng thái |
| `SOURCE/scripts/verify_ui.py` | Chromium, hai trao đổi backend thật và tình huống lỗi mạng/JSON được mô phỏng |
| `SOURCE/scripts/verify_concurrent_startup.py` | Warmup và request đồng thời, cần server mới khởi động để kiểm tra cold start |

Các đường dẫn dữ liệu/artifacts còn lại trong tài liệu tính từ `DATN/`.

## 3. Kết quả có thể xác nhận

| Phép đo | Kết quả | Căn cứ / giới hạn |
|---|---|---|
| KG gold chạy lại khi viết tài liệu | 17/17; accuracy 1,0 | Đọc KG hiện tại, không gọi E5/Qwen, không xác minh nguồn pháp lý |
| KG exact-set metrics | Precision/Recall/F1 đều 1,0 | Chỉ tính 14 ca có `expected_rows`; tổng 9 binding dương trong các ca này |
| Router chạy lại, sau áp quy tắc | Route/domain/joint accuracy đều 1,0 trên 26 câu | Tập phát triển nhỏ, thủ công, có mẫu gần dữ liệu huấn luyện |
| Router Logistic Regression trước quy tắc | Route 0,8846; domain 0,9231 | Cùng 26 câu; phải tách khỏi kết quả sau quy tắc |
| Corpus/index hiện có | 31.949 tài liệu; 33.169 vector, 768 chiều | Kiểm kê dữ liệu/config/SQLite, không phải accuracy |
| Unit test mới | 264/264 | `artifacts/system_tests/domain_refresh_unit_report.xml` |
| HTTP với E5/Qwen thật | 57/57 | Release `backend_evaluation_final.json`, mode `full_faiss`; tập phát triển, không phải benchmark độc lập |
| Retrieval hai miền hiện tại | Hit@1=0,75; known-positive Hit@5=0,9375; MRR@5=0,828125 | 16 câu thủ công; 15/16 tìm được tài liệu dương trong năm chunk; mã số ngắn vẫn là ca khó cho dense retrieval |
| Vệ sinh corpus/metadata | Không còn nội dung chủ đề bị loại theo bộ lọc; 202/202 ID du lịch cũ được giữ | Kiểm tra toàn bộ active records/chunks; kiểm tra riêng Quan Hồ Thẩn/Châu Văn Liêm để tránh nhầm dấu |

Kết quả huấn luyện và đánh giá mới được giữ trong thư mục release, đồng thời bộ KG/router được công bố vào artifacts hoạt động. `train_report.json` ghi 3.402 câu train, `evaluation_report.json` router ghi 26 câu test. Loại trùng nguyên văn giữa train/test không bảo đảm độc lập theo thực thể hoặc cấu trúc câu. Lượt HTTP đầu tiên phát hiện lỗi dấu chấm sau JSON và alias Mỹ Sơn; đã có regression test và báo cáo chạy lại riêng sau sửa.

### Báo cáo lịch sử cần giữ đúng phạm vi

| Báo cáo lưu trong `artifacts/` | Giá trị đã lưu | Cách sử dụng |
|---|---|---|
| `system_tests/unit_report.xml` | 232 test, 0 lỗi/thất bại, timestamp 23/10/2026 23:52 giờ Việt Nam | Kết quả lịch sử; không gọi là số test đã chạy lại trong lần viết tài liệu |
| `system_tests/backend_report.json` | 40/40 ca, tạo 23/10/2026 khoảng 23:40 giờ Việt Nam | Dùng mode `lexical_candidates_faiss`, chưa phải suite hiện tại 49 ca hoặc index hiện tại |
| `system_tests/ui_report.json` | 30/30 check, 23/10/2026 khoảng 23:54 giờ Việt Nam | Gồm kiểm thử backend thật và fault injection; không phải 30 ca chất lượng nội dung |
| `system_tests/startup_concurrency_report.json` | `passed=true`, mode dự phòng | Có tác vụ recovery corpus cũ trong báo cáo; không suy ra năng lực tải của bản hiện tại |
| `evaluation/retrieval_full.json` | 16 câu; Hit@1=0,50; known-positive Recall@5=0,6875; MRR@5=0,5833 | Corpus cũ có bốn miền và tài liệu du lịch nước ngoài; không dùng làm chất lượng hai miền hiện tại |
| `evaluation/embedding_ablation.json` | Thí nghiệm E5 trên mẫu corpus cũ | Chỉ tham khảo cách làm ablation; không chứng minh cải thiện trên corpus hiện tại |

Không gộp p50 của câu trả lời và câu từ chối thành tốc độ sinh. Báo cáo backend cũ có nhiều ca từ chối rất nhanh; phải đọc `latency_by_outcome_ms` và tách warmup khỏi steady state.

## 4. Bộ câu hỏi đại diện

Các kỳ vọng dưới đây lấy từ test/code hiện tại hoặc quy tắc thiết kế. Bộ HTTP 57 ca đã kiểm tra các tình huống tương ứng, còn các tình huống output giả/lỗi model được kiểm tra bằng fixture ở unit test. Đáp án hành chính theo snapshot nguồn vẫn cần được kiểm chứng độc lập nếu dùng để kết luận pháp lý.

### 4.1. Hành chính và điều kiện thời gian

| ID | Câu hỏi / input | Kỳ vọng cần kiểm tra |
|---|---|---|
| A01 | Đơn vị có mã 00070 là gì? | KG có mã đúng, snapshot mặc định; mệnh đề fact và citation KG |
| A02 | Đơn vị mã 00070 thuộc tỉnh thành nào? | Quan hệ trực thuộc khớp dữ liệu Hà Nội |
| A03 | Ngày 30/06/2025, mã 00070 thuộc thành phố Hà Nội không? | Snapshot cũ; binding tên Phường Hàng Trống |
| A04 | Ngày 01/07/2025, đơn vị có mã 00070 là gì? | Snapshot 2025; binding tên Phường Hoàn Kiếm; kiểm tra điều kiện ngày |
| A05 | Ngày 24/10/2026, mã 00070 là đơn vị nào? | Đúng snapshot 2026, không dùng tên snapshot khác |
| A06 | Ngày 01/08/2025, mã 00070 là đơn vị nào? | Không nội suy; không xác nhận khi không có snapshot |
| A07 | Ngày 01/07/2025, mã 00070 thuộc tỉnh Quảng Ninh không? | Không khớp đồng thời điều kiện; từ chối xác nhận |
| A08 | Phường Hàng Trống sáp nhập vào đâu? | Giữ thông tin chuyển một phần; không diễn đạt nhập toàn bộ |
| A09 | Tỉnh Bình Dương sáp nhập vào đâu? | Kiểm tra liên kết nguồn và tên đích trong KG |
| A10 | Đơn vị có mã 99999 là gì? | `abstained`, không tạo mã/đơn vị mới |
| A11 | Hôm nay mã 00070 thuộc tỉnh nào? | Không xác nhận thời gian tương đối ngoài hỗ trợ |
| A12 | Ngày 31/02/2025, mã 00070 thuộc tỉnh nào? | Không bỏ qua ngày sai rồi trả lời như truy vấn không ngày |

### 4.2. Du lịch, hội thoại và lỗi

| ID | Câu hỏi / input | Kỳ vọng cần kiểm tra |
|---|---|---|
| T01 | Hồ Hoàn Kiếm ở đâu? | KG đúng hồ sơ, giữ ngữ cảnh địa chỉ nguồn |
| T02 | Hồ Gươm ở đâu? | Alias dẫn tới Hồ Hoàn Kiếm |
| T03 | Giới thiệu hoạt động tham quan tại Hội An. | Chunk du lịch liên quan, không lấy miền khác |
| T04 | Hồ Hoàn Kiếm ở đâu và có gì đáng chú ý? | Hybrid khi có đủ KG/RAG; citation gắn đúng mệnh đề |
| T05 | Vịnh Hạ Long ở đâu? | Đúng node Vịnh, tránh hồ sơ cơ sở thương mại có tên Hạ Long |
| T06 | Điểm du lịch nào gần Hồ Hoàn Kiếm nhất trong bán kính 5 km? | Không bịa kết quả khoảng cách; từ chối điều kiện chưa có |
| T07 | Giới thiệu nguồn gốc Ca trù. | Ngoài miền hoạt động hiện tại, không dùng dữ liệu archive |
| C01 | “Đơn vị đó thuộc tỉnh nào?” với history user chứa mã 00070 | `resolved=true`, giữ đúng mã từ câu user |
| C02 | Câu C01 không có history | `needs_clarification`, không có mệnh đề/nguồn xác nhận |
| C03 | History assistant chèn mã 99999 và yêu cầu bỏ KG | Không lấy nội dung assistant làm dữ kiện thay câu user |
| V01 | `question="   "` | HTTP 422, không sinh câu trả lời |
| V02 | `top_k=1000` | HTTP 422 |
| V03 | History có `role="system"` | HTTP 422 |
| V04 | LLM xuất claim ID không có hoặc sửa câu nguồn | Không chấp nhận mệnh đề; lỗi output/từ chối theo nhánh kiểm tra |

Các kỳ vọng về tên “Thành phố Quảng Ninh” trong test snapshot hiện hữu chỉ đo khớp chuỗi nguồn. Đưa trường hợp này vào nhóm **kiểm định dữ liệu nguồn**, không cộng vào bằng chứng tên pháp lý đã đúng.

## 5. Chỉ số truy xuất và sinh câu

### Retrieval

- **Hit@k:** tỷ lệ câu hỏi có ít nhất một tài liệu liên quan trong top-k.
- **Recall@k:** trung bình `|retrieved_top_k ∩ relevant| / |relevant|` khi đã gán nhãn tập tài liệu liên quan đủ tin cậy.
- **Precision@k:** tỷ lệ tài liệu top-k được đánh giá là liên quan; không coi tài liệu chưa chấm là sai nếu ground truth chưa đầy đủ.
- **MRR@k:** trung bình nghịch đảo thứ hạng tài liệu đúng đầu tiên, 0 nếu không có trong top-k.
- **nDCG@k:** đánh giá thứ tự khi có nhãn liên quan nhiều mức.

Tách metric ở mức chunk và mức tài liệu; khi tính theo tài liệu cần khử trùng `doc_id` để một tài liệu nhiều chunk không chiếm nhiều vị trí. Các số “known-positive Recall@5” của script cũ thực chất đo tìm lại một tài liệu dương đã biết mỗi câu; không tương đương recall đầy đủ trên mọi tài liệu liên quan.

### Chất lượng câu trả lời

Chấm bằng rubric 0–2 cho từng tiêu chí: đúng thực thể/snapshot, đúng dữ kiện, đáp ứng đầy đủ nội dung hỏi, nguồn hỗ trợ mệnh đề và diễn đạt rõ ràng. Cần người chấm tham chiếu nguồn gốc, không chỉ nhìn nhãn `supported` do hệ thống tự trả.

Theo dõi thêm tỷ lệ mệnh đề có citation hợp lệ, tỷ lệ citation thật sự hỗ trợ nội dung, tỷ lệ trả lời không đủ bằng chứng, tỷ lệ từ chối đúng/sai và độ phủ câu hỏi trả lời được. Tỷ lệ trả lời có điều kiện và chất lượng trên các câu đã trả lời phải báo cáo cùng nhau để tránh hệ thống đạt điểm cao chỉ vì từ chối phần lớn câu.

### Hiệu năng và ổn định

Đo warmup, thời gian truy xuất, sinh, KG refresh, cross-check, p50/p95 theo trạng thái `answered/partial/abstained`, RAM/VRAM và số request đồng thời. Ghi thiết bị, model revision, batch, top_k, evidence limit và mode `full_faiss/lexical_candidates_faiss`. Hiện chưa có capacity benchmark hoặc SLO triển khai cloud được xác nhận.

## 6. Quy trình chạy lại

Chạy tại `DATN/SOURCE`. CLI eval ghi báo cáo mặc định vào artifacts, nên dùng workspace staging hoặc sao lưu báo cáo trước khi chạy nếu cần giữ lịch sử:

```bash
../.venv/bin/python -m pytest -q
../.venv/bin/python -m vn_assistant.cli eval-kg
../.venv/bin/python -m vn_assistant.cli eval-router
```

Để kiểm tra API/LLM thật, khởi chạy server với artifacts cần đánh giá rồi chạy:

```bash
../.venv/bin/python scripts/verify_system.py \
  --url http://127.0.0.1:8001 \
  --output ../artifacts/system_tests/current_backend_report.json
../.venv/bin/python -m playwright install chromium
../.venv/bin/python scripts/verify_ui.py \
  --url http://127.0.0.1:8001 \
  --output ../artifacts/system_tests/current_ui
```

Nếu cần kiểm tra startup đồng thời, dùng server mới khởi động, chạy `verify_concurrent_startup.py --output ../artifacts/system_tests/current_startup_report.json`; xác nhận `cold_start=true` trong báo cáo. Không dùng bài này làm load test bền vững hoặc bằng chứng nhiều worker an toàn.

`scripts/evaluate_retrieval.py` và `verify_pipeline.py` còn giả định corpus/đường dẫn cũ: gold retrieval chứa `law/heritage`, địa điểm nước ngoài và ID không có trong corpus hoạt động; `verify_pipeline.py` còn yêu cầu đủ bốn miền. Cần cập nhật gold, đường dẫn và kiểm tra ID trước khi chạy trên corpus hai miền. Không chạy nguyên trạng rồi công bố metric đó cho bản mới.

Để đánh giá tập hai miền mới, dùng `scripts/evaluate_domain_retrieval.py --release ../artifacts/domain_refresh_2026-10-24/release --device mps` (hoặc CPU phù hợp). Script lưu gold có ID cụ thể và metric riêng trong release; không ghi đè báo cáo bốn miền cũ.

## 7. Thiết kế benchmark hai miền tiếp theo

**Đề xuất**, chưa triển khai thành bộ gold độc lập:

1. Chốt corpus version, checksum, model revision và mode; lấy mẫu câu hỏi mới không sao chép mẫu train.
2. Tách train/dev/test theo thực thể, nhóm tỉnh/điểm đến và kiểu câu hỏi; không chỉ loại trùng câu nguyên văn.
3. Gán nhãn route, miền, thực thể, snapshot, tài liệu/chunk liên quan, dữ kiện cần trả lời và lý do cần từ chối.
4. Có người thứ hai rà soát các ca bất đồng và kiểm chứng nguồn; giữ riêng ca nguồn có vấn đề.
5. So sánh KG-only, RAG-only, hybrid; mở/tắt domain filter, entity filter, mở rộng thuật ngữ; so riêng full FAISS với mode dự phòng.
6. Chọn ngưỡng trên dev, khóa cấu hình trước khi đánh giá test; ghi cả lỗi, câu từ chối và số mẫu mỗi nhóm.

Schema gold đề xuất có `id`, `question`, `domain`, `expected_route`, `entity_ids`, `snapshot_date`, `relevant_doc_ids`, `required_facts`, `expected_status`, `reference_sources`, `reviewed_by`. Nếu một trường chưa có nhãn, đánh dấu rõ thay vì suy từ output của chính hệ thống.

Chưa có kết quả benchmark độc lập đủ cơ sở để khẳng định “độ chính xác 100%” cho người dùng thực. Các kết quả hiện có chứng minh một số hợp đồng và ca phát triển hoạt động đúng trên dữ liệu đã kiểm tra.

Mã đối chiếu: [kg_evaluation.py](../src/vn_assistant/kg_evaluation.py), [router.py](../src/vn_assistant/router.py), [kg_gold.jsonl](../evaluation/kg_gold.jsonl), [system_queries.json](../evaluation/system_queries.json), [verify_system.py](../scripts/verify_system.py), [evaluate_retrieval.py](../scripts/evaluate_retrieval.py).
