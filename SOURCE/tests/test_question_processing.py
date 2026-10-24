import pytest
from rdflib import Graph, Literal, Namespace, URIRef

from vn_assistant.question_processing import QuestionProcessor
from vn_assistant.router import QuestionRouter, extract_query_plan


class RecordingKG:
    def __init__(self, rows=None, graph=None):
        self.rows = rows or []
        self.calls = []
        self.graph = graph

    def execute(self, query, params):
        self.calls.append((query, params))
        return self.rows


class RecordingRAG:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def search(self, question, **kwargs):
        self.calls.append((question, kwargs))
        return self.rows


def test_hybrid_filters_candidates_using_kg_provenance_and_names(tmp_path):
    vn = Namespace("https://w3id.org/vn-assistant/ontology#")
    entity = URIRef("urn:heritage:my-son")
    graph = Graph()
    graph.add((entity, vn.sourceRecordId, Literal("record-1")))
    graph.add((entity, vn.sourceName, Literal("Tài liệu gốc")))
    kg = RecordingKG([{"entity": str(entity), "type": str(vn.HeritageSite), "name": "Mỹ Sơn", "provinceName": "Quảng Nam"}], graph)
    rag = RecordingRAG([{"doc_id": "record-1", "text": "Mỹ Sơn có giá trị văn hóa."}])
    processor = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, rag)

    result = processor.process("Mỹ Sơn nằm ở đâu và có giá trị văn hóa gì?", top_k=3)

    assert kg.calls == [("08_entity_facts", {"keyword": "Mỹ Sơn", "limit": 10})]
    assert result["effective_route"] == "hybrid"
    assert result["status"] == "ready"
    assert result["kg_results"][0]["source_record_ids"] == ["record-1"]
    assert result["kg_results"][0]["source_names"] == ["Tài liệu gốc"]
    assert rag.calls[0][1] == {"top_k": 3, "domain": "heritage", "doc_ids": ["record-1"], "entity_terms": ["Mỹ Sơn", "Quảng Nam"]}
    assert result["physical_filters"]["doc_ids"] == ["record-1"]
    assert result["plan"]["rag"]["top_k"] == 3
    assert set(result["timings_ms"]) == {"classification", "kg", "rag", "total"}
    assert all(value >= 0 for value in result["timings_ms"].values())


def test_kg_route_does_not_run_rag_when_facts_exist(tmp_path):
    kg = RecordingKG([{"name": "Phường X", "code": "00070"}])
    rag = RecordingRAG([{"text": "unused"}])
    result = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, rag).process("Đơn vị có mã 00070 là gì?")

    assert result["classification"]["domain"] == "administration"
    assert kg.calls == [("03_unit_by_code", {"code": "00070"})]
    assert rag.calls == []
    assert result["status"] == "ready"


@pytest.mark.parametrize("question", [
    "Danh sách các phường thuộc Hà Nội trong năm 2020?",
    "Ngày 01/01/2020 phường Long Biên thuộc tỉnh nào?",
    "Di tích nào nằm trong bán kính 5 km quanh Hội An?",
    "Di sản nào gần Hội An nhất?",
    "Mỹ Sơn được công nhận năm nào?",
])
def test_unsupported_constraints_never_execute_current_kg(tmp_path, question):
    kg = RecordingKG([{"name": "Current snapshot result"}])
    rag = RecordingRAG([{"text": "Possible textual evidence"}])
    result = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, rag).process(question)

    assert kg.calls == []
    assert rag.calls == []
    assert result["plan"]["kg"] is None
    assert result["plan"]["route"] == "rag"
    assert result["status"] == "unsupported_constraints"
    assert result["warnings"]


def test_empty_kg_falls_back_without_false_entity_filter(tmp_path):
    kg = RecordingKG()
    rag = RecordingRAG([{"text": "Minh chứng"}])
    result = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, rag).process("Phường có mã 99999 là gì?")

    assert result["effective_route"] == "rag_fallback"
    assert rag.calls[0][1] == {"top_k": 5, "domain": "administration", "entity_terms": ["99999"]}
    assert result["physical_filters"]["entity_terms"] == ["99999"]
    assert result["evidence_count"] == 1


def test_missing_services_report_no_evidence(tmp_path):
    processor = QuestionProcessor(QuestionRouter(tmp_path / "missing"))
    result = processor.process("Phường có mã 99999 là gì?")

    assert result["status"] == "no_evidence"
    assert result["evidence_count"] == 0
    assert len(result["warnings"]) == 2


