"""Reproducible small retrieval ablation and optional full-index evaluation.
Gold queries are manually paraphrased from corpus passages, not independently fact-checked.
"""
import argparse
from dataclasses import replace, asdict
import json
import os
from pathlib import Path
import random
import sys
import time
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
from vn_assistant.dataio import iter_documents, chunk_document
from vn_assistant.embedding import EmbeddingConfig, TransformerEncoder
from vn_assistant.faiss_store import FaissRetriever

GOLD = [
 ('law','ecb89a376e9b874f3c2dd31e1b8eba88778325b30d9e01e259ed09f320233cc3','Vợ chồng chia tay thì căn nhà riêng đã dùng chung được xử lý thế nào?'),
 ('law','93c710de22b78b48e923f4ee3558701166f05572f326d75cfa06d43c02991787','Đi chứng thực chữ ký cần đem giấy tờ tùy thân nào?'),
 ('law','2a634a6a02205448c48897c0114bd17d522f2148810e0c6f9af604db8e4e3398','Sau ly hôn, người nuôi con muốn cho con đi du học khi người kia phản đối.'),
 ('law','65240b5de139c2c8e0d6ded531f7bed6b86ca8fe2c03c7ff7277249c7e5d0024','Cha mẹ nuôi có giữ quyền chăm sóc bé Linh khi mẹ ruột đòi lại con không?'),
 ('administration','9a28af531ca201098c08dc8f8f42379880032bb44cd1d41241084e2dee7c58d1','Hà Nội là đơn vị hành chính cấp nào?'),
 ('administration','c62056c948efa0da7c6adff6c69a545e7799f2f70c710e7de66c91be638b41c5','Mã số hành chính của phường Ba Đình và thành phố quản lý phường này'),
 ('administration','bd4419e078f8e9073c04336540730fc57d957cbf33b75196873cec479b5583a3','Ngọc Hà trực thuộc thành phố nào và có mã gì?'),
 ('administration','f3fe153527f49536188644d55ccac3abb18d59b3854d9d2e2859d89fd1e487a5','Tra cứu thông tin đơn vị hành chính Giảng Võ'),
 ('heritage','ecd80fd17557687cf0c680457b21149ca4f8a262230575421d870088e9aaee5d','Kỷ vật áo dù của tướng Lê Hữu Đức gắn liền với mặt trận nào?'),
 ('heritage','3de31779e3cd7437c9806fbcefe31cd6896e037b6a75a9f8e60328ab3e97e787','Dụng cụ khám chữa bệnh trên đảo Trường Sa Lớn được sử dụng trong giai đoạn nào?'),
 ('heritage','1fafa1dfdbbb822684201823f9d4dc8e7d5ff135c895826dc03ba94b1eeb3ae0','Ai là bác sĩ phụ trách bệnh xá Trường Sa Lớn gắn với bộ dụng cụ y tế?'),
 ('heritage','5c24cb5de26bc45c9431965b8c595016bbaa220ffd75ba96007992ad5a924209','Trần Văn Vinh tham gia cứu trợ động đất năm 2023 ở nước nào?'),
 ('tourism','a86f0606a324dba9319c84ea14e35034a90b9056ff1a100bd264de73b8f044d2','Tôi muốn nghỉ đông ở nơi có tuyết để trượt tuyết và nghỉ bên lò sưởi.'),
 ('tourism','be14c95ba1384138fb94bde14764deaccd290be81422eb574f82bd54b14293fd','Khách sạn The Little Nell ở Aspen có những tiện nghi gì?'),
 ('tourism','cff0e0ee76208149c82fdca5c44f80293e47665c6d4dbf1d5e1f17753b86f1bd','Gợi ý đi Chiang Mai để trải nghiệm ngoài trời và thưởng thức món ăn địa phương'),
 ('tourism','12e8a8e83deb004ad2357ebe8475dc0637c8adf0410c9edc45f19ca7859e5b7f','Có thể lặn ngắm san hô và chơi những môn thể thao nào trong kỳ nghỉ ở biển?'),
]


def metrics(ranks):
    return {'cases':len(ranks), 'hit_at_1':sum(r == 1 for r in ranks)/len(ranks),
            'recall_at_5_known_positive':sum(r is not None and r <= 5 for r in ranks)/len(ranks),
            'mrr_at_5':sum(1/r for r in ranks if r is not None and r <= 5)/len(ranks)}


