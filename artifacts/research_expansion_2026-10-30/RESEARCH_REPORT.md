# Dữ liệu và thực nghiệm sơ bộ — mở rộng 30–31/10/2026

Bản nghiên cứu riêng, chưa thay bộ dữ liệu của ứng dụng. Các số dưới đây đọc trực tiếp từ JSON kết quả.

## 1. Đối chiếu ba yêu cầu giảng viên

| Yêu cầu | Hiện thực và bằng chứng |
|---|---|
| (1) Dữ liệu/phương pháp có sẵn, kết quả sơ bộ | D0: corpus dự án trước mở rộng; TF-IDF, BM25, E5, RRF; bảng kết quả D0 bên dưới. Danh mục cộng đồng vietnam-provinces là nguồn công khai đã có, không phải dữ liệu do tác giả tự điều tra. |
| (2) Xây dựng dữ liệu mới và thử nhiều phương pháp | D1: D0 + đoạn sắp xếp từ Chính phủ + điểm du lịch mới + quan sát bảng đối chiếu có ngày; cùng bảy cấu hình và cùng câu hỏi trên D0/D1. |
| (3) Đề xuất lai và thực nghiệm | Tách miền, ánh xạ tên tỉnh cũ/mới, điều kiện mã/ngày rồi RRF; có ablation bỏ điều kiện thời gian/tỉnh, dữ liệu cũ/mới, và bootstrap theo nhóm thực thể. Đây là đóng góp tích hợp cho bài toán; chưa chứng minh thuật toán mới trên thế giới. |

## 2. Kiểm kê dữ liệu

- D0: **31,949** tài liệu. D1: **38,993** tài liệu.
- Thêm **3,351** đoạn hành chính sau loại **2,757** bản trùng dấu câu/số thứ tự; nguyên văn được giữ, gộp URL nguồn bổ sung.
- Thêm **372** điểm tham quan/trải nghiệm; tổng **825** điểm, phủ **34** tỉnh/thành theo bộ lọc nguồn.
- Thêm **3,321** dòng quan sát bảng NSO tại 30/10/2026; đây không phải 3.321 sự kiện thay đổi mới.
- Snapshot nền: 30/06/2025, 01/07/2025, 24/10/2026. Quan sát 30/10/2026 được giữ riêng, không suy ra khoảng hiệu lực liên tục.
- Địa chỉ du lịch giữ đúng câu nguồn, có thể còn huyện/tỉnh cũ; không tự gán xã mới. Chuyển một phần địa bàn không được coi là nhập toàn bộ.
- Giữ toàn bộ ID/nội dung D0; không sửa archives. Bản raw và manifest SHA256 ở `data/raw/2026-10-30-research/`.

## 3. Thiết kế thực nghiệm

- **263 câu silver** sinh từ khóa/mã/ngày/tên điểm và đoạn nguồn; chia dev/test theo nhóm thực thể bằng SHA256. Các snapshot cùng mã không đi sang hai split.
- Giữ riêng 16 câu phát triển thủ công từ đợt trước; không gọi đó là benchmark độc lập. Dữ liệu đã có trong dự án không đồng nghĩa bộ test chuẩn công khai.
- Query encoder E5 pretrained, không fine-tune. BM25 dùng k1=1.2, b=0.75; RRF k=60; tối đa 200 chunk ứng viên mỗi nguồn, gộp thành tài liệu rồi đánh giá top 10.
- Baseline cùng corpus/chunk; các bước ràng buộc là ablation riêng. Điều kiện chỉ trích từ câu hỏi và metadata, không đọc nhãn đáp án.
- Bộ phân miền của D0 được đóng băng và dùng chung trên D0/D1 để tách tác động corpus; router train lại của D1 được đánh giá riêng.
- D0/D1 chạy cùng tập câu; D0 thiếu tài liệu mới nên cần đọc thêm bảng “câu hỏi cũ” để tách tác động phủ dữ liệu khỏi năng lực thuật toán.
- Hit@k/MRR/nDCG là truy xuất theo nhãn dương đã biết, không phải độ đúng câu trả lời cuối. Query tỉnh có nhiều đáp án nên đọc thêm known-positive Recall@10 trong JSON.
- Ca thiếu snapshot đo tỷ lệ từ chối. Baseline tìm kiếm thường luôn trả kết quả nên chưa có cơ chế từ chối; đây là so sánh thêm chính sách an toàn, không chỉ xếp hạng.
- `ranking_ms` đo cả pipeline các ranker cùng lúc, bỏ thời gian mã hóa query; không dùng để tuyên bố phương pháp nào nhanh hơn.

