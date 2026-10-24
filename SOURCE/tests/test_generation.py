import copy
import json

import pytest

from vn_assistant.generation import AnswerService
from vn_assistant.llm import LLMUnavailableError
from vn_assistant.question_processing import QuestionProcessor


def fact(name="Phường A", code="00070", uri="urn:unit:a"):
    return {
        "unit": uri,
        "name": name,
        "code": code,
        "type": "https://w3id.org/vn-assistant/ontology#Ward",
        "source_record_ids": ["local-source-1"],
        "source_names": ["Bộ dữ liệu địa giới"],
    }


def processed(kg=None, rag=None, query="03_unit_by_code", status="ready", unsupported=False):
    return {
        "question": "Đơn vị có mã 00070 là gì?",
        "classification": {"route": "kg", "domain": "administration"},
        "plan": {"kg": {"query": query, "params": {"code": "00070"}} if query else None,
                 "constraints": {"unsupported": unsupported}},
        "kg_results": kg or [],
        "rag_results": rag or [],
        "status": status,
        "warnings": [],
        "effective_route": "kg" if kg else "rag",
    }


class FakeKG:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        if self.error:
            raise self.error
        return copy.deepcopy(self.rows)


class FakeProcessor:
    def __init__(self, result, current_rows=None, kg_error=None):
        self.result = result
        self.kg_service = FakeKG(result["kg_results"] if current_rows is None else current_rows, error=kg_error)
        self.calls = []

    def process(self, question, top_k=5):
        self.calls.append((question, top_k))
        return copy.deepcopy(self.result)


