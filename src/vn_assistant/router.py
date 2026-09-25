from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.pipeline import FeatureUnion, Pipeline

from .normalization import clean_text, expand_domain_terms


@dataclass
class Classification:
    question: str
    route: str
    domain: str
    route_confidence: float
    domain_confidence: float
    method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _features() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=25000, sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, max_features=25000, sublinear_tf=True)),
    ])


def _pipeline() -> Pipeline:
    return Pipeline([
        ("features", _features()),
        ("classifier", LogisticRegression(max_iter=2500, class_weight="balanced", random_state=42)),
    ])


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def train_router(train_path: str | Path, model_path: str | Path, report_path: str | Path | None = None) -> dict[str, Any]:
    rows = _read_csv(train_path)
    questions = [expand_domain_terms(row["question"]) for row in rows]
    route_model = _pipeline().fit(questions, [row["route"] for row in rows])
    domain_model = _pipeline().fit(questions, [row["domain"] for row in rows])
    artifact = {"route_model": route_model, "domain_model": domain_model, "version": "1.0.0"}
    output = Path(model_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output)
    report = {"training_rows": len(rows), "route_labels": sorted({row["route"] for row in rows}), "domain_labels": sorted({row["domain"] for row in rows})}
    if report_path:
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def evaluate_router(model_path: str | Path, test_path: str | Path, report_path: str | Path) -> dict[str, Any]:
    router = QuestionRouter(model_path)
    rows = _read_csv(test_path)
    details = []
    route_ok = domain_ok = joint_ok = 0
    expected_routes: list[str] = []
    predicted_routes: list[str] = []
    expected_domains: list[str] = []
    predicted_domains: list[str] = []
    for row in rows:
        result = router.classify(row["question"])
        current_route_ok = result.route == row["route"]
        current_domain_ok = result.domain == row["domain"]
        route_ok += int(current_route_ok)
        domain_ok += int(current_domain_ok)
        joint_ok += int(current_route_ok and current_domain_ok)
        expected_routes.append(row["route"])
        predicted_routes.append(result.route)
        expected_domains.append(row["domain"])
        predicted_domains.append(result.domain)
        details.append({**result.to_dict(), "expected_route": row["route"], "expected_domain": row["domain"]})
    n = max(len(rows), 1)
    report = {
        "cases": len(rows), "route_accuracy": route_ok / n, "domain_accuracy": domain_ok / n,
        "joint_accuracy": joint_ok / n,
        "route_metrics": classification_report(expected_routes, predicted_routes, output_dict=True, zero_division=0),
        "domain_metrics": classification_report(expected_domains, predicted_domains, output_dict=True, zero_division=0),
        "details": details,
    }
    output = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


class QuestionRouter:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.artifact = joblib.load(self.model_path) if self.model_path.exists() else None

    def classify(self, question: str) -> Classification:
        question = clean_text(question)
        if not question:
            raise ValueError("Câu hỏi không được để trống")
        if self.artifact:
            expanded = expand_domain_terms(question)
            route_model = self.artifact["route_model"]
            domain_model = self.artifact["domain_model"]
            route = str(route_model.predict([expanded])[0])
            domain = str(domain_model.predict([expanded])[0])
            route_conf = float(route_model.predict_proba([expanded]).max())
            domain_conf = float(domain_model.predict_proba([expanded]).max())
            # High precision physical-fact cues override uncertain small-data predictions.
            rule_route, rule_domain = self._rules(question)
            if rule_route:
                route, route_conf = rule_route, 0.70
            if rule_domain:
                domain, domain_conf = rule_domain, 0.70
            return Classification(question, route, domain, route_conf, domain_conf, "tfidf_logistic_regression")
        route, domain = self._rules(question)
        return Classification(question, route or "rag", domain or "tourism", 0.55, 0.55, "rule_fallback")

    @staticmethod
    def _rules(question: str) -> tuple[str | None, str | None]:
        lowered = question.lower()
        law = any(term in lowered for term in ("luật", "điều luật", "quy định", "pháp luật", "thẩm quyền"))
        heritage = any(term in lowered for term in ("di sản", "di tích", "bảo tàng", "unesco", "ca trù", "nhã nhạc", "mỹ sơn", "hội an", "cố đô huế"))
        tourism = any(term in lowered for term in ("du lịch", "tham quan", "điểm đến", "lịch trình", "mùa nào", "tháng mấy"))
        administration = any(term in lowered for term in ("sáp nhập", "phường", "xã", "tỉnh", "huyện", "quận", "mã hành chính", "cư trú", "tạm trú", "dịch vụ công"))
        domain = "law" if law else "heritage" if heritage else "tourism" if tourism else "administration" if administration else None
        hard_fact = any(term in lowered for term in ("mã ", "thuộc", "nằm ở", "ở đâu", "năm nào", "bao nhiêu", "sáp nhập", "danh sách", "cơ quan nào", "loại di sản", "điều luật nào", "văn bản nào"))
        descriptive = any(term in lowered for term in ("như thế nào", "ý nghĩa", "mô tả", "hướng dẫn", "cần gì", "gồm những gì", "đặc sắc", "gợi ý", "giá trị", "nội dung"))
        route = "hybrid" if hard_fact and descriptive else "kg" if hard_fact else "rag"
        if not hard_fact and not descriptive:
            route = None
        return route, domain


