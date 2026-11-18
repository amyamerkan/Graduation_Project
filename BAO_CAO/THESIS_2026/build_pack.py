from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,shutil,csv
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;MD=OUT/'markdown';R=ROOT/'artifacts/research_expansion_2026-10-30'
audit=json.loads((R/'corpus_audit.json').read_text());exp=json.loads((R/'experiment_report.json').read_text());train=json.loads((R/'training_report.json').read_text())
NAMES={'tfidf':'TF-IDF','bm25':'BM25','dense_e5':'E5','rrf':'RRF','rrf_domain':'RRF + miền','rrf_domain_province':'RRF + miền + tỉnh','proposed_temporal_province_rrf':'Lai mã/ngày/tỉnh'}
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|',*['| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in rows]])
def save(name,text): (MD/name).write_text(text.strip()+'\n',encoding='utf-8')
def metric_table(label):
 return table(['Phương pháp','Hit@1','Hit@5','MRR@10','nDCG@10','Từ chối đúng'],[[NAMES[m],*[f"{p['test'][k]:.4f}" for k in ['hit_at_1','hit_at_5','mrr_at_10','ndcg_at_10','abstention_accuracy']]] for m,p in exp['datasets'][label]['summary'].items()])
old=table(['Phương pháp','D0 MRR@10','D1 MRR@10'],[[NAMES[m],*[f"{exp['datasets'][d]['old_questions'][m]['mrr_at_10']:.4f}" for d in ['existing','expanded']]] for m in NAMES])
manual=table(['Phương pháp','D0 MRR@10','D1 MRR@10'],[[NAMES[m],*[f"{exp['datasets'][d]['manual_development'][m]['mrr_at_10']:.4f}" for d in ['existing','expanded']]] for m in NAMES])
slices=table(['Phương pháp','Mã/ngày MRR','Điểm đến MRR','Đoạn sắp xếp MRR','Theo tỉnh nDCG'],[[NAMES[m],*[f"{exp['datasets']['expanded']['slices'][m][k][v]:.4f}" for k,v in [('temporal_code','mrr_at_10'),('destination','mrr_at_10'),('merger_clause','mrr_at_10'),('province_destinations','ndcg_at_10')]]] for m in NAMES])
boot=table(['Đối chứng','Chênh lệch MRR','Khoảng percentile 95%'],[[NAMES[m],f"{v['delta_mrr']:.4f}",f"[{v['percentile_95_ci'][0]:.4f}; {v['percentile_95_ci'][1]:.4f}]"] for m,v in exp['paired_bootstrap'].items()])
data=table(['Loại bản ghi','D0','D1'],[['Snapshot hành chính',17520,17520],['Liên kết chuyển đổi',10618,10618],['Hồ sơ thuộc tính văn bản',37,37],['Dòng quan sát đối chiếu',3321,6642],['Đoạn hành chính riêng biệt',0,3351],['Điểm du lịch',453,825],['Tổng tài liệu',31949,38993]])
replacements={'{{DATA_TABLE}}':'Bảng 3.1 Thành phần corpus theo loại bản ghi\n\n'+data,'{{EXISTING_TABLE}}':'Bảng 5.1 Kết quả D0 trên silver test\n\n'+metric_table('existing'),'{{EXPANDED_TABLE}}':'Bảng 5.2 Kết quả D1 trên silver test\n\n'+metric_table('expanded'),'{{SLICE_TABLE}}':'Bảng 5.3 Kết quả D1 theo nhóm câu\n\n'+slices,'{{OLD_QUESTIONS_TABLE}}':'Bảng 5.4 Chỉ các câu hỏi cũ trên hai corpus\n\n'+old,'{{MANUAL_TABLE}}':'Bảng 5.5 Bộ phát triển thủ công giữ riêng\n\n'+manual,'{{BOOTSTRAP_TABLE}}':'Bảng 5.6 Bootstrap chênh lệch MRR trên D1\n\n'+boot}
for f in MD.glob('CHUONG_*.md'):
 t=f.read_text()
 for k,v in replacements.items(): t=t.replace(k,v)
 f.write_text(t)
