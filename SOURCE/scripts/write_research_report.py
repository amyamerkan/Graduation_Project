"""Generate reviewable thesis tables from measured results, never estimates."""
import argparse
import csv
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
from vn_assistant.dataio import iter_records


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);a=p.parse_args();r=a.release
    audit=json.loads((r/'corpus_audit.json').read_text()); exp=json.loads((r/'experiment_report.json').read_text())
    names={'tfidf':'TF-IDF','bm25':'BM25','dense_e5':'E5','rrf':'BM25 + E5 / RRF',
        'rrf_domain':'RRF + miền','rrf_domain_province':'RRF + miền + tỉnh',
        'proposed_temporal_province_rrf':'Đề xuất: RRF + mã/ngày/tỉnh'}
    lines=['# Dữ liệu và thực nghiệm sơ bộ — mở rộng 30–31/10/2026','',
        'Bản nghiên cứu riêng, chưa thay bộ dữ liệu của ứng dụng. Các số dưới đây đọc trực tiếp từ JSON kết quả.', '',
        '## 1. Đối chiếu ba yêu cầu giảng viên','',
        '| Yêu cầu | Hiện thực và bằng chứng |','|---|---|',
        '| (1) Dữ liệu/phương pháp có sẵn, kết quả sơ bộ | D0: corpus dự án trước mở rộng; TF-IDF, BM25, E5, RRF; bảng kết quả D0 bên dưới. Danh mục cộng đồng vietnam-provinces là nguồn công khai đã có, không phải dữ liệu do tác giả tự điều tra. |',
        '| (2) Xây dựng dữ liệu mới và thử nhiều phương pháp | D1: D0 + đoạn sắp xếp từ Chính phủ + điểm du lịch mới + quan sát bảng đối chiếu có ngày; cùng bảy cấu hình và cùng câu hỏi trên D0/D1. |',
        '| (3) Đề xuất lai và thực nghiệm | Tách miền, ánh xạ tên tỉnh cũ/mới, điều kiện mã/ngày rồi RRF; có ablation bỏ điều kiện thời gian/tỉnh, dữ liệu cũ/mới, và bootstrap theo nhóm thực thể. Đây là đóng góp tích hợp cho bài toán; chưa chứng minh thuật toán mới trên thế giới. |', '',
        '## 2. Kiểm kê dữ liệu','',f"- D0: **{audit['previous_documents']:,}** tài liệu. D1: **{audit['documents']:,}** tài liệu.",
        f"- Thêm **{audit['new_distinct_legal_passages']:,}** đoạn hành chính sau loại **{audit['punctuation_numbering_duplicates_removed']:,}** bản trùng dấu câu/số thứ tự; nguyên văn được giữ, gộp URL nguồn bổ sung.",
        f"- Thêm **{audit['new_destinations']:,}** điểm tham quan/trải nghiệm; tổng **{audit['types']['tourism_place']:,}** điểm, phủ **{len(audit['tourism_by_province'])}** tỉnh/thành theo bộ lọc nguồn.",
        f"- Thêm **{audit['new_dated_table_observations']:,}** dòng quan sát bảng NSO tại 30/10/2026; đây không phải 3.321 sự kiện thay đổi mới.",
        '- Snapshot nền: 30/06/2025, 01/07/2025, 24/10/2026. Quan sát 30/10/2026 được giữ riêng, không suy ra khoảng hiệu lực liên tục.',
        '- Địa chỉ du lịch giữ đúng câu nguồn, có thể còn huyện/tỉnh cũ; không tự gán xã mới. Chuyển một phần địa bàn không được coi là nhập toàn bộ.',
        '- Giữ toàn bộ ID/nội dung D0; không sửa archives. Bản raw và manifest SHA256 ở `data/raw/2026-10-30-research/`.', '',
        '## 3. Thiết kế thực nghiệm','',
        f"- **{exp['gold_cases']} câu silver** sinh từ khóa/mã/ngày/tên điểm và đoạn nguồn; chia dev/test theo nhóm thực thể bằng SHA256. Các snapshot cùng mã không đi sang hai split.",
        '- Giữ riêng 16 câu phát triển thủ công từ đợt trước; không gọi đó là benchmark độc lập. Dữ liệu đã có trong dự án không đồng nghĩa bộ test chuẩn công khai.',
        '- Query encoder E5 pretrained, không fine-tune. BM25 dùng k1=1.2, b=0.75; RRF k=60; tối đa 200 chunk ứng viên mỗi nguồn, gộp thành tài liệu rồi đánh giá top 10.',
        '- Baseline cùng corpus/chunk; các bước ràng buộc là ablation riêng. Điều kiện chỉ trích từ câu hỏi và metadata, không đọc nhãn đáp án.',
        '- Bộ phân miền của D0 được đóng băng và dùng chung trên D0/D1 để tách tác động corpus; router train lại của D1 được đánh giá riêng.',
        '- D0/D1 chạy cùng tập câu; D0 thiếu tài liệu mới nên cần đọc thêm bảng “câu hỏi cũ” để tách tác động phủ dữ liệu khỏi năng lực thuật toán.',
        '- Hit@k/MRR/nDCG là truy xuất theo nhãn dương đã biết, không phải độ đúng câu trả lời cuối. Query tỉnh có nhiều đáp án nên đọc thêm known-positive Recall@10 trong JSON.',
        '- Ca thiếu snapshot đo tỷ lệ từ chối. Baseline tìm kiếm thường luôn trả kết quả nên chưa có cơ chế từ chối; đây là so sánh thêm chính sách an toàn, không chỉ xếp hạng.',
        '- `ranking_ms` đo cả pipeline các ranker cùng lúc, bỏ thời gian mã hóa query; không dùng để tuyên bố phương pháp nào nhanh hơn.', '']
    for label in ('existing','expanded'):
        lines += [f'## 4. Kết quả {label} — silver test','', '| Phương pháp | Hit@1 | Hit@5 | MRR@10 | nDCG@10 | Từ chối đúng ca thiếu ngày |','|---|---:|---:|---:|---:|---:|']
        for method, parts in exp['datasets'][label]['summary'].items():
            m=parts['test'];fmt=lambda x:'—' if x is None else f'{x:.4f}'
            lines.append('| '+names[method]+' | '+' | '.join(fmt(m[k]) for k in ('hit_at_1','hit_at_5','mrr_at_10','ndcg_at_10','abstention_accuracy'))+' |')
        lines += ['',f"Độ phủ đầy đủ nhãn dương: {exp['datasets'][label]['known_positive_coverage']:.2%}. Câu test có đáp án: {m['answerable']}; không có snapshot: {m['unanswerable']}.",'']
    lines += ['## 5. Chỉ các câu hỏi đã có trước mở rộng — silver test','', '| Phương pháp | D0 MRR@10 | D1 MRR@10 |','|---|---:|---:|']
    for method in names:
        lines.append(f"| {names[method]} | {exp['datasets']['existing']['old_questions'][method]['mrr_at_10']:.4f} | {exp['datasets']['expanded']['old_questions'][method]['mrr_at_10']:.4f} |")
    lines += ['', '## 6. Bộ phát triển thủ công trước đó — tách khỏi silver','', '| Phương pháp | D0 MRR@10 | D1 MRR@10 |','|---|---:|---:|']
    for method in names:
        m0=exp['datasets']['existing']['manual_development'][method]['mrr_at_10'];m1=exp['datasets']['expanded']['manual_development'][method]['mrr_at_10']
        lines.append(f'| {names[method]} | {m0:.4f} | {m1:.4f} |')
    lines += ['', '### Kết quả D1 theo loại câu — tránh che lỗi bằng điểm tổng','',
        '| Phương pháp | Mã/ngày MRR | Điểm đến MRR | Đoạn sắp xếp MRR | Theo tỉnh nDCG |','|---|---:|---:|---:|---:|']
    for method in names:
        slices=exp['datasets']['expanded']['slices'][method]
        values=[slices[k][metric] for k,metric in [('temporal_code','mrr_at_10'),('destination','mrr_at_10'),('merger_clause','mrr_at_10'),('province_destinations','ndcg_at_10')]]
        lines.append('| '+names[method]+' | '+' | '.join('—' if v is None else f'{v:.4f}' for v in values)+' |')
    train=json.loads((r/'training_report.json').read_text())
    lines += ['', '### Huấn luyện router và kiểm tra KG','',
        f"Router TF-IDF/Logistic Regression train lại với {train['router_train']['training_rows']} câu; tập phát triển {train['router_evaluation']['cases']} câu có joint accuracy sau quy tắc {train['router_evaluation']['joint_accuracy']:.4f}. Đây là tập nhỏ đã dùng phát triển, không phải test kín.",
        f"KG development accuracy: {train['kg_evaluation']['accuracy']:.4f}; legal passages mới là minh chứng văn bản, không tự chuyển thành cạnh sáp nhập suy diễn. E5 chỉ tạo embedding; không fine-tune E5/Qwen.",'']
    lines += [f"Router D0 chạy lại với cùng code/quy tắc hiện tại: joint accuracy {exp['existing_router_evaluation']['joint_accuracy']:.4f}. Một nhãn cũ kỳ vọng hybrid cho câu hỏi vừa có mã/ngày vừa yêu cầu mô tả; quy tắc tra mã hiện ưu tiên kg và trả phần chưa đủ mô tả là partial. Giữ nguyên điểm/nhãn gốc trong báo cáo, không sửa gold để tăng accuracy.",'']
    lines += ['### Diễn giải kết quả sơ bộ','',
        '- Ràng buộc mã/ngày có lợi thế rõ trên câu hỏi mã chính xác; đây là lợi ích của tra cứu cấu trúc kết hợp IR, không chứng minh embedding được cải thiện.',
        '- E5 riêng tốt hơn RRF/đề xuất trên nhóm mô tả điểm đến và đoạn sắp xếp trong lượt đo này. Không nên thay mọi truy vấn ngữ nghĩa bằng cùng một công thức lai chỉ vì điểm tổng tốt.',
        '- Trên 16 câu thủ công, RRF thường tốt hơn đề xuất có ràng buộc. Đây là phản chứng cần giữ và phân tích trước khi áp dụng rộng.',
        '- Điểm tổng D1 tăng một phần vì D0 chưa có tài liệu mới. Ở nhóm câu cũ, một số phương pháp giảm điểm sau mở rộng; bổ sung dữ liệu không bảo đảm chất lượng tăng ở mọi câu.',
        '- Nhãn dương đã biết chưa bao phủ mọi nguồn mới tương đương; ví dụ hai quan sát NSO cùng mã có thể đều phù hợp câu không hỏi ngày. Vì vậy cần duyệt nguồn trong CSV trước khi diễn giải một thứ hạng sai là sai nội dung.',
        '- Không chọn lại trọng số/cấu hình sau khi xem test trong đợt này. Bước tiếp theo là phát triển trên dev, rồi dùng tập test kín mới do người duyệt gán nhãn.', '']
    lines += ['', '## 7. Độ bất định và giới hạn','']
    for method,m in exp['paired_bootstrap'].items():
        lines.append(f"- Đề xuất trừ {names[method]}, ΔMRR={m['delta_mrr']:.4f}; khoảng percentile 95% [{m['percentile_95_ci'][0]:.4f}, {m['percentile_95_ci'][1]:.4f}], bootstrap 1.000 lần theo {m['entity_groups']} nhóm thực thể.")
    lines += ['', '- Kết quả silver có thể ưu ái tra mã chính xác, tên điểm và mẫu câu; không suy rộng thành accuracy thực tế hay kết luận đề xuất tốt hơn mọi phương pháp.',
        '- Cần người gán nhãn/duyệt độc lập file `annotation_review.csv`, bổ sung câu hỏi tự nhiên, tên trùng, ngày ngoài snapshot, địa chỉ thiếu cấp, chuyển một phần; giữ test kín trước khi điều chỉnh tham số.',
        '- Chưa thực nghiệm sinh câu trả lời dài, factuality thủ công, reranker cross-encoder, GIS/polygon hoặc một benchmark công khai độc lập như BEIR. Không báo các việc này là đã làm.', '',
        '## 8. Nguồn và công trình liên quan','',
        '- [Bảng đối chiếu NSO](https://danhmuchanhchinh.nso.gov.vn/Doi_Chieu_Moi.aspx): nguồn hành chính chính thức; lưu ngày quan sát và ngày cột đối chiếu, chưa độc lập xác minh từng văn bản hiệu lực.',
        '- [Tổng hợp đơn vị cấp xã và liên kết toàn văn nghị quyết](https://xaydungchinhsach.chinhphu.vn/danh-sach-3321-don-vi-hanh-chinh-cap-xa-tai-34-tinh-thanh-sau-sap-xep-sap-nhap-119250710102358656.htm): trích đoạn nguyên văn, giữ URL và phần chuyển một phần.',
        '- [CSDL ngành Du lịch](https://csdl.vietnamtourism.gov.vn/dest/): truy vấn theo tỉnh, phân trang và URL chi tiết; thời gian địa chỉ có thể khác danh mục hành chính mới.',
        '- [vietnam-provinces 2026.9.0](https://pypi.org/project/vietnam-provinces/2026.9.0/): nguồn cộng đồng của dữ liệu nền, cần tuân thủ giấy phép GPL-3.0-or-later khi phân phối theo điều kiện áp dụng.',
        '- [Multilingual E5, Wang et al.](https://arxiv.org/abs/2402.05672): nền tảng embedding được sử dụng.',
        '- [RRF, Cormack et al., SIGIR 2009](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf): phép gộp hạng có sẵn, không phải phần mới do đồ án phát minh.',
        '- [BEIR, Thakur et al.](https://arxiv.org/abs/2104.08663): tham khảo thiết kế so sánh lexical/dense và đánh giá đa bộ dữ liệu; chưa chạy BEIR trong đợt này.',
        '- Truy cập công khai không tự động đồng nghĩa mọi bài viết/ảnh có giấy phép mở. Manifest lưu nguồn để truy nguyên; đợt này không thu ảnh.', '',
        '## 9. Tái lập','', 'Chạy từ `DATN/SOURCE`; dùng môi trường `.venv` và trọng số E5 đã tải. Các lệnh ghi vào release riêng:', '', '```bash',
        '../.venv/bin/python scripts/collect_research_expansion.py --output ../artifacts/research_expansion_2026-10-30 --tourism-pages 4',
        '../.venv/bin/python scripts/finalize_research_corpus.py --release ../artifacts/research_expansion_2026-10-30',
        '../.venv/bin/python scripts/retrain_domain_refresh.py --release ../artifacts/research_expansion_2026-10-30',
        '../.venv/bin/python scripts/refresh_vectors.py --dataset ../artifacts/research_expansion_2026-10-30/data/rag_dataset_final.jsonl --seed ../artifacts/faiss --output ../artifacts/research_expansion_2026-10-30/artifacts/faiss --device mps',
        '../.venv/bin/python scripts/run_research_experiments.py --release ../artifacts/research_expansion_2026-10-30 --device mps',
        '```', '', 'Thư mục FAISS output phải chưa có index khi rebuild; chọn phiên bản/thư mục mới để chạy lại. Không tự đè artifacts đang dùng. Các raw đã cache được tái sử dụng và manifest ghi `cached`; không coi đó là lần tải mới trên mạng.', '']
    (r/'RESEARCH_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    rows=json.loads((r/'expanded_experiment_details.json').read_text())['proposed_temporal_province_rrf']
    records={x['record_id']:x for x in iter_records(r/'data/structured_records.jsonl')}
    with (r/'annotation_review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=['id','question','split','kind','relevant_doc_ids','retrieved','rank','source_url','evidence_preview','human_approved','corrected_ids','notes']);w.writeheader()
        for row in rows:
            entry={k:json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],list) else row[k] for k in ('id','question','split','kind','relevant_doc_ids','retrieved','rank')}
            sources=[records[d] for d in row['relevant_doc_ids'][:3] if d in records]
            entry.update(source_url=' | '.join(s['source_url'] for s in sources),evidence_preview=' | '.join(s['data']['description'][:700] for s in sources))
            w.writerow(entry)
    manifest=dict(packages={p:version(p) for p in ('numpy','scikit-learn','faiss-cpu','sentence-transformers','vietnam-provinces')},
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        code_state='working tree includes uncommitted changes; retain script hashes with results',dataset_sha256=audit['dataset_sha256'])
    import hashlib
    manifest['script_sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(__file__).parent.glob('*research*.py')}
    (r/'reproducibility_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(r/'RESEARCH_REPORT.md')


if __name__=='__main__':main()