def extract_query_plan(question: str, classification: Classification) -> dict[str, Any]:
    """Step 2: select a physical KG template or FAISS domain filter."""
    lowered = question.lower()
    code_match = re.search(r"\bmã(?:\s+(?:số|hành chính))?\s*[:#]?\s*(\d{2,6})\b", lowered)
    quoted = re.findall(r'["“](.*?)["”]', question)
    province_match = re.search(r"(?:thuộc|tại|ở|của|trong)\s+(?:(?:tỉnh|thành phố|tp\.?)\s+)?(.+?)(?:[?.!]|$)", question, flags=re.I)
    if classification.route in {"kg", "hybrid"}:
        if "sáp nhập" in lowered or "trước đây" in lowered or "nay" in lowered:
            name = quoted[0] if quoted else _extract_entity_keyword(question)
            kg = {"query": "04_merger_history", "params": {"old_name": name}}
        elif code_match:
            kg = {"query": "03_unit_by_code", "params": {"code": code_match.group(1)}}
        elif re.search(r"\bnăm\s+\d{4}\b", lowered):
            # Recognition year is not currently represented by the KG schema.
            # Retrieve textual evidence instead of treating a year as a unit code.
            kg = None
        elif province_match and re.search(r"\b(?:phường|xã)\b", lowered) and any(t in lowered for t in ("danh sách", "các ", "bao nhiêu")):
            kg = {"query": "02_wards_in_province", "params": {"province": province_match.group(1).strip()}}
        elif province_match and any(t in lowered for t in ("di sản", "di tích", "bảo tàng")) and any(t in lowered for t in ("danh sách", "các ", "nào", "bao nhiêu")):
            kg = {"query": "05_heritage_in_province", "params": {"province": province_match.group(1).strip()}}
        elif "danh sách" in lowered and "tỉnh" in lowered and not province_match:
            kg = {"query": "01_list_provinces", "params": {}}
        else:
            keyword = quoted[0] if quoted else _extract_entity_keyword(question)
            kg = {"query": "08_entity_facts", "params": {"keyword": keyword, "limit": 10}}
    else:
        kg = None
    route = "rag" if classification.route in {"kg", "hybrid"} and kg is None else classification.route
    rag = {"domain": classification.domain, "top_k": 5} if route in {"rag", "hybrid"} else None
    return {"route": route, "kg": kg, "rag": rag}


def _extract_entity_keyword(question: str) -> str:
    patterns = [
        r"((?:thành phố|tỉnh|phường|xã|thị trấn|huyện|quận|di sản|di tích|bảo tàng|vịnh|phố cổ|cố đô|thánh địa)\s+[A-ZÀ-Ỹ][^?.,]+)",
        r"(?:của|về)\s+([^?.,]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.I)
        if match:
            value = match.group(1)
            value = re.split(r"\s+(?:là|ở|thuộc|có|được|năm|mã|sau|trước|nay|sáp nhập|thành)\b", value, maxsplit=1, flags=re.I)[0]
            return value.strip()
    stop = {"là", "gì", "nào", "ở", "đâu", "có", "cho", "biết", "hãy", "được", "thuộc", "về"}
    tokens = [token for token in re.findall(r"[0-9A-Za-zÀ-ỹ]+", question) if token.lower() not in stop]
    return " ".join(tokens[-5:]) or question.rstrip("? .")
