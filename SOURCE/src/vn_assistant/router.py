from __future__ import annotations

import csv
import json
import re
from datetime import date
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.pipeline import FeatureUnion, Pipeline

from .normalization import clean_text, expand_domain_terms
from .domain_scope import contains_intangible


_TEMPORAL_LITERAL = r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|(?:năm|giai đoạn)\s+\d{4}(?:\s*[-–]\s*\d{4})?)\b"
_RELATIVE_TIME_TERMS = ("hôm qua", "hôm nay", "ngày mai", "tuần trước", "tuần sau", "tháng trước", "tháng sau", "năm trước", "năm sau", "năm ngoái", "gần đây", "mới đây", "hiện nay", "hiện tại", "bây giờ")


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
    artifact = {"route_model": route_model, "domain_model": domain_model, "version": "1.1.0",
                "supported_domains": sorted({row["domain"] for row in rows})}
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
    if router.artifact:
        questions = [expand_domain_terms(row["question"]) for row in rows]
        raw_routes = router.artifact["route_model"].predict(questions)
        raw_domains = router.artifact["domain_model"].predict(questions)
        report["model_without_rules"] = {
            "route_accuracy": sum(a == b for a,b in zip(expected_routes, raw_routes)) / n,
            "domain_accuracy": sum(a == b for a,b in zip(expected_domains, raw_domains)) / n,
            "scope": "Raw Logistic Regression predictions before deterministic routing rules",
        }
    output = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


class QuestionRouter:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.artifact = joblib.load(self.model_path) if self.model_path.exists() else None

    def match_tourism_places(self, question: str) -> list[str]:
        artifact = self.artifact or {}
        lowered = question.casefold()
        names = [name for name in artifact.get("tourism_entities", []) if name.casefold() in lowered]
        for alias, destinations in artifact.get("tourism_aliases", {}).items():
            if alias.casefold() in lowered:
                names.extend(destinations)
        return sorted(set(names))

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
            rule_route, rule_domain = self._rules(question)
            supported = set(self.artifact.get("supported_domains", ("law", "administration", "heritage", "tourism")))
            if rule_domain not in supported:
                rule_domain = "tourism" if rule_domain == "heritage" and "tourism" in supported else "administration" if rule_domain == "law" and "administration" in supported else None
            if "tourism" in supported and self.match_tourism_places(question) and not re.search(r"\b(?:phường|xã|mã|sáp nhập)\b", question, re.I):
                rule_domain = "tourism"
            if rule_route:
                route, route_conf = rule_route, 0.70
            if rule_domain:
                domain, domain_conf = rule_domain, 0.70
            return Classification(question, route, domain, route_conf, domain_conf, "tfidf_logistic_regression")
        route, domain = self._rules(question)
        return Classification(question, route or "rag", domain or "tourism", 0.55, 0.55, "rule_fallback")

    @staticmethod
    def _rules(question: str) -> tuple[str | None, str | None]:
        lowered = expand_domain_terms(question).lower()
        law = any(term in lowered for term in ("luật", "điều luật", "quy định", "pháp luật", "thẩm quyền"))
        heritage = any(term in lowered for term in ("di sản", "di tích", "bảo tàng", "unesco", "ca trù", "nhã nhạc", "mỹ sơn", "hội an", "cố đô huế"))
        tourism = any(term in lowered for term in ("du lịch", "tham quan", "điểm đến", "lịch trình", "mùa nào", "tháng mấy"))
        administration = any(term in lowered for term in ("địa giới", "đơn vị hành chính", "danh mục hành chính", "sáp nhập", "sắp xếp", "phường", "xã", "tỉnh", "huyện", "quận", "mã hành chính", "cư trú", "tạm trú", "dịch vụ công", "thủ tục", "ủy ban nhân dân"))
        administration = administration or bool(re.search(r"\bmã(?:\s+(?:số|hành chính))?\s*[:#]?\s*\d{2,6}\b", lowered))
        domain = "law" if law else "heritage" if heritage else "tourism" if tourism else "administration" if administration else None
        hard_fact = any(term in lowered for term in ("mã ", "thuộc", "nằm ở", "ở đâu", "địa chỉ", "năm nào", "bao nhiêu", "sáp nhập", "sắp xếp", "danh sách", "cơ quan nào", "loại di sản", "điều luật nào", "văn bản nào"))
        hard_fact = hard_fact or bool(re.search(r"\bcó\s+(?:những\s+)?(?:điểm\s+(?:tham quan|du lịch)|di sản|di tích).+?\bnào\b", lowered))
        descriptive = any(term in lowered for term in ("như thế nào", "ý nghĩa", "mô tả", "giới thiệu", "nguồn gốc", "lịch sử", "hướng dẫn", "cần gì", "gồm những gì", "đặc sắc", "gợi ý", "giá trị", "nội dung", "ra sao", "đáng chú ý"))
        route = "hybrid" if hard_fact and descriptive else "kg" if hard_fact else "rag"
        if not hard_fact and not descriptive:
            route = None
        return route, domain


