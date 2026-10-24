import json
from pathlib import Path

import numpy as np
import pytest

from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import FaissRetriever, build_faiss_index
from vn_assistant.kg_evaluation import evaluate_kg
from vn_assistant.question_processing import QuestionProcessor
from vn_assistant.router import QuestionRouter, extract_query_plan


def test_router_selects_province_wards_and_never_uses_year_as_code(tmp_path):
    router = QuestionRouter(tmp_path / 'missing')
    q = 'Danh sách các phường thuộc Thành phố Hà Nội'
    plan = extract_query_plan(q, router.classify(q))
    assert plan['kg'] == {'query': '02_wards_in_province', 'params': {'province': 'Hà Nội'}}
    q = 'Di sản được công nhận năm nào trong năm 1999?'
    plan = extract_query_plan(q, router.classify(q))
    assert plan['kg'] is None and plan['rag'] is not None
    q = 'Đơn vị có mã hành chính 00070 là gì?'
    assert extract_query_plan(q, router.classify(q))['kg']['params']['code'] == '00070'


def test_exhaustive_gold_penalizes_extra_rows(tmp_path):
    graph = tmp_path / 'kg.ttl'
    graph.write_text('@prefix v: <urn:v:> . v:a v:name "A" . v:b v:name "B" .')
    (tmp_path / 'names.rq').write_text('SELECT ?name WHERE { ?s <urn:v:name> ?name }')
    gold = tmp_path / 'gold.jsonl'
    gold.write_text(json.dumps({'case_id': 'extra', 'query': 'names', 'expected_rows': [{'name': 'A'}]})+'\n')
    report = evaluate_kg(graph, tmp_path, gold, tmp_path / 'report.json')
    assert report['precision'] == .5 and report['recall'] == 1
    assert report['false_positives'] == 1 and report['passed'] == 0
    gold.write_text(json.dumps({'case_id': 'partial', 'query': 'names', 'must_contain': [{'name': 'A'}]})+'\n')
    report = evaluate_kg(graph, tmp_path, gold, tmp_path / 'report.json')
    assert report['precision'] is None and report['passed'] == 1


def test_domain_filter_searches_entire_domain_and_cosine(tmp_path):
    faiss = pytest.importorskip('faiss')
    data = tmp_path / 'data.jsonl'
    # 130 identical other-domain records would crowd out the old candidate shortlist.
    rows = [{'id': f'x{i}', 'domain': 'law', 'text': 'hồ sơ giấy tờ cần thiết để đăng ký thủ tục hành chính'} for i in range(130)]
    rows += [{'id': 'target', 'domain': 'heritage', 'text': 'di sản văn hóa tại hội an có nhiều giá trị lịch sử lâu đời'}]
    data.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows))
    index, metadata, config = (tmp_path / n for n in ('vn.index', 'metadata.sqlite3', 'index_config.json'))
    build_faiss_index(data, index, metadata, config, EmbeddingConfig(batch_size=16), backend='hashing')
    retriever = FaissRetriever(index, metadata, EmbeddingConfig(), backend='hashing')
    query = rows[0]['text']
    result = retriever.search(query, top_k=1, domain='heritage')
    assert len(result) == 1 and result[0]['doc_id'] == 'target'
    assert retriever.search(query, top_k=1, domain='law')[0]['score'] == pytest.approx(1, abs=1e-6)
    assert retriever.search(query, domain='nonexistent') == []


def test_build_resumes_after_encoder_failure(tmp_path, monkeypatch):
    import vn_assistant.faiss_store as module
    from vn_assistant.embedding import HashingEncoder
    rows = [{'id': str(i), 'domain': 'law', 'text': f'Văn bản số {i} hướng dẫn quy trình thực hiện thủ tục đăng ký.'} for i in range(5)]
    data = tmp_path / 'data.jsonl'
    data.write_text('\n'.join(json.dumps(r) for r in rows))
    encoder = HashingEncoder()
    encode = encoder.encode_passages
    calls = 0
    def failing(texts):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('simulated interruption')
        return encode(texts)
    encoder.encode_passages = failing
    monkeypatch.setattr(module, 'create_encoder', lambda *a, **kw: encoder)
    args = (data, tmp_path/'vn.index', tmp_path/'metadata.sqlite3', tmp_path/'index_config.json', EmbeddingConfig(batch_size=2))
    with pytest.raises(RuntimeError, match='simulated'):
        build_faiss_index(*args, backend='hashing')
    encoder.encode_passages = encode
    result = build_faiss_index(*args, backend='hashing')
    assert result['vectors'] == 5
    import faiss
    index = faiss.read_index(str(tmp_path/'vn.index'))
    assert index.ntotal == 5


def test_kg_empty_uses_rag_and_keeps_evidence(tmp_path):
    class EmptyKG:
        def execute(self, *args): return []
    class RAG:
        def search(self, question, top_k, domain, **kwargs): return [{'text': 'evidence', 'domain': domain}]
    processor = QuestionProcessor(QuestionRouter(tmp_path/'missing'), EmptyKG(), RAG())
    result = processor.process('Phường có mã 99999 là gì?')
    assert result['effective_route'] == 'rag_fallback'
    assert result['evidence_count'] == 1


def test_append_reuses_only_a_verified_checkpoint_prefix(tmp_path):
    pytest.importorskip('faiss')
    rows = [{'id':str(i),'domain':'tourism','text':f'Điểm tham quan số {i} có thông tin và địa chỉ theo nguồn thu thập.'} for i in range(2)]
    data = tmp_path/'data.jsonl'
    def save():
        data.write_text('\n'.join(json.dumps(row,ensure_ascii=False) for row in rows))
    save()
    args = (data,tmp_path/'vn.index',tmp_path/'metadata.sqlite3',tmp_path/'index_config.json',EmbeddingConfig(batch_size=2))
    first = build_faiss_index(*args,backend='hashing')
    rows.append({'id':'new','domain':'administration','text':'Danh mục hành chính hiện có các đơn vị được phân chia theo từng mốc thời gian.'})
    save()
    second = build_faiss_index(*args,backend='hashing')
    assert second['resumed_vectors'] == first['vectors'] == 2
    assert second['vectors'] == 3
    rows[0]['text'] = 'Nội dung thay đổi có thể làm vector cũ không còn phù hợp với dữ liệu mới.'
    save()
    with pytest.raises(ValueError,match='encoded checkpoint prefix'):
        build_faiss_index(*args,backend='hashing')
