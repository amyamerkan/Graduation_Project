from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rdflib import Graph


PLACEHOLDER = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")


def _escape_literal(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")


class SparqlService:
    def __init__(self, graph_path: str | Path, query_dir: str | Path):
        self.graph_path = Path(graph_path)
        self.query_dir = Path(query_dir)
        self.graph = Graph()
        self.graph.parse(self.graph_path)

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
        for key, value in params.items():
            placeholder = "{{" + key + "}}"
            if key == "limit":
                rendered = str(max(1, min(int(value), 1000)))
            else:
                rendered = _escape_literal(value)
            template = template.replace(placeholder, rendered)
        return template

    def execute(self, query_name: str, params: dict[str, Any] | None = None) -> list[dict[str, str]]:
        query = self.render_query(query_name, params)
        result = self.graph.query(query)
        rows: list[dict[str, str]] = []
        for row in result:
            rows.append({str(name): str(value) for name, value in row.asdict().items() if value is not None})
        return rows

    def search_entities(self, keyword: str, limit: int = 10) -> list[dict[str, str]]:
        return self.execute("06_entity_search", {"keyword": keyword, "limit": limit})

