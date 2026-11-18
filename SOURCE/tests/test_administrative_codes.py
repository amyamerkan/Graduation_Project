"""Regression contracts for administrative-code lookup and the reported UI bug."""
import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vn_assistant import api
from vn_assistant.administrative_codes import recognize_administrative_code
from vn_assistant.cross_check import CrossChecker, render_administrative_lookup
from vn_assistant.dialogue import resolve_question
from vn_assistant.generation import AnswerService
from vn_assistant.question_processing import QuestionProcessor
from vn_assistant.router import Classification, QuestionRouter, extract_query_plan
from vn_assistant.sparql_service import SparqlService

VN = "https://w3id.org/vn-assistant/ontology#"
LOOKUPS = [
    "00008 thuộc địa phương nào", "mã địa phương 00008 thuộc địa phương nào",
    "Đơn vị có mã 00008 là gì?", "Mã hành chính 00008 thuộc tỉnh nào?",
    "mã đơn vị hành chính 00008 là gì?", "00008 thuộc tỉnh thành nào?",
    "00008 là phường nào?", "00008 ở đâu?",
    "ma dia phuong 00008 thuoc tinh nao", "00008 thuoc dia phuong nao?",
    "Mã:00008 là gì?", "Mã #00008 là gì?", "Mã số 00008 là gì?",
    "MÃ ĐỊA PHƯƠNG 00008 THUỘC ĐỊA PHƯƠNG NÀO?",
]


class NoRAG:
    def __init__(self):
        self.calls = []

    def search(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("Code lookup must not use vector search")


class NoLLM:
    def __init__(self):
        self.calls = []

    def generate(self, *args):
        self.calls.append(args)
        raise AssertionError("Lookup must work while the LLM is unavailable")

    def status(self):
        return {"ready": False, "backend": "disabled_for_test"}


class RecordingKG:
    def __init__(self, rows, changed=None, error=False):
        self.rows, self.changed, self.error = rows, changed, error
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        if self.error:
            raise RuntimeError("test unavailable")
        return copy.deepcopy(self.changed if len(self.calls) > 1 and self.changed is not None else self.rows)


def code_row(**changes):
    return {"unit": "urn:unit:current", "type": VN + "Ward", "code": "00008", "name": "Phường Ngọc Hà",
            "provinceName": "Thành phố Hà Nội", "snapshotDate": "2026-10-24",
            "source_urls": ["https://danhmuchanhchinh.nso.gov.vn/Doi_Chieu_Moi.aspx"], **changes}


def fake_service(tmp_path, rows=None, changed=None, error=False):
    kg = RecordingKG([code_row()] if rows is None else rows, changed=changed, error=error)
    rag, generator = NoRAG(), NoLLM()
    service = AnswerService(QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, rag), generator)
    return service, kg, rag, generator


@pytest.mark.parametrize("question", LOOKUPS)
def test_code_contract_overrides_wrong_classification_and_answers_without_llm(tmp_path, question):
    service, kg, rag, generator = fake_service(tmp_path)
    classified = service.processor.router.classify(question)
    assert (classified.route, classified.domain, classified.method) == ("kg", "administration", "administrative_code_rule")
    stale = Classification(question, "rag", "tourism", .9, .9, "fake")
    plan = extract_query_plan(question, stale)
    assert plan["kg"] == {"query": "03_unit_by_code", "params": {"code": "00008"}}
    assert plan["rag"] is None and plan["route"] == "kg"
    result = service.answer(question)
    assert result["status"] == "answered" and result["generation_mode"] == "structured_kg"
    assert "Mã hành chính 00008 là Phường Ngọc Hà, thuộc Thành phố Hà Nội." in result["answer"]
    assert "2026-10-24" in result["answer"] and "Mường Ảng" not in result["answer"]
    assert result["cross_check"]["question_constraints_checked"] is True
    assert len(kg.calls) == 2 and rag.calls == generator.calls == []
    assert result["citations"][0]["kind"] == "kg"


