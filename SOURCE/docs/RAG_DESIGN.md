# Thiết kế KG + RAG và sinh câu trả lời

> Theo code, prompt và artifacts ngày **25/10/2026**. Hệ thống dùng retrieval có định tuyến và sinh có kiểm soát bằng lựa chọn mệnh đề. Những kỹ thuật được ghi là đề xuất chưa có trong runtime hiện tại.
> Đợt cập nhật dữ liệu và huấn luyện lại: [DATA_REFRESH_2026-10-25.md](DATA_REFRESH_2026-10-25.md).

## 1. Mục tiêu và lựa chọn thiết kế

KG phù hợp cho mã đơn vị, quan hệ trực thuộc, liên kết chuyển đổi và snapshot theo ngày. RAG cung cấp phần mô tả điểm đến, lịch sử, văn hóa và văn bản nguồn. Router chọn một trong ba route `kg`, `rag`, `hybrid`; hai miền hoạt động là `administration`, `tourism`.

Tên “hybrid” mô tả phối hợp KG với RAG, không có nghĩa runtime đang áp dụng dense–sparse fusion trên mọi câu hỏi. Không có cross-encoder reranker trong nhánh FAISS đầy đủ.

## 2. Encoder và cấu hình chỉ mục

| Thuộc tính | Giá trị |
|---|---|
| Embedding model | `intfloat/multilingual-e5-base` |
| Revision tải bằng script | `d128750597153bb5987e10b1c3493a34e5a4502a` |
| Chiều vector hiện có | 768 |
| Chuẩn hóa | `normalize_embeddings=True`, float32 |
| Prefix | `query: ` / `passage: ` |
| Tiền xử lý | NFC, gộp khoảng trắng, mở rộng thuật ngữ mặc định bật |
| Chunk | 900 ký tự, overlap 150 |
| FAISS | `IndexIDMap2(IndexFlatIP)` |
| Corpus hiện có | 31.949 tài liệu, 33.169 vector |

Độ tương tự là `score(q,d) = qᵀd`; với vector chuẩn hóa L2, đây là cosine. Score đo độ tương tự biểu diễn, không phải xác suất đúng của tài liệu hay câu trả lời. Backend kiểm thử `HashingEncoder` có trong code để smoke test, không dùng làm embedding sản xuất hoặc so trực tiếp điểm với E5.

`index_config.json` lưu model và preprocessing của build. Retriever ưu tiên khôi phục cấu hình đó; device/batch có thể đổi lúc phục vụ nhưng model/chiều/cách mở rộng phải khớp chỉ mục. Runtime dùng tên model; muốn bảo đảm đúng revision cần quản lý cache và manifest, vì tên model đơn thuần chưa pin revision trong lời gọi `SentenceTransformer`.

## 3. Phân tích câu hỏi

1. Chuẩn hóa văn bản.
2. Dự đoán route và miền bằng hai pipeline TF-IDF + Logistic Regression.
3. Áp quy tắc cho câu hỏi dữ kiện, mô tả, tên/alias du lịch và mã đơn vị.
4. Tạo query plan: mẫu SPARQL, tham số, RAG domain/top_k, điều kiện thời gian/không gian và phạm vi.

Mã có số 0 đầu được giữ dạng chuỗi. Query SPARQL lấy từ các mẫu `.rq`, không do LLM tự viết. Câu hỏi đòi bán kính/khoảng cách, thời gian tương đối hoặc khoảng năm chưa có bằng chứng sẽ bị đánh dấu unsupported. Đường xử lý ngày cụ thể theo mã dùng `09_unit_at_time`; xem [ADMINISTRATIVE_DATA.md](ADMINISTRATIVE_DATA.md).

## 4. Retrieval và bộ lọc

### 4.1. Nhánh FAISS đầy đủ

`FaissRetriever.search` mã hóa query bằng E5, tìm inner product, rồi nối metadata SQLite theo ID. HTTP nhận `top_k` từ 1–20, mặc định 5; UI gửi 3. Hàm Python nội bộ hỗ trợ tối đa 100.

Bộ lọc được áp trước tìm vector bằng `faiss.IDSelectorBatch`:

