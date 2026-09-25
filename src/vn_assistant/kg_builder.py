from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef, XSD

from .dataio import infer_domain, iter_records, source_name, unwrap_data
from .normalization import clean_text, normalized_key, stable_id


VN = Namespace("https://w3id.org/vn-assistant/ontology#")
RES = Namespace("https://w3id.org/vn-assistant/resource/")

CLASS_MAP = {
    "Province": VN.Province,
    "District": VN.District,
    "Ward": VN.Ward,
    "HistoricalAdministrativeUnit": VN.HistoricalAdministrativeUnit,
    "Heritage": VN.Heritage,
    "HeritageSite": VN.HeritageSite,
    "WorldHeritage": VN.WorldHeritage,
    "IntangibleHeritage": VN.IntangibleHeritage,
    "Museum": VN.Museum,
    "TourismPlace": VN.TourismPlace,
    "SourceDocument": VN.SourceDocument,
}

REL_MAP = {
    "LOCATED_IN": VN.locatedIn,
    "MERGED_INTO": VN.mergedInto,
    "REPLACED_BY": VN.replacedBy,
    "RECOGNIZED_BY": VN.recognizedBy,
    "MENTIONS": VN.mentions,
    "HAS_SOURCE": VN.hasSource,
}


@dataclass
class Node:
    node_id: str
    label: str
    name: str
    code: str = ""
    description: str = ""
    valid_from: str = ""
    valid_to: str = ""
    source: set[str] = field(default_factory=set)
    source_record_id: set[str] = field(default_factory=set)
    latitude: str = ""
    longitude: str = ""


@dataclass(frozen=True)
class Relationship:
    source_id: str
    rel_type: str
    target_id: str
    source_record_id: str = ""


