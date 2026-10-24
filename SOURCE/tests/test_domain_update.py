from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from vn_assistant.corpus_update import collect_administration, document_from_record, parse_tourism_detail
from vn_assistant.kg_builder import KnowledgeGraphBuilder, VN
from vn_assistant.question_processing import QuestionProcessor
from vn_assistant.router import Classification, QuestionRouter, extract_query_plan
from vn_assistant.sparql_service import SparqlService


@pytest.fixture(scope="module")
def catalogue():
    return collect_administration()[0]


@pytest.fixture()
def versioned_service(tmp_path, catalogue):
    root = Path(__file__).resolve().parents[1]
    builder = KnowledgeGraphBuilder(root / "ontology/vn_heritage_admin.ttl")
    for row in catalogue:
        data = row["data"]
        if row["record_type"] == "administrative_snapshot" and data["code"] in {"01", "22", "00070", "002"}:
            builder.ingest_record(row)
    for row in catalogue:
        data = row["data"]
        if row["record_type"] == "administrative_conversion" and data["old_code"] == "00070" and data["new_code"] == "00070":
            builder.ingest_record(row)
    path = tmp_path / "graph.ttl"
    builder._to_graph().serialize(destination=path, format="turtle")
    return SparqlService(path, root / "queries"), builder


def test_catalogue_dates_are_separate_and_missing_bridges_are_reported(catalogue):
    records, _, report = collect_administration()
    assert report["current_provinces"] == 34
    assert report["legacy_provinces"] == 63
    assert report["skipped_conversion_links"]
    snapshots = {(r["data"]["snapshot"], r["data"]["name"]) for r in records if r["record_type"] == "administrative_snapshot" and r["data"]["code"] == "22"}
    assert ("reorganized2025", "Tỉnh Quảng Ninh") in snapshots
    assert ("current", "Thành phố Quảng Ninh") in snapshots
    assert all(r["domain"] == "administration" for r in catalogue)


def test_reused_ward_code_retains_old_and_new_name(versioned_service):
    service, _ = versioned_service
    for moment, name in [("2025-06-30", "Phường Hàng Trống"), ("2025-07-01", "Phường Hoàn Kiếm"), ("2026-10-24", "Phường Hoàn Kiếm")]:
        rows = service.execute("09_unit_at_time", {"code": "00070", "as_of": moment, "province": "Hà Nội"})
        assert [row["name"] for row in rows] == [name]
        assert rows[0]["snapshotDate"] == moment
    assert service.execute("09_unit_at_time", {"code": "00070", "as_of": "2025-08-01", "province": ""}) == []
    assert service.execute("09_unit_at_time", {"code": "00070", "as_of": "2025-07-01", "province": "Quảng Ninh"}) == []


def test_current_lookup_does_not_return_2025_alias(versioned_service):
    service, builder = versioned_service
    rows = service.execute("03_unit_by_code", {"code": "22"})
    assert [row["name"] for row in rows] == ["Thành phố Quảng Ninh"]
    assert builder.nodes[builder.code_index["Province", "22"]].snapshot_date == "2026-10-24"


def test_partial_conversion_is_not_a_whole_merger(versioned_service):
    service, _ = versioned_service
    rows = service.execute("04_merger_history", {"old_name": "Phường Hàng Trống"})
    assert rows
    assert all(row["transitionType"] == "chuyển một phần địa bàn" for row in rows)


def test_tourism_parser_keeps_address_separate_and_rejects_empty_page():
    html = '<main><div class="listing-shot"><h4>Bảo tàng A</h4><span class="d-block">Địa chỉ: Quận cũ, Hà Nội</span><div class="content-detail">Điểm tham quan trưng bày các tư liệu về thành phố, mở ra nhiều trải nghiệm tìm hiểu lịch sử cho du khách.</div></div></main>'
    result = parse_tourism_detail(BeautifulSoup(html, "html.parser"))
    assert result["address"] == "Quận cũ, Hà Nội"
    assert result["name"] == "Bảo tàng A"
    assert parse_tourism_detail(BeautifulSoup("<main>Không có dữ liệu</main>", "html.parser")) is None


def test_tourism_stays_supported_but_intangible_questions_stop():
    classification = Classification("", "rag", "tourism", .8, .8, "test")
    assert extract_query_plan("Giới thiệu Ca trù", classification)["scope"] == "out_of_scope"
    assert extract_query_plan("Giới thiệu tham quan Bảo tàng Hà Nội", classification)["scope"] == "supported"
    logical = Classification("", "kg", "tourism", .8, .8, "test")
    plan = extract_query_plan("Danh sách điểm tham quan ở Hà Nội", logical)
    assert plan["kg"]["query"] == "10_tourism_in_province"


def test_document_keeps_source_and_snapshot(catalogue):
    document = document_from_record(catalogue[0])
    assert document["source"]["url"].startswith("https://pypi.org/")
    assert "2025-06-30" in document["text"]
    assert document["metadata"]["source_verified"] is False


def test_tourism_alias_binds_kg_to_the_canonical_place(tmp_path):
    class Router(QuestionRouter):
        def classify(self, question):
            return Classification(question, "kg", "tourism", .8, .8, "test")
    class KG:
        def execute(self, name, params):
            self.last = name, params
            return []
    router = Router(tmp_path / "missing")
    router.artifact = {"tourism_entities":["Hồ Hoàn Kiếm"], "tourism_aliases":{"Hồ Gươm":["Hồ Hoàn Kiếm"]}}
    kg = KG()
    result = QuestionProcessor(router, kg).process("Hồ Gươm ở đâu?")
    assert router.match_tourism_places("Giới thiệu Hồ Gươm") == ["Hồ Hoàn Kiếm"]
    assert kg.last == ("08_entity_facts", {"keyword":"Hồ Hoàn Kiếm", "limit":10})
    assert result["plan"]["kg"]["params"]["keyword"] == "Hồ Hoàn Kiếm"