class FakeGenerator:
    def __init__(self, raw='{"claim_ids":["E01-C01"]}', error=None):
        self.raw = raw
        self.error = error
        self.calls = []

    def generate(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.raw

    def status(self):
        return {"backend": "fake", "ready": True}


def test_answer_selects_server_claim_requeries_and_renders_internal_provenance():
    processor = FakeProcessor(processed(kg=[fact()]))
    generator = FakeGenerator()
    result = AnswerService(processor, generator).answer("question", top_k=3)
    assert result["status"] == "answered"
    assert "Phường A" in result["answer"] and "00070" in result["answer"]
    assert "[1]" in result["answer"] and "Nguồn minh chứng" in result["answer"]
    assert "bản ghi KG nội bộ; Bộ dữ liệu địa giới (1 bản ghi nguồn)" in result["answer"]
    assert result["citations"][0]["source_url"] is None
    assert result["claims"][0]["verification"] == "exact_kg_fact_match"
    assert result["cross_check"]["supported_count"] == 1
    assert processor.calls == [("question", 3)]
    assert processor.kg_service.calls == [("03_unit_by_code", {"code": "00070"})]
    assert len(generator.calls) == 1
    assert all(value >= 0 for value in result["timings_ms"].values())


def test_no_evidence_abstains_before_generation():
    processor = FakeProcessor(processed(query=None, status="no_evidence"))
    generator = FakeGenerator()
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "abstained"
    assert result["claims"] == result["citations"] == []
    assert generator.calls == []


def test_unsupported_constraints_abstain_even_with_valid_evidence():
    processor = FakeProcessor(processed(kg=[fact()], unsupported=True))
    generator = FakeGenerator()
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "unsupported_constraints"
    assert generator.calls == []
    assert processor.kg_service.calls == []


@pytest.mark.parametrize("raw", [
    '{"claim_ids":["invented-id"]}',
    '{"claim_ids":["E01-C01","E01-C01"]}',
    '{"claim_ids":["E01-C01"],"answer":"Mã 99999"}',
    '{"claim_ids":["E01-C01"],"claim_ids":[]}',
    '{"claim_ids":["E01-C01","E02-C01","E03-C01","E04-C01"]}',
    '{"claim_ids":[null]}',
    'Đây là câu trả lời {"claim_ids":["E01-C01"]}',
    '{"claim_ids":NaN}',
    '```json\n{"claim_ids":["E01-C01"]}\n``` extra',
    'x' * 8193,
])
def test_invalid_model_output_cannot_publish_claims_or_sources(raw):
    processor = FakeProcessor(processed(kg=[fact()]))
    generator = FakeGenerator(raw)
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["status"] == "invalid_output"
    assert result["claims"] == result["citations"] == []
    assert "99999" not in result["answer"]
    assert processor.kg_service.calls == []
    assert len(generator.calls) == 1


def test_optional_json_fence_is_accepted():
    processor = FakeProcessor(processed(kg=[fact()]))
    generator = FakeGenerator('```json\n{"claim_ids":["E01-C01"]}\n```')
    assert AnswerService(processor, generator).answer("question")["status"] == "answered"


def test_single_sentence_stop_after_exact_json_does_not_discard_verified_answer():
    processor = FakeProcessor(processed(kg=[fact()]))
    generator = FakeGenerator('{"claim_ids":["E01-C01"]}.')
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "answered"
    assert result["cross_check"]["supported_count"] == 1


@pytest.mark.parametrize("suffix", ["..", ". Additional answer", ".{\"claim_ids\":[]}"])
def test_sentence_wrapper_does_not_allow_trailing_prose_or_second_object(suffix):
    processor = FakeProcessor(processed(kg=[fact()]))
    generator = FakeGenerator('{"claim_ids":["E01-C01"]}' + suffix)
    assert AnswerService(processor, generator).answer("question")["status"] == "abstained"


def test_no_claim_selection_abstains():
    processor = FakeProcessor(processed(kg=[fact()]))
    result = AnswerService(processor, FakeGenerator('{"claim_ids":[]}')).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "model_selected_no_claims"


def test_model_unavailable_propagates_for_api_503():
    processor = FakeProcessor(processed(kg=[fact()]))
    with pytest.raises(LLMUnavailableError):
        AnswerService(processor, FakeGenerator(error=LLMUnavailableError("offline"))).answer("question")


@pytest.mark.parametrize("current", [[], [fact(uri="urn:unit:different")], [fact(), fact(uri="urn:unit:new")]])
def test_kg_membership_changes_force_abstention(current):
    processor = FakeProcessor(processed(kg=[fact()]), current_rows=current)
    result = AnswerService(processor, FakeGenerator()).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "kg_snapshot_membership_changed"
    assert result["claims"] == result["citations"] == []


def test_kg_value_change_is_detected_by_independent_checker():
    processor = FakeProcessor(processed(kg=[fact()]), current_rows=[fact(code="12345")])
    result = AnswerService(processor, FakeGenerator()).answer("question")
    assert result["status"] == "abstained"
    assert "kg_snapshot_changed" in result["cross_check"]["rejected"][0]["reasons"]
    assert result["claims"] == result["citations"] == []


def test_refresh_failure_is_closed_and_does_not_expose_exception_body():
    processor = FakeProcessor(processed(kg=[fact()]), kg_error=RuntimeError("private database credentials"))
    result = AnswerService(processor, FakeGenerator()).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "kg_refresh_failed:RuntimeError"
    assert "private database credentials" not in json.dumps(result)


def test_only_supported_claims_and_their_sources_are_returned():
    first = fact()
    second = fact(name="Phường B", code="00071", uri="urn:unit:b")
    current_second = {**second, "code": "12345"}
    processor = FakeProcessor(processed(kg=[first, second]), current_rows=[first, current_second])
    generator = FakeGenerator('{"claim_ids":["E01-C01","E02-C01"]}')
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "partial"
    assert len(result["claims"]) == len(result["citations"]) == 1
    assert result["cross_check"]["rejected_count"] == 1
    assert "Phường B" not in result["answer"]


def test_limited_list_is_marked_partial():
    rows = [fact(), fact(name="Phường B", code="00071", uri="urn:unit:b")]
    processor = FakeProcessor(processed(kg=rows, query="02_wards_in_province"))
    result = AnswerService(processor, FakeGenerator()).answer("question")
    assert result["status"] == "partial"
    assert any("danh sách đầy đủ" in warning for warning in result["warnings"])


def rag(text="Di sản A có giá trị lịch sử và kiến trúc đặc sắc.", score=.8, doc_id="document-a", url="https://example.org/source"):
    return {"text": text, "score": score, "doc_id": doc_id, "chunk_id": doc_id + "-0", "title": "Tài liệu di sản", "source_url": url}


def test_rag_answers_keep_exact_excerpt_and_only_selected_url():
    rows = [rag(), rag(doc_id="document-b", url="https://example.org/unused")]
    processor = FakeProcessor(processed(rag=rows, query=None))
    result = AnswerService(processor, FakeGenerator()).answer("question")
    assert result["status"] == "answered"
    assert rows[0]["text"] in result["answer"]
    assert result["citations"][0]["source_url"] == "https://example.org/source"
    assert "unused" not in result["answer"]
    assert len(result["citations"]) == 1
    assert processor.kg_service.calls == []


def test_low_score_rag_abstains_before_llm():
    processor = FakeProcessor(processed(rag=[rag(score=.69)], query=None))
    generator = FakeGenerator()
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "abstained"
    assert generator.calls == []


def test_extract_conflicting_with_kg_code_is_rejected():
    processor = FakeProcessor(processed(kg=[fact()], rag=[rag("Phường A có mã hành chính 12345.")]))
    generator = FakeGenerator('{"claim_ids":["E02-C01"]}')
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "abstained"
    assert "kg_code_conflict" in result["cross_check"]["rejected"][0]["reasons"]


def test_kg_newly_appearing_after_rag_fallback_abstains():
    result = processed(rag=[rag()], query="08_entity_facts")
    result["plan"]["kg"]["params"] = {"name": "Di sản A"}
    processor = FakeProcessor(result, current_rows=[fact()])
    result = AnswerService(processor, FakeGenerator()).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "kg_snapshot_membership_changed"


def test_missing_kg_code_cannot_answer_using_generic_rag():
    processor = FakeProcessor(processed(rag=[rag()]))
    generator = FakeGenerator()
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "missing_verified_code"
    assert generator.calls == []


def test_count_question_without_validated_count_abstains_before_llm():
    data = processed(kg=[fact()], query="02_wards_in_province")
    data["question"] = "Hà Nội có bao nhiêu phường?"
    generator = FakeGenerator()
    result = AnswerService(FakeProcessor(data), generator).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "missing_verified_count"
    assert generator.calls == []


def test_refresh_uses_same_typed_domain_filter_as_question_processing():
    heritage = {"entity": "urn:heritage:myson", "name": "Mỹ Sơn", "type": "https://w3id.org/vn-assistant/ontology#WorldHeritage"}
    ward = {"entity": "urn:ward:myson", "name": "Mỹ Sơn", "type": "https://w3id.org/vn-assistant/ontology#Ward"}
    data = processed(kg=[heritage], query="08_entity_facts")
    data["classification"]["domain"] = "heritage"
    data["plan"]["kg"]["params"] = {"name": "Mỹ Sơn"}

    class TypedProcessor(FakeProcessor):
        filter_kg_rows = staticmethod(QuestionProcessor.filter_kg_rows)

    processor = TypedProcessor(data, current_rows=[heritage, ward])
    result = AnswerService(processor, FakeGenerator()).answer("question")
    assert result["status"] == "answered"
    assert result["cross_check"]["supported_count"] == 1
    assert "ambiguous_entity" not in result["warnings"]


def test_distinct_homonym_uris_are_partial_and_explained_to_user():
    rows = [fact(), fact(name="Phường A", code="00071", uri="urn:unit:another")]
    data = processed(kg=rows, query="08_entity_facts")
    data["plan"]["kg"]["params"] = {"name": "Phường A"}
    result = AnswerService(FakeProcessor(data), FakeGenerator()).answer("question")
    assert result["status"] == "partial"
    assert "ambiguous_entity" in result["warnings"]
    assert "khớp với nhiều thực thể" in result["answer"]


def test_multiple_rdf_types_of_same_uri_do_not_trigger_homonym_warning():
    first = {"entity": "urn:heritage:catru", "name": "Ca trù", "type": "https://w3id.org/vn-assistant/ontology#Heritage"}
    second = {**first, "type": "https://w3id.org/vn-assistant/ontology#IntangibleHeritage"}
    data = processed(kg=[first, second], query="08_entity_facts")
    data["plan"]["kg"]["params"] = {"name": "Ca trù"}
    result = AnswerService(FakeProcessor(data), FakeGenerator()).answer("question")
    assert result["status"] == "answered"
    assert "ambiguous_entity" not in result["warnings"]


def test_existing_code_requires_selected_verified_code_fact():
    processor = FakeProcessor(processed(kg=[fact()], rag=[rag()]))
    generator = FakeGenerator('{"claim_ids":["E02-C01"]}')
    result = AnswerService(processor, generator).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "missing_requested_fact(code)"
    assert result["claims"] == result["citations"] == []


def test_explicit_heritage_type_request_is_partial_when_only_rag_selected():
    row = {"entity": "urn:heritage:a", "name": "Di sản A", "type": "https://w3id.org/vn-assistant/ontology#Heritage"}
    data = processed(kg=[row], rag=[rag()], query="08_entity_facts")
    data["question"] = "Di sản A là loại di sản nào?"
    data["plan"]["kg"]["params"] = {"name": "Di sản A"}
    result = AnswerService(FakeProcessor(data), FakeGenerator('{"claim_ids":["E02-C01"]}')).answer("question")
    assert result["status"] == "partial"
    assert "missing_requested_fact(type)" in result["warnings"]
    assert "chưa xác nhận được loại di sản" in result["answer"]


def test_selected_type_fact_covers_explicit_heritage_type_request():
    row = {"entity": "urn:heritage:a", "name": "Di sản A", "type": "https://w3id.org/vn-assistant/ontology#Heritage"}
    data = processed(kg=[row], query="08_entity_facts")
    data["question"] = "Di sản A là loại di sản nào?"
    data["plan"]["kg"]["params"] = {"name": "Di sản A"}
    result = AnswerService(FakeProcessor(data), FakeGenerator()).answer("question")
    assert result["status"] == "answered"
    assert "missing_requested_fact(type)" not in result["warnings"]


@pytest.mark.parametrize("question, field", [
    ("Di sản A thuộc tỉnh nào?", "provinceName"),
    ("Văn bản A có hiệu lực từ ngày nào?", "validFrom"),
    ("Văn bản A kết thúc hiệu lực ngày nào?", "validTo"),
])
def test_missing_requested_location_or_validity_is_explicit_partial(question, field):
    data = processed(kg=[fact()], query="08_entity_facts")
    data["question"] = question
    data["plan"]["kg"]["params"] = {"name": "A"}
    result = AnswerService(FakeProcessor(data), FakeGenerator()).answer("question")
    assert result["status"] == "partial"
    assert f"missing_requested_fact({field})" in result["warnings"]
    assert "chưa xác nhận được" in result["answer"]


def test_statistics_requires_selected_count_claim_even_when_count_exists_in_kg():
    data = processed(kg=[{"type": "https://w3id.org/vn-assistant/ontology#Province", "count": "34"}], rag=[rag()], query="07_kg_statistics")
    data["question"] = "Thống kê các loại thực thể trong KG"
    data["plan"]["kg"]["params"] = {}
    result = AnswerService(FakeProcessor(data), FakeGenerator('{"claim_ids":["E02-C01"]}')).answer("question")
    assert result["status"] == "abstained"
    assert result["cross_check"]["reason"] == "missing_requested_fact(count)"


def test_large_kg_provenance_is_kept_structured_and_summarized_in_answer():
    row = fact()
    row["source_record_ids"] = [f"local-source-{number}" for number in range(150)]
    row["source_names"] = ["D" * 500]
    result = AnswerService(FakeProcessor(processed(kg=[row])), FakeGenerator()).answer("question")
    assert result["status"] == "answered"
    assert result["citations"][0]["source_record_ids"] == row["source_record_ids"]
    assert "(150 bản ghi nguồn)" in result["answer"]
    assert "local-source-149" not in result["answer"]
    assert len(result["answer"]) < 1000