def extract_query_plan(question: str, classification: Classification) -> dict[str, Any]:
    question = clean_text(question)
    lowered = question.lower()
    code_match = re.search(r"\bmã(?:\s+(?:số|hành chính))?\s*[:#]?\s*(\d{2,6})\b", lowered)
    quoted = re.findall(r'["“](.*?)["”]', question)
    province = _extract_province(question)
    constraints = _extract_constraints(question)
    warnings = list(constraints["unsupported"])
    temporal_plan = _dated_unit_plan(question, code_match.group(1) if code_match else None)
    if temporal_plan and not constraints["spatial"]:
        constraints["unsupported"] = []
        warnings = []
    out_of_scope = bool(re.search(r"\b(?:bitcoin|chứng khoán|xổ số|lập trình python|viết code|viết mã nguồn|chẩn đoán bệnh|giải phương trình|thời tiết ngày mai)\b", lowered))
    if contains_intangible(question):
        out_of_scope = True
    if classification.route in {"kg", "hybrid"} and not constraints["unsupported"]:
        if temporal_plan:
            kg = temporal_plan
        elif "sáp nhập" in lowered or "sắp xếp" in lowered or "trước đây" in lowered:
            name = quoted[0] if quoted else _extract_entity_keyword(question)
            kg = {"query": "04_merger_history", "params": {"old_name": name}}
        elif code_match:
            kg = {"query": "03_unit_by_code", "params": {"code": code_match.group(1)}}
        elif province and re.search(r"\b(?:phường|xã)\b", lowered) and any(t in lowered for t in ("danh sách", "các ", "bao nhiêu")):
            kg = {"query": "02_wards_in_province", "params": {"province": province}}
        elif classification.domain == "tourism" and province and any(t in lowered for t in ("danh sách", "các ", "nào", "bao nhiêu")):
            kg = {"query": "10_tourism_in_province", "params": {"province": province, "limit": 30}}
        elif province and any(t in lowered for t in ("di sản", "di tích", "bảo tàng")) and any(t in lowered for t in ("danh sách", "các ", "nào", "bao nhiêu")):
            kg = {"query": "05_heritage_in_province", "params": {"province": province}}
        elif "danh sách" in lowered and "tỉnh" in lowered and not province:
            kg = {"query": "01_list_provinces", "params": {}}
        else:
            keyword = quoted[0] if quoted else _extract_entity_keyword(question)
            kg = {"query": "08_entity_facts", "params": {"keyword": keyword, "limit": 10}}
    else:
        kg = None
    route = "rag" if classification.route in {"kg", "hybrid"} and kg is None else classification.route
    rag = {"domain": classification.domain, "top_k": 5} if route in {"rag", "hybrid"} else None
    intent = {"kg": "logical", "rag": "textual", "hybrid": "hybrid"}[classification.route]
    return {"route": route, "kg": kg, "rag": rag, "intent": intent, "constraints": constraints, "warnings": warnings,
            "scope": "out_of_scope" if out_of_scope else "supported"}


def _dated_unit_plan(question: str, code: str | None) -> dict | None:
    if not code:
        return None
    dates = re.findall(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4})\b", question)
    lowered = question.casefold()
    if len(dates) > 1 or re.findall(_TEMPORAL_LITERAL, question, re.I) != dates:
        return None
    if any(term in lowered for term in _RELATIVE_TIME_TERMS) or re.search(r"\b(?:giai đoạn|năm nào|khi nào|trước ngày|sau ngày|từ ngày|đến ngày|(?:trước|sau|từ|đến)\s+\d)", question, re.I):
        return None
    as_of = ""
    if dates:
        parts = dates[0].replace("/", "-").split("-")
        try:
            as_of = (date(*map(int, parts)) if len(parts[0]) == 4 else date(int(parts[2]), int(parts[1]), int(parts[0]))).isoformat()
        except ValueError:
            return None
    match = re.search(r"\b(?:thuộc|tại|ở|trong)\s+(?:tỉnh|thành phố|tp\.?)\s+(.+?)(?=\s+(?:vào|ngày|tại thời điểm|từ|và|có|là|đúng|không)\b|[?!.,]|$)", question, re.I)
    province = match.group(1).strip() if match and not re.match(r"(?:nào|gì|thành(?: phố)?\s+(?:nào|gì))\b", match.group(1), re.I) else ""
    return {"query": "09_unit_at_time", "params": {"code": code, "as_of": as_of, "province": province}} if as_of or province else None


