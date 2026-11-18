"""Collect source-grounded additions into a separate research release."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urljoin, urlsplit

from vn_assistant.corpus_update import PublicCrawler, _record, parse_tourism_detail, write_jsonl, document_from_record, TOURISM_ROOT
from vn_assistant.dataio import iter_records
from vn_assistant.domain_scope import sanitize_tourism_record
from vn_assistant.normalization import clean_text

LEGAL_INDEX = 'https://xaydungchinhsach.chinhphu.vn/danh-sach-3321-don-vi-hanh-chinh-cap-xa-tai-34-tinh-thanh-sau-sap-xep-sap-nhap-119250710102358656.htm'


def legal(crawler):
    soup = crawler.get(LEGAL_INDEX)
    main = soup.select_one('.detail-content')
    if main is None:
        raise ValueError('Missing legal article body')
    urls = list(dict.fromkeys(urljoin(LEGAL_INDEX, a['href']) for a in main.select('a[href]')
        if 'toan-van-nghi-quyet' in a['href'] and 'sap-xep' in a['href'] and urlsplit(urljoin(LEGAL_INDEX, a['href'])).netloc == urlsplit(LEGAL_INDEX).netloc))
    records, errors = {}, []
    for url in [LEGAL_INDEX, *urls]:
        try:
            page = soup if url == LEGAL_INDEX else crawler.get(url)
            content = page.select_one('.detail-content')
            if content is None:
                raise ValueError('Missing article content')
            section = clean_text(page.h1.get_text(' ', strip=True)) if page.h1 else 'Sắp xếp hành chính 2025'
            for tag in content.find_all(['h2', 'h3', 'p']):
                text = clean_text(tag.get_text(' ', strip=True))
                if tag.name in {'h2', 'h3'}:
                    section = text
                if tag.name != 'p' or len(text) < 80 or not re.search(r'\b(?:Sắp xếp|sắp xếp|hợp nhất|sáp nhập|chính thức hoạt động)\b', text):
                    continue
                # Keep clauses verbatim. No inferred old/new edges or dates.
                digest = hashlib.sha256(text.encode()).hexdigest()
                if digest in records:
                    records[digest]['data'].setdefault('additional_source_urls', []).append(url)
                    continue
                data = dict(name=section + ' — ' + text[:110], description=text, section=section,
                    content_sha256=digest, reference_period='sắp xếp năm 2025', effective_from=None,
                    retrieved_at=datetime.now(timezone.utc).isoformat(), country='VN',
                    extraction_scope='verbatim official article passage; dates and merger edges not inferred',
                    partial_transfer_mentioned=bool(re.search('một phần|phần còn lại', text, re.I)))
                record = _record('administrative_legal_passage', data, source='Cổng Chính phủ — Xây dựng chính sách', url=url)
                record['record_id'] = 'legal_passage_' + digest[:24]
                records[digest] = record
            print(json.dumps({'legal_pages': url, 'clauses': len(records)}, ensure_ascii=False), flush=True)
        except Exception as exc:
            errors.append({'url': url, 'error': str(exc)})
    return list(records.values()), {'linked_full_texts': len(urls), 'errors': errors}


def tourism(crawler, previous, limit, progress, pages=1):
    provinces = {r['data']['code']: r['data']['name'] for r in previous
                 if r['record_type'] == 'administrative_snapshot' and r['data']['snapshot'] == 'current' and r['data']['level'] == 'province'}
    soup = crawler.get(TOURISM_ROOT + '/dest/')
    selectors = {}
    for option in soup.select('select#province option[value]'):
        current = set(option['value'].split(',')).intersection(provinces)
        if len(current) == 1:
            selectors[next(iter(current))] = option['value']
    seen = {r['source_url'] for r in previous if r['domain'] == 'tourism'}
    rows, errors, coverage = [], [], Counter()
    for code, value in sorted(selectors.items()):
        for section, page_number in [(s, n) for s in ('dest', 'area', 'vcgt') for n in range(1, pages+1)]:
            params = {'province': value}
            if page_number > 1:
                params['page'] = page_number
            url = TOURISM_ROOT + '/' + section + '/?' + urlencode(params)
            try:
                directory = crawler.get(url)
                for anchor in directory.select('main h4 a[href]'):
                    target = urljoin(url, anchor['href'])
                    if target in seen or urlsplit(target).netloc != urlsplit(TOURISM_ROOT).netloc or 'item=' not in target:
                        continue
                    seen.add(target)
                    data = parse_tourism_detail(crawler.get(target))
                    if data is None:
                        continue
                    data.update(province_code=code, province_name=provinces[code], country='VN', section=section,
                        source_directory_url=url,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                        province_mapping_basis='official tourism directory province filter; grouped legacy codes',
                        address_time_scope='verbatim source; no inferred post-merger commune address')
                    row, audit = sanitize_tourism_record(_record('tourism_place', data, 'tourism', 'CSDL ngành Du lịch — TITC', target))
                    if row:
                        rows.append(row)
                        coverage[code] += 1
                    if coverage[code] >= limit:
                        break
            except Exception as exc:
                errors.append({'url': url, 'error': str(exc)})
            if coverage[code] >= limit:
                break
        write_jsonl(progress, rows)
        print(json.dumps({'province': provinces[code], 'new': coverage[code], 'total_new': len(rows)}, ensure_ascii=False), flush=True)
    return rows, {'coverage': dict(coverage), 'errors': errors, 'target_new_per_province': limit}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--new-per-province', type=int, default=20)
    parser.add_argument('--tourism-pages', type=int, default=1)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    previous = list(iter_records(args.root / 'data/structured_records.jsonl'))
    raw = args.root / 'data/raw/2026-10-30-research'
    crawler = PublicCrawler(raw / 'http_cache')
    try:
        clauses, lr = legal(crawler)
        write_jsonl(raw / 'legal_passages.jsonl', clauses)
        destinations, tr = tourism(crawler, previous, args.new_per_province, raw / 'tourism_additions.jsonl', args.tourism_pages)
        merged = {r['record_id']: r for r in [*previous, *clauses, *destinations]}
        write_jsonl(args.output / 'data/structured_records.jsonl', merged.values())
        write_jsonl(args.output / 'data/rag_dataset_final.jsonl', (document_from_record(r) for r in merged.values()))
        report = dict(created_at=datetime.now(timezone.utc).isoformat(), before=len(previous), after=len(merged),
            added_legal_passages=len(clauses), added_tourism=len(destinations), legal=lr, tourism=tr,
            types=dict(Counter(r['record_type'] for r in merged.values())),
            source_dataset_sha256=hashlib.sha256((args.root / 'data/structured_records.jsonl').read_bytes()).hexdigest(),
            publication_status='research release only; active application unchanged')
        (args.output / 'collection_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        write_jsonl(raw / 'research_http_manifest.jsonl', crawler.manifest)


if __name__ == '__main__':
    main()