## 4. Kết quả existing — silver test

| Phương pháp | Hit@1 | Hit@5 | MRR@10 | nDCG@10 | Từ chối đúng ca thiếu ngày |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0.0851 | 0.4415 | 0.2524 | 0.3022 | 0.0000 |
| BM25 | 0.1862 | 0.3085 | 0.2459 | 0.2468 | 0.0000 |
| E5 | 0.2926 | 0.3298 | 0.3106 | 0.2658 | 0.0000 |
| BM25 + E5 / RRF | 0.2500 | 0.3883 | 0.3063 | 0.2882 | 0.0000 |
| RRF + miền | 0.2500 | 0.3883 | 0.3063 | 0.2882 | 0.0000 |
| RRF + miền + tỉnh | 0.3191 | 0.4309 | 0.3634 | 0.3824 | 0.0000 |
| Đề xuất: RRF + mã/ngày/tỉnh | 0.6436 | 0.6702 | 0.6531 | 0.6491 | 1.0000 |

Độ phủ đầy đủ nhãn dương: 56.22%. Câu test có đáp án: 188; không có snapshot: 23.

## 4. Kết quả expanded — silver test

| Phương pháp | Hit@1 | Hit@5 | MRR@10 | nDCG@10 | Từ chối đúng ca thiếu ngày |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0.2128 | 0.6968 | 0.4264 | 0.4992 | 0.0000 |
| BM25 | 0.2553 | 0.5213 | 0.3769 | 0.4154 | 0.0000 |
| E5 | 0.5798 | 0.6596 | 0.6181 | 0.5865 | 0.0000 |
| BM25 + E5 / RRF | 0.5160 | 0.7553 | 0.6127 | 0.6039 | 0.0000 |
| RRF + miền | 0.5160 | 0.7553 | 0.6127 | 0.6042 | 0.0000 |
| RRF + miền + tỉnh | 0.5904 | 0.7926 | 0.6669 | 0.6985 | 0.0000 |
| Đề xuất: RRF + mã/ngày/tỉnh | 0.8936 | 0.9840 | 0.9297 | 0.9402 | 1.0000 |

Độ phủ đầy đủ nhãn dương: 100.00%. Câu test có đáp án: 188; không có snapshot: 23.

## 5. Chỉ các câu hỏi đã có trước mở rộng — silver test

| Phương pháp | D0 MRR@10 | D1 MRR@10 |
|---|---:|---:|
| TF-IDF | 0.4413 | 0.4669 |
| BM25 | 0.4047 | 0.3832 |
| E5 | 0.3275 | 0.3208 |
| BM25 + E5 / RRF | 0.4053 | 0.4442 |
| RRF + miền | 0.4053 | 0.4442 |
| RRF + miền + tỉnh | 0.4053 | 0.4442 |
| Đề xuất: RRF + mã/ngày/tỉnh | 0.9668 | 0.9536 |

## 6. Bộ phát triển thủ công trước đó — tách khỏi silver

| Phương pháp | D0 MRR@10 | D1 MRR@10 |
|---|---:|---:|
| TF-IDF | 0.4881 | 0.4887 |
| BM25 | 0.7903 | 0.7917 |
| E5 | 0.8281 | 0.7266 |
| BM25 + E5 / RRF | 0.8958 | 0.8854 |
| RRF + miền | 0.8958 | 0.8854 |
| RRF + miền + tỉnh | 0.8958 | 0.8854 |
| Đề xuất: RRF + mã/ngày/tỉnh | 0.8125 | 0.8125 |

