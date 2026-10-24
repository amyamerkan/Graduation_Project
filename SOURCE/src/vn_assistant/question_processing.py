from __future__ import annotations

from time import perf_counter
import re
from typing import Any

from rdflib import Namespace, URIRef

from .router import QuestionRouter, extract_query_plan


VN = Namespace("https://w3id.org/vn-assistant/ontology#")
_HERITAGE_TYPES = {"Heritage", "HeritageSite", "WorldHeritage", "IntangibleHeritage", "TangibleHeritage", "Museum"}
_DOMAIN_TYPES = {
    "heritage": _HERITAGE_TYPES,
    "tourism": _HERITAGE_TYPES | {"TourismPlace", "TourismActivity"},
    "administration": {"AdministrativeUnit", "Ward", "Province", "HistoricalProvince", "District", "HistoricalAdministrativeUnit", "AdministrativeProcedure", "Organization"},
    "law": {"LegalDocument", "LegalArticle"},
}


class QuestionProcessor:
    def __init__(self, router: QuestionRouter, kg_service=None, faiss_retriever=None):
        self.router = router
        self.kg_service = kg_service
        self.faiss_retriever = faiss_retriever

    def process(self, question: str, top_k: int = 5) -> dict[str, Any]:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 100:
            raise ValueError("top_k phải nằm trong [1, 100]")
        started = perf_counter()
        classification = self.router.classify(question)
        plan = extract_query_plan(classification.question, classification)
        match_places = getattr(self.router, "match_tourism_places", lambda question: [])
        named_places = match_places(classification.question) if classification.domain == "tourism" else []
        if len(named_places) == 1 and (plan.get("kg") or {}).get("query") == "08_entity_facts":
            plan["kg"]["params"]["keyword"] = named_places[0]
        if plan["rag"]:
            plan["rag"]["top_k"] = top_k
        timings = {"classification": (perf_counter() - started) * 1000, "kg": 0.0, "rag": 0.0}
        kg_results: list[dict[str, Any]] = []
        rag_results: list[dict[str, Any]] = []
        warnings: list[str] = list(plan.get("warnings", []))
        physical_filters: dict[str, Any] = {"domain": classification.domain, "doc_ids": None, "entity_terms": None}

        allow_retrieval = not plan["constraints"]["unsupported"] and plan.get("scope") != "out_of_scope"
        if plan["kg"] and allow_retrieval:
            kg_started = perf_counter()
            if self.kg_service:
                try:
                    kg_results = self.kg_service.execute(plan["kg"]["query"], plan["kg"]["params"])
                    if plan["kg"]["query"] == "08_entity_facts":
                        allowed_types = {str(VN[name]) for name in _DOMAIN_TYPES.get(classification.domain, set())}
                        rejected_types = [row for row in kg_results if row.get("type") and str(row["type"]) not in allowed_types]
                        unresolved_types = [row for row in kg_results if not row.get("type")]
                        kg_results = self.filter_kg_rows(kg_results, classification.domain, plan["kg"]["query"])
                        if rejected_types:
                            warnings.append("domain_scope_mismatch: Loại thực thể KG không khớp miền câu hỏi; đã loại khỏi minh chứng.")
                        if unresolved_types:
                            warnings.append("domain_scope_unresolved: Kết quả KG thiếu loại thực thể; chưa đủ căn cứ để xác nhận miền.")
                    kg_results = [self._attach_provenance(row) for row in kg_results]
                except Exception as exc:
                    warnings.append(f"KG query failed: {type(exc).__name__}: {exc}")
            else:
                warnings.append("KG chưa được nạp")
            timings["kg"] = (perf_counter() - kg_started) * 1000

        use_rag = allow_retrieval and (plan["rag"] is not None or (plan["kg"] is not None and not kg_results))
        if plan["kg"] and plan["kg"]["query"] == "09_unit_at_time" and not kg_results:
            use_rag = False
        if use_rag:
            rag_started = perf_counter()
            if self.faiss_retriever:
                try:
                    kwargs: dict[str, Any] = {"top_k": top_k, "domain": classification.domain}
                    if classification.domain == "tourism" and named_places:
                        kwargs["entity_terms"] = named_places
                        physical_filters["entity_terms"] = named_places
                    if plan["kg"] and plan["kg"]["query"] == "03_unit_by_code" and not kg_results:
                        kwargs["entity_terms"] = [plan["kg"]["params"]["code"]]
                        physical_filters["entity_terms"] = kwargs["entity_terms"]
                    named = re.search(r"\b(?:Ca trù|Mỹ Sơn|Hội An|Cố đô Huế|Nhã nhạc)\b", classification.question, re.I)
                    if classification.domain == "heritage" and named and not kg_results:
                        kwargs["entity_terms"] = [named.group(0)]
                        physical_filters["entity_terms"] = kwargs["entity_terms"]
                    if plan["route"] == "hybrid" and kg_results:
                        doc_ids, entity_terms = self._retrieval_scope(kg_results)
                        if doc_ids or entity_terms:
                            physical_filters.update({"doc_ids": doc_ids or None, "entity_terms": entity_terms or None})
                            kwargs.update({"doc_ids": doc_ids or None, "entity_terms": entity_terms or None})
                        else:
                            warnings.append("KG không cung cấp định danh nguồn hoặc tên thực thể để giới hạn ứng viên FAISS.")
                    rag_results = self.faiss_retriever.search(classification.question, **kwargs)
                except Exception as exc:
                    warnings.append(f"RAG search failed: {type(exc).__name__}: {exc}")
            else:
                warnings.append("FAISS chưa được lập chỉ mục")
            timings["rag"] = (perf_counter() - rag_started) * 1000

        effective_route = plan["route"]
        if plan["kg"] and not kg_results and rag_results:
            effective_route = "rag_fallback"
        evidence_count = len(kg_results) + len(rag_results)
        status = "ready" if evidence_count else "no_evidence"
        if plan["constraints"]["unsupported"]:
            status = "unsupported_constraints"
        elif plan.get("scope") == "out_of_scope":
            status = "out_of_scope"
        elif warnings and evidence_count:
            status = "partial"
        timings["total"] = (perf_counter() - started) * 1000
        return {
            "question": classification.question,
            "classification": classification.to_dict(),
            "plan": plan,
            "effective_route": effective_route,
            "kg_results": kg_results,
            "rag_results": rag_results,
            "evidence_count": evidence_count,
            "warnings": warnings,
            "status": status,
            "physical_filters": physical_filters,
            "timings_ms": {name: round(value, 3) for name, value in timings.items()},
        }

    @staticmethod
    def filter_kg_rows(rows: list[dict[str, Any]], domain: str, query_name: str) -> list[dict[str, Any]]:
        if query_name != "08_entity_facts":
            return rows
        allowed_types = {str(VN[name]) for name in _DOMAIN_TYPES.get(domain, set())}
        return [row for row in rows if row.get("type") and str(row["type"]) in allowed_types]

    def _attach_provenance(self, row: dict[str, Any]) -> dict[str, Any]:
        graph = getattr(self.kg_service, "graph", None)
        if graph is None:
            return row
        record_ids = set(row.get("source_record_ids", []))
        source_names = set(row.get("source_names", []))
        source_urls = set(row.get("source_urls", []))
        for key in ("entity", "ward", "heritage", "oldUnit", "newUnit", "province", "unit"):
            if row.get(key):
                subject = URIRef(str(row[key]))
                record_ids.update(str(value) for value in graph.objects(subject, VN.sourceRecordId))
                source_names.update(str(value) for value in graph.objects(subject, VN.sourceName))
                source_urls.update(str(value) for value in graph.objects(subject, VN.sourceUrl))
        return {**row, "source_record_ids": sorted(record_ids), "source_names": sorted(source_names), "source_urls": sorted(source_urls)}

    @staticmethod
    def _retrieval_scope(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
        doc_ids = set()
        names = {}
        for row in rows:
            doc_ids.update(str(value) for value in row.get("source_record_ids", []) if value)
            for key in ("name", "wardName", "oldName", "newName", "unitName", "provinceName"):
                value = str(row.get(key, "")).strip()
                if value:
                    names.setdefault(value.casefold(), value)
        return sorted(doc_ids), sorted(names.values(), key=str.casefold)
