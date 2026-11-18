# Đối chiếu yêu cầu với sản phẩm

Kiểm kê dữ liệu và nghiên cứu đợt 30–31/10/2026, bổ sung kiểm thử tích hợp D1 ngày 18/11/2026. Nguồn yêu cầu là PDF kế hoạch ba trang, PDF báo cáo mẫu 62 trang và ba yêu cầu nghiên cứu được giảng viên nêu qua người dùng. Mốc tuần là kế hoạch dự kiến; không phải ngày hoàn thành đã xác minh. Đạt phạm vi chỉ có nghĩa có bằng chứng trong giới hạn được ghi.

| Mã | Mốc dự kiến | Yêu cầu | Trạng thái | Bằng chứng | Khoảng trống |
|---|---|---|---|---|---|
| W01 | 03/08–09/08 | Khảo sát, môi trường, dữ liệu thô | Một phần | SOURCE/docs/ARCHITECTURE.md; data/raw | Có runtime PyTorch và khảo sát; benchmark công khai chưa có thực nghiệm; vLLM chưa kiểm chứng. |
| W02 | 10/08–16/08 | Pipeline, dataset và câu hỏi mẫu | Đạt phạm vi | SOURCE/src/vn_assistant/corpus_update.py; data/structured_records.jsonl | Có pipeline và dữ liệu; độ phủ/nhãn độc lập vẫn là giới hạn. |
| W03 | 17/08–23/08 | Ontology và KG | Đạt phạm vi | SOURCE/ontology/vn_heritage_admin.ttl; artifacts/kg | Graph RDF đã có; chưa phải graph hình học hoặc timeline pháp lý đầy đủ. |
| W04 | 24/08–30/08 | SPARQL và đánh giá KG | Đạt phạm vi | SOURCE/queries; artifacts/research_expansion_2026-10-30/artifacts/kg/evaluation_report.json | 10 mẫu; 17 ca development đạt, không đồng nghĩa mọi fact đúng. |
| W05 | 31/08–06/09 | Transformer embedding và tối ưu lexical gap | Một phần | SOURCE/src/vn_assistant/embedding.py; artifacts/faiss/index_config.json | E5 768 chiều; có so sánh lexical/dense, chưa fine-tune hay sweep siêu tham số. |
| W06 | 07/09–13/09 | FAISS và API RAG | Đạt phạm vi | SOURCE/src/vn_assistant/faiss_store.py; SOURCE/src/vn_assistant/api.py | IndexFlatIP chuẩn hóa cosine; không phải IVF-PQ/GPU index. |
| W07 | 14/09–20/09 | Question processing và lọc | Đạt phạm vi | SOURCE/src/vn_assistant/router.py; SOURCE/src/vn_assistant/question_processing.py | TF-IDF/LR + quy tắc; nhận diện mã/ngày có giới hạn diễn đạt. |
| W08 | 21/09–27/09 | LLM và prompt | Thay phương án | SOURCE/src/vn_assistant/llm.py; models/Qwen3-0.6B | Qwen3/Transformers đã chạy; LLaMA-2/vLLM trong kế hoạch chưa được chạy tương đương. |
| W09 | 28/09–04/10 | Trả lời có minh chứng | Một phần | SOURCE/src/vn_assistant/generation.py; SOURCE/src/vn_assistant/evidence.py | Có chọn mệnh đề và nguồn; không phải tổng hợp tự do dài. |
| W10 | 05/10–11/10 | Cross-check và giảm ảo giác | Một phần | SOURCE/src/vn_assistant/cross_check.py; SOURCE/tests/test_generation.py | Kiểm tra cú pháp, trích đoạn, KG; chưa đo giảm ảo giác bằng người chấm/A-B. |
| W11 | 12/10–18/10 | Giao diện assistant end-to-end | Đạt phạm vi | SOURCE/src/vn_assistant/static; artifacts/admin_code_fix_2026-10-25/ui/ui_report.json | UI local; 33 check lịch sử D0; không có ảnh/voice/tài khoản. |
| W12 | 19/10–25/10 | Test toàn hệ thống không-thời gian | Một phần | artifacts/admin_code_fix_2026-10-25/backend_report.json; artifacts/research_validation_2026-11-18 | D0 và D1 đều đạt 65 HTTP/33 UI; chưa tính bán kính/hình học hoặc chấm factuality độc lập. |
| W13 | 26/10–01/11 | Accuracy/F1, Faithfulness, Context Relevancy | Một phần | artifacts/research_expansion_2026-10-30/experiment_report.json | Có router/KG/retrieval; chưa có chấm độc lập chất lượng câu trả lời. |
| W14 | 02/11–08/11 | Tối ưu siêu tham số/prompt/query | Chưa nghiệm thu | SOURCE/scripts/run_research_experiments.py | Có ablation cố định; chưa sweep dev rồi test kín mới. |
| W15 | 09/11–15/11 | Viết báo cáo phần đầu | Có bản thảo | BAO_CAO/THESIS_2026/markdown | Sáu chương đã viết; thông tin bìa đã được người dùng xác nhận. |
| W16 | 16/11–22/11 | Hoàn thiện thuyết minh | Cần rà soát | BAO_CAO/THESIS_2026/output | Đợt này tạo báo cáo đầy đủ nội dung hiện có; chưa có xác nhận nghiệm thu/ký. |
| W17 | 23/11–29/11 | Đóng gói và hướng dẫn | Một phần | SOURCE/scripts/run_assistant.sh; SOURCE/docs/DEPLOYMENT.md | Có hướng dẫn/script; chưa chứng minh cài mới sạch trên máy độc lập. |
| W18 | 30/11–06/12 | Slide và video demo | Chưa có bằng chứng | BAO_CAO | Chưa thấy sản phẩm slide/video tương ứng trong thư mục kiểm kê. |
| W19 | 07/12–13/12 | Diễn tập và bảo vệ | Chưa thực hiện | BAO_CAO | Đây là mốc tương lai theo kế hoạch, không ghi đã hoàn thành. |