### Kết quả D1 theo loại câu — tránh che lỗi bằng điểm tổng

| Phương pháp | Mã/ngày MRR | Điểm đến MRR | Đoạn sắp xếp MRR | Theo tỉnh nDCG |
|---|---:|---:|---:|---:|
| TF-IDF | 0.4049 | 0.6502 | 0.3109 | 0.0622 |
| BM25 | 0.3622 | 0.5323 | 0.2887 | 0.0980 |
| E5 | 0.0524 | 0.9542 | 0.9667 | 0.6184 |
| BM25 + E5 / RRF | 0.2838 | 0.8750 | 0.7650 | 0.3858 |
| RRF + miền | 0.2838 | 0.8750 | 0.7650 | 0.3880 |
| RRF + miền + tỉnh | 0.2838 | 0.8972 | 0.7650 | 0.9639 |
| Đề xuất: RRF + mã/ngày/tỉnh | 1.0000 | 0.8972 | 0.7650 | 0.9639 |

### Huấn luyện router và kiểm tra KG

Router TF-IDF/Logistic Regression train lại với 5598 câu; tập phát triển 26 câu có joint accuracy sau quy tắc 0.9615. Đây là tập nhỏ đã dùng phát triển, không phải test kín.
KG development accuracy: 1.0000; legal passages mới là minh chứng văn bản, không tự chuyển thành cạnh sáp nhập suy diễn. E5 chỉ tạo embedding; không fine-tune E5/Qwen.

Router D0 chạy lại với cùng code/quy tắc hiện tại: joint accuracy 0.9615. Một nhãn cũ kỳ vọng hybrid cho câu hỏi vừa có mã/ngày vừa yêu cầu mô tả; quy tắc tra mã hiện ưu tiên kg và trả phần chưa đủ mô tả là partial. Giữ nguyên điểm/nhãn gốc trong báo cáo, không sửa gold để tăng accuracy.

### Diễn giải kết quả sơ bộ

- Ràng buộc mã/ngày có lợi thế rõ trên câu hỏi mã chính xác; đây là lợi ích của tra cứu cấu trúc kết hợp IR, không chứng minh embedding được cải thiện.
- E5 riêng tốt hơn RRF/đề xuất trên nhóm mô tả điểm đến và đoạn sắp xếp trong lượt đo này. Không nên thay mọi truy vấn ngữ nghĩa bằng cùng một công thức lai chỉ vì điểm tổng tốt.
- Trên 16 câu thủ công, RRF thường tốt hơn đề xuất có ràng buộc. Đây là phản chứng cần giữ và phân tích trước khi áp dụng rộng.
- Điểm tổng D1 tăng một phần vì D0 chưa có tài liệu mới. Ở nhóm câu cũ, một số phương pháp giảm điểm sau mở rộng; bổ sung dữ liệu không bảo đảm chất lượng tăng ở mọi câu.
- Nhãn dương đã biết chưa bao phủ mọi nguồn mới tương đương; ví dụ hai quan sát NSO cùng mã có thể đều phù hợp câu không hỏi ngày. Vì vậy cần duyệt nguồn trong CSV trước khi diễn giải một thứ hạng sai là sai nội dung.
- Không chọn lại trọng số/cấu hình sau khi xem test trong đợt này. Bước tiếp theo là phát triển trên dev, rồi dùng tập test kín mới do người duyệt gán nhãn.


## 7. Độ bất định và giới hạn

- Đề xuất trừ BM25, ΔMRR=0.5528; khoảng percentile 95% [0.5055, 0.5918], bootstrap 1.000 lần theo 142 nhóm thực thể.
- Đề xuất trừ E5, ΔMRR=0.3116; khoảng percentile 95% [0.2026, 0.4134], bootstrap 1.000 lần theo 142 nhóm thực thể.
- Đề xuất trừ BM25 + E5 / RRF, ΔMRR=0.3170; khoảng percentile 95% [0.2430, 0.3918], bootstrap 1.000 lần theo 142 nhóm thực thể.