@pytest.mark.parametrize("question", [
    "Ngày 01/07/2025 đi du lịch Hà Nội?", "Năm 2025 Hà Nội có gì?", "Tháng 12 ở Đà Lạt có gì?",
    "Gợi ý 12 điểm du lịch ở Hà Nội", "34 tỉnh thành có điểm du lịch nào?",
    "Khách sạn ở Huế giá 500000 đồng", "Đà Nẵng cách Huế 100 km?", "Tour 12 ngày ở Huế có gì?",
    "Đi Hà Nội 10 ngày 12 đêm", "Hà Nội có 12.5 triệu khách du lịch?",
    "Số nhà 123 ở Hà Nội", "Quốc lộ 100 ở đâu?",
    "Phường 12 thuộc thành phố nào?", "Quận 10 thuộc tỉnh nào?", "Xã 12 ở đâu?",
    "Gợi ý 12 địa điểm du lịch thuộc Hà Nội", "Lịch trình 12 ở đâu?",
])
def test_dates_prices_quantities_and_addresses_are_not_codes(question):
    assert recognize_administrative_code(question).status == "none"


@pytest.mark.parametrize("question", [
    "00008", "01", "12 là gì?", "Mã 0008 thuộc đâu?", "Mã 100000 thuộc đâu?",
    "00008 và 00070 thuộc đâu?", "mã 00008 và 00070 là gì?",
    "Mã bưu chính 00008 thuộc địa phương nào?", "Mã bưu chính 100000 thuộc đâu?",
    "ma dat phong 00008 la gi?", "Mã tour 00008 thuộc đâu?", "Tour 00008 ở đâu?",
    "Số điện thoại 090 123 4567 ở tỉnh nào?", "Booking code 00008 là gì?",
])
def test_ambiguous_or_other_identifiers_need_clarification_without_retrieval(tmp_path, question):
    service, kg, rag, generator = fake_service(tmp_path)
    result = service.answer(question)
    assert result["status"] == "needs_clarification"
    assert result["claims"] == result["citations"] == []
    assert kg.calls == rag.calls == generator.calls == []


@pytest.mark.parametrize("rows,error", [
    ([], False), ([code_row(code="00070")], False), ([code_row(code=8)], False),
    ([code_row(type=VN + "TourismPlace")], False), ([code_row(type="")], False),
    ([code_row(name="")], False), ([code_row(provinceName="")], False), ([], True),
])
def test_missing_or_invalid_code_evidence_abstains_without_fallback(tmp_path, rows, error):
    service, kg, rag, generator = fake_service(tmp_path, rows=rows, error=error)
    result = service.answer(LOOKUPS[0])
    assert result["status"] == "abstained" and result["cross_check"]["reason"] == "missing_verified_code"
    assert result["claims"] == result["citations"] == [] and rag.calls == generator.calls == []


@pytest.mark.parametrize("question,accepted", [
    ("Ngày 24/10/2026 mã 00008 thuộc Hà Nội không?", True),
    ("Ma 00008 tai ngay 2026-10-24 thuoc thanh pho Ha Noi khong?", True),
    ("Mã 00008 tại ngày 2026-10-24 thuộc tỉnh nào?", True),
    ("Mã 00008 ở thời điểm 24/10/2026 thuộc Hà Nội không?", True),
    ("Mã 00008 thuộc Hà Nội không?", True), ("Mã 00008 thuộc Hà không?", False),
    ("Mã 00008 thuộc thành phố Hồ Chí Minh không?", False),
    ("Mã 00008 thuộc Nam Định không?", False),
    ("Ngày 23/10/2026 mã 00008 thuộc Hà Nội không?", False),
    ("Mã 00008 nam 2020 thuoc Ha Noi khong?", False),
    ("Mã 00008 thuộc Hà Nội ở Hồ Chí Minh?", False),
    ("Mã 00008 thuộc Hà Nội ngày 31/02/2026?", False),
    ("Hom qua ma 00008 thuoc Ha Noi khong?", False),
])
def test_code_date_and_province_must_jointly_match(tmp_path, question, accepted):
    service, kg, rag, generator = fake_service(tmp_path)
    result = service.answer(question)
    assert (result["status"] == "answered") is accepted
    assert rag.calls == generator.calls == []
    if not accepted:
        assert result["claims"] == result["citations"] == []