def test_failed_filtered_search_keeps_kg_without_broadening(tmp_path):
    class BrokenRAG:
        def search(self, question, **kwargs):
            raise RuntimeError("search unavailable")

    row = {"name": "Mỹ Sơn", "type": "https://w3id.org/vn-assistant/ontology#HeritageSite"}
    kg = RecordingKG([row])
    result = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, BrokenRAG()).process("Mỹ Sơn nằm ở đâu và có giá trị gì?")

    assert result["status"] == "partial"
    assert result["kg_results"] == [row]
    assert result["rag_results"] == []
    assert any("RAG search failed" in warning for warning in result["warnings"])


@pytest.mark.parametrize("top_k", [0, 101, True, 2.5])
def test_top_k_validation_also_applies_to_kg_queries(tmp_path, top_k):
    processor = QuestionProcessor(QuestionRouter(tmp_path / "missing"))
    with pytest.raises(ValueError, match="top_k"):
        processor.process("Phường có mã 00070 là gì?", top_k=top_k)


def test_current_time_requires_current_evidence_instead_of_merger_guess(tmp_path):
    router = QuestionRouter(tmp_path / "missing")
    question = "Phường Long Biên hiện nay thuộc tỉnh nào?"
    plan = extract_query_plan(question, router.classify(question))

    assert plan["kg"] is None
    assert plan["constraints"]["temporal"]
    assert plan["constraints"]["unsupported"]


def test_descriptive_question_uses_text_without_synthetic_kg_subject(tmp_path):
    router = QuestionRouter(tmp_path / "missing")
    question = "Giới thiệu ý nghĩa văn hóa của Mỹ Sơn"
    plan = extract_query_plan(question, router.classify(question))

    assert plan["intent"] == "textual"
    assert plan["route"] == "rag"
    assert plan["kg"] is None


@pytest.mark.parametrize("entity_type", ["https://w3id.org/vn-assistant/ontology#Ward", "https://example.org/ontology#HeritageSite", None])
def test_generic_heritage_lookup_drops_wrong_or_missing_exact_type(tmp_path, entity_type):
    row = {"name": "Xã Mỹ Sơn"}
    if entity_type:
        row["type"] = entity_type
    kg = RecordingKG([row])
    rag = RecordingRAG([{"text": "candidate text"}])
    result = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, rag).process("Mỹ Sơn thuộc tỉnh nào và có giá trị gì?")

    assert result["kg_results"] == []
    assert result["effective_route"] == "rag_fallback"
    assert result["physical_filters"]["entity_terms"] == ["Mỹ Sơn"]
    prefix = "domain_scope_mismatch" if entity_type else "domain_scope_unresolved"
    assert any(warning.startswith(prefix) for warning in result["warnings"])


def test_generic_kg_keeps_only_matching_domain_rows_before_hybrid_filter(tmp_path):
    vn = "https://w3id.org/vn-assistant/ontology#"
    kg = RecordingKG([
        {"name": "Xã Mỹ Sơn", "type": vn + "Ward"},
        {"name": "Di tích Mỹ Sơn", "type": vn + "HeritageSite"},
    ])
    rag = RecordingRAG([{"text": "matching text"}])
    result = QuestionProcessor(QuestionRouter(tmp_path / "missing"), kg, rag).process("Mỹ Sơn thuộc tỉnh nào và có giá trị gì?")

    assert result["kg_results"] == [{"name": "Di tích Mỹ Sơn", "type": vn + "HeritageSite"}]
    assert rag.calls[0][1]["entity_terms"] == ["Di tích Mỹ Sơn"]
    assert result["status"] == "partial"


@pytest.mark.parametrize("category", ["loại di sản", "nhóm di sản", "danh mục di sản"])
def test_entity_category_is_not_mistaken_for_geographical_province(tmp_path, category):
    router = QuestionRouter(tmp_path / "missing")
    question = f"Ca trù thuộc {category} nào và có giá trị văn hóa gì?"

    plan = extract_query_plan(question, router.classify(question))

    assert plan["route"] == "hybrid"
    assert plan["kg"] == {"query": "08_entity_facts", "params": {"keyword": "Ca trù", "limit": 10}}


def test_heritage_location_list_keeps_actual_province_template(tmp_path):
    router = QuestionRouter(tmp_path / "missing")
    question = "Danh sách các di sản thuộc tỉnh Bắc Ninh?"

    plan = extract_query_plan(question, router.classify(question))

    assert plan["kg"] == {"query": "05_heritage_in_province", "params": {"province": "Bắc Ninh"}}