- Kết quả silver có thể ưu ái tra mã chính xác, tên điểm và mẫu câu; không suy rộng thành accuracy thực tế hay kết luận đề xuất tốt hơn mọi phương pháp.
- Cần người gán nhãn/duyệt độc lập file `annotation_review.csv`, bổ sung câu hỏi tự nhiên, tên trùng, ngày ngoài snapshot, địa chỉ thiếu cấp, chuyển một phần; giữ test kín trước khi điều chỉnh tham số.
- Chưa thực nghiệm sinh câu trả lời dài, factuality thủ công, reranker cross-encoder, GIS/polygon hoặc một benchmark công khai độc lập như BEIR. Không báo các việc này là đã làm.

## 8. Nguồn và công trình liên quan

- [Bảng đối chiếu NSO](https://danhmuchanhchinh.nso.gov.vn/Doi_Chieu_Moi.aspx): nguồn hành chính chính thức; lưu ngày quan sát và ngày cột đối chiếu, chưa độc lập xác minh từng văn bản hiệu lực.
- [Tổng hợp đơn vị cấp xã và liên kết toàn văn nghị quyết](https://xaydungchinhsach.chinhphu.vn/danh-sach-3321-don-vi-hanh-chinh-cap-xa-tai-34-tinh-thanh-sau-sap-xep-sap-nhap-119250710102358656.htm): trích đoạn nguyên văn, giữ URL và phần chuyển một phần.
- [CSDL ngành Du lịch](https://csdl.vietnamtourism.gov.vn/dest/): truy vấn theo tỉnh, phân trang và URL chi tiết; thời gian địa chỉ có thể khác danh mục hành chính mới.
- [vietnam-provinces 2026.9.0](https://pypi.org/project/vietnam-provinces/2026.9.0/): nguồn cộng đồng của dữ liệu nền, cần tuân thủ giấy phép GPL-3.0-or-later khi phân phối theo điều kiện áp dụng.
- [Multilingual E5, Wang et al.](https://arxiv.org/abs/2402.05672): nền tảng embedding được sử dụng.
- [RRF, Cormack et al., SIGIR 2009](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf): phép gộp hạng có sẵn, không phải phần mới do đồ án phát minh.
- [BEIR, Thakur et al.](https://arxiv.org/abs/2104.08663): tham khảo thiết kế so sánh lexical/dense và đánh giá đa bộ dữ liệu; chưa chạy BEIR trong đợt này.
- Truy cập công khai không tự động đồng nghĩa mọi bài viết/ảnh có giấy phép mở. Manifest lưu nguồn để truy nguyên; đợt này không thu ảnh.

## 9. Tái lập

Chạy từ `DATN/SOURCE`; dùng môi trường `.venv` và trọng số E5 đã tải. Các lệnh ghi vào release riêng:

```bash
../.venv/bin/python scripts/collect_research_expansion.py --output ../artifacts/research_expansion_2026-10-30 --tourism-pages 4
../.venv/bin/python scripts/finalize_research_corpus.py --release ../artifacts/research_expansion_2026-10-30
../.venv/bin/python scripts/retrain_domain_refresh.py --release ../artifacts/research_expansion_2026-10-30
../.venv/bin/python scripts/refresh_vectors.py --dataset ../artifacts/research_expansion_2026-10-30/data/rag_dataset_final.jsonl --seed ../artifacts/faiss --output ../artifacts/research_expansion_2026-10-30/artifacts/faiss --device mps
../.venv/bin/python scripts/run_research_experiments.py --release ../artifacts/research_expansion_2026-10-30 --device mps
```

Thư mục FAISS output phải chưa có index khi rebuild; chọn phiên bản/thư mục mới để chạy lại. Không tự đè artifacts đang dùng. Các raw đã cache được tái sử dụng và manifest ghi `cached`; không coi đó là lần tải mới trên mạng.
