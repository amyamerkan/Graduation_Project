"""Check research metrics, group splits and temporal-gate ablation semantics."""
import importlib.util
from pathlib import Path
import sqlite3

import faiss
import numpy as np

from vn_assistant.faiss_store import SCHEMA

spec=importlib.util.spec_from_file_location('research',Path(__file__).resolve().parents[1]/'scripts/run_research_experiments.py')
research=importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


def snapshot(identifier, day, label):
    return dict(record_id=identifier,record_type='administrative_snapshot',domain='administration',
        data=dict(name='Phường kiểm thử',code='00008',snapshot_date=day,snapshot=label,level='ward',province_code='01',province_name='Thành phố Hà Nội'))


def test_metrics_handle_abstentions_separately_from_retrieval():
    rows=[dict(relevant_doc_ids=['a'],rank=1,ndcg=1,ranking_ms=2,retrieved=['a']),
          dict(relevant_doc_ids=['b'],rank=None,ndcg=0,ranking_ms=4,retrieved=['x']),
          dict(relevant_doc_ids=[],rank=None,ndcg=0,ranking_ms=1,retrieved=[])]
    result=research.metrics(rows)
    assert result['mrr_at_10']==result['hit_at_1']==result['ndcg_at_10']==.5
    assert result['abstention_accuracy']==1 and result['answerable']==2


def test_silver_gold_groups_all_snapshots_of_a_code_in_one_split():
    records=[snapshot('a','2025-06-30','legacy'),snapshot('b','2025-07-01','reorganized2025'),snapshot('c','2026-10-24','current')]
    gold=research.make_gold(records,records)
    assert len(gold)==4 and len({g['split'] for g in gold})==1
    assert {g['relevant_doc_ids'][0] for g in gold if g['relevant_doc_ids']}=={'a','b','c'}
    assert research.make_gold(list(reversed(records)),records)==gold


def test_real_sparse_dense_pipeline_gates_date_and_abstains_without_gold_access(tmp_path):
    records=[snapshot('a','2025-06-30','legacy'),snapshot('b','2025-07-01','reorganized2025'),snapshot('c','2026-10-24','current')]
    path=tmp_path/'artifacts/faiss';path.mkdir(parents=True)
    with sqlite3.connect(path/'metadata.sqlite3') as db:
        db.executescript(SCHEMA)
        db.executemany('INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)',[
            (i,r['record_id']+':0',r['record_id'],'Mã 00008 phường kiểm thử tại Hà Nội '+r['data']['snapshot_date'],'phường','administration','fixture','')
            for i,r in enumerate(records)])
    index=faiss.IndexIDMap2(faiss.IndexFlatIP(4))
    index.add_with_ids(np.eye(4,dtype='float32')[:3],np.arange(3,dtype='int64'))
    faiss.write_index(index,str(path/'vn.index'))
    gold=[dict(id='1',question='Ngày 2025-07-01 mã 00008 thuộc đâu?',relevant_doc_ids=['b'],split='test',kind='temporal',origin='existing'),
          dict(id='2',question='Ngày 2024-01-01 mã 00008 thuộc đâu?',relevant_doc_ids=[],split='test',kind='unknown',origin='existing'),
          dict(id='3',question='Trước ngày 2025-07-01 mã 00008 thuộc đâu?',relevant_doc_ids=[],split='test',kind='unsupported',origin='existing'),
          dict(id='4',question='Ngày 2025-07-01 mã 00008 thuộc Điện Biên không?',relevant_doc_ids=[],split='test',kind='wrong_province',origin='existing')]
    details,summary,_=research.evaluate(tmp_path,records,gold,np.array([[1,0,0,0]]*4,dtype='float32'))
    assert details['dense_e5'][0]['retrieved'][0]=='a'  # Deliberately wrong dense ranking.
    assert details['proposed_temporal_province_rrf'][0]['retrieved']==['b']
    assert details['proposed_temporal_province_rrf'][1]['retrieved']==[]
    assert summary['proposed_temporal_province_rrf']['test']['abstention_accuracy']==1
