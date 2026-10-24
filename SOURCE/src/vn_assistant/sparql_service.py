from __future__ import annotations

import re
from functools import lru_cache
from threading import RLock
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.plugins.sparql import prepareQuery


PLACEHOLDER = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")
NAME_PROPERTY = URIRef("https://w3id.org/vn-assistant/ontology#name")


def _escape_literal(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


class SparqlService:
    def __init__(self, graph_path: str | Path, query_dir: str | Path):
        self.graph_path = Path(graph_path)
        self.query_dir = Path(query_dir)
        self.graph = Graph()
        self.graph.parse(self.graph_path)
        self._query_lock = RLock()

    @staticmethod
    @lru_cache(maxsize=128)
    def _prepare(query):
        return prepareQuery(query)

    def available_queries(self) -> list[str]:
        return sorted(path.stem for path in self.query_dir.glob("*.rq"))

    def render_query(self, query_name: str, params: dict[str, Any] | None = None) -> str:
        safe_name = Path(query_name).stem
        if safe_name != query_name or not re.fullmatch(r"[A-Za-z0-9_-]+", safe_name):
            raise ValueError("Tên query không hợp lệ")
        path = self.query_dir / f"{safe_name}.rq"
        if not path.is_file():
            raise KeyError(f"Không có query: {safe_name}")
        template = path.read_text(encoding="utf-8")
        params = params or {}
        missing = set(PLACEHOLDER.findall(template)) - set(params)
        if missing:
            raise ValueError(f"Thiếu tham số: {sorted(missing)}")
        def replace(match):
            key = match.group(1)
            value = params[key]
            if key == "limit":
                return str(max(1, min(int(value), 1000)))
            return _escape_literal(value)
        return PLACEHOLDER.sub(replace, template)

    def execute(self, query_name: str, params: dict[str, Any] | None = None) -> list[dict[str, str]]:
        query = self.render_query(query_name, params)
        if query_name in {"08_entity_facts", "04_merger_history", "02_wards_in_province", "10_tourism_in_province"}:
            key, variable = {"08_entity_facts": ("keyword", "entity"), "04_merger_history": ("old_name", "oldUnit"),
                             "02_wards_in_province": ("province", "province"), "10_tourism_in_province": ("province", "province")}[query_name]
            keyword = str((params or {})[key]).replace("\n", " ").replace("\r", " ").lower()
            candidates = {subject for subject, name in self.graph.subject_objects(NAME_PROPERTY)
                          if keyword in str(name).lower()}
            if not candidates:
                return []
            if len(candidates) <= 1000 and all(isinstance(subject, URIRef) for subject in candidates):
                values = " VALUES ?" + variable + " { " + " ".join(subject.n3() for subject in sorted(candidates, key=str)) + " } "
                query = re.sub(r"(WHERE\s*\{)", lambda match: match.group(1) + values, query, count=1, flags=re.IGNORECASE)
        with self._query_lock:
            result = self.graph.query(self._prepare(query))
            rows = [{str(name): str(value) for name, value in row.asdict().items() if value is not None} for row in result]
        return rows

    def search_entities(self, keyword: str, limit: int = 10) -> list[dict[str, str]]:
        return self.execute("06_entity_search", {"keyword": keyword, "limit": limit})
