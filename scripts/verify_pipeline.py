"""Run real KG + Transformer/FAISS integration checks against a specified index."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TRANSFORMERS_OFFLINE','1')
from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import FaissRetriever
from vn_assistant.router import QuestionRouter
from vn_assistant.sparql_service import SparqlService
from vn_assistant.question_processing import QuestionProcessor


def verify(index_dir, device='cpu'):
    retriever=FaissRetriever(index_dir/'vn.index',index_dir/'metadata.sqlite3',EmbeddingConfig(device=device))
    kg=SparqlService('artifacts/kg/vn_knowledge_graph.ttl','queries')
    router=QuestionRouter('artifacts/router/router.joblib')
    processor=QuestionProcessor(router,kg,retriever)
    code=processor.process('Phường có mã 00070 là gì?')
    assert any(row.get('name')=='Phường Hoàn Kiếm' for row in code['kg_results'])
    wards=processor.process('Danh sách các phường thuộc Thành phố Hà Nội')
    assert wards['plan']['kg']['query']=='02_wards_in_province'
    assert any(row.get('code')=='00004' for row in wards['kg_results'])
    year=processor.process('Di sản nào được UNESCO công nhận năm 1999?')
    assert year['plan']['kg'] is None and year['effective_route']=='rag'
    rag=processor.process('Hướng dẫn chuẩn bị giấy tờ chứng thực chữ ký theo quy định pháp luật')
    assert rag['rag_results'] and all(row['domain']=='law' for row in rag['rag_results'])
    for domain in ('law','heritage','tourism','administration'):
        rows=retriever.search('Thông tin '+domain,top_k=5,domain=domain)
        assert len(rows)==5 and all(row['domain']==domain for row in rows)
        assert all(-1.00001 <= row['score'] <= 1.00001 for row in rows)
    # Verify actual hybrid and KG-empty fallback with real retriever.
    hybrid=processor.process('Phường có mã 00070 thuộc đâu và mô tả như thế nào?')
    assert hybrid['kg_results'] and hybrid['rag_results'] and hybrid['effective_route']=='hybrid'
    fallback=processor.process('Phường có mã 999999 là gì?')
    assert fallback['effective_route']=='rag_fallback' and fallback['rag_results']
    report={'index_directory':str(index_dir),'backend':'transformer','vectors':retriever.index.ntotal,
            'passed':True,'checks':['KG code','province ward list','year fallback','RAG law',
                                     'cosine and full-domain top-k in four domains','hybrid','KG empty fallback'],
            'scope':'Integration correctness, not factual accuracy of retrieved passages.'}
    (index_dir/'integration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--index-dir',type=Path,default=Path('artifacts/faiss'));parser.add_argument('--device',default='cpu')
    args=parser.parse_args();verify(args.index_dir,args.device)
