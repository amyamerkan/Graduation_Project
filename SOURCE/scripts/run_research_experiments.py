"""Reproducible development experiments, not independent factual accuracy."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from time import perf_counter

import faiss
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer

from vn_assistant.administrative_codes import fold_query, recognize_administrative_code, province_key, province_matches
from vn_assistant.corpus_update import write_jsonl
from vn_assistant.dataio import iter_records
from vn_assistant.embedding import EmbeddingConfig, create_encoder
from vn_assistant.router import Classification, QuestionRouter, extract_query_plan, evaluate_router


def stable_order(rows):
    return sorted(rows, key=lambda r: hashlib.sha256(r['record_id'].encode()).hexdigest())


def make_gold(old, new):
    cases = []
    def add(question, ids, group, kind, origin):
        split = 'dev' if int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) % 5 == 0 else 'test'
        cases.append(dict(id=f'Q{len(cases)+1:04}', question=question, relevant_doc_ids=ids,
            group=group, split=split, kind=kind, origin=origin, annotation='silver/source-derived; requires human review'))
    current = stable_order([r for r in old if r['record_type']=='administrative_snapshot' and r['data']['snapshot']=='current' and r['data']['level']=='ward'])[:30]
    for row in current:
        code = row['data']['code']
        for snapshot in ('legacy','reorganized2025','current'):
            matches = [r for r in new if r['record_type']=='administrative_snapshot' and r['data']['code']==code and r['data']['snapshot']==snapshot]
            if matches:
                day=matches[0]['data']['snapshot_date']
                add(f'Vào ngày {day}, mã hành chính {code} thuộc địa phương nào?', [r['record_id'] for r in matches], 'code:'+code, 'temporal_code', 'existing')
        add(f'Ngày 2024-01-01 mã {code} thuộc địa phương nào?', [], 'code:'+code, 'unanswerable_date', 'existing')
    seen_provinces=set()
    for row in stable_order([r for r in old if r['record_type']=='tourism_place']):
        p=row['data']['province_code']
        if p in seen_provinces:
            continue
        seen_provinces.add(p)
        add(f"Tham quan và trải nghiệm tại {row['data']['name']} có gì?", [row['record_id']], 'place:'+row['data']['name'].casefold(), 'destination', 'existing')
    old_ids={r['record_id'] for r in old}
    new_tour=stable_order([r for r in new if r['record_type']=='tourism_place' and r['record_id'] not in old_ids])[:40]
    for row in new_tour:
        add(f"Du lịch {row['data']['name']} ở {row['data']['province_name']} có gì để khám phá?", [row['record_id']], 'place:'+row['data']['name'].casefold(), 'destination', 'new')
    clauses=stable_order([r for r in new if r['record_type']=='administrative_legal_passage'])
    selected=0
    for row in clauses:
        match=re.search(r'có tên gọi là (.+?)[.!;]', row['data']['description'])
        if not match:
            continue
        name=match.group(1).strip()
        positives=[r['record_id'] for r in clauses if r['data']['section']==row['data']['section'] and f'có tên gọi là {name}' in r['data']['description']]
        add(f"Những đơn vị nào được sắp xếp để thành lập {name}? {row['data']['section']}", positives, 'legal:'+name, 'merger_clause', 'new')
        selected+=1
        if selected>=35:
            break
    # Province keyword queries: all known destinations in the province are positives.
    for p in sorted(seen_provinces):
        matches=[r for r in new if r['record_type']=='tourism_place' and r['data']['province_code']==p]
        if matches:
            add(f"Các địa điểm tham quan du lịch tại {matches[0]['data']['province_name']}?", [r['record_id'] for r in matches], 'province:'+p, 'province_destinations', 'mixed')
    # No entity group can cross dev/test; duplicate questions are removed.
    return list({c['question']:c for c in cases}.values())


def metrics(results):
    positive=[r for r in results if r['relevant_doc_ids']]
    negative=[r for r in results if not r['relevant_doc_ids']]
    return dict(cases=len(results), answerable=len(positive), unanswerable=len(negative),
        hit_at_1=np.mean([r['rank']==1 for r in positive]).item() if positive else None,
        hit_at_5=np.mean([r['rank'] is not None and r['rank']<=5 for r in positive]).item() if positive else None,
        mrr_at_10=np.mean([1/r['rank'] if r['rank'] else 0 for r in positive]).item() if positive else None,
        ndcg_at_10=np.mean([r['ndcg'] for r in positive]).item() if positive else None,
        known_positive_recall_at_10=np.mean([len(set(r['retrieved']) & set(r['relevant_doc_ids']))/len(set(r['relevant_doc_ids'])) for r in positive]).item() if positive else None,
        answerable_response_coverage=np.mean([bool(r['retrieved']) for r in positive]).item() if positive else None,
        abstention_accuracy=np.mean([not r['retrieved'] for r in negative]).item() if negative else None,
        ranking_p50_ms=float(np.median([r['ranking_ms'] for r in results])) if results else None)


def evaluate(root, records, gold, query_vectors, router=None):
    index_dir=root/'artifacts/faiss'
    with sqlite3.connect(index_dir/'metadata.sqlite3') as db:
        chunks=db.execute('SELECT vector_id,doc_id,text,domain FROM chunks ORDER BY vector_id').fetchall()
    index=faiss.read_index(str(index_dir/'vn.index'))
    by_id={r['record_id']:r for r in records}
    # Same chunks and domain-unrestricted candidate units for all base rankers.
    vectorizer=CountVectorizer(preprocessor=fold_query, token_pattern=r'(?u)\b\w+\b', dtype=np.float32, max_features=120000)
    counts=vectorizer.fit_transform([r[2] for r in chunks]).tocsr()
    tfidf=TfidfTransformer().fit(counts)
    tfidf_docs=tfidf.transform(counts)
    lengths=np.asarray(counts.sum(axis=1)).ravel()
    df=np.bincount(counts.indices,minlength=counts.shape[1])
    idf=np.log(1+(len(chunks)-df+.5)/(df+.5))
    bm25=counts.copy()
    row_ids=np.repeat(np.arange(len(chunks)),np.diff(bm25.indptr))
    bm25.data=(bm25.data*2.2/(bm25.data+1.2*(.25+.75*lengths[row_ids]/max(lengths.mean(),1))))*idf[bm25.indices]
    aliases=defaultdict(set)
    province_conversions={r['data']['old_code']:r['data']['new_code'] for r in records if r['record_type']=='administrative_conversion' and r['data']['level']=='province'}
    for r in records:
        if r['record_type']=='administrative_snapshot' and r['data']['level']=='province':
            d=r['data']; aliases[province_key(d['name'])].add(province_conversions.get(d['code'],d['code']) if d['snapshot']=='legacy' else d['code'])
    doc_chunks=defaultdict(list)
    for pos,c in enumerate(chunks):
        doc_chunks[c[1]].append(pos)
    methods=('tfidf','bm25','dense_e5','rrf','rrf_domain','rrf_domain_province','proposed_temporal_province_rrf')
    output={m:[] for m in methods}
    def docs(order):
        return list(dict.fromkeys(chunks[int(i)][1] for i in order))
    def sparse_rank(matrix, q):
        scores=(matrix@q.T).toarray().ravel()
        eligible=np.flatnonzero(scores>0)
        return docs(eligible[np.argsort(-scores[eligible],kind='stable')[:200]])
    for i,case in enumerate(gold):
        started=perf_counter()
        q=vectorizer.transform([case['question']]); binary=q.copy();binary.data[:]=1
        sparse=sparse_rank(bm25,binary)
        lexical=sparse_rank(tfidf_docs,tfidf.transform(q))
        _, ids=index.search(query_vectors[i:i+1],min(200,index.ntotal))
        dense=docs(ids[0][ids[0]>=0])
        fused=defaultdict(float)
        for ranked in (sparse,dense):
            for rank,doc in enumerate(ranked,1):
                fused[doc]+=1/(60+rank)
        fusion=sorted(fused,key=lambda doc:(-fused[doc],doc))
        folded=fold_query(case['question'])
        domain=router.classify(case['question']).domain if router else ('tourism' if re.search(r'\b(?:du lich|tham quan|trai nghiem)\b',folded) else 'administration')
        province_codes=set()
        if domain=='tourism':
            for alias,codes in aliases.items():
                if alias and re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',folded):
                    province_codes.update(codes)
        domain_rows=[doc for doc in fusion if by_id.get(doc,{}).get('domain')==domain]
        province_rows=[doc for doc in domain_rows if not province_codes or by_id[doc]['data'].get('province_code') in province_codes]
        proposed=province_rows
        reference=recognize_administrative_code(case['question'])
        if reference.status=='clarify':
            proposed=[]
        if reference.code and domain=='administration' and not re.search(r'bang doi chieu|ghi chu|chuyen doi|sap xep|sap nhap',folded):
            # Exact gate uses query text and record keys, never relevance labels.
            plan=extract_query_plan(case['question'],Classification(case['question'],'kg','administration',1,1,'research_rule'))
            params=(plan.get('kg') or {}).get('params',{})
            exact=[r['record_id'] for r in records if r['record_type']=='administrative_snapshot'
                and r['data']['code']==reference.code and
                (r['data']['snapshot_date']==params['as_of'] if params.get('as_of') else r['data']['snapshot']=='current')
                and (not params.get('province') or province_matches(params['province'],r['data']['province_name']))]
            if plan['constraints']['unsupported'] or not plan.get('kg'):
                exact=[]
            proposed=sorted(exact,key=lambda doc:(-fused.get(doc,0),doc))
        ranks={'tfidf':lexical,'bm25':sparse,'dense_e5':dense,'rrf':fusion,'rrf_domain':domain_rows,
               'rrf_domain_province':province_rows,'proposed_temporal_province_rrf':proposed}
        elapsed=(perf_counter()-started)*1000
        for method,ranked in ranks.items():
            retrieved=ranked[:10]; positives=set(case['relevant_doc_ids'])
            rank=next((n for n,d in enumerate(retrieved,1) if d in positives),None)
            dcg=sum(1/np.log2(n+1) for n,d in enumerate(retrieved,1) if d in positives)
            ideal=sum(1/np.log2(n+1) for n in range(1,min(len(positives),10)+1))
            output[method].append({**case,'retrieved':retrieved,'rank':rank,'ndcg':float(dcg/ideal) if ideal else 0,
                'ranking_ms':elapsed,'known_positives_present':sum(d in by_id for d in positives)})
        if i%40==0:
            print(json.dumps({'dataset':str(root),'evaluated':i+1,'total':len(gold)}),flush=True)
    summary={method:{split:metrics([r for r in rows if r['split']==split]) for split in ('dev','test')} for method,rows in output.items()}
    slices={method:{kind:metrics([r for r in rows if r['split']=='test' and r['kind']==kind])
        for kind in sorted({r['kind'] for r in rows})} for method,rows in output.items()}
    return output,summary,slices


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--device',default='mps');a=p.parse_args()
    faiss.omp_set_num_threads(2)
    old=list(iter_records(a.root/'data/structured_records.jsonl'));new=list(iter_records(a.release/'data/structured_records.jsonl'))
    gold=make_gold(old,new);write_jsonl(a.release/'research_gold.jsonl',gold)
    started=perf_counter();encoder=create_encoder(EmbeddingConfig(device=a.device));vectors=encoder.encode_queries([c['question'] for c in gold]);encoding=perf_counter()-started
    frozen_router=QuestionRouter(a.root/'artifacts/router/router.joblib')
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),scope='Silver development benchmark, not human-verified test accuracy. No new global algorithm novelty claimed.',
        settings=dict(seed=42,rrf_k=60,top_candidates=200,top_documents=10,query_encoding_seconds_including_load=encoding,
            latency_scope='ranking_ms measures all rankers together, excludes encoding; do not compare per-method latency',
            tuning='fixed parameters, no test tuning',split='entity-group SHA256 split; no embedding fine-tuning'),
        gold_cases=len(gold),datasets={})
    # Keep the earlier manually-authored development set separate from silver
    # templates; evaluate all methods on exactly the same old questions.
    manual_path=a.root/'artifacts/domain_refresh_2026-10-24/release/retrieval_gold.jsonl'
    manual=[]
    if manual_path.exists():
        for i,c in enumerate(iter_records(manual_path)):
            manual.append({**c,'id':f'M{i+1:03}','split':'manual_dev','kind':'manual_known_positive',
                           'origin':'existing','annotation':'earlier manually-authored development questions; not held-out'})
    if manual:
        manual_vectors=encoder.encode_queries([c['question'] for c in manual])
        combined=gold+manual; query_vectors=np.concatenate([vectors,manual_vectors])
    else:
        combined=gold; query_vectors=vectors
    for label,root,records in [('existing',a.root,old),('expanded',a.release,new)]:
        details,summary,slices=evaluate(root,records,combined,query_vectors,router=frozen_router)
        (a.release/f'{label}_experiment_details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2))
        available={r['record_id'] for r in records}
        report['datasets'][label]=dict(documents=len(records),summary=summary,slices=slices,
            manual_development={m:metrics([r for r in rows if r['split']=='manual_dev']) for m,rows in details.items()},
            old_questions={m:metrics([r for r in rows if r['split']=='test' and r['origin']=='existing']) for m,rows in details.items()},
            known_positive_coverage=sum(all(d in available for d in c['relevant_doc_ids']) for c in gold if c['relevant_doc_ids'])/sum(bool(c['relevant_doc_ids']) for c in gold))
    write_jsonl(a.release/'manual_development_gold.jsonl',manual)
    # Paired bootstrap by ENTITY GROUP, not correlated query paraphrases.
    rng=np.random.default_rng(42); bootstrap={}
    for method in ('bm25','dense_e5','rrf'):
        ours=[r for r in details['proposed_temporal_province_rrf'] if r['split']=='test' and r['relevant_doc_ids']]
        comparator={r['id']:r for r in details[method]}
        groups=defaultdict(list)
        for r in ours:
            other=comparator[r['id']]
            groups[r['group']].append((1/r['rank'] if r['rank'] else 0)-(1/other['rank'] if other['rank'] else 0))
        values=list(groups.values()); deltas=[]
        for _ in range(1000):
            sample=rng.integers(0,len(values),len(values))
            deltas.append(float(np.mean([x for idx in sample for x in values[idx]])))
        bootstrap[method]=dict(delta_mrr=float(np.mean([x for v in values for x in v])),
            percentile_95_ci=[float(x) for x in np.percentile(deltas,[2.5,97.5])],entity_groups=len(values),scope='expanded corpus, silver test, group bootstrap')
    report['paired_bootstrap']=bootstrap
    report['settings']['domain_router']='Frozen pre-expansion D0 router for both corpora; retrained D1 router evaluated separately'
    frozen_eval=evaluate_router(a.root/'artifacts/router/router.joblib',Path(__file__).resolve().parents[1]/'evaluation/router_test.csv',a.release/'existing_router_evaluation.json')
    report['existing_router_evaluation']={k:frozen_eval[k] for k in ('cases','route_accuracy','domain_accuracy','joint_accuracy')}
    (a.release/'experiment_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({'cases':len(gold),'report':str(a.release/'experiment_report.json')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
