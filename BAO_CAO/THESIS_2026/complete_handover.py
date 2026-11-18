"""Assemble handover evidence from actual validation outputs, without grading QA."""
from pathlib import Path
import csv
import hashlib
import json
import sqlite3

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
RELEASE = ROOT / 'artifacts/research_expansion_2026-10-30'
VALIDATION = ROOT / 'artifacts/research_validation_2026-11-18'
read = lambda path: json.loads(path.read_text())
backend = read(VALIDATION / 'backend_report.json')
ui = read(VALIDATION / 'ui/ui_report.json')
latency = read(VALIDATION / 'latency_report.json')
assert backend['passed'] and backend['passed_cases'] == 65
assert ui['passed'] and ui['check_count'] == 33
assert latency['expected_statuses_passed']
assert backend['health']['retrieval_mode'] == 'full_faiss'

paths = [RELEASE / 'data/structured_records.jsonl', RELEASE / 'data/rag_dataset_final.jsonl',
         RELEASE / 'artifacts/kg/vn_knowledge_graph.ttl', RELEASE / 'artifacts/router/router.joblib',
         RELEASE / 'artifacts/faiss/vn.index', RELEASE / 'artifacts/faiss/metadata.sqlite3',
         RELEASE / 'artifacts/faiss/index_config.json', ROOT / 'SOURCE/evaluation/system_queries.json',
         ROOT / 'SOURCE/scripts/verify_system.py', ROOT / 'SOURCE/scripts/verify_ui.py',
         ROOT / 'SOURCE/scripts/measure_runtime.py', BASE / 'unit_audit.xml']
with sqlite3.connect((RELEASE / 'artifacts/faiss/metadata.sqlite3').as_uri() + '?mode=ro', uri=True) as connection:
    integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
    vectors, documents = connection.execute('SELECT COUNT(*), COUNT(DISTINCT doc_id) FROM chunks').fetchone()