@pytest.mark.parametrize("changed", [[], [code_row(code="00070")], [code_row(name="Tên thay đổi")],
    [code_row(provinceName="Điện Biên")], [code_row(snapshotDate="2026-10-23")], [code_row(type=VN + "TourismPlace")]])
def test_changed_kg_record_is_not_published(tmp_path, changed):
    service, kg, rag, generator = fake_service(tmp_path, changed=changed)
    result = service.answer(LOOKUPS[0])
    assert result["status"] == "abstained" and result["claims"] == result["citations"] == []
    assert len(kg.calls) == 2 and rag.calls == generator.calls == []


def test_two_matching_records_need_disambiguation(tmp_path):
    rows = [code_row(), code_row(unit="urn:unit:other", name="Phường khác")]
    service, kg, rag, generator = fake_service(tmp_path, rows=rows)
    result = service.answer(LOOKUPS[0])
    assert result["status"] == "needs_clarification" and result["claims"] == []
    assert rag.calls == generator.calls == []


@pytest.mark.parametrize("question", ["Mã 00008 thuộc đâu và có điểm du lịch nào?", "Mã 00008 có diện tích thế nào?", "Mã 00008 thuộc huyện nào?"])
def test_unanswered_additional_fields_are_partial(tmp_path, question):
    service, kg, rag, generator = fake_service(tmp_path)
    result = service.answer(question)
    assert result["status"] == "partial" and "phần mô tả" in result["answer"]
    assert result["cross_check"]["question_constraints_checked"] is False
    assert rag.calls == generator.calls == []


@pytest.mark.parametrize("params", [{"code": "00070"}, {"code": "00008", "province": "Điện Biên", "as_of": ""},
    {"code": "00008", "province": "Hà Nội", "as_of": "2026-10-23"}])
def test_checker_reconstructs_question_instead_of_trusting_plan(params):
    facts, fields = code_row(), ["name", "code", "provinceName", "snapshotDate"]
    claim = {"mode": "fact", "template": "administrative_code_lookup", "text": render_administrative_lookup(facts, fields),
             "fields": fields, "evidence_ids": ["E1"],
             "fact_checks": [{"field": f, "value": facts[f], "evidence_id": "E1"} for f in fields]}
    result = CrossChecker().verify([claim], [{"id": "E1", "kind": "kg", "facts": facts, "current_facts": facts}],
        question="Ngày 24/10/2026 mã 00008 thuộc Hà Nội không?",
        plan={"kg": {"query": "09_unit_at_time", "params": params}})
    assert not result["supported"] and not result["question_constraints_checked"]
    assert "question_plan_constraint_mismatch" in result["rejected"][0]["reasons"]


@pytest.mark.parametrize("question", ["Đơn vị đó thuộc tỉnh nào?", "don vi do thuoc tinh nao?", "ở đâu?"])
def test_dialogue_recognises_bare_code_and_keeps_previous_date(question):
    history = [{"role": "user", "content": "Ngày 01/07/2025, 00008 thuộc đâu?"},
               {"role": "assistant", "content": "Mã 99999 nằm ở Điện Biên."}]
    result = resolve_question(question, history)
    assert result["resolved"] and "00008" in result["question"] and "2025-07-01" in result["question"]
    assert "99999" not in result["question"]


def test_explicit_new_code_overrides_history_and_ambiguous_history_does_not_guess():
    result = resolve_question("00070 thuộc đâu?", [{"role": "user", "content": LOOKUPS[0]}])
    assert result["question"] == "00070 thuộc đâu?" and not result["resolved"]
    for previous in ["00008 và 00070 thuộc đâu?", "Mã 00008 trong năm 2020 thuộc đâu?"]:
        assert resolve_question("Đơn vị đó thuộc tỉnh nào?", [{"role": "user", "content": previous}])["needs_context"]