```text
domain = miền cần tìm
AND (
    doc_id thuộc tập ID cho phép
    OR title/text chứa ít nhất một entity_term
)
```

Nếu không có bộ lọc thực thể thì chỉ lọc miền; nếu không lọc miền thì tìm toàn corpus. Tìm chuỗi thực thể dùng `casefold`, không phải hệ thống entity linking đầy đủ. Tập `doc_ids` tối đa 1.000, `entity_terms` tối đa 100 ở lớp retriever.

Với hybrid có KG, processor lấy `source_record_ids` và các tên thực thể/tỉnh từ KG làm phạm vi RAG. Với du lịch, tên đầy đủ/alias nhận diện được cũng được dùng để giới hạn ứng viên. Nếu không có provenance hoặc tên thích hợp, processor đưa cảnh báo và phạm vi có thể rộng hơn mong muốn.

### 4.2. Nhánh dự phòng khi thiếu file index

Nếu metadata có nhưng `vn.index` chưa có, `MetadataFaissRetriever` tạo SQLite FTS5 và lấy khoảng 48 ứng viên theo BM25 (ít nhất bằng top_k), mã hóa bằng E5 rồi tìm vector trên tập ứng viên. Cache vector trong bộ nhớ tối đa 4.096 mục.

Mode này được công bố là `lexical_candidates_faiss`. Có bước xếp hạng lại bằng vector trên tập ứng viên, nhưng không có cross-encoder. Phạm vi ứng viên có thể làm mất tài liệu mà nhánh full FAISS sẽ tìm thấy; cần đánh giá riêng hai mode.

### 4.3. Fallback

KG không có dòng có thể kích hoạt RAG fallback trong processor. Riêng truy vấn thời gian `09_unit_at_time` không fallback sang văn bản để tự xác nhận ngày. Dịch vụ trả lời còn từ chối mã đơn vị chưa được KG chứng thực, dù processor tìm được văn bản có nhắc mã.

## 5. Tạo minh chứng và mệnh đề ứng viên

`build_evidence` dùng mặc định `ANSWER_MAX_EVIDENCE=6`, `ANSWER_MIN_RAG_SCORE=0.70`.

- Khi có cả KG và RAG, KG chiếm tối đa `max(1, max_evidence // 2)` vị trí trước, phần còn lại dành cho RAG.
- KG được khử trùng theo nội dung dòng; mỗi dòng chọn tối đa năm trường được hỗ trợ và render thành một mệnh đề fact.
- Chunk RAG cần score hữu hạn và đạt ngưỡng. Trùng chunk bị loại.
- Mỗi chunk tạo tối đa ba câu trích xuất dài 20–420 ký tự; ưu tiên câu có nhiều từ giao với câu hỏi. Đây là heuristic lựa chọn câu, không phải model reranker.
- Mã minh chứng dạng `E01`; mã mệnh đề dạng `E01-C01`. Chỉ có ý nghĩa trong một lần trả lời.

Ngưỡng 0,70 là mặc định cấu hình, chưa phải ngưỡng tối ưu đã được xác lập trên benchmark độc lập. Tăng ngưỡng thường làm giảm số minh chứng; giảm ngưỡng có thể đưa thêm đoạn ít liên quan vào prompt.

## 6. Prompt và sinh câu trả lời

Prompt nằm ở `prompt_templates/system.txt` và `select_claims.txt`, được đọc bởi `prompts.build_messages`. Input user chứa câu hỏi dưới dạng chuỗi JSON và danh sách `{claim_id,text,kind}`; nội dung dữ liệu không được coi là chỉ thị thay đổi quy tắc.

Hợp đồng output của LLM:

```json
{"claim_ids": ["E01-C01", "E02-C01"]}
```

Chỉ được chọn 0–3 ID đã có, không lặp, không thêm khóa, không viết lại câu hoặc tạo dữ kiện. Nếu không có mệnh đề trả lời được câu hỏi, trả `{"claim_ids":[]}`.