def _extract_constraints(question: str) -> dict[str, list[str]]:
    lowered = question.lower()
    temporal = re.findall(_TEMPORAL_LITERAL, lowered)
    if any(term in lowered for term in (*_RELATIVE_TIME_TERMS, "vào thời điểm", "tại thời điểm", "trước năm", "sau năm", "trước ngày", "sau ngày", "vào ngày")):
        temporal.append("thời điểm hoặc khoảng thời gian được yêu cầu")
    spatial = [term for term in ("bán kính", "tọa độ", "vĩ độ", "kinh độ", "giao nhau", "giáp ranh", "gần nhất", "cách bao xa") if term in lowered]
    if re.search(r"\bgần\s+(?!đây\b)", lowered):
        spatial.append("quan hệ gần về không gian")
    if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:km|kilômét|ki lô mét|mét)\b", lowered):
        spatial.append("khoảng cách theo đơn vị đo")
    if re.search(r"\bcách\s+.+?\s+(?:bao nhiêu|mấy)\s*(?:km|mét|kilômét)", lowered):
        spatial.append("tính khoảng cách")
    if re.search(r"\bcách\s+(?:bao nhiêu|mấy)\s*(?:km|mét|kilômét)", lowered):
        spatial.append("tính khoảng cách")
    unsupported = []
    if temporal:
        unsupported.append("Chưa xác minh được đầy đủ ràng buộc thời gian bằng KG; cần mã đơn vị, ngày cụ thể được hỗ trợ và mốc hiệu lực trong dữ liệu.")
    if spatial:
        unsupported.append("KG hiện tại chưa có truy vấn hình học hoặc khoảng cách; kết quả RAG không tự xác nhận ràng buộc không gian.")
    if any(term in lowered for term in ("năm nào", "khi nào")) and "sáp nhập" not in lowered:
        unsupported.append("KG chưa có truy vấn năm công nhận hoặc sự kiện đầy đủ; cần minh chứng văn bản.")
    return {"temporal": temporal, "spatial": spatial, "unsupported": unsupported}


def _extract_province(question: str) -> str | None:
    match = re.search(r"(?:thuộc|tại|ở|của|trong)\s+(?:(?:tỉnh|thành phố|tp\.?)\s+)?(.+?)(?:[?.!]|$)", question, flags=re.I)
    if not match:
        return None
    value = re.split(r"\s+(?:và|có|được|trước|sau|năm|để|hiện nay)\b", match.group(1), maxsplit=1, flags=re.I)[0]
    value = value.strip(' \"“”')
    if re.match(r"(?:loại|nhóm|danh mục|phân loại|hạng|mức|diện|hệ|ngành|đối tượng)\b", value, flags=re.I):
        return None
    return value if value and not re.match(r"(?:đâu|nào|gì|bao nhiêu)\b", value, flags=re.I) else None


def _extract_entity_keyword(question: str) -> str:
    question = clean_text(question)
    question = re.sub(r"^(?:(?:hãy|vui lòng)\s+)?(?:cho (?:tôi|mình|em) biết|cho biết|giới thiệu|mô tả|thông tin|tóm tắt)\s+(?:về\s+)?", "", question, flags=re.I)
    patterns = [r"(?:của|về)\s+([^?.,]+)", r"^(.+?)\s+(?:nằm|thuộc|được|có|là|ở đâu|sáp nhập|hiện nay|nay)\b",
                r"((?:thành phố|tỉnh|phường|xã|thị trấn|huyện|quận|di sản|di tích|bảo tàng|vịnh|phố cổ|cố đô|thánh địa)\s+[^?.,]+)"]
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.I)
        if match:
            value = match.group(1)
            value = re.split(r"\s+(?:hiện nay|là|ở|thuộc|có|được|nằm|năm|mã|sau|trước|nay|sáp nhập|thành|và)\b", value, maxsplit=1, flags=re.I)[0]
            value = re.sub(r"^(?:hãy|cho biết|các|danh sách)\s+", "", value, flags=re.I).strip()
            if value:
                return value
    stop = {"là", "gì", "nào", "ở", "đâu", "có", "cho", "biết", "hãy", "được", "thuộc", "về"}
    tokens = [token for token in re.findall(r"[0-9A-Za-zÀ-ỹ]+", question) if token.lower() not in stop]
    return " ".join(tokens[-5:]) or question.rstrip("? .")