def test_multiple_user_followups_keep_code_and_date_without_assistant_facts():
    history = [{"role": "user", "content": "Ngày 01/07/2025, 00008 thuộc đâu?"},
               {"role": "assistant", "content": "Mã 99999 ở Điện Biên."},
               {"role": "user", "content": "Đơn vị đó thuộc tỉnh nào?"}]
    resolved = resolve_question("ở đâu?", history)
    assert resolved["resolved"] and "00008" in resolved["question"] and "2025-07-01" in resolved["question"]
    assert "99999" not in resolved["question"]


@pytest.fixture
def real_service(tmp_path):
    # Historical names here are synthetic; production names are checked in the
    # separate live-KG regression script.
    graph = tmp_path / "graph.ttl"
    graph.write_text('''@prefix vn:<https://w3id.org/vn-assistant/ontology#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
<urn:current> a vn:Ward; vn:code "00008"; vn:name "Phường Ngọc Hà"; vn:isCurrentSnapshot true;
 vn:snapshotDate "2026-10-24"^^xsd:date; vn:locatedIn <urn:province> .
<urn:old> a vn:HistoricalAdministrativeUnit; vn:code "00008"; vn:name "Phường Cũ (dữ liệu kiểm thử)";
 vn:isCurrentSnapshot false; vn:snapshotDate "2025-07-01"^^xsd:date; vn:locatedIn <urn:province> .
<urn:province> a vn:Province; vn:code "01"; vn:name "Thành phố Hà Nội" .
<urn:tourism> a vn:TourismPlace; vn:code "00008"; vn:name "Địa điểm không phải đơn vị hành chính" .
''', encoding="utf-8")
    kg = SparqlService(graph, Path(__file__).resolve().parents[1] / "queries")
    processor = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, NoRAG())
    return AnswerService(processor, NoLLM()), processor


def test_real_kg_current_historical_and_accentless_province(real_service):
    service, _ = real_service
    current = service.answer(LOOKUPS[0])
    historical = service.answer("Ngày 01/07/2025 mã 00008 thuộc Hà Nội không?")
    accentless = service.answer("ma 00008 tai ngay 2026-10-24 thuoc Ha Noi khong?")
    assert current["status"] == historical["status"] == accentless["status"] == "answered"
    assert "Phường Ngọc Hà" in current["answer"] and "Phường Cũ" not in current["answer"]
    assert "Phường Cũ" in historical["answer"] and "2025-07-01" in historical["answer"]
    assert service.answer("Ngày 02/07/2025 mã 00008 thuộc Hà Nội không?")["status"] == "abstained"
    assert service.answer("Mã 00008 thuộc Điện Biên không?")["status"] == "abstained"


def test_http_classify_query_answer_chat_share_the_same_contract(real_service):
    service, processor = real_service
    api.app.dependency_overrides.update({api.get_answer_service: lambda: service,
        api.get_processor: lambda: processor, api.get_router: lambda: processor.router})
    try:
        client = TestClient(api.app)
        for question in LOOKUPS[:2]:
            classified = client.post("/v1/classify", json={"question": question}).json()
            assert classified["classification"]["domain"] == "administration"
            queried = client.post("/v1/query", json={"question": question}).json()
            assert queried["rag_results"] == [] and queried["kg_results"][0]["code"] == "00008"
            for endpoint in ("/v1/answer", "/v1/chat"):
                response = client.post(endpoint, json={"question": question})
                assert response.status_code == 200
                result = response.json()
                assert result["status"] == "answered" and result["generation_mode"] == "structured_kg"
        result = client.post("/v1/chat", json={"question": "Đơn vị đó thuộc tỉnh nào?",
            "history": [{"role": "user", "content": "Ngày 01/07/2025, 00008 thuộc đâu?"}]}).json()
        assert result["status"] == "answered" and "Phường Cũ" in result["answer"]
        for question in ("00008", "Mã bưu chính 00008 thuộc đâu?", "Mã 99999 là gì?"):
            result = client.post("/v1/chat", json={"question": question}).json()
            assert result["status"] in {"needs_clarification", "abstained"}
            assert result["claims"] == result["citations"] == []
    finally:
        api.app.dependency_overrides.clear()
