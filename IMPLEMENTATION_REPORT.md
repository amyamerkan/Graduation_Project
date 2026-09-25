# Báo cáo triển khai kỹ thuật

## Phạm vi đã thực hiện

| Phase | Kết quả |
|---|---|
| KG Phase 1 | Ontology OWL/RDF, bộ trích xuất entity/relation, RDF Turtle, RDF/XML OWL, CSV import Neo4j |
| KG Phase 2 | 8 SPARQL template có tham số, service truy vấn, gold test và report Precision/Recall/F1 |
| RAG Vectorization | Adapter dữ liệu streaming, cleaning, chunking, multilingual E5, query/passage prefix và chuẩn hóa vector |
| FAISS & Indexing | Index cosine, incremental batching, SQLite metadata, domain filter và top-k API |
| Question Processing | TF-IDF word/char + Logistic Regression, rule precision layer, route/domain confidence và KG/RAG fallback |

## Kết quả chạy trên file được đính kèm

File thực tế: `vn_complete_dataset.json`, 81.090 records.

### Knowledge Graph ban đầu

- Nodes: **14.094**
- Relationships: **56.316**
- Province nodes hiện tại/lịch sử: **63**
- Ward nodes hiện hành: **3.321**
- District nodes lịch sử: **696**
- Đơn vị lịch sử: **10.014**
- `LOCATED_IN`: **35.122**
- `MERGED_INTO`: **10.597**
- `REPLACED_BY`: **10.597**

Số province node lớn hơn 34 vì KG lưu đồng thời tên đơn vị hiện tại và lịch sử. Các mốc hiệu lực được biểu diễn bằng `validFrom`/`validTo`.

### SPARQL evaluation

- Gold cases: **4/4 pass**
- Accuracy: **1.0000**
- Precision: **1.0000**
- Recall: **1.0000**
- F1: **1.0000**

Đây là smoke/golden evaluation cho các fact đã biết trong dataset, không nên diễn giải là độ chính xác tổng quát của toàn hệ thống. Bộ test chính thức cần nhiều câu hơn và được gán nhãn độc lập.

### Question router

- Seed training: **44 câu**
- Independent test: **11 câu**
- Route accuracy: **100%**
- Domain accuracy: **100%**
- Joint accuracy: **100%**
- Route macro-F1: **100%**
- Domain macro-F1: **100%**

Đây là baseline chạy được, chưa phải kết quả cuối luận văn. Nên tăng lên 500-1.000 câu và báo cáo thêm macro Precision/Recall/F1.

### FAISS smoke test

- 100 documents đầu tiên
- 434 chunks/vectors
- Cosine search trả top-3 thành công
- Backend smoke: Hashing 1.024 chiều, `production_ready=false`

Backend Hashing chỉ xác nhận logic index + metadata + search. Index nộp đồ án phải chạy bằng backend mặc định `transformer`, model `intfloat/multilingual-e5-base`, trên `rag_dataset_final.jsonl` 130.999 records ở máy người dùng.

## Giới hạn dữ liệu của phiên triển khai

Hai report đính kèm cho biết:

- `vn_complete_dataset_v2.json`: 193.708 records;
- `rag_dataset_final.jsonl`: 130.999 records sau clean.

Hai file lớn này không có trong tệp đính kèm của phiên, nên không thể tạo index Transformer cuối cùng từ 130.999 records tại đây. Project đã hỗ trợ trực tiếp cả JSON object lớn và JSONL streaming; chỉ cần chạy lệnh trong README trên máy chứa file final.

## Tiêu chí hoàn tất production index

Một lần chạy được xem là hoàn tất khi `artifacts/faiss/index_config.json` có:

```json
{
  "backend": "transformer",
  "production_ready": true,
  "metric": "cosine_via_normalized_inner_product"
}
```

và `/health` trả `faiss_ready: true`.

## Cập nhật thực thi ngày 24/09/2026

Phần này cập nhật và thay thế các số liệu/giới hạn của phiên cũ ở trên. Dữ liệu đầy đủ hiện đã có trên máy.

- Đã sửa nhận diện truy vấn danh sách phường theo tỉnh/thành phố. Năm 1999 không còn bị coi là mã hành chính; câu hỏi về năm công nhận được chuyển sang RAG vì KG chưa biểu diễn thuộc tính đó.
- Đã sửa đánh giá KG: precision/recall/F1 chỉ tính trên các ca `expected_rows` đầy đủ, tính cả kết quả dư và khớp một-một. 12/12 ca pass, gồm 10 ca đầy đủ và 2 ca kiểm tra bao phủ. Đây vẫn là tập hồi quy nhỏ, không phải đánh giá độc lập về sự thật trong toàn KG.
- Benchmark tra mã `00070`: trung vị 5 lần khoảng 364 ms trước và 3,54 ms sau dùng `VALUES`, cùng tập kết quả. Không suy rộng mức tăng tốc này sang mọi truy vấn.
- Router: chạy lại 11/11 ca đúng route và domain. Chưa mở rộng bộ nhãn độc lập.
- 9 unit/regression test pass, bao gồm lỗi route, false positive KG, lọc domain top-k và phục hồi sau khi encode bị ngắt.
- Index Transformer mẫu: 216 tài liệu, 588 đoạn thuộc đủ 4 miền. Kiểm tra tích hợp KG/RAG/hybrid/fallback/cosine/top-k đã pass.
- Ablation 16 câu diễn đạt lại, 50 tài liệu nhiễu lấy mẫu mỗi miền: Hit@1 tăng từ 0,8125 lên 0,875; MRR@5 từ 0,859375 lên 0,90625; recall đối với tài liệu đúng đã biết ở top-5 giữ 0,9375. Phép đo chỉ chứng minh cải tiến ban đầu của mở rộng thuật ngữ, không phải fine-tuning trọng số hoặc benchmark độc lập. Văn bản nguồn chưa được thẩm định tính đúng đắn.
- Cấu hình số luồng CPU mặc định giới hạn ở 1 để tránh lỗi native đã tái hiện khi kết hợp Transformer, sklearn và FAISS trên máy này; có thể override bằng biến môi trường trước khi khởi động Python.
- Build đầy đủ bằng E5 trên Metal đã khởi động, có checkpoint theo batch. **Không coi full index là hoàn tất khi chỉ có kết quả pilot.** Trạng thái hiện hành nằm ở `artifacts/faiss/build_progress.json`; kết quả kiểm tra sau build ở `artifacts/faiss/validation_status.json`. Lượt kiểm tra sau build đã được khởi động và đang đợi index đầy đủ.

Báo cáo chi tiết: `artifacts/kg/sparql_benchmark.json`, `artifacts/kg/evaluation_report.json`, `artifacts/evaluation/embedding_ablation.json`, `artifacts/evaluation/sample_index/integration_report.json`. `artifacts/pipeline_report.json` sẽ được cập nhật sau khi bước finalize hoàn tất.