class KnowledgeGraphBuilder:
    def __init__(self, ontology_path: str | Path):
        self.ontology_path = Path(ontology_path)
        self.nodes: dict[str, Node] = {}
        self.relationships: set[Relationship] = set()
        self.name_index: dict[tuple[str, str], str] = {}
        self.code_index: dict[tuple[str, str], str] = {}
        self.stats: Counter[str] = Counter()

    def add_node(
        self,
        label: str,
        name: Any,
        *,
        code: Any = "",
        description: Any = "",
        valid_from: Any = "",
        valid_to: Any = "",
        source: Any = "",
        source_record_id: Any = "",
        identity_context: Any = "",
        latitude: Any = "",
        longitude: Any = "",
    ) -> str | None:
        name_text = clean_text(name)
        code_text = clean_text(code)
        if not name_text:
            return None
        node_id = self.code_index.get((label, code_text)) if code_text else None
        globally_named = {"Province", "Heritage", "HeritageSite", "WorldHeritage", "IntangibleHeritage", "Museum", "Organization", "SourceDocument"}
        if not code_text and label in globally_named:
            node_id = self.name_index.get((label, normalized_key(name_text)))
        node_id = node_id or stable_id(label, code_text or name_text, identity_context)
        node = self.nodes.get(node_id)
        if node is None:
            node = Node(node_id=node_id, label=label, name=name_text, code=code_text)
            self.nodes[node_id] = node
            self.stats[f"node:{label}"] += 1
        node.name = node.name or name_text
        node.code = node.code or code_text
        node.description = node.description or clean_text(description)[:4000]
        node.valid_from = node.valid_from or clean_text(valid_from)
        node.valid_to = node.valid_to or clean_text(valid_to)
        node.latitude = node.latitude or clean_text(latitude)
        node.longitude = node.longitude or clean_text(longitude)
        if source:
            node.source.add(clean_text(source))
        if source_record_id:
            node.source_record_id.add(clean_text(source_record_id))
        self.name_index[(label, normalized_key(name_text))] = node_id
        if code_text:
            self.code_index[(label, code_text)] = node_id
        return node_id

    def add_relationship(self, source_id: str | None, rel_type: str, target_id: str | None, record_id: str = "") -> None:
        if source_id and target_id and source_id != target_id:
            relationship = Relationship(source_id, rel_type, target_id, clean_text(record_id))
            if relationship not in self.relationships:
                self.relationships.add(relationship)
                self.stats[f"relationship:{rel_type}"] += 1

    def ingest_record(self, record: dict[str, Any]) -> None:
        source = source_name(record)
        record_id = clean_text(record.get("record_id") or record.get("id"))
        data = unwrap_data(record)
        source_lower = source.lower()

        if "vietnam-administrative-division-json-server" in source_lower or "vietnamese-provinces-database" in source_lower:
            self._ingest_current_administration(data, source, record_id)
        elif "sap-nhap" in source_lower or "sáp nhập" in source_lower:
            self._ingest_merger(data, source, record_id)
        elif infer_domain(record) == "heritage":
            self._ingest_heritage(record, data, source, record_id)

    def _ingest_current_administration(self, data: dict[str, Any], source: str, record_id: str) -> None:
        province_code = data.get("idProvince") or data.get("province_code") or data.get("provinceCode")
        ward_code = data.get("idCommune") or data.get("ward_code") or data.get("commune_code")
        name = data.get("name") or data.get("province") or data.get("ward")
        if ward_code:
            province_name = data.get("province_name") or data.get("province")
            ward_id = self.add_node(
                "Ward", name, code=ward_code, valid_from="2025-07-01", source=source,
                source_record_id=record_id, latitude=data.get("lat"), longitude=data.get("lon"),
            )
            province_id = self.code_index.get(("Province", clean_text(province_code)))
            if not province_id and province_name:
                province_id = self.add_node("Province", province_name, code=province_code, source=source)
            self.add_relationship(ward_id, "LOCATED_IN", province_id, record_id)
        else:
            self.add_node(
                "Province", name, code=province_code, valid_from="2025-07-01", source=source,
                source_record_id=record_id, latitude=data.get("lat"), longitude=data.get("lon"),
            )

    def _ingest_merger(self, data: dict[str, Any], source: str, record_id: str) -> None:
        old_ward = data.get("Phường/Xã cũ") or data.get("old_ward") or data.get("old_name")
        old_district = data.get("Quận/Huyện cũ") or data.get("old_district")
        old_province = data.get("Tỉnh/TP cũ (trước sáp nhập)") or data.get("old_province")
        new_province = data.get("Tỉnh/TP mới") or data.get("new_province")
        new_ward = data.get("Phường/Xã mới (từ 1/7/2025)") or data.get("new_ward") or data.get("new_name")
        new_code = data.get("Mã phường/xã mới") or data.get("new_code") or data.get("ward_code")
        area = data.get("Diện tích mới (km²)") or data.get("area_km2")
        merger_type = data.get("Hình thức sáp nhập") or data.get("merger_type")
        description = clean_text(f"{merger_type or ''}; diện tích mới {area or ''} km²").strip("; ")

        old_province_id = self.add_node("Province", old_province, valid_to="2025-06-30", source=source)
        new_province_id = self.add_node("Province", new_province, valid_from="2025-07-01", source=source)
        district_id = self.add_node(
            "District", old_district, valid_to="2025-06-30", source=source,
            identity_context=old_province,
        )
        old_ward_id = self.add_node(
            "HistoricalAdministrativeUnit", old_ward, valid_to="2025-06-30", source=source,
            source_record_id=record_id, identity_context=f"{old_district}|{old_province}",
        )
        new_ward_id = self.add_node(
            "Ward", new_ward, code=new_code, valid_from="2025-07-01", source=source,
            source_record_id=record_id, description=description, identity_context=new_province,
        )
        self.add_relationship(old_ward_id, "LOCATED_IN", district_id, record_id)
        self.add_relationship(district_id, "LOCATED_IN", old_province_id, record_id)
        self.add_relationship(new_ward_id, "LOCATED_IN", new_province_id, record_id)
        self.add_relationship(old_ward_id, "MERGED_INTO", new_ward_id, record_id)
        self.add_relationship(old_ward_id, "REPLACED_BY", new_ward_id, record_id)

    def _ingest_heritage(self, record: dict[str, Any], data: dict[str, Any], source: str, record_id: str) -> None:
        subtype = clean_text(record.get("subtype") or data.get("subtype") or data.get("type") or data.get("category")).lower()
        class_name = "Heritage"
        if "museum" in subtype or "bảo tàng" in subtype:
            class_name = "Museum"
        elif "intangible" in subtype or "phi vật thể" in subtype:
            class_name = "IntangibleHeritage"
        elif "world" in subtype or "unesco" in subtype:
            class_name = "WorldHeritage"
        elif "site" in subtype or "di tích" in subtype:
            class_name = "HeritageSite"

        name = data.get("name") or data.get("title") or data.get("keyword")
        description = data.get("description") or data.get("content") or data.get("cultural_context")
        province = data.get("province") or data.get("province_name")
        entity_id = self.add_node(
            class_name, name, code=data.get("code"), description=description,
            source=source, source_record_id=record_id,
            latitude=data.get("lat") or data.get("latitude"),
            longitude=data.get("lon") or data.get("longitude"),
        )
        province_id = self.add_node("Province", province, source=source) if province else None
        self.add_relationship(entity_id, "LOCATED_IN", province_id, record_id)

        entities = data.get("entities")
        if not entities:
            return
        document_id = self.add_node(
            "SourceDocument", data.get("source_doc") or f"Bản ghi {record_id[:12]}",
            source=source, source_record_id=record_id,
        )
        pairs: list[tuple[str, Any]] = []
        if isinstance(entities, dict):
            for kind, values in entities.items():
                for value in values if isinstance(values, list) else [values]:
                    pairs.append((clean_text(kind).lower(), value))
        elif isinstance(entities, list):
            for value in entities:
                if isinstance(value, dict):
                    pairs.append((clean_text(value.get("type")).lower(), value.get("name") or value.get("text")))
                else:
                    pairs.append(("heritage", value))
        for kind, value in pairs:
            label = "Museum" if "museum" in kind or "bảo tàng" in kind else "Heritage"
            mentioned_id = self.add_node(label, value, source=source, source_record_id=record_id)
            self.add_relationship(document_id, "MENTIONS", mentioned_id, record_id)

    def build(self, dataset_path: str | Path, limit: int = 0) -> dict[str, Any]:
        for index, record in enumerate(iter_records(dataset_path), 1):
            self.stats["records_seen"] += 1
            self.ingest_record(record)
            if limit and index >= limit:
                break
        return self.report(dataset_path)

    def _to_graph(self) -> Graph:
        graph = Graph()
        graph.parse(self.ontology_path, format="turtle")
        graph.bind("vn", VN)
        graph.bind("res", RES)
        for node in self.nodes.values():
            uri = RES[node.node_id]
            graph.add((uri, RDF.type, CLASS_MAP[node.label]))
            graph.add((uri, RDFS.label, Literal(node.name, lang="vi")))
            graph.add((uri, VN.name, Literal(node.name)))
            if node.code:
                graph.add((uri, VN.code, Literal(node.code)))
            if node.description:
                graph.add((uri, VN.description, Literal(node.description, lang="vi")))
            if node.valid_from:
                graph.add((uri, VN.validFrom, Literal(node.valid_from, datatype=XSD.date)))
            if node.valid_to:
                graph.add((uri, VN.validTo, Literal(node.valid_to, datatype=XSD.date)))
            if node.latitude:
                graph.add((uri, VN.latitude, Literal(node.latitude, datatype=XSD.decimal)))
            if node.longitude:
                graph.add((uri, VN.longitude, Literal(node.longitude, datatype=XSD.decimal)))
            for value in sorted(node.source):
                graph.add((uri, VN.sourceName, Literal(value)))
            for value in sorted(node.source_record_id):
                graph.add((uri, VN.sourceRecordId, Literal(value)))
        for rel in self.relationships:
            graph.add((RES[rel.source_id], REL_MAP[rel.rel_type], RES[rel.target_id]))
        return graph

    def write(self, ttl_path: str | Path, owl_path: str | Path, nodes_path: str | Path, relationships_path: str | Path) -> None:
        for path in map(Path, (ttl_path, owl_path, nodes_path, relationships_path)):
            path.parent.mkdir(parents=True, exist_ok=True)
        graph = self._to_graph()
        graph.serialize(destination=str(ttl_path), format="turtle")
        graph.serialize(destination=str(owl_path), format="xml")
        with Path(nodes_path).open("w", encoding="utf-8", newline="") as stream:
            fields = ["id", "label", "name", "code", "description", "valid_from", "valid_to", "source", "source_record_id", "latitude", "longitude"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for node in sorted(self.nodes.values(), key=lambda item: item.node_id):
                writer.writerow({
                    "id": node.node_id, "label": node.label, "name": node.name, "code": node.code,
                    "description": node.description, "valid_from": node.valid_from, "valid_to": node.valid_to,
                    "source": "|".join(sorted(node.source)),
                    "source_record_id": "|".join(sorted(node.source_record_id)),
                    "latitude": node.latitude, "longitude": node.longitude,
                })
        with Path(relationships_path).open("w", encoding="utf-8", newline="") as stream:
            fields = ["source_id", "type", "target_id", "source_record_id"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for rel in sorted(self.relationships, key=lambda item: (item.source_id, item.rel_type, item.target_id)):
                writer.writerow({"source_id": rel.source_id, "type": rel.rel_type, "target_id": rel.target_id, "source_record_id": rel.source_record_id})

    def report(self, dataset_path: str | Path) -> dict[str, Any]:
        return {
            "generated_at": date.today().isoformat(),
            "dataset": str(dataset_path),
            "records_seen": self.stats["records_seen"],
            "nodes": len(self.nodes),
            "relationships": len(self.relationships),
            "counts": dict(sorted(self.stats.items())),
        }


def build_kg(
    dataset_path: str | Path,
    ontology_path: str | Path,
    ttl_path: str | Path,
    owl_path: str | Path,
    nodes_path: str | Path,
    relationships_path: str | Path,
    report_path: str | Path,
    limit: int = 0,
) -> dict[str, Any]:
    builder = KnowledgeGraphBuilder(ontology_path)
    report = builder.build(dataset_path, limit=limit)
    builder.write(ttl_path, owl_path, nodes_path, relationships_path)
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
