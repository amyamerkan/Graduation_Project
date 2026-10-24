import sqlite3

import numpy as np
import pytest

from vn_assistant.embedding import EmbeddingConfig
from vn_assistant.faiss_store import SCHEMA, FaissRetriever


class FixedQueryEncoder:
    dimension = 2

    def __init__(self):
        self.calls = []

    def encode_queries(self, queries):
        self.calls.append(list(queries))
        return np.asarray([[1.0, 0.0] for _ in queries], dtype="float32")


@pytest.fixture
def retriever(tmp_path, monkeypatch):
    faiss = pytest.importorskip("faiss")
    import vn_assistant.faiss_store as module

    encoder = FixedQueryEncoder()
    monkeypatch.setattr(module, "create_encoder", lambda *args, **kwargs: encoder)
    records = [
        (7, "outside-law", "law", "Văn bản pháp luật", "Phường Điện Dương và Hội An", 1.0),
        (19, "unrelated-high", "heritage", "Di sản khác", "Một nguồn không liên quan", 0.99),
        (31, "chosen-doc", "heritage", "Di sản được chọn", "Tài liệu cần lấy", 0.20),
        (44, "hoi-an", "heritage", "PHỐ CỔ HỘI AN", "Kiến trúc truyền thống", 0.40),
        (58, "dien-duong", "heritage", "Tài liệu địa phương", "PHƯỜNG ĐIỆN DƯƠNG có di sản", 0.30),
        (60, "chosen-tourism", "tourism", "Hội An", "Phường Điện Dương", 0.98),
        (77, "literal-percent", "heritage", "Giảm 50% tại địa điểm", "Mô tả chương trình", 0.10),
        (83, "literal-underscore", "heritage", "Tên mẫu A_B", "Mô tả bản ghi", 0.05),
    ]
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(2))
    scores = np.asarray([row[5] for row in records], dtype="float32")
    vectors = np.column_stack((scores, np.sqrt(1.0 - scores**2))).astype("float32")
    index.add_with_ids(vectors, np.asarray([row[0] for row in records], dtype="int64"))
    index_path = tmp_path / "index.faiss"
    metadata_path = tmp_path / "metadata.sqlite3"
    faiss.write_index(index, str(index_path))
    with sqlite3.connect(metadata_path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (vector_id, f"chunk-{vector_id}", doc_id, text, title, domain, "test-fixture", "")
                for vector_id, doc_id, domain, title, text, score in records
            ],
        )
    instance = FaissRetriever(index_path, metadata_path, EmbeddingConfig())
    return instance, encoder


def test_doc_filter_physically_selects_lower_similarity_without_top_k_starvation(retriever):
    search, encoder = retriever
    assert search.search("question", top_k=1, domain="heritage")[0]["doc_id"] == "unrelated-high"
    result = search.search("question", top_k=1, domain="heritage", doc_ids=["chosen-doc"])
    assert [row["doc_id"] for row in result] == ["chosen-doc"]
    assert result[0]["vector_id"] == 31
    assert result[0]["score"] == pytest.approx(0.20)
    assert len(encoder.calls) == 2


def test_combined_filter_is_domain_and_doc_id_or_entity_term(retriever):
    search, _ = retriever
    result = search.search(
        "question",
        top_k=5,
        domain="heritage",
        doc_ids=["chosen-doc", "chosen-tourism"],
        entity_terms=["hội an"],
    )
    assert [row["doc_id"] for row in result] == ["hoi-an", "chosen-doc"]
    assert all(row["domain"] == "heritage" for row in result)
    assert all(row["doc_id"] not in {"outside-law", "chosen-tourism", "unrelated-high"} for row in result)


@pytest.mark.parametrize(
    "term,doc_id,score",
    [("hội an", "hoi-an", 0.40), ("phường điện dương", "dien-duong", 0.30)],
)
def test_vietnamese_entity_filter_casefolds_title_and_text(retriever, term, doc_id, score):
    search, _ = retriever
    result = search.search("question", top_k=1, domain="heritage", entity_terms=[term])
    assert [row["doc_id"] for row in result] == [doc_id]
    assert result[0]["score"] == pytest.approx(score)


@pytest.mark.parametrize("term,doc_id", [("%", "literal-percent"), ("_", "literal-underscore")])
def test_entity_filter_treats_sql_wildcard_characters_as_literal_text(retriever, term, doc_id):
    search, _ = retriever
    result = search.search("question", top_k=10, domain="heritage", entity_terms=[term])
    assert [row["doc_id"] for row in result] == [doc_id]


@pytest.mark.parametrize(
    "filters",
    [
        {"doc_ids": []},
        {"entity_terms": []},
        {"entity_terms": ["", "  "]},
        {"doc_ids": [], "entity_terms": []},
        {"domain": "heritage", "doc_ids": []},
        {"domain": "unknown-domain"},
        {"domain": "heritage", "doc_ids": ["missing-doc"]},
        {"domain": "heritage", "entity_terms": ["không có bản ghi này"]},
    ],
)
def test_empty_or_unmatched_explicit_filter_returns_before_encoding(retriever, filters):
    search, encoder = retriever
    assert search.search("question", top_k=1, **filters) == []
    assert encoder.calls == []


def test_empty_doc_list_still_allows_explicit_entity_alternative(retriever):
    search, _ = retriever
    result = search.search("question", top_k=5, domain="heritage", doc_ids=[], entity_terms=["hội an"])
    assert [row["doc_id"] for row in result] == ["hoi-an"]


def test_repeated_filter_reuses_allowed_ids_but_still_encodes_each_query(retriever):
    search, encoder = retriever
    before = search._allowed_ids.cache_info()
    first = search.search("first question", top_k=1, domain="heritage", doc_ids=["chosen-doc", "chosen-doc"])
    middle = search._allowed_ids.cache_info()
    second = search.search("second question", top_k=1, domain="heritage", doc_ids=["chosen-doc"])
    after = search._allowed_ids.cache_info()
    assert [row["vector_id"] for row in first] == [31]
    assert [row["vector_id"] for row in second] == [31]
    assert middle.misses == before.misses + 1
    assert after.hits == middle.hits + 1
    assert encoder.calls == [["first question"], ["second question"]]


def test_top_k_cannot_overflow_allowed_subset_or_duplicate_ids(retriever):
    search, _ = retriever
    result = search.search("question", top_k=10, domain="heritage", doc_ids=["chosen-doc", "chosen-doc"])
    assert [row["vector_id"] for row in result] == [31]


def test_missing_filters_preserve_global_similarity_order(retriever):
    search, _ = retriever
    result = search.search("question", top_k=3)
    assert [row["vector_id"] for row in result] == [7, 19, 60]
    assert [row["score"] for row in result] == pytest.approx([1.0, 0.99, 0.98])
