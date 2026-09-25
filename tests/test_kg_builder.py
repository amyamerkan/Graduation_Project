import json

from rdflib import Graph

from vn_assistant.kg_builder import build_kg


def test_build_merger_graph(tmp_path):
    dataset = tmp_path / "records.json"
    dataset.write_text(json.dumps({"records": [
        {"record_id": "p1", "provenance": {"source_name": "vietnam-administrative-division-json-server"}, "data": {"idProvince": "92", "name": "Thành phố Cần Thơ"}},
        {"record_id": "w1", "provenance": {"source_name": "vietnam-administrative-division-json-server"}, "data": {"idProvince": "92", "idCommune": "31261", "name": "Xã Cờ Đỏ"}},
        {"record_id": "m1", "provenance": {"source_name": "vietnam-sap-nhap-phuong-xa.csv"}, "data": {"Phường/Xã cũ": "Thị trấn Cờ Đỏ", "Quận/Huyện cũ": "Huyện Cờ Đỏ", "Tỉnh/TP cũ (trước sáp nhập)": "Thành phố Cần Thơ", "Tỉnh/TP mới": "Thành phố Cần Thơ", "Phường/Xã mới (từ 1/7/2025)": "Xã Cờ Đỏ", "Mã phường/xã mới": "31261"}},
    ]}, ensure_ascii=False), encoding="utf-8")
    root = tmp_path / "out"
    report = build_kg(dataset, "ontology/vn_heritage_admin.ttl", root / "kg.ttl", root / "kg.owl", root / "nodes.csv", root / "rels.csv", root / "report.json")
    assert report["nodes"] >= 4
    graph = Graph().parse(root / "kg.ttl")
    result = list(graph.query("PREFIX vn: <https://w3id.org/vn-assistant/ontology#> SELECT ?n WHERE { ?o vn:name 'Thị trấn Cờ Đỏ' ; vn:mergedInto ?n }"))
    assert len(result) == 1