def run(dataset='data/rag_dataset_final.jsonl', device='cpu', full_index=None):
    output = Path('artifacts/evaluation'); output.mkdir(parents=True, exist_ok=True)
    if full_index:
        retriever = FaissRetriever(full_index/'vn.index',full_index/'metadata.sqlite3',EmbeddingConfig(device=device))
        details=[]
        for domain,doc_id,question in GOLD:
            rows=retriever.search(question,5,domain)
            rank=next((i for i,r in enumerate(rows,1) if r['doc_id']==doc_id),None)
            details.append({'question':question,'doc_id':doc_id,'rank':rank,'retrieved_doc_ids':[r['doc_id'] for r in rows]})
        report={'scope':'Full index; one known positive per query; unjudged alternatives may also be relevant.',
                'metrics':metrics([r['rank'] for r in details]),'details':details}
        path=output/'retrieval_full.json'
    else:
        targets={row[1] for row in GOLD}; found={}; pools={}; counts={}; rng=random.Random(42)
        for document in iter_documents(dataset):
            if document.doc_id in targets: found[document.doc_id]=document
            domain=document.domain; counts[domain]=counts.get(domain,0)+1
            pool=pools.setdefault(domain,[])
            if len(pool)<50: pool.append(document)
            else:
                slot=rng.randrange(counts[domain])
                if slot<50: pool[slot]=document
        if targets-set(found): raise ValueError(f'Missing gold documents: {targets-set(found)}')
        documents={d.doc_id:d for pool in pools.values() for d in pool}; documents.update(found)
        chunks=[c for d in documents.values() for c in chunk_document(d)]
        (output/'retrieval_gold.jsonl').write_text('\n'.join(json.dumps({'domain':d,'doc_id':i,'question':q},ensure_ascii=False) for d,i,q in GOLD)+'\n')
        (output/'sample_manifest.json').write_text(json.dumps({'seed':42,'doc_ids':list(documents),'chunks':len(chunks)},indent=2))
        encoder=TransformerEncoder(EmbeddingConfig(device=device,batch_size=8))
        variants={}
        for expand in (False,True):
            encoder.config=replace(encoder.config,expand_terms=expand)
            start=time.perf_counter()
            passages=encoder.encode_passages([c['text'] for c in chunks])
            queries=encoder.encode_queries([row[2] for row in GOLD])
            details=[]
            for (domain,doc_id,question),query in zip(GOLD,queries):
                candidates=[i for i,c in enumerate(chunks) if c['domain']==domain]
                scores=np.einsum('ij,j->i', passages[candidates], query)
                if not np.isfinite(scores).all(): raise ValueError('Non-finite similarity scores')
                order=np.argsort(-scores)[:5]
                retrieved=[chunks[candidates[i]]['doc_id'] for i in order]
                rank=next((i for i,value in enumerate(retrieved,1) if value==doc_id),None)
                details.append({'question':question,'rank':rank,'retrieved_doc_ids':retrieved})
            variants['domain_expansion' if expand else 'baseline_e5']={
                **metrics([r['rank'] for r in details]),'elapsed_seconds':time.perf_counter()-start,'details':details}
        # Persist the final variant as a four-domain Transformer integration fixture.
        import faiss
        import sqlite3
        from vn_assistant.faiss_store import SCHEMA
        sample_index = output / 'sample_index'
        sample_index.mkdir(exist_ok=True)
        index = faiss.IndexIDMap2(faiss.IndexFlatIP(passages.shape[1]))
        index.add_with_ids(passages, np.arange(len(chunks), dtype='int64'))
        faiss.write_index(index, str(sample_index/'vn.index'))
        with sqlite3.connect(sample_index/'metadata.sqlite3') as connection:
            connection.executescript(SCHEMA)
            connection.execute('DELETE FROM chunks')
            connection.executemany('INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [
                (i,c['chunk_id'],c['doc_id'],c['text'],c['title'],c['domain'],c['source'],c['source_url'])
                for i,c in enumerate(chunks)])
        (sample_index/'index_config.json').write_text(json.dumps({
            'backend':'transformer','production_ready':False,'scope':'evaluation_sample',
            'embedding':asdict(encoder.config),'vectors':len(chunks),'dimension':passages.shape[1]}))
        report={'scope':'Development ablation: 16 hand-paraphrased known-positive queries, 50 random distractor documents/domain. Not an independent thesis benchmark or fact validation.',
                'documents':len(documents),'chunks':len(chunks),'variants':variants}
        path=output/'embedding_ablation.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('details','variants')},ensure_ascii=False))
    if 'variants' in report:
        print(json.dumps({k:{a:b for a,b in v.items() if a!='details'} for k,v in report['variants'].items()},indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--device',default='cpu'); parser.add_argument('--full-index',type=Path)
    args=parser.parse_args(); run(device=args.device,full_index=args.full_index)
