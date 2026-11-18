# Kết quả thực nghiệm đã có

## D1 silver test

| Phương pháp | Hit@1 | Hit@5 | MRR@10 | nDCG@10 | Từ chối đúng |
|---|---|---|---|---|---|
| TF-IDF | 0.2128 | 0.6968 | 0.4264 | 0.4992 | 0.0000 |
| BM25 | 0.2553 | 0.5213 | 0.3769 | 0.4154 | 0.0000 |
| E5 | 0.5798 | 0.6596 | 0.6181 | 0.5865 | 0.0000 |
| RRF | 0.5160 | 0.7553 | 0.6127 | 0.6039 | 0.0000 |
| RRF + miền | 0.5160 | 0.7553 | 0.6127 | 0.6042 | 0.0000 |
| RRF + miền + tỉnh | 0.5904 | 0.7926 | 0.6669 | 0.6985 | 0.0000 |
| Lai mã/ngày/tỉnh | 0.8936 | 0.9840 | 0.9297 | 0.9402 | 1.0000 |

## Câu hỏi cũ

| Phương pháp | D0 MRR@10 | D1 MRR@10 |
|---|---|---|
| TF-IDF | 0.4413 | 0.4669 |
| BM25 | 0.4047 | 0.3832 |
| E5 | 0.3275 | 0.3208 |
| RRF | 0.4053 | 0.4442 |
| RRF + miền | 0.4053 | 0.4442 |
| RRF + miền + tỉnh | 0.4053 | 0.4442 |
| Lai mã/ngày/tỉnh | 0.9668 | 0.9536 |

## Bộ thủ công giữ riêng

| Phương pháp | D0 MRR@10 | D1 MRR@10 |
|---|---|---|
| TF-IDF | 0.4881 | 0.4887 |
| BM25 | 0.7903 | 0.7917 |
| E5 | 0.8281 | 0.7266 |
| RRF | 0.8958 | 0.8854 |
| RRF + miền | 0.8958 | 0.8854 |
| RRF + miền + tỉnh | 0.8958 | 0.8854 |
| Lai mã/ngày/tỉnh | 0.8125 | 0.8125 |

## Kết luận được phép

Tổ hợp mã/ngày/tỉnh có lợi trên bộ silver hiện tại; E5 tốt hơn ở một số nhóm mô tả; RRF thường tốt hơn tổ hợp trên 16 câu thủ công. Dữ liệu mới tăng độ phủ nhưng một số điểm câu cũ giảm. Không chứng minh một phương pháp thắng tổng quát, không có điểm QA factual accuracy 90–98% và không có benchmark ngoài độc lập.

Router mới: 5.598 câu train, route/joint 25/26 sau quy tắc và domain 26/26; raw route 23/26, raw domain 24/26. KG: 17/17 development; 14 ca expected_rows chỉ có 9 binding dương. Unit kiểm tra lại ngày 18/11: 353/353. HTTP D0 lịch sử: 65/65; UI D0 lịch sử: 33/33. D1 được chạy riêng ngày 18/11, cũng đạt 65/65 HTTP và 33/33 UI. Đây là hai lần chạy có artifact riêng, không chuyển nhãn bằng chứng D0 thành D1. Xem [nghiệm thu D1](11_NGHIEM_THU_D1.md).

## Kết quả chưa có

Faithfulness và Context Relevancy độc lập; factuality câu trả lời theo người chấm; so sánh bật/tắt cross-check; sweep prompt/siêu tham số; benchmark GS-QA/MapQA/Tourism QA; tải đồng thời và cloud/GPU tương đương kế hoạch. Không điền các mục này bằng điểm ước tính.