assert (integrity, vectors, documents) == ('ok', 41280, 38993)
manifest = {
    'validation_date': '2026-11-18', 'release': str(RELEASE.relative_to(ROOT)),
    'configuration': {'port': 8011, 'dataset': str(paths[0].relative_to(ROOT)),
        'kg': str(paths[2].relative_to(ROOT)), 'router': str(paths[3].relative_to(ROOT)),
        'index': str(paths[4].relative_to(ROOT)), 'metadata': str(paths[5].relative_to(ROOT))},
    'checks': {'http_passed': backend['passed_cases'], 'http_cases': len(backend['cases']),
        'ui_checks': ui['check_count'], 'sqlite_integrity': integrity, 'vectors': vectors, 'documents': documents},
    'scope': 'Isolated D1 compatibility validation and sequential development latency; default D0 unchanged. No independent factuality, concurrency, cloud or GIS certification.',
    'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
}
(VALIDATION / 'validation_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

# Actual responses are available for independent human review. Scores stay empty.
fields = ['id', 'question', 'answer', 'status', 'citation_urls', 'reviewer', 'factuality_0_2',
          'faithfulness_0_2', 'completeness_0_2', 'citation_0_2', 'abstention_0_2', 'notes']
with (VALIDATION / 'answer_review.csv').open('w', newline='', encoding='utf-8-sig') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for item in backend['cases']:
        response = item['response']
        if item['http_status'] != 200:
            continue
        writer.writerow({'id': item['id'], 'question': item['question'], 'answer': response.get('answer', ''),
            'status': response.get('status', ''),
            'citation_urls': ' | '.join(c.get('source_url') or '' for c in response.get('citations', []))})

rows = '\n'.join(f"| {case['id']} | {case['http_ms']['n']} | {case['http_ms']['p50']:.3f} | {case['http_ms']['p95']:.3f} |"
                 for case in latency['cases'])
doc = f'''# Nghiệm thu kỹ thuật D1 ngày 18/11/2026

D1 đã được khởi chạy riêng tại cổng 8011 với corpus, graph, router và FAISS của release research_expansion_2026-10-30. Không thay dữ liệu mặc định D0. Cùng bộ ca phát triển được dùng để kiểm tra tương thích; đây chưa phải benchmark QA độc lập.

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Unit toàn bộ | 353/353 | unit_audit.xml trong bộ báo cáo |
| HTTP với E5/Qwen thật | 65/65 | backend_report.json |
| Chromium desktop/mobile | 33/33 kiểm tra; 2 trao đổi backend thật, các lỗi còn lại có mô phỏng | ui/ui_report.json |
| SQLite integrity | {integrity} | validation_manifest.json |
| Metadata D1 | {vectors:,} vectors; {documents:,} tài liệu | validation_manifest.json |
| Runtime health | full_faiss; LLM sẵn sàng | backend_report.json |

## Độ trễ sơ bộ

Mỗi câu bỏ một lượt warmup, sau đó gửi tuần tự năm yêu cầu. Phép đo chính được thực hiện sau khi bộ UI đã kết thúc. Đơn vị mili giây; p95 theo nearest rank với n = 5 gần như giá trị lớn nhất, không phải ước lượng vững cho sản phẩm. Khởi tạo mô hình được ghi riêng. Các pha question_processing, generation, kg_refresh, cross_check và total nằm trong JSON; encode/search chưa được tách. Thiết bị mô hình: {backend['health']['llm']['device']}; máy {latency['machine']}.

| Ca phát triển | Số lượt | HTTP p50 ms | HTTP p95 ms |
|---|---|---|---|
{rows}

Không so sánh độ trễ này với ranking_ms trong harness truy xuất. Không có tải đồng thời, máy độc lập hoặc triển khai cloud trong phép đo.

## Tái lập

Từ SOURCE, đặt các biến môi trường tương ứng manifest trước khi chạy server. Các đường dẫn bên dưới được tính từ SOURCE:

```bash
export DATASET_PATH=../artifacts/research_expansion_2026-10-30/data/structured_records.jsonl
export KG_TTL_PATH=../artifacts/research_expansion_2026-10-30/artifacts/kg/vn_knowledge_graph.ttl
export ROUTER_MODEL_PATH=../artifacts/research_expansion_2026-10-30/artifacts/router/router.joblib
export FAISS_INDEX_PATH=../artifacts/research_expansion_2026-10-30/artifacts/faiss/vn.index
export FAISS_METADATA_PATH=../artifacts/research_expansion_2026-10-30/artifacts/faiss/metadata.sqlite3
../.venv/bin/python -m vn_assistant.cli serve --port 8011
```

Terminal khác, cũng từ SOURCE, chạy lần lượt để không gây nhiễu phép đo:

```bash
../.venv/bin/python scripts/verify_system.py --url http://127.0.0.1:8011 --output ../artifacts/new_validation/backend_report.json
../.venv/bin/python scripts/verify_ui.py --url http://127.0.0.1:8011 --output ../artifacts/new_validation/ui
../.venv/bin/python scripts/measure_runtime.py --url http://127.0.0.1:8011 --output ../artifacts/new_validation/latency_report.json
```

Không khởi động mặc định D0 trong shell còn các biến D1. Chọn thư mục output mới để bảo toàn kết quả lịch sử.

## Phần cần người đánh giá

answer_review.csv chứa câu hỏi, câu trả lời và URL thật của lần chạy, các cột điểm để trống. Hai người chấm cần sao chép phiếu riêng, kiểm tra nguồn, ghi bất đồng và tổng hợp theo rubric phụ lục C. Chưa có điểm Faithfulness/factuality nào được suy ra từ 65 ca HTTP. G01, G02, G03, G05 và các phần pháp lý/GIS/triển khai độc lập còn cần thực hiện đúng tiêu chí trong backlog.
'''
(BASE / 'markdown/11_NGHIEM_THU_D1.md').write_text(doc)
(VALIDATION / 'README.md').write_text(doc.replace('unit_audit.xml trong bộ báo cáo', '../../BAO_CAO/THESIS_2026/unit_audit.xml'))
print({'http': 65, 'ui': 33, 'vectors': vectors, 'documents': documents, 'review_scores': 'empty pending human annotation'})
