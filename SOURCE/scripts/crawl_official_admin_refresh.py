"""Archive official administrative tables and their explicitly dated comparison rows."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from vn_assistant.corpus_update import PublicCrawler, _record, write_jsonl
from vn_assistant.normalization import clean_text

NSO = "https://danhmuchanhchinh.nso.gov.vn/"
COMPARE = NSO + "Doi_Chieu_Moi.aspx"
BASELINE = "https://baochinhphu.vn/bang-danh-muc-va-ma-so-cua-34-tinh-thanh-moi-3321-don-vi-hanh-chinh-cap-xa-moi-102250704153652947.htm"


def table_rows(soup, selector):
    return [[clean_text(c.get_text(" ", strip=True)) for c in r.find_all("td", recursive=False)]
            for r in soup.select(selector)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    crawler = PublicCrawler(args.output / "admin_http_cache")
    rows = table_rows(crawler.get(NSO), 'table[id$="grid1N_DXMainTable"] tr[id*="DXDataRow"]')
    provinces = [{"code": r[1], "name": r[2], "division_type": r[4], "legal_reference": r[5]}
                 for r in rows if len(r) == 6 and r[1].isdigit()]
    if len(provinces) != 34:
        raise ValueError("Official current province table is incomplete")
    article = crawler.get(BASELINE)
    baseline = []
    for row in table_rows(article, ".detail-content table tr"):
        if len(row) == 3 and row[1].isdigit() and len(row[1]) == 2:
            baseline.append({"code": row[1], "name": row[2]})
    if len(baseline) != 34:
        raise ValueError("Official 2025 province table is incomplete")
    # Check robots with the same crawler before using the site's visible pagination.
    crawler.get(COMPARE)
    snapshots, manifest = [], []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        # Legacy DevExpress uses browser sniffing; keep Chromium's real User-Agent.
        page = browser.new_page()
        page.goto(COMPARE, wait_until="networkidle", timeout=90000)
        grid = 'table[id$="gridXa_DXMainTable"] tr[id*="DXDataRow"]'
        page.wait_for_selector(grid)
        observed = page.locator('input[name="ctl00$PlaceHolderMain$txtNgay"]').input_value()
        reference = page.locator('input[name="ctl00$PlaceHolderMain$txtNgayDC"]').input_value()
        for number in range(1, 6):
            if number > 1:
                previous = page.locator(grid).first.inner_text()
                page.locator(f'td[onclick="aspxGVPagerOnClick(\'ctl00_PlaceHolderMain_gridXa\',\'PN{number-1}\');"]').first.click()
                page.wait_for_function("previous => document.querySelector('table[id$=\"gridXa_DXMainTable\"] tr[id*=\"DXDataRow\"]').innerText !== previous", arg=previous, timeout=90000)
                page.wait_for_timeout(1000)
            body = page.content().encode("utf-8")
            filename = f"nso_comparison_page_{number}.html"
            (args.output / filename).write_bytes(body)
            manifest.append({"url": COMPARE, "page": number, "file": filename,
                             "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                             "retrieved_at": datetime.now(timezone.utc).isoformat(),
                             "request_scope": "visible grid pagination; rendered DOM"})
            parsed = table_rows(BeautifulSoup(body, "html.parser"), grid)
            snapshots.extend(r for r in parsed if len(r) == 13 and r[2].isdigit())
            print(json.dumps({"page": number, "rows": len(parsed)}), flush=True)
        browser.close()
    if len(snapshots) != 3321 or len({r[2] for r in snapshots}) != 3321:
        raise ValueError("Official comparison pagination has missing or duplicate wards")
    references = []
    for r in snapshots:
        description = (f"Bảng đối chiếu Cục Thống kê: {r[3]}, mã {r[2]}, thuộc {r[1]} ({r[0]}), "
                       f"được tra cứu đến ngày {observed}. Cột đối chiếu tại {reference}: {r[6]}, mã {r[7]}, "
                       f"thuộc {r[10]} ({r[11]}). Văn bản được bảng ghi: {r[4]}. "
                       f"Ngày áp dụng được bảng ghi: {r[5]}. Ghi chú thay đổi: {r[12]}")
        data = {"name": r[3], "code": r[2], "province_code": r[0], "province_name": r[1],
                "description": description, "observed_date": observed, "reference_date": reference,
                "reference_name": r[6], "reference_code": r[7], "reference_province_code": r[11],
                "reference_province_name": r[10], "legal_reference": r[4], "recorded_date": r[5],
                "change_note": r[12], "country": "VN", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "extraction_scope": "official comparison row; narrative is not parsed into inferred merger edges"}
        references.append(_record("administrative_reference", data, source="Cục Thống kê — đối chiếu ĐVHC", url=COMPARE))
    write_jsonl(args.output / "official_admin_references.jsonl", references)
    write_jsonl(args.output / "official_admin_manifest.jsonl", crawler.manifest + manifest)
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "current_provinces": provinces,
              "baseline_provinces": baseline, "comparison_rows": len(references),
              "observed_date": observed, "reference_date": reference, "current_source": NSO,
              "baseline_source": BASELINE, "comparison_source": COMPARE}
    (args.output / "official_admin_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"provinces": len(provinces), "comparison_rows": len(references)}), flush=True)


if __name__ == "__main__":
    main()
