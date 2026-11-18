"""Deduplicate new passages, retain observations separately, audit coverage."""
import argparse
from collections import Counter
import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from bs4 import BeautifulSoup

from vn_assistant.corpus_update import document_from_record, write_jsonl, parse_tourism_detail
from vn_assistant.dataio import iter_records
from vn_assistant.domain_scope import contains_intangible, sanitize_tourism_record


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[2]; raw=root/'data/raw/2026-10-30-research'
    previous=list(iter_records(root/'data/structured_records.jsonl'))
    merged={r['record_id']:r for r in previous}; passages={}; duplicates=0
    for row in iter_records(raw/'legal_passages.jsonl'):
        key=re.sub(r'\W+','',re.sub(r'^\d+[.)]\s*','',row['data']['description'])).casefold()
        if key in passages:
            duplicates+=1
            retained=passages[key]
            retained['data']['additional_source_urls']=sorted(set([*retained['data'].get('additional_source_urls',[]),row['source_url'],*row['data'].get('additional_source_urls',[])]))
            retained['data'].setdefault('section_variants',[]).append(row['data']['section'])
        else:
            passages[key]=copy.deepcopy(row)
    for row in passages.values():
        merged[row['record_id']]=row
    added_tour=0
    tourism_filter_audits=[]
    for row in iter_records(raw/'tourism_additions.jsonl'):
        if contains_intangible(json.dumps(row['data'],ensure_ascii=False)):
            raise ValueError('Excluded tourism subject: '+row['record_id'])
        added_tour+=row['record_id'] not in merged
        merged[row['record_id']]=row
        cache=raw/'http_cache'/(hashlib.sha256(row['source_url'].encode()).hexdigest()+'.html')
        if cache.exists():
            parsed=parse_tourism_detail(BeautifulSoup(cache.read_bytes(),'html.parser'))
            if parsed:
                original=copy.deepcopy(row);original['data']['description']=parsed['description']
                _,audit=sanitize_tourism_record(original)
                tourism_filter_audits.append(audit)
    old_observations={r['data']['code']:r['data'] for r in previous if r['record_type']=='administrative_reference'}
    observed_changes=[]
    observations=list(iter_records(raw/'official_admin_references.jsonl'))
    if len(observations)!=3321 or len({r['data']['code'] for r in observations})!=3321:
        raise ValueError('Incomplete official comparison observation')
    for row in observations:
        row=copy.deepcopy(row)
        date=row['data']['observed_date']
        row['record_id']+='_'+date.replace('/','-')
        row['data']['observation_policy']='source table observed on stated date; no inferred legal validity interval'
        before=old_observations.get(row['data']['code'],{})
        differences={k:{'before':before.get(k),'after':row['data'].get(k)} for k in ('name','province_code','province_name','legal_reference','change_note') if before.get(k)!=row['data'].get(k)}
        if differences:
            observed_changes.append(dict(code=row['data']['code'],differences=differences))
        merged[row['record_id']]=row
    records=list(merged.values())
    write_jsonl(a.release/'data/structured_records.jsonl',records)
    write_jsonl(a.release/'data/rag_dataset_final.jsonl',(document_from_record(r) for r in records))
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),previous_documents=len(previous),documents=len(records),
        new_distinct_legal_passages=len(passages),punctuation_numbering_duplicates_removed=duplicates,
        new_destinations=added_tour,new_dated_table_observations=len(observations),
        table_observed_dates=sorted({r['data']['observed_date'] for r in observations}),
        table_reference_dates=sorted({r['data']['reference_date'] for r in observations}),
        domains=dict(Counter(r['domain'] for r in records)),types=dict(Counter(r['record_type'] for r in records)),
        tourism_by_province=dict(sorted(Counter(r['data']['province_code'] for r in records if r['record_type']=='tourism_place').items())),
        snapshot_dates=sorted({r['data']['snapshot_date'] for r in records if r['record_type']=='administrative_snapshot'}),
        preservation=all(r['record_id'] in merged and merged[r['record_id']]==r for r in previous),
        dataset_sha256=hashlib.sha256((a.release/'data/structured_records.jsonl').read_bytes()).hexdigest(),
        raw_path=str(raw),active_data_unchanged=True)
    report['observed_field_changes']=observed_changes
    report['tourism_removed_source_sentences']=sum(x['removed_sentences'] for x in tourism_filter_audits)
    write_jsonl(a.release/'tourism_filter_audit.jsonl',tourism_filter_audits)
    assert report['preservation']
    (a.release/'corpus_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    snapshots={(r['data']['snapshot'],r['data']['level'],r['data']['code']):r['data'] for r in records if r['record_type']=='administrative_snapshot'}
    with (a.release/'administrative_crosswalk.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=['level','old_code','old_name','old_province','old_district','new_code','new_name','new_province','is_partial','reference_date','source_url']);w.writeheader()
        for r in records:
            if r['record_type']!='administrative_conversion':continue
            d=r['data'];old=snapshots.get(('legacy',d['level'],d['old_code']),{});new=snapshots.get(('reorganized2025',d['level'],d['new_code']),{})
            w.writerow(dict(level=d['level'],old_code=d['old_code'],old_name=d['old_name'],old_province=old.get('province_name',''),old_district=old.get('district_name',''),
                new_code=d['new_code'],new_name=d['new_name'],new_province=new.get('province_name',''),is_partial=d['is_partial'],reference_date=d.get('valid_from',''),source_url=r['source_url']))
    with (a.release/'tourism_by_province.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=['province_code','province_name','destinations','keyword_query']);w.writeheader()
        for code,count in report['tourism_by_province'].items():
            province=snapshots[('current','province',code)]['name']
            w.writerow(dict(province_code=code,province_name=province,destinations=count,keyword_query='Địa điểm tham quan trải nghiệm tại '+province))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