LLM mặc định là Qwen3-0.6B, revision tải bằng script `c1899de289a04d12100db370d81485cdf75e47ca`. Runtime Transformers chọn thiết bị CUDA → MPS → CPU khi `LLM_DEVICE=auto`; sinh greedy (`do_sample=False`), tắt thinking trong chat template. Mặc định context 4.096 token, ngân sách sinh 384 token, timeout 60 giây.

Mô hình **không viết bài trả lời tự do** trong quy trình hiện tại. Backend dựng câu trả lời từ mệnh đề đã xác nhận và phần dẫn nguồn. Cách này giới hạn khả năng tổng hợp dài/diễn giải mới; đồng thời cho phép kiểm tra chặt nội dung xuất ra.

## 7. Cross-check và trích dẫn

1. Parse output JSON theo schema nghiêm ngặt: giới hạn kích thước, loại khóa trùng, giá trị không hữu hạn, schema/ID không hợp lệ. Chấp nhận lớp bọc Markdown fence hoặc đúng một dấu chấm cuối sau `}`; không chấp nhận lời giải thích hoặc một đối tượng JSON thứ hai. Tất cả mệnh đề vẫn phải qua kiểm tra ID và cross-check.
2. Truy vấn lại cùng kế hoạch KG sau khi LLM chọn; kiểm tra tập thực thể không thay đổi và lấy dữ kiện hiện tại để so sánh.
3. Với fact, so sánh từng trường và giá trị, bảo đảm câu đúng mẫu render từ KG.
4. Với extractive, kiểm tra câu là trích đoạn nguyên văn theo ranh giới câu; phát hiện một số xung đột mã/ngày với KG.
5. Với `09_unit_at_time`, kiểm tra lại ngày snapshot/khoảng hiệu lực và điều kiện tỉnh trên dữ kiện KG.
6. Loại mệnh đề không đạt; từ chối khi không còn mệnh đề hợp lệ. Nếu chỉ đáp ứng một phần thì trả `partial` và cảnh báo.

Citation giữ số thứ tự, ID minh chứng, loại nguồn, tiêu đề, URL đã kiểm tra định dạng và ID bản ghi nguồn. Không có kiểm chứng URL trực tuyến trong lúc trả lời, không có xác minh ngữ nghĩa mọi thông tin trong nguồn. Trạng thái cross-check `supported` nghĩa là khớp chứng cứ trong phạm vi `extractive_text_and_structured_kg_facts`.

## 8. Tình huống cần từ chối hoặc trả một phần

| Tình huống | Hành vi |
|---|---|
| Không có minh chứng qua ngưỡng | `abstained`, `no_eligible_evidence` |
| Mã chưa được KG xác nhận | `abstained`, `missing_verified_code` |
| Ngày không có snapshot | Không nội suy; từ chối nếu không có căn cứ thời gian |
| LLM chọn ID không có/schema sai | `abstained`, cross-check `invalid_output` |
| Tên khớp nhiều thực thể | `partial`, cảnh báo `ambiguous_entity` |
| Danh sách KG dài hơn phần được chọn | `partial`, `evidence_truncated`; không gọi là danh sách đầy đủ |
| Ngoài miền hỗ trợ | `abstained`, `out_of_scope` |

## 9. Đề xuất cải tiến và cách đo

Chỉ bổ sung reranker cross-encoder sau khi có gold corpus hai miền và đo Recall@k, MRR/nDCG, độ trễ, tỷ lệ từ chối và lỗi dẫn nguồn. Có thể thử chunk theo token/ngữ nghĩa, cải thiện entity linking, hợp nhất dense/sparse và lựa chọn evidence theo độ phủ câu hỏi. Các lựa chọn này chưa triển khai; không đưa chúng vào mô tả kết quả hiện tại.

Chi tiết phép đo, bộ câu hỏi và giới hạn báo cáo cũ: [EVALUATION.md](EVALUATION.md). Mã đối chiếu: [embedding.py](../src/vn_assistant/embedding.py), [router.py](../src/vn_assistant/router.py), [question_processing.py](../src/vn_assistant/question_processing.py), [evidence.py](../src/vn_assistant/evidence.py), [generation.py](../src/vn_assistant/generation.py), [cross_check.py](../src/vn_assistant/cross_check.py).
