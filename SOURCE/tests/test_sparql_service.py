from pathlib import Path
import json

import pytest

from rdflib import Literal, URIRef

from vn_assistant.sparql_service import NAME_PROPERTY, SparqlService


def test_candidate_binding_matches_original_sparql_and_reads_current_names(tmp_path):
    folder = Path(__file__).resolve().parents[1] / "queries"
    graph = tmp_path / "graph.ttl"
    graph.write_text('@prefix vn: <https://w3id.org/vn-assistant/ontology#> . <urn:a> a vn:Ward; vn:name "Xã Mỹ Sơn"; vn:code "00100". <urn:b> a vn:IntangibleHeritage; vn:name "Ca trù".', encoding="utf-8")
    service = SparqlService(graph, folder)
    params = {"keyword": "MỸ SƠN", "limit": 10}
    expected = [{str(k): str(v) for k, v in row.asdict().items()} for row in service.graph.query(service.render_query("08_entity_facts", params))]
    assert service.execute("08_entity_facts", params) == expected
    assert service.execute("08_entity_facts", {"keyword": "Không tồn tại", "limit": 10}) == []
    service.graph.set((URIRef("urn:a"), NAME_PROPERTY, Literal("Xã Tên Mới")))
    assert service.execute("08_entity_facts", params) == []
    assert service.execute("08_entity_facts", {"keyword": "Tên Mới", "limit": 10})[0]["code"] == "00100"


def test_render_preserves_literal_placeholders_and_escapes_quotes(tmp_path):
    graph = tmp_path / "g.ttl"
    graph.write_text("<urn:a> <urn:b> <urn:c> .")
    (tmp_path / "template.rq").write_text('SELECT ?s WHERE { ?s <urn:name> "{{keyword}}" } LIMIT {{limit}}')
    service = SparqlService(graph, tmp_path)
    query = service.render_query("template", {"keyword": '{{limit}}"} UNION {?a ?b ?c}', "limit": 5})
    assert '{{limit}}\\"}' in query
    assert query.endswith("LIMIT 5")


def test_named_blank_nodes_use_original_query_semantics(tmp_path):
    graph = tmp_path / "graph.ttl"
    graph.write_text('@prefix vn: <https://w3id.org/vn-assistant/ontology#> . [] a vn:Heritage; vn:name "Ca trù" .')
    service = SparqlService(graph, Path(__file__).resolve().parents[1] / "queries")
    assert service.execute("08_entity_facts", {"keyword": "Ca trù", "limit": 10})[0]["name"] == "Ca trù"


@pytest.mark.parametrize("query,params", [
    ("04_merger_history", {"old_name": "Xã Cũ"}),
    ("04_merger_history", {"old_name": "không có"}),
    ("02_wards_in_province", {"province": "HÀ NỘI"}),
    ("10_tourism_in_province", {"province": "Hà Nội", "limit": 30}),
])
def test_named_candidate_optimization_preserves_sparql_results(tmp_path, query, params):
    path = tmp_path / "graph.ttl"
    path.write_text('''@prefix vn: <https://w3id.org/vn-assistant/ontology#> .
<urn:p> a vn:Province; vn:name "Thành phố Hà Nội".
<urn:w> a vn:Ward; vn:name "Xã Mới"; vn:code "00001"; vn:locatedIn <urn:p>.
<urn:old> a vn:HistoricalAdministrativeUnit; vn:name "Xã Cũ"; vn:partlyMergedInto <urn:w>.
<urn:poi> a vn:TourismPlace; vn:name "Điểm tham quan Hà Nội"; vn:locatedIn <urn:p>; vn:address "Địa chỉ theo nguồn".
''', encoding="utf-8")
    service = SparqlService(path, Path(__file__).resolve().parents[1] / "queries")
    expected = [{str(k):str(v) for k,v in row.asdict().items() if v is not None}
                for row in service.graph.query(service.render_query(query, params))]
    assert sorted(map(lambda r: json.dumps(r, sort_keys=True), service.execute(query, params))) == sorted(map(lambda r: json.dumps(r, sort_keys=True), expected))
