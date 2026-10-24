import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph, Literal, URIRef

from vn_assistant import api
from vn_assistant.cross_check import CrossChecker, render_fact_claim
from vn_assistant.dialogue import resolve_question
from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import SCHEMA
from vn_assistant.metadata_retriever import MetadataFaissRetriever, prepare_lexical_index
from vn_assistant.router import QuestionRouter, extract_query_plan
from vn_assistant.sparql_service import SparqlService


@pytest.fixture
def dated_service(tmp_path):
    path = tmp_path / "g.ttl"
    path.write_text('''@prefix vn:<https://w3id.org/vn-assistant/ontology#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
<urn:a> a vn:Ward; vn:name "Phường A"; vn:code "00070"; vn:validFrom "2025-07-01"^^xsd:date; vn:locatedIn <urn:p> .
<urn:p> a vn:Province; vn:name "Thành phố Hà Nội" .
''', encoding="utf-8")
    return SparqlService(path, Path(__file__).resolve().parents[1] / "queries")


@pytest.mark.parametrize("day,province,found", [
    ("2025-07-01", "Hà Nội", True), ("2025-06-30", "Hà Nội", False),
    ("2026-10-23", "Hà Nội", False), ("2025-07-01", "Quảng Ninh", False),
    ("", "Hà Nội", True), ("2025-07-01", "", True),
])
def test_joint_spatial_temporal_query_uses_snapshot_limits(dated_service, day, province, found):
    rows = dated_service.execute("09_unit_at_time", {"code": "00070", "as_of": day, "province": province})
    assert bool(rows) is found


def test_prepared_query_cache_does_not_cache_facts(dated_service):
    params = {"code": "00070", "as_of": "2025-07-01", "province": "Hà Nội"}
    assert dated_service.execute("09_unit_at_time", params)
    dated_service.graph.set((URIRef("urn:a"), URIRef("https://w3id.org/vn-assistant/ontology#code"), Literal("00071")))
    assert dated_service.execute("09_unit_at_time", params) == []


def test_province_question_wording_does_not_become_a_place_name(tmp_path):
    question = "Đơn vị mã 00070 thuộc tỉnh thành nào?"
    plan = extract_query_plan(question, QuestionRouter(tmp_path / "missing").classify(question))
    assert plan["kg"]["query"] == "03_unit_by_code"


def test_distance_without_numerical_radius_is_still_unsupported(tmp_path):
    question = "Từ Hội An đến Mỹ Sơn cách bao nhiêu km?"
    plan = extract_query_plan(question, QuestionRouter(tmp_path / "missing").classify(question))
    assert plan["constraints"]["spatial"] and plan["constraints"]["unsupported"]
    assert plan["kg"] is None


@pytest.mark.parametrize("question", [
    "Ngày 01/07/2025 mã 00070 thuộc thành phố Hà Nội không?",
    "Mã hành chính 00070 tại ngày 2025-7-1 thuộc tỉnh nào?",
])
def test_router_preserves_code_and_normalizes_date(tmp_path, question):
    plan = extract_query_plan(question, QuestionRouter(tmp_path / "missing").classify(question))
    assert plan["kg"]["query"] == "09_unit_at_time"
    assert plan["kg"]["params"]["code"] == "00070"
    assert plan["kg"]["params"]["as_of"] == "2025-07-01"
    assert not plan["constraints"]["unsupported"]


@pytest.mark.parametrize("question", ["Ngày 31/02/2025 mã 00070 thuộc đâu?", "Trước ngày 01/07/2025 mã 00070 thuộc đâu?", "Mã 00070 nằm trong bán kính 5 km ngày 01/07/2025?"])
def test_unsupported_or_invalid_constraints_do_not_become_supported(tmp_path, question):
    plan = extract_query_plan(question, QuestionRouter(tmp_path / "missing").classify(question))
    assert plan["constraints"]["unsupported"]
    assert plan["kg"] is None


@pytest.mark.parametrize("question", [
    "Hôm qua mã 00070 thuộc thành phố Hà Nội không?",
    "Hôm nay mã 00070 thuộc thành phố Hà Nội không?",
    "Ngày mai mã 00070 thuộc thành phố Hà Nội không?",
    "Mã 00070 thuộc thành phố Hà Nội vào năm 2020 không?",
    "Ngày 01/07/2025 mã 00070 thuộc thành phố Hà Nội, còn năm 2020 thì sao?",
    "Mã 00070 thuộc thành phố Hà Nội ngày 01.07.2025 không?",
    "Trước 01/07/2025 mã 00070 thuộc thành phố Hà Nội không?",
    "Mã 00070 thuộc thành phố Hà Nội từ ngày 01/07/2025 không?",
])
def test_other_temporal_constraints_are_not_cleared_by_province_filter(tmp_path, question):
    plan = extract_query_plan(question, QuestionRouter(tmp_path / "missing").classify(question))
    assert plan["constraints"]["unsupported"]
    assert plan["kg"] is None