chap5=MD/'CHUONG_05.md';t=chap5.read_text();pos='### 5.4.3 Tác động bổ sung corpus trên câu hỏi cũ'
if '![Hình 5.1' not in t:t=t.replace(pos,'![Hình 5.1 MRR trên silver test và bộ thủ công](../assets/mrr_comparison.png)\n\n![Hình 5.2 Chất lượng truy xuất theo loại câu](../assets/task_results.png)\n\n'+pos)
chap5.write_text(t)
requirements=[
('W01','03/08–09/08','Khảo sát, môi trường, dữ liệu thô','Một phần','SOURCE/docs/ARCHITECTURE.md; data/raw','Có runtime PyTorch và khảo sát; benchmark công khai chưa có thực nghiệm; vLLM chưa kiểm chứng.'),
('W02','10/08–16/08','Pipeline, dataset và câu hỏi mẫu','Đạt phạm vi','SOURCE/src/vn_assistant/corpus_update.py; data/structured_records.jsonl','Có pipeline và dữ liệu; độ phủ/nhãn độc lập vẫn là giới hạn.'),
('W03','17/08–23/08','Ontology và KG','Đạt phạm vi','SOURCE/ontology/vn_heritage_admin.ttl; artifacts/kg','Graph RDF đã có; chưa phải graph hình học hoặc timeline pháp lý đầy đủ.'),
('W04','24/08–30/08','SPARQL và đánh giá KG','Đạt phạm vi','SOURCE/queries; artifacts/research_expansion_2026-10-30/artifacts/kg/evaluation_report.json','10 mẫu; 17 ca development đạt, không đồng nghĩa mọi fact đúng.'),
('W05','31/08–06/09','Transformer embedding và tối ưu lexical gap','Một phần','SOURCE/src/vn_assistant/embedding.py; artifacts/faiss/index_config.json','E5 768 chiều; có so sánh lexical/dense, chưa fine-tune hay sweep siêu tham số.'),
('W06','07/09–13/09','FAISS và API RAG','Đạt phạm vi','SOURCE/src/vn_assistant/faiss_store.py; SOURCE/src/vn_assistant/api.py','IndexFlatIP chuẩn hóa cosine; không phải IVF-PQ/GPU index.'),
('W07','14/09–20/09','Question processing và lọc','Đạt phạm vi','SOURCE/src/vn_assistant/router.py; SOURCE/src/vn_assistant/question_processing.py','TF-IDF/LR + quy tắc; nhận diện mã/ngày có giới hạn diễn đạt.'),
('W08','21/09–27/09','LLM và prompt','Thay phương án','SOURCE/src/vn_assistant/llm.py; models/Qwen3-0.6B','Qwen3/Transformers đã chạy; LLaMA-2/vLLM trong kế hoạch chưa được chạy tương đương.'),
('W09','28/09–04/10','Trả lời có minh chứng','Một phần','SOURCE/src/vn_assistant/generation.py; SOURCE/src/vn_assistant/evidence.py','Có chọn mệnh đề và nguồn; không phải tổng hợp tự do dài.'),
('W10','05/10–11/10','Cross-check và giảm ảo giác','Một phần','SOURCE/src/vn_assistant/cross_check.py; SOURCE/tests/test_generation.py','Kiểm tra cú pháp, trích đoạn, KG; chưa đo giảm ảo giác bằng người chấm/A-B.'),
('W11','12/10–18/10','Giao diện assistant end-to-end','Đạt phạm vi','SOURCE/src/vn_assistant/static; artifacts/admin_code_fix_2026-10-25/ui/ui_report.json','UI local; 33 check lịch sử D0; không có ảnh/voice/tài khoản.'),
('W12','19/10–25/10','Test toàn hệ thống không-thời gian','Một phần','artifacts/admin_code_fix_2026-10-25/backend_report.json; artifacts/research_validation_2026-11-18','D0 và D1 đều đạt 65 HTTP/33 UI; chưa tính bán kính/hình học hoặc chấm factuality độc lập.'),
('W13','26/10–01/11','Accuracy/F1, Faithfulness, Context Relevancy','Một phần','artifacts/research_expansion_2026-10-30/experiment_report.json','Có router/KG/retrieval; chưa có chấm độc lập chất lượng câu trả lời.'),
('W14','02/11–08/11','Tối ưu siêu tham số/prompt/query','Chưa nghiệm thu','SOURCE/scripts/run_research_experiments.py','Có ablation cố định; chưa sweep dev rồi test kín mới.'),
('W15','09/11–15/11','Viết báo cáo phần đầu','Có bản thảo','BAO_CAO/THESIS_2026/markdown','Sáu chương đã viết; thông tin bìa đã được người dùng xác nhận.'),
('W16','16/11–22/11','Hoàn thiện thuyết minh','Cần rà soát','BAO_CAO/THESIS_2026/output','Đợt này tạo báo cáo đầy đủ nội dung hiện có; chưa có xác nhận nghiệm thu/ký.'),
('W17','23/11–29/11','Đóng gói và hướng dẫn','Một phần','SOURCE/scripts/run_assistant.sh; SOURCE/docs/DEPLOYMENT.md','Có hướng dẫn/script; chưa chứng minh cài mới sạch trên máy độc lập.'),
('W18','30/11–06/12','Slide và video demo','Chưa có bằng chứng','BAO_CAO','Chưa thấy sản phẩm slide/video tương ứng trong thư mục kiểm kê.'),
('W19','07/12–13/12','Diễn tập và bảo vệ','Chưa thực hiện','BAO_CAO','Đây là mốc tương lai theo kế hoạch, không ghi đã hoàn thành.')]
req_table=table(['Mã','Mốc dự kiến','Yêu cầu','Trạng thái','Bằng chứng','Khoảng trống'],requirements)
save('01_DOI_CHIEU_YEU_CAU.md','''# Đối chiếu yêu cầu với sản phẩm

Kiểm kê dữ liệu và nghiên cứu đợt 30–31/10/2026, bổ sung kiểm thử tích hợp D1 ngày 18/11/2026. Nguồn yêu cầu là PDF kế hoạch ba trang, PDF báo cáo mẫu 62 trang và ba yêu cầu nghiên cứu được giảng viên nêu qua người dùng. Mốc tuần là kế hoạch dự kiến; không phải ngày hoàn thành đã xác minh. Đạt phạm vi chỉ có nghĩa có bằng chứng trong giới hạn được ghi.

'''+req_table+'''

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
''')
gaps=[
('G01','P0','Duyệt gold và tạo test kín','Hai người chấm; xác nhận đáp án/nguồn; lưu bất đồng và quy tắc giải quyết','annotation_review.csv và tập test mới đóng băng'),
('G02','P0','Đánh giá câu trả lời','Chấm factuality, faithfulness, completeness, citation và từ chối theo rubric','Phiếu chấm; số mẫu; thống kê theo nhóm'),
('G03','P0','Chọn benchmark ngoài phù hợp','Đúng phiên bản, giấy phép, adapter và task; không coi câu tự sinh là GS-QA','Manifest dữ liệu và output công khai phù hợp'),
('G04','P0','Xác nhận phạm vi với GVHD','Người dùng đã xác nhận bìa; còn chấp thuận đổi runtime và thu hẹp miền','Bìa đã đồng bộ TS.; biên bản phạm vi cần GVHD'),
('G05','P1','Đối chứng cross-check','Cùng câu, nguồn, mô hình; bật/tắt kiểm tra; chấm mệnh đề và coverage','Kết quả A/B, không chỉ unit test'),
('G06','P1','Mở rộng đo độ trễ','Đã đo 3 câu x 5 lần và từng pha thô; còn tách encode/search và tăng mẫu, tải','artifacts/research_validation_2026-11-18/latency_report.json'),
('G07','P1','Tối ưu trên dev','Chọn k, RRF, ngưỡng, prompt trên dev rồi khóa cấu hình','Config và hash trước test kín'),
('G08','P1','Nghiệm thu phát hành D1','Đã đạt 353 unit, 65 HTTP, 33 UI trên D1 cô lập; còn duyệt nội dung và phát hành','artifacts/research_validation_2026-11-18/validation_manifest.json'),
('G09','P1','Căn cứ hiệu lực và chuyển một phần','Gắn văn bản/khoản cho sự kiện; không nội suy các ngày còn thiếu','Bảng sự kiện được thẩm định'),
('G10','P1','Tăng độ phủ du lịch','Ưu tiên tỉnh ít bản ghi, nhiều cách hỏi tên cũ/mới; audit địa chỉ','Coverage theo tỉnh và nguồn'),
('G11','P2','Truy vấn bán kính/hình học','Tọa độ có nguồn, mốc gốc, hệ quy chiếu, khoảng cách; test điểm chuẩn','Dữ liệu GIS và engine; chưa có hiện tại'),
('G12','P1','Đóng gói cài mới','Dùng môi trường sạch trên máy khác; kiểm soát phiên bản và tài nguyên','Log cài/khởi chạy và quickstart'),
('G13','P1','Slide và video','Demo mã/ngày, mô tả, ca không có dữ liệu, giới hạn phương pháp','Slide và video thực tế'),
('G14','P1','Người viết và GVHD rà báo cáo','Đã xuất và kiểm tra bố cục/mục lục; cần tác giả duyệt nội dung, giấy phép và ký','qa_manifest.json; checklist tác giả/GVHD')]
save('02_CONG_VIEC_CAN_THUC_HIEN.md','# Công việc cần thực hiện và tiêu chí nghiệm thu\n\n'+table(['Mã','Ưu tiên','Công việc','Tiêu chí','Sản phẩm cần có'],gaps)+'''

P0 là điều kiện để đưa ra kết luận nghiên cứu mạnh hoặc nộp bản chính thức; P1 phục vụ hoàn thiện và bàn giao; P2 là mở rộng nếu phạm vi được duyệt. Thứ tự đề xuất: G01–G04 trước, sau đó G05–G10 và G12, cuối cùng G13–G14. G11 cần nguồn lực riêng và không thể thay bằng crawl thêm văn bản.

Nếu giữ giới hạn hình học hoặc không chạy được một benchmark, cần ghi rõ điều chỉnh phạm vi và thống nhất với GVHD; không tạo số liệu để lấp chỗ thiếu. Không có phân công thời lượng thực tế hoặc chữ ký tác giả trong bằng chứng nên tài liệu không tự gán người chịu trách nhiệm và ngày hoàn tất.
''')
save('03_GIAO_THUC_THUC_NGHIEM.md','''# Giao thức thực nghiệm và kiểm soát rò rỉ

D0 gồm 31.949 tài liệu; D1 gồm 38.993. Tập silver 263 câu chia 52 dev, 211 test; test có 188 câu dương và 23 câu không có snapshot. 16 câu thủ công là development set riêng. Nhóm thực thể theo mã hoặc tên được giữ cùng split. Bộ router D0 đóng băng cho cả hai corpus; router D1 được đánh giá riêng.

## Cấu hình

M1 TF-IDF; M2 BM25 (k1=1.2, b=0.75); M3 E5 pretrained; M4 BM25+E5/RRF (k=60); M5 M4+miền; M6 M5+tỉnh; M7 M6+khóa mã/ngày. Hai nguồn cung cấp tối đa 200 chunk, gộp doc_id và đánh giá top 10. Không fine-tune E5/Qwen, không chọn lại trọng số bằng test.

## Chỉ số

Hit@k và MRR tính trên câu có nhãn dương; nDCG xét tập dương top 10; Recall@10 là known-positive recall. Ca thiếu snapshot đo abstention accuracy riêng. Bootstrap 1.000 lượt theo 142 nhóm thực thể của các câu test dương. ranking_ms là tổng runner nhiều phương pháp, không phải độ trễ từng phương pháp. Không đổi MRR thành Accuracy trả lời.

## Cải thiện giao thức trước kết luận cuối

Giữ dữ liệu đóng băng trước khi gán nhãn; hai người duyệt nguồn và nhiều đáp án tương đương; thêm câu hỏi tự nhiên, ngày không rõ, tên trùng và chuyển một phần. Mẫu test kín mới không được dùng để lựa chọn cấu hình. Việc dữ liệu train có tên thực thể không phải bằng chứng fine-tune E5; vẫn cần chia nhóm đúng cho câu hỏi router nếu đánh giá router tổng quát.

Đánh giá nguồn độc lập với kiểm tra câu khớp nguồn. Khi corpus mới có quan sát tương đương chưa nằm trong positive IDs, ghi nhãn chưa đầy đủ, không tự kết luận nguồn mới sai. Cần báo kết quả D0/D1 trên cả toàn tập và nhóm câu hỏi cũ.
''')
save('04_KET_QUA_VA_GIOI_HAN.md','# Kết quả thực nghiệm đã có\n\n## D1 silver test\n\n'+metric_table('expanded')+'\n\n## Câu hỏi cũ\n\n'+old+'\n\n## Bộ thủ công giữ riêng\n\n'+manual+'''

## Kết luận được phép

Tổ hợp mã/ngày/tỉnh có lợi trên bộ silver hiện tại; E5 tốt hơn ở một số nhóm mô tả; RRF thường tốt hơn tổ hợp trên 16 câu thủ công. Dữ liệu mới tăng độ phủ nhưng một số điểm câu cũ giảm. Không chứng minh một phương pháp thắng tổng quát, không có điểm QA factual accuracy 90–98% và không có benchmark ngoài độc lập.

Router mới: 5.598 câu train, route/joint 25/26 sau quy tắc và domain 26/26; raw route 23/26, raw domain 24/26. KG: 17/17 development; 14 ca expected_rows chỉ có 9 binding dương. Unit kiểm tra lại ngày 18/11: 353/353. HTTP D0 lịch sử: 65/65; UI D0 lịch sử: 33/33. D1 được chạy riêng ngày 18/11, cũng đạt 65/65 HTTP và 33/33 UI. Đây là hai lần chạy có artifact riêng, không chuyển nhãn bằng chứng D0 thành D1. Xem [nghiệm thu D1](11_NGHIEM_THU_D1.md).

## Kết quả chưa có

Faithfulness và Context Relevancy độc lập; factuality câu trả lời theo người chấm; so sánh bật/tắt cross-check; sweep prompt/siêu tham số; benchmark GS-QA/MapQA/Tourism QA; tải đồng thời và cloud/GPU tương đương kế hoạch. Không điền các mục này bằng điểm ước tính.
''')
save('05_TAI_LAP_VA_VAN_HANH.md','''# Tái lập và vận hành

## App đang dùng

```bash
cd "/Users/amyas/HK1 26-27/DATN/SOURCE"
bash scripts/run_assistant.sh
```

Mở http://127.0.0.1:8001. Dữ liệu mặc định vẫn là D0. Không cần train hoặc tạo embedding lại mỗi lần khởi động. Lần tải trọng số đầu có thể chậm hơn. Hướng dẫn này giả định môi trường và trọng số hiện có, không thay log cài mới trên máy khác.

## Bản nghiên cứu

```bash
../.venv/bin/python scripts/collect_research_expansion.py --output ../artifacts/research_expansion_2026-10-30 --tourism-pages 4
../.venv/bin/python scripts/finalize_research_corpus.py --release ../artifacts/research_expansion_2026-10-30
../.venv/bin/python scripts/retrain_domain_refresh.py --release ../artifacts/research_expansion_2026-10-30
../.venv/bin/python scripts/run_research_experiments.py --release ../artifacts/research_expansion_2026-10-30 --device mps
```

Các lệnh chạy từ SOURCE; raw cache có thể được tái sử dụng. Để build FAISS lại, dùng refresh_vectors.py với dataset candidate, thư mục seed hợp lệ và output **mới chưa có index**. Release hiện đã có chỉ mục, không chạy lệnh ghi đè tùy tiện. Vector chỉ tái sử dụng nếu nội dung passage và cấu hình encoder phù hợp; không gọi đó là fine-tune.

## Kiểm thử và version

```bash
../.venv/bin/python -m pytest -q
../.venv/bin/python scripts/verify_system.py
../.venv/bin/python scripts/verify_ui.py
```

Hai lệnh cuối cần server đúng phiên bản. Chỉ định output riêng để không mất báo cáo lịch sử. Trước khi công bố release mới: kiểm tra toàn bộ ID/nguồn, SQLite integrity, số vector, graph, alias, HTTP/UI và rollback. Không thay index khi server đang giữ metadata/graph của bản khác. Code hiện có một process và lock nội bộ, không mặc nhiên dùng nhiều worker trên cùng máy 16 GiB.

## Build báo cáo

Chạy build_pack.py để cập nhật bảng số đo và Markdown từ artifacts. Chạy build_document.py bằng Python bundled để xuất Word, sau đó render_docx.py của runtime để chuyển PDF và PNG kiểm tra. File qa_manifest.json ghi số trang, kiểm tra liên kết và audit số liệu của lần xuất. Sửa nội dung chương trong markdown/ rồi build lại; không sửa bảng kết quả bằng tay nếu JSON gốc chưa thay.
''')
save('06_THE_DU_LIEU.md','''# Thẻ dữ liệu D0 và D1

Mục đích: hỏi đáp văn bản địa giới cũ–mới và điểm tham quan Việt Nam. Ngôn ngữ chủ yếu tiếng Việt. D0 là dữ liệu ứng dụng, D1 là release nghiên cứu riêng. Không phải tổng điều tra địa điểm du lịch hoặc timeline pháp lý liên tục.

'''+data+'''

## Nguồn và quyền sử dụng

Danh mục nền vietnam-provinces 2026.9.0, nguồn cộng đồng có điều kiện GPL-3.0-or-later cần xem xét khi phân phối. Bảng NSO và bài Chính phủ là nguồn hành chính có thẩm quyền; thời điểm bảng hiển thị và hiệu lực cần được phân biệt. TITC cung cấp các điểm được lấy theo bộ lọc tỉnh và phân trang. Truy cập công khai không tự động đồng nghĩa mọi bài và ảnh có giấy phép mở; đợt này không thu ảnh.

## Đơn vị dữ liệu và thời gian

Code là string có số 0 đầu. Snapshot 2025-06-30, 2025-07-01, 2026-10-24 được giữ riêng. 3.321 quan sát mới ngày 30/10/2026 so với cột tham chiếu 31/10/2025; cột tham chiếu này không phải trước sắp xếp tháng 7. Không có thay đổi ở các trường được script đối chiếu giữa hai lần quan sát. Không đếm dòng quan sát thành sự kiện sáp nhập mới.

Đoạn pháp lý khử trùng theo biến thể số thứ tự/dấu câu, giữ nguyên văn và URL bổ sung. Có 2.757 biến thể trùng được gộp. Điểm du lịch mới: 372; tổng 825, thuộc 34 tỉnh theo nguồn. Audit mới loại 38 câu chủ đề phi vật thể. Tỉnh ít dữ liệu vẫn có thể có nhiều điểm thực tế chưa được crawl.

## Giới hạn và rủi ro

Nguồn có thể đổi nội dung; cache và SHA256 giúp truy nguyên nhưng không chứng minh sự thật. Địa chỉ có thể còn huyện/tỉnh cũ; không tự gán xã mới. Chuyển một phần không phải nhập toàn bộ. Corpus cũ và mới có tài liệu tương đương chưa được gán đầy đủ positive IDs. Những archives không hoạt động không phải input của D1; ghi chú sự cố vệ sinh archive trước đây được giữ ở hồ sơ bảo trì.
''')
save('07_THE_HE_THONG.md','''# Thẻ hệ thống và mô hình

Tri Việt dùng FastAPI, RDFLib/SPARQL, E5/FAISS, SQLite metadata và Qwen3-0.6B/Transformers. Neo4j có công cụ import nhưng không phải engine query chính. vLLM là adapter/phương án cấu hình, chưa có thực nghiệm tương đương LLaMA-2/vLLM trong kế hoạch.

## Đầu vào và đầu ra

Đầu vào văn bản dài 2–2.000 ký tự; HTTP top_k 1–20; tối đa 12 lượt lịch sử. Route kg/rag/hybrid; miền administration/tourism. Trạng thái answered, partial, abstained, needs_clarification không phải thang factual accuracy. Câu tra mã có thể trả lời không nạp LLM. Các câu còn lại có thể dùng LLM chọn tối đa 3 claim ID từ registry.

## Kiểm tra và giới hạn

Có kiểm tra mã, loại thực thể, tên, tỉnh, snapshot và thay đổi KG giữa hai lần đọc. Có kiểm tra JSON, trích đoạn, các trường fact và nguồn URL an toàn. Không có bộ chứng minh mọi phát biểu ngôn ngữ tự nhiên đều suy ra từ nguồn. source_verified=false không tự biến thành true chỉ vì URL chính thức.

Chưa nhận/hiển thị ảnh du lịch, chưa GIS bán kính, chưa voice, chưa tài khoản/đồng bộ history server. Lịch sử ở localStorage; không nên lưu dữ liệu nhạy cảm. API chưa có xác thực/rate limit phù hợp public deployment. Không suy từ demo local thành khả năng tải nhiều người dùng.

## Huấn luyện và tài nguyên

D0 router 3.402 câu; candidate D1 5.598 câu. E5/Qwen pretrained, không fine-tune. Thiết bị encoder ghi mps; chiều vector 768. IndexFlatIP trên vector chuẩn hóa không phải GPU FAISS hoặc IVF-PQ. Môi trường kiểm kê arm64/macOS, bộ nhớ 16 GiB. Số liệu tải/nhiệt độ/bộ nhớ cực đại từng lượt chưa đo.
''')
save('08_CONG_TRINH_LIEN_QUAN.md','''# Công trình liên quan và khoảng trống

| Công trình hoặc chuẩn | Vai trò trong đồ án | Điều không được suy ra |
|---|---|---|
| RAG — Lewis et al., arXiv:2005.11401 | Cơ sở kết hợp truy xuất và mô hình ngôn ngữ | Không đồng nghĩa đã lặp lại huấn luyện của paper |
| Multilingual E5 — arXiv:2402.05672 | Encoder pretrained đa ngôn ngữ | Không fine-tune theo miền trong dự án |
| FAISS — arXiv:2401.08281 | Lập chỉ mục vector | Không có nghĩa đã dùng IVF-PQ/HNSW/GPU |
| RRF — Cormack et al., SIGIR 2009 | Gộp thứ hạng | Là phương pháp có sẵn, không phải phát minh của đồ án |
| BEIR — arXiv:2104.08663 | Tham khảo protocol nhiều retriever | Chưa chạy bộ benchmark này |
| RAGAs — ACL 2024 eacl-demo.16 | Phân biệt các chiều chất lượng RAG | Chưa có điểm Faithfulness độc lập |
| GS-QA — arXiv:2605.22811 | Hướng QA trên dữ liệu hình học | Chưa có engine và thực nghiệm tương ứng |
| MapQA — arXiv:2211.08545 | Hỏi đáp ảnh choropleth maps | Khác đầu vào văn bản hiện tại; tránh lẫn các bộ cùng tên |
| Tourism QA — arXiv:1909.03527 | QA đề xuất thực thể từ reviews | Corpus giới thiệu điểm đến chưa phải reviews benchmark |
| SPARQL 1.1 — W3C | Ngữ nghĩa truy vấn RDF | Cú pháp đúng không chứng minh nguồn đúng |

## Phát biểu đóng góp phù hợp

Có thể mô tả đóng góp là tổ chức dữ liệu Việt Nam theo phiên bản và tổ hợp truy xuất có ràng buộc mã/ngày/tỉnh, kèm thực nghiệm ablation. Chưa có cơ sở nói thuật toán mới toàn cầu, giảm ảo giác bao nhiêu phần trăm hoặc thắng mọi baseline. Mục tiêu nghiên cứu tiếp theo là nguồn chuẩn, gold độc lập, nhiều cách hỏi và đánh giá câu trả lời.

Danh mục đầy đủ gồm URL và ngày kiểm tra nằm ở TAI_LIEU_THAM_KHAO.md. Tài liệu mẫu được dùng để đối chiếu bố cục và phạm vi, không coi là nguồn xác nhận số liệu của sản phẩm.
''')
save('09_CHECKLIST_BAO_CAO.md','''# Checklist rà báo cáo trước nộp

- [x] Sáu chương đều có giới thiệu, liên quan, phương pháp/dữ liệu, thực nghiệm, kết luận.
- [x] Bảng số đo lấy từ JSON; D0/D1 và thủ công/silver tách riêng.
- [x] Mẫu số 188 câu dương, 23 câu thiếu snapshot, 16 câu thủ công được ghi rõ.
- [x] Không ghi đã chạy GS-QA/MapQA/Tourism QA hoặc chấm Faithfulness khi chưa có bằng chứng.
- [x] Không đổi MRR thành Accuracy trả lời; không nói triệt tiêu ảo giác.
- [x] Có hạn chế GIS, timeline, runtime khác kế hoạch và nguồn dữ liệu.
- [x] Có danh mục hình/bảng/ký hiệu, tham khảo và phụ lục.
- [x] Người dùng xác nhận tên đề tài, hai sinh viên/MSSV và GVHD TS. Trần Thanh Phước.
- [ ] Xác nhận quy chuẩn lề/font riêng của khoa nếu có tài liệu bổ sung.
- [ ] Người viết đọc lại lời cảm ơn/cam đoan và ký đúng ngày thực tế.
- [ ] Duyệt nhãn độc lập, chấm câu trả lời, hoàn thiện benchmark và thí nghiệm còn thiếu.
- [x] Bản bàn giao đã cập nhật mục lục từ PDF và kiểm tra bố cục; nếu sửa Word phải xuất và kiểm tra lại.
- [ ] GVHD rà nội dung và xác nhận phạm vi cuối; không coi bản báo cáo được sinh là đã nghiệm thu.

Bìa lấy tên và MSSV từ PDF được cung cấp. Mẫu ghi học vị GVHD không nhất quán; người dùng đã xác nhận TS. Trần Thanh Phước. Năm được thống nhất 2026. Các mục hình thức chưa có quy định trong PDF được lựa chọn theo định dạng học thuật dễ đọc, không tự nhận là quy chuẩn chính thức của trường.
''')
manifest_paths=['SOURCE/src/vn_assistant/router.py','SOURCE/src/vn_assistant/administrative_codes.py','SOURCE/src/vn_assistant/question_processing.py','SOURCE/src/vn_assistant/generation.py','SOURCE/src/vn_assistant/cross_check.py','SOURCE/src/vn_assistant/api.py','SOURCE/scripts/run_research_experiments.py','artifacts/research_expansion_2026-10-30/corpus_audit.json','artifacts/research_expansion_2026-10-30/experiment_report.json','artifacts/research_expansion_2026-10-30/training_report.json','artifacts/admin_code_fix_2026-10-25/backend_report.json','artifacts/admin_code_fix_2026-10-25/ui/ui_report.json']
evidence=[{'path':p,'exists':(ROOT/p).exists(),'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in manifest_paths]
(OUT/'evidence_manifest.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
save('10_DANH_MUC_BANG_CHUNG.md','# Danh mục bằng chứng\n\nCác đường dẫn dưới đây tính từ DATN. Hash được giữ trong evidence_manifest.json; không hiển thị .env hoặc thông tin bí mật.\n\n'+table(['Tệp','Có trong kiểm kê'],[[x['path'],x['exists']] for x in evidence])+'''\n\nPDF đầu vào có đường dẫn, số trang và SHA256 ở input_manifest.json. Thời điểm báo cáo cũ được giữ nguyên; không đặt lại ngày để giả thành chạy mới. Unit audit của đợt viết báo cáo nằm tại BAO_CAO/THESIS_2026/unit_audit.xml. Các báo cáo active và candidate có phạm vi khác nhau, cần đọc scope/metric_scope trước khi dùng số.
''')
save('00_BAT_DAU.md','''# Hồ sơ đối chứng và báo cáo đồ án Tri Việt

Bộ hồ sơ này kiểm tra yêu cầu của hai PDF với sản phẩm trong DATN và trình bày kết quả nghiên cứu đã có. Bản báo cáo đầy đủ ở BAO_CAO_DO_AN_TOT_NGHIEP.md; chương nguồn ở CHUONG_01.md đến CHUONG_06.md. Word và PDF được xuất từ cùng nguồn Markdown để chỉnh sửa và đọc.

1. [Đối chiếu 19 tuần và yêu cầu nghiên cứu](01_DOI_CHIEU_YEU_CAU.md).
2. [Công việc còn thiếu và tiêu chí nghiệm thu](02_CONG_VIEC_CAN_THUC_HIEN.md).
3. [Protocol thực nghiệm](03_GIAO_THUC_THUC_NGHIEM.md).
4. [Kết quả và giới hạn](04_KET_QUA_VA_GIOI_HAN.md).
5. [Tái lập và vận hành](05_TAI_LAP_VA_VAN_HANH.md).
6. [Thẻ dữ liệu](06_THE_DU_LIEU.md).
7. [Thẻ hệ thống](07_THE_HE_THONG.md).
8. [Liên quan và đóng góp](08_CONG_TRINH_LIEN_QUAN.md).
9. [Checklist nộp báo cáo](09_CHECKLIST_BAO_CAO.md).
10. [Danh mục bằng chứng](10_DANH_MUC_BANG_CHUNG.md).

Có code và số đo cho lõi KG/RAG/LLM, dữ liệu mở rộng và bảy cấu hình. D1 đã được kiểm thử end-to-end riêng ngày 18/11/2026, xem [nghiệm thu và đo độ trễ](11_NGHIEM_THU_D1.md). Chưa đủ căn cứ coi kế hoạch đã hoàn tất toàn bộ: còn benchmark ngoài, GIS, chấm Faithfulness độc lập và sản phẩm bảo vệ. Nội dung báo cáo giữ các điểm chưa hoàn tất ở dạng giới hạn/backlog, không tạo kết quả giả.
''')
# Compact appendix for report; full paths remain in the separate traceability file.
save('PHU_LUC.md','''# PHỤ LỤC A ĐỐI CHIẾU KẾ HOẠCH

Bảng A.1 Trạng thái theo 19 tuần dự kiến

'''+table(['Mã','Nội dung','Trạng thái'],[[x[0],x[2],x[3]] for x in requirements])+'''

Chi tiết đường dẫn và tiêu chí chưa đạt được giữ trong 01_DOI_CHIEU_YEU_CAU.md. Các mốc sau ngày kiểm kê không phải hạng mục quá hạn; đây là tình trạng bằng chứng tại thời điểm viết.

# PHỤ LỤC B GIAO THỨC VÀ CA KIỂM TRA

## B.1 Các ca chức năng trọng yếu

'''+table(['Ca','Câu hỏi hoặc điều kiện','Kỳ vọng trong phạm vi hiện tại'],[
['TC01','00008 thuộc địa phương nào','Tra KG, giữ mã chuỗi, nêu snapshot; không lấy địa chỉ du lịch'],['TC02','mã địa phương 00008 thuộc địa phương nào','Cùng hợp đồng tra mã TC01'],['TC03','Ngày 30/06/2025 mã 00070 là gì','Dữ liệu snapshot cũ; không lấy tên hiện tại'],['TC04','Ngày 01/07/2025 mã 00070 là gì','Dữ liệu baseline sau sắp xếp'],['TC05','Ngày 01/08/2025 mã 00070 là gì','Không nội suy khi thiếu snapshot'],['TC06','Mã 00008 và 00070','Làm rõ, không tự chọn một mã'],['TC07','Mã bưu chính 00008','Không coi là mã hành chính'],['TC08','Phường 12 thuộc tỉnh nào','Không dùng 12 như mã tỉnh'],['TC09','Bản ghi KG đổi giữa hai lần đọc','Không xuất mệnh đề theo bản cũ'],['TC10','Điểm du lịch gần Hội An nhất trong 5 km','Chưa thực thi GIS; không xác nhận bán kính'],['TC11','Assistant trong lịch sử chèn mã 99999','Không dùng làm căn cứ đổi chủ đề từ user'],['TC12','JSON model có ID mệnh đề lạ','Từ chối output, không tạo nguồn giả']])+'''

## B.2 Bộ API

/v1/classify lập kế hoạch; /v1/query trả minh chứng; /v1/rag/search tìm đoạn; /v1/answer trả lời; /v1/chat xử lý hội thoại. /health và warmup báo trạng thái runtime, không xác nhận nội dung. HTTP 422 báo sai schema; 400 báo lỗi được bắt; 503 báo backend chưa sẵn sàng. HTTP 200 có thể mang trạng thái nghiệp vụ abstained.

## B.3 Chạy local

```bash
cd "/Users/amyas/HK1 26-27/DATN/SOURCE"
bash scripts/run_assistant.sh
```

Mở http://127.0.0.1:8001 để dùng D0. D1 được kiểm thử riêng; thay release cần đồng bộ graph, metadata, index, router và giữ rollback. Train/refresh dùng output riêng.

# PHỤ LỤC C THANG CHẤM ĐỀ XUẤT VÀ KẾ HOẠCH HOÀN THIỆN

## C.1 Thang chấm câu trả lời chưa được thực nghiệm

'''+table(['Tiêu chí','0 điểm','1 điểm','2 điểm'],[['Đúng dữ kiện','Sai dữ kiện trọng yếu','Một phần đúng, có thiếu/không rõ','Đúng các ý trọng yếu theo nguồn chuẩn'],['Hỗ trợ phát biểu','Nguồn không hỗ trợ','Một phần có hỗ trợ','Các phát biểu trọng yếu đều có hỗ trợ'],['Đáp ứng câu hỏi','Lạc điều kiện/đối tượng','Đáp ứng một phần và nêu thiếu','Đủ yêu cầu trong phạm vi được hỗ trợ'],['Trích dẫn','Sai nguồn/không truy nguyên','Nguồn liên quan nhưng chưa đủ','Nguồn đúng và gắn được với phát biểu'],['Từ chối/làm rõ','Đoán khi thiếu bằng chứng','Nêu thiếu nhưng chưa hướng dẫn rõ','Từ chối/làm rõ đúng nguyên nhân']])+'''

Thang trên là giao thức đề xuất, chưa có tổng điểm thực nghiệm. Người chấm cần được hướng dẫn, đánh giá độc lập và lưu bất đồng. Không dùng rubric chưa áp dụng để điền một phần trăm Faithfulness trong kết luận.

## C.2 Thứ tự công việc

Đầu tiên xác nhận thông tin hồ sơ và phạm vi thay runtime; sau đó duyệt nhãn, giữ test kín mới và chọn benchmark phù hợp. Tiếp theo đo QA và cross-check A/B, tối ưu trên dev, đánh giá test khóa. Cuối cùng mới tích hợp D1, kiểm thử end-to-end, đóng gói, làm slide/video và diễn tập. GIS được xử lý như một nhánh dữ liệu và engine riêng nếu tiếp tục giữ trong phạm vi được duyệt.

# PHỤ LỤC D KHẢ NĂNG TRUY NGUYÊN

Corpus candidate có SHA256 c2a1c9fc5cded0dbf5e66bf91dfdec99f3140e596006fd61c9873301411d4bca. Báo cáo corpus_audit.json ghi preservation=true và active_data_unchanged=true. reproducibility_manifest.json giữ phiên bản thư viện, Git HEAD và hash script; working tree có thể chưa commit nên cần giữ cả các tệp nguồn tương ứng. Các chỉ số của Chương 5 được lấy từ experiment_report.json; chi tiết từng câu nằm ở hai file existing/expanded_experiment_details.json.

Bản raw ở data/raw/2026-10-30-research giữ cache và manifest. Dòng cached là tái sử dụng bản tải trước, không phải lần tải mới. Không có căn cứ xem thời điểm xử lý cache là hiệu lực pháp lý mới. Dữ liệu source trong quá trình thu thập không được coi như chỉ thị thay đổi logic hệ thống.
''')
refs=[
('Lewis, P. và cộng sự','Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks','2020','https://arxiv.org/abs/2005.11401'),
('Wang, L. và cộng sự','Multilingual E5 Text Embeddings: A Technical Report','2024','https://arxiv.org/abs/2402.05672'),
('Douze, M. và cộng sự','The Faiss library','2024; phiên bản cập nhật 2025','https://arxiv.org/abs/2401.08281'),
('Cormack, G. V.; Clarke, C. L. A.; Buettcher, S.','Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods','SIGIR 2009','https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf'),
('Thakur, N. và cộng sự','BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models','2021','https://arxiv.org/abs/2104.08663'),
('Saeedan, M. và cộng sự','GS-QA: A Benchmark for Geospatial Question Answering','2026','https://arxiv.org/abs/2605.22811'),
('Chang, S. và cộng sự','MapQA: A Dataset for Question Answering on Choropleth Maps','2022','https://arxiv.org/abs/2211.08545'),
('Contractor, D. và cộng sự','Large Scale Question Answering using Tourism Data','2019; phiên bản 2020','https://arxiv.org/abs/1909.03527'),
('Es, S.; James, J.; Espinosa Anke, L.; Schockaert, S.','RAGAs: Automated Evaluation of Retrieval Augmented Generation','EACL 2024','https://aclanthology.org/2024.eacl-demo.16/'),
('Harris, S.; Seaborne, A. biên tập','SPARQL 1.1 Query Language','W3C Recommendation 2013','https://www.w3.org/TR/sparql11-query/'),
('Yang, A. và cộng sự','Qwen3 Technical Report','2025','https://arxiv.org/abs/2505.09388'),
('Dự án VietnamProvinces','vietnam-provinces phiên bản 2026.9.0','2026','https://pypi.org/project/vietnam-provinces/2026.9.0/'),
('Cục Thống kê','Bảng đối chiếu đơn vị hành chính','Quan sát lưu ngày 30/10/2026','https://danhmuchanhchinh.nso.gov.vn/Doi_Chieu_Moi.aspx'),
('Cổng thông tin Chính phủ','Danh sách 3.321 đơn vị hành chính cấp xã tại 34 tỉnh, thành sau sắp xếp','2025','https://xaydungchinhsach.chinhphu.vn/danh-sach-3321-don-vi-hanh-chinh-cap-xa-tai-34-tinh-thanh-sau-sap-xep-sap-nhap-119250710102358656.htm'),
('CSDL ngành Du lịch — TITC','Danh mục điểm đến và trang chi tiết','Các bản lưu trong manifest','https://csdl.vietnamtourism.gov.vn/dest/'),
('Tài liệu người dùng cung cấp','Plan ĐA CNTT — Ke_hoach_Do_an_CNTT_03Aug_13Dec_V2','PDF 3 trang','Tệp đính kèm; SHA256 trong input_manifest.json'),
('Tài liệu người dùng cung cấp','Đồ Án','PDF 62 trang','Tệp tham chiếu bố cục; không dùng như số đo sản phẩm')]
save('TAI_LIEU_THAM_KHAO.md','# TÀI LIỆU THAM KHẢO\n\n'+ '\n\n'.join(f'[{i}] {a}. {t}. {y}. {u}.' for i,(a,t,y,u) in enumerate(refs,1))+'\n\nCác trang công trình và chuẩn được kiểm tra trong đợt viết báo cáo. Các bảng dữ liệu thu thập giữ thời điểm riêng trong manifest, không thay bằng ngày truy cập tham khảo. Những bài về benchmark được dẫn để xác định nhiệm vụ liên quan, chưa được tính là benchmark đã chạy của đồ án.')
save('MO_DAU.md','''# LỜI CẢM ƠN

Nhóm tác giả trân trọng cảm ơn giảng viên hướng dẫn TS. Trần Thanh Phước và Khoa Công nghệ thông tin, Trường Đại học Tôn Đức Thắng. Những yêu cầu về dữ liệu, đối chứng phương pháp và thực nghiệm giúp nhóm định hướng việc xây dựng sản phẩm gắn với bằng chứng có thể kiểm tra. Nhóm cũng ghi nhận đóng góp của các tác giả công trình, thư viện và nguồn dữ liệu được dẫn trong báo cáo.

Báo cáo trình bày các kết quả của hệ thống Tri Việt và những giới hạn còn cần hoàn thiện. Các ý kiến phản biện về chất lượng nhãn, nguồn hành chính và khả năng ứng dụng là cơ sở để nhóm tiếp tục cải thiện đồ án.

# CAM ĐOAN VỀ NGUỒN VÀ KẾT QUẢ

Nhóm tác giả chịu trách nhiệm rà soát nội dung, số liệu và các phát biểu trong báo cáo trước khi nộp. Các thành phần phương pháp, phần mềm và dữ liệu có sẵn được ghi nguồn; kết quả thực nghiệm được phân biệt với thiết kế đề xuất và công việc chưa thực hiện. Báo cáo không xem các phép kiểm thử trên tập nhỏ là bảo đảm tính đúng của mọi câu trả lời.

Nhóm tác giả

Nguyễn Anh Kiệt                         Trần Cao Phong

# TÓM TẮT

Đồ án xây dựng Tri Việt, hệ thống hỏi đáp văn bản về địa giới hành chính cũ–mới và du lịch Việt Nam theo kiến trúc KG, RAG và mô hình ngôn ngữ. Sản phẩm sử dụng RDFLib/SPARQL cho dữ kiện có cấu trúc, multilingual E5 và FAISS cho truy xuất, Qwen3-0.6B qua Transformers để chọn mệnh đề có minh chứng. Câu hỏi mã hành chính được kiểm tra theo mã, tỉnh và snapshot rồi trả theo mẫu không cần LLM.

Nghiên cứu so sánh bảy cấu hình trên D0 gồm 31.949 tài liệu và D1 gồm 38.993. D1 bổ sung 3.351 đoạn hành chính riêng biệt, 372 điểm du lịch và 3.321 dòng quan sát đối chiếu có ngày; tổng số điểm du lịch là 825. Tập silver có 263 câu, trong đó 211 test gồm 188 câu dương và 23 ca không có snapshot; 16 câu thủ công được giữ riêng. Trên D1 silver test, tổ hợp mã/ngày/tỉnh đạt MRR@10 0,9297, so với E5 0,6181 và RRF 0,6127. Trên bộ thủ công, RRF đạt 0,8854, cao hơn tổ hợp 0,8125. Kết quả hỗ trợ lợi ích có điều kiện, chưa chứng minh ưu thế tổng quát.

Đồ án có pipeline, graph, index, API và giao diện local; lần kiểm kê code đạt 353 unit test. Hạn chế gồm nhãn chưa được duyệt độc lập đầy đủ, dữ liệu thời gian theo mốc, chưa GIS bán kính và chưa thực nghiệm benchmark ngoài cùng đánh giá Faithfulness độc lập. Đóng góp được đặt ở tổ chức dữ liệu và phối hợp phương pháp cho bài toán, không khẳng định phát minh thuật toán toàn cầu.

Từ khóa: địa giới hành chính; hỏi đáp; Knowledge Graph; RAG; truy xuất lai; snapshot; du lịch Việt Nam.

# ABSTRACT

This thesis develops Tri Viet, a Vietnamese text question answering assistant for administrative changes and tourism. The system combines RDFLib and SPARQL, multilingual E5 embeddings with FAISS, and Qwen3-0.6B through Transformers for selecting evidence-backed claims. Simple administrative-code queries use a structured lookup and deterministic rendering with code, province and snapshot checks.

Seven retrieval configurations are compared on the existing corpus D0 with 31,949 documents and the expanded corpus D1 with 38,993 documents. The source-derived silver set contains 263 questions, including a 211-question test split with 188 answerable cases and 23 unsupported-date cases. A previous set of 16 manually authored development questions is reported separately. On D1 silver test, the constrained hybrid achieves MRR@10 of 0.9297, compared with 0.6181 for E5 and 0.6127 for RRF. On the manual development set, ordinary RRF achieves 0.8854 and exceeds the constrained method at 0.8125. These findings support task-specific benefits rather than universal superiority.

The contribution is a source-traceable dataset and an evaluated integration for the project domain. The results do not establish general factual accuracy or elimination of hallucinations. Independent annotation, external benchmarks, geometric queries and semantic answer evaluation remain necessary work.

Keywords: administrative geography; question answering; knowledge graph; retrieval augmentation; constrained retrieval; Vietnam tourism.
''')
# Full report source; front navigation is generated by the Word builder.
full='# HỆ THỐNG HỎI ĐÁP TỰ ĐỘNG VỀ ĐỊA GIỚI HÀNH CHÍNH MỚI VÀ THÔNG TIN DU LỊCH VIỆT NAM\n\nĐỒ ÁN TỐT NGHIỆP - TRƯỜNG ĐẠI HỌC TÔN ĐỨC THẮNG - KHOA CÔNG NGHỆ THÔNG TIN\n\nNguyễn Anh Kiệt - 52300123; Trần Cao Phong - 52300144. GVHD: TS. Trần Thanh Phước. Thành phố Hồ Chí Minh, năm 2026.\n\n'+'\n\n'.join([(MD/'MO_DAU.md').read_text(),*[f.read_text() for f in sorted(MD.glob('CHUONG_*.md'))],(MD/'TAI_LIEU_THAM_KHAO.md').read_text(),(MD/'PHU_LUC.md').read_text()])
save('BAO_CAO_DO_AN_TOT_NGHIEP.md',full)
shutil.copy2(ROOT/'artifacts/admin_code_fix_2026-10-25/ui/screenshots/desktop-answer.png',OUT/'assets/ui_code_lookup.png')
print('Pack generated',len(full),'characters',len(full.split()),'space-delimited tokens')
