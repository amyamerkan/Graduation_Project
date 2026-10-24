import json

from vn_assistant.dataio import chunk_document, iter_documents


def test_jsonl_to_chunks(tmp_path):
    path = tmp_path / "rag.jsonl"
    row = {
        "doc_id": "d1", "domain": "heritage", "source": "test",
        "title": "Phố cổ Hội An", "text": "Phố cổ Hội An là một địa điểm di sản văn hóa tại Việt Nam với nhiều giá trị lịch sử.",
    }
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    documents = list(iter_documents(path))
    assert len(documents) == 1
    chunks = list(chunk_document(documents[0], size=60, overlap=10))
    assert chunks and chunks[0]["domain"] == "heritage"