@pytest.mark.parametrize("moment,accepted", [("2025-06-30", False), ("2025-07-01", True), ("2025-07-15", True), ("2025-07-31", True), ("2025-08-01", False)])
def test_bounded_interval_filters_and_cross_check_agree(dated_service, moment, accepted):
    valid_to = "https://w3id.org/vn-assistant/ontology#validTo"
    dated_service.graph.add((URIRef("urn:a"), URIRef(valid_to), Literal("2025-07-31", datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))))
    plan = {"kg": {"query": "09_unit_at_time", "params": {"code": "00070", "as_of": moment, "province": "Hà Nội"}}}
    assert bool(dated_service.execute("09_unit_at_time", plan["kg"]["params"])) is accepted
    facts = {"name": "Phường A", "code": "00070", "provinceName": "Thành phố Hà Nội", "validFrom": "2025-07-01", "validTo": "2025-07-31"}
    fields = list(facts)
    claim = {"mode": "fact", "text": render_fact_claim(facts, fields), "fields": fields, "evidence_ids": ["E1"],
             "fact_checks": [{"evidence_id": "E1", "field": field, "value": facts[field]} for field in fields]}
    checked = CrossChecker().verify([claim], [{"id": "E1", "kind": "kg", "facts": facts, "current_facts": facts}], plan=plan)
    assert bool(checked["supported"]) is accepted


@pytest.mark.parametrize("date_value,province,accepted", [("2025-07-01", "Hà Nội", True), ("2025-06-30", "Hà Nội", False), ("2026-01-01", "Hà Nội", False), ("2025-07-01", "Quảng Ninh", False)])
def test_cross_check_independently_checks_constraints(date_value, province, accepted):
    facts = {"name": "Phường A", "code": "00070", "provinceName": "Thành phố Hà Nội", "validFrom": "2025-07-01"}
    fields = ["name", "code", "provinceName", "validFrom"]
    claim = {"mode": "fact", "text": render_fact_claim(facts, fields), "fields": fields, "evidence_ids": ["E1"],
             "fact_checks": [{"evidence_id": "E1", "field": field, "value": facts[field]} for field in fields]}
    plan = {"kg": {"query": "09_unit_at_time", "params": {"as_of": date_value, "province": province}}}
    result = CrossChecker().verify([claim], [{"id": "E1", "kind": "kg", "facts": facts, "current_facts": facts}], plan=plan)
    assert bool(result["supported"]) is accepted
    assert result["constraints_checked"] is True


def test_text_cannot_substitute_for_temporal_verification():
    text = "Phường A có nhiều công trình văn hóa quan trọng."
    result = CrossChecker().verify([{"mode": "extractive", "text": text, "evidence_ids": ["E1"]}],
        [{"id": "E1", "kind": "rag", "text": text}], plan={"kg": {"query": "09_unit_at_time", "params": {"as_of": "2025-07-01"}}})
    assert result["supported"] == []


def test_dialogue_uses_user_reference_and_ignores_assistant_invention():
    result = resolve_question("Đơn vị đó thuộc tỉnh nào?", [{"role": "user", "content": "Mã 00070 là gì?"}, {"role": "assistant", "content": "Mã 99999 thuộc tỉnh giả."}])
    assert "00070" in result["question"] and "99999" not in result["question"]
    assert result["resolved"]
    assert resolve_question("Đơn vị đó thuộc tỉnh nào?", [])["needs_context"]
    assert not resolve_question("Giới thiệu Ca trù", [])["needs_context"]


def test_metadata_faiss_filters_and_reuses_passage_vectors(tmp_path):
    database = tmp_path / "metadata.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA)
        connection.executemany("INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?)", [
            (0, "a:0", "a", "Ca trù có giá trị văn hóa lâu đời.", "Ca trù", "heritage", "s", ""),
            (1, "b:0", "b", "Ca trù có quy định riêng trong tài liệu.", "Ca trù", "law", "s", ""),
            (2, "c:0", "c", "Hội An là điểm du lịch trong dữ liệu.", "Hội An", "tourism", "s", ""),
        ])
    report = prepare_lexical_index(database, tmp_path / "lexical.sqlite3")
    assert report["passages"] == 3
    retriever = MetadataFaissRetriever(database, EmbeddingConfig(), backend="hashing")
    first = retriever.search("Ca trù văn hóa", domain="heritage", entity_terms=["CA TRÙ"])
    assert len(first) == 1 and first[0]["doc_id"] == "a" and first[0]["retrieval_mode"] == "lexical_candidates_faiss"
    count = len(retriever._vectors)
    retriever.search("Ca trù văn hóa", domain="heritage")
    assert len(retriever._vectors) == count
    assert retriever.search("Ca trù", domain="heritage", doc_ids=[]) == []
    assert retriever.search('Ca trù " OR 1=1 --', domain="law")[0]["domain"] == "law"


def test_ui_assets_and_chat_validation_are_served():
    client = TestClient(api.app)
    assert client.get("/").status_code == 200
    assert "Tri Việt" in client.get("/").text
    assert client.get("/assets/app.js").status_code == 200
    api.app.dependency_overrides[api.get_answer_service] = lambda: object()
    try:
        assert client.post("/v1/chat", json={"question": "  "}).status_code == 422
        assert client.post("/v1/chat", json={"question": "a" * 2001}).status_code == 422
        assert client.post("/v1/chat", json={"question": "abc", "history": [{"role": "system", "content": "bad"}]}).status_code == 422
        result = client.post("/v1/chat", json={"question": "Đơn vị đó thuộc tỉnh nào?"})
        assert result.status_code == 200 and result.json()["status"] == "needs_clarification"
    finally:
        api.app.dependency_overrides.clear()
