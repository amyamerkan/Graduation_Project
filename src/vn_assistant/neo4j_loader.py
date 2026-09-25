from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .normalization import safe_label


def _batches(items: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def load_neo4j(
    nodes_path: str | Path,
    relationships_path: str | Path,
    uri: str,
    user: str,
    password: str,
    batch_size: int = 1000,
) -> dict[str, int]:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("Thiếu neo4j Python driver") from exc
    with Path(nodes_path).open("r", encoding="utf-8-sig", newline="") as stream:
        nodes = list(csv.DictReader(stream))
    with Path(relationships_path).open("r", encoding="utf-8-sig", newline="") as stream:
        relationships = list(csv.DictReader(stream))

    node_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for node in nodes:
        node_groups[safe_label(node["label"])].append(node)
    rel_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for relationship in relationships:
        rel_groups[safe_label(relationship["type"])].append(relationship)

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    with driver.session() as session:
        session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE").consume()
        for label, group in node_groups.items():
            query = f"""
            UNWIND $rows AS row
            MERGE (n:Entity:{label} {{id: row.id}})
            SET n.name = row.name, n.code = row.code, n.description = row.description,
                n.valid_from = row.valid_from, n.valid_to = row.valid_to,
                n.source = row.source, n.source_record_id = row.source_record_id,
                n.latitude = row.latitude, n.longitude = row.longitude
            """
            for batch in _batches(group, batch_size):
                session.run(query, rows=batch).consume()
        for rel_type, group in rel_groups.items():
            query = f"""
            UNWIND $rows AS row
            MATCH (source:Entity {{id: row.source_id}}), (target:Entity {{id: row.target_id}})
            MERGE (source)-[r:{rel_type}]->(target)
            SET r.source_record_id = row.source_record_id
            """
            for batch in _batches(group, batch_size):
                session.run(query, rows=batch).consume()
    driver.close()
    return {"nodes": len(nodes), "relationships": len(relationships)}

