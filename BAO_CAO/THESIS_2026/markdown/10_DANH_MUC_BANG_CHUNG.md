# Danh mục bằng chứng

Các đường dẫn dưới đây tính từ DATN. Hash được giữ trong evidence_manifest.json; không hiển thị .env hoặc thông tin bí mật.

| Tệp | Có trong kiểm kê |
|---|---|
| SOURCE/src/vn_assistant/router.py | True |
| SOURCE/src/vn_assistant/administrative_codes.py | True |
| SOURCE/src/vn_assistant/question_processing.py | True |
| SOURCE/src/vn_assistant/generation.py | True |
| SOURCE/src/vn_assistant/cross_check.py | True |
| SOURCE/src/vn_assistant/api.py | True |
| SOURCE/scripts/run_research_experiments.py | True |
| artifacts/research_expansion_2026-10-30/corpus_audit.json | True |
| artifacts/research_expansion_2026-10-30/experiment_report.json | True |
| artifacts/research_expansion_2026-10-30/training_report.json | True |
| artifacts/admin_code_fix_2026-10-25/backend_report.json | True |
| artifacts/admin_code_fix_2026-10-25/ui/ui_report.json | True |

PDF đầu vào có đường dẫn, số trang và SHA256 ở input_manifest.json. Thời điểm báo cáo cũ được giữ nguyên; không đặt lại ngày để giả thành chạy mới. Unit audit của đợt viết báo cáo nằm tại BAO_CAO/THESIS_2026/unit_audit.xml. Các báo cáo active và candidate có phạm vi khác nhau, cần đọc scope/metric_scope trước khi dùng số.
