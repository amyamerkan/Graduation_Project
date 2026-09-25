from __future__ import annotations

from typing import Any

from .router import QuestionRouter, extract_query_plan


class QuestionProcessor:
    """Implements Step 1 (classification) and Step 2 (physical retrieval)."""

    def __init__(self, router: QuestionRouter, kg_service=None, faiss_retriever=None):
        self.router = router
        self.kg_service = kg_service
        self.faiss_retriever = faiss_retriever

    def process(self, question: str, top_k: int = 5) -> dict[str, Any]:
        classification = self.router.classify(question)
        plan = extract_query_plan(question, classification)
        kg_results: list[dict[str, Any]] = []
        rag_results: list[dict[str, Any]] = []
        warnings: list[str] = []

        if plan["kg"]:
            if self.kg_service:
                try:
                    kg_results = self.kg_service.execute(plan["kg"]["query"], plan["kg"]["params"])
                except Exception as exc:
                    warnings.append(f"KG query failed: {type(exc).__name__}: {exc}")
            else:
                warnings.append("KG chưa được nạp")

        use_rag = plan["rag"] is not None or (plan["kg"] is not None and not kg_results)
        if use_rag:
            if self.faiss_retriever:
                rag_results = self.faiss_retriever.search(question, top_k=top_k, domain=classification.domain)
            else:
                warnings.append("FAISS chưa được lập chỉ mục")

        effective_route = plan["route"]
        if plan["kg"] and not kg_results and rag_results:
            effective_route = "rag_fallback"
        return {
            "question": question,
            "classification": classification.to_dict(),
            "plan": plan,
            "effective_route": effective_route,
            "kg_results": kg_results,
            "rag_results": rag_results,
            "evidence_count": len(kg_results) + len(rag_results),
            "warnings": warnings,
        }
