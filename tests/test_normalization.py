from vn_assistant.normalization import clean_text, expand_domain_terms, normalized_key, stable_id


def test_normalization_and_id_are_stable():
    assert clean_text("  Hà   Nội\n") == "Hà Nội"
    assert normalized_key("Phường Cửa Nam") == "phuong cua nam"
    assert stable_id("Ward", "00082") == stable_id("Ward", "00082")
    assert "thủ tục hành chính" in expand_domain_terms("Hỏi về TTHC").lower()