## Ba yêu cầu nghiên cứu

| Yêu cầu | Bằng chứng | Mức đáp ứng |
|---|---|---|
| Dữ liệu/phương pháp có sẵn và thực nghiệm sơ bộ | D0; TF-IDF, BM25, E5, RRF; existing_experiment_details.json | Có bằng chứng sơ bộ; D0 là corpus dự án, không phải benchmark công khai độc lập |
| Dữ liệu mới và nhiều phương pháp | corpus_audit.json; 7 cấu hình D0/D1 | Đã chạy; nhãn silver cần duyệt |
| Đề xuất lai và thực nghiệm | M7 và ablation M4–M6; paired_bootstrap | Có tổ hợp cho ứng dụng; chưa chứng minh tính mới toàn cầu hoặc ưu thế mọi nhóm |

## Điều chỉnh so với PDF mẫu

Giữ tên đề tài và bố cục bìa/mở đầu/chương/tham khảo/phụ lục; thay mục lục lời bài hát bằng nội dung địa giới và du lịch. Đồng bộ năm 2026. Người dùng đã xác nhận học vị TS., tên đề tài và thông tin hai sinh viên; dùng thống nhất TS. Trần Thanh Phước. Không giữ các khẳng định triệt tiêu ảo giác hay KG chính xác tuyệt đối. Dùng Qwen3/Transformers đúng artifact, ghi LLaMA-2/vLLM là khác phương án. Không bịa điểm GS-QA/MapQA/Tourism QA hoặc Faithfulness.

## Quy tắc bằng chứng

Tệp code cho biết có cơ chế, báo cáo chạy cho biết cơ chế đã được kiểm tra trên tập nào, và nguồn chuẩn/người chấm mới có thể hỗ trợ kết luận nội dung đúng. Chưa thấy bằng chứng không đồng nghĩa khẳng định sinh viên chưa làm ở nơi khác; cần bổ sung artifact nếu có. Không cộng các tỷ lệ test phần mềm thành accuracy của đề tài.
