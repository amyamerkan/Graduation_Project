import json
import sqlite3

import numpy as np
import pytest

from vn_assistant.domain_scope import contains_intangible, sanitize_tourism_record
from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import build_faiss_index
from vn_assistant.router import Classification, extract_query_plan
from vn_assistant.router import QuestionRouter
from vn_assistant.question_processing import QuestionProcessor
from vn_assistant.vector_refresh import refresh_vectors


def test_destination_survives_removal_of_intangible_sentences():
    record = {"record_id": "museum", "domain": "tourism", "data": {
        "name": "Bảo tàng thành phố", "address": "Địa chỉ nguồn",
        "description": "Bảo tàng có không gian trưng bày lịch sử của thành phố và khuôn viên dành cho khách tham quan. Ca trù là một di sản phi vật thể. Du khách có thể tìm hiểu kiến trúc và xem các hiện vật trong nhà trưng bày."}}
    result, audit = sanitize_tourism_record(record)
    assert result is not None and audit["removed_sentences"] == 1
    assert "kiến trúc" in result["data"]["description"]
    assert not contains_intangible(result["data"]["description"])
    assert "Ca trù" in record["data"]["description"]  # Input/raw remains an auditable source.


@pytest.mark.parametrize("title", ["Ca trù", "Nghệ thuật bài chòi", "Lễ hội địa phương", "Ca tru", "Intangible cultural heritage"])
def test_intangible_subject_is_excluded_even_when_labelled_tourism(title):
    record = {"domain": "tourism", "data": {"name": title, "description": "Mô tả " * 30}}
    assert sanitize_tourism_record(record)[0] is None


@pytest.mark.parametrize("text", ["Xã Quan Hồ Thẩn", "Phường Châu Văn Liêm", "Du khách tham quan hồ.", "Chè có vị đậm và hương thơm."])
def test_geographical_names_and_travel_descriptions_are_not_accent_folded(text):
    assert not contains_intangible(text)


@pytest.mark.parametrize("domain", ["administration", "tourism", "heritage"])
def test_tourism_keyword_cannot_reenable_excluded_subject(domain):
    result = extract_query_plan("Gợi ý du lịch và tìm hiểu ca trù", Classification("", "rag", domain, .8, .8, "test"))
    assert result["scope"] == "out_of_scope"


def test_unique_destination_alias_restricts_kg_even_when_name_contains_alias(tmp_path):
    class Router(QuestionRouter):
        def classify(self, question):
            return Classification(question, "hybrid", "tourism", .8, .8, "test")
    class KG:
        def execute(self, query, params):
            self.keyword = params["keyword"]
            return []
    router = Router(tmp_path / "absent")
    router.artifact = {"tourism_entities": ["Di sản văn hóa Mỹ Sơn"], "tourism_aliases": {"Mỹ Sơn": ["Di sản văn hóa Mỹ Sơn"]}}
    kg = KG()
    QuestionProcessor(router, kg).process("Mỹ Sơn thuộc tỉnh nào và có gì đáng chú ý?")
    assert kg.keyword == "Di sản văn hóa Mỹ Sơn"


def test_refresh_discards_deleted_passages_and_reencodes_changed_content(tmp_path):
    pytest.importorskip("faiss")
    source = tmp_path / "corpus.jsonl"
    old_rows = [
        {"id": "keep", "domain": "tourism", "title": "Điểm A", "text": "Phong cảnh thiên nhiên đẹp, có khuôn viên dành cho khách tham quan và trải nghiệm."},
        {"id": "remove", "domain": "heritage", "title": "Ca trù", "text": "Ca trù là di sản phi vật thể đã được ghi nhận trong một bộ dữ liệu cũ."},
        {"id": "change", "domain": "tourism", "title": "Điểm B", "text": "Khu du lịch có rừng cây và các dịch vụ dành cho khách tham quan vào dịp cuối tuần."},
    ]
    source.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in old_rows))
    seed, target = tmp_path / "seed", tmp_path / "new"
    build_faiss_index(source, seed / "vn.index", seed / "metadata.sqlite3", seed / "index_config.json",
                      EmbeddingConfig(), backend="hashing")
    rows = [old_rows[0], {**old_rows[2], "text": "Khu du lịch đã cập nhật tuyến đường tham quan rừng cây và bổ sung thông tin cho khách."}]
    source.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    report = refresh_vectors(source, seed, target, backend="hashing")
    assert report["reused_vectors"] == 1 and report["encoded_vectors"] == 1
    assert report["vectors"] == 2 and report["production_ready"] is False
    with sqlite3.connect(target / "metadata.sqlite3") as connection:
        assert {r[0] for r in connection.execute("SELECT doc_id FROM chunks")} == {"keep", "change"}
    import faiss
    old_index, new_index = (faiss.read_index(str(p / "vn.index")) for p in (seed, target))
    np.testing.assert_array_equal(old_index.reconstruct(0), new_index.reconstruct(0))
    with pytest.raises(ValueError, match="must differ"):
        refresh_vectors(source, seed, seed, backend="hashing")
