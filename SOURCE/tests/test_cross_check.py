import pytest

from vn_assistant.cross_check import CrossChecker, render_fact_claim, render_kg_fact


@pytest.fixture
def evidence():
    return [
        {
            "id": "E01",
            "kind": "kg",
            "facts": {
                "name": "Phường A",
                "code": "00070",
                "validFrom": "2025-07-01",
                "type": "https://example.org/vn#Ward",
            },
            "text": "Phường A có mã 00070.",
            "source_verified": False,
        },
        {
            "id": "E02",
            "kind": "rag",
            "text": "Di sản B có giá trị kiến trúc truyền thống. Công trình sử dụng vật liệu địa phương.",
            "source_verified": True,
        },
    ]


def fact_claim(evidence, fields):
    facts = evidence[0]["facts"]
    return {
        "mode": "fact",
        "text": render_fact_claim(facts, fields),
        "evidence_ids": ["E01"],
        "fields": fields,
        "fact_checks": [
            {"evidence_id": "E01", "field": field, "value": facts[field]}
            for field in fields
        ],
    }


def extract_claim(text, ids=None):
    return {"mode": "extractive", "text": text, "evidence_ids": ids or ["E02"]}


def test_exact_kg_fact_and_source_provenance_are_separate(evidence):
    result = CrossChecker().verify([fact_claim(evidence, ["name", "code", "type"])], evidence)
    assert result["status"] == "supported"
    assert result["supported"][0]["verification"] == "exact_kg_fact_match"
    assert result["supported"][0]["source_verified"] is False
    assert "đơn vị hành chính cấp xã" in result["supported"][0]["text"]


def test_wrong_code_is_rejected_even_when_name_and_citation_are_correct(evidence):
    claim = fact_claim(evidence, ["code"])
    claim["text"] = "Mã của Phường A: 00071."
    claim["fact_checks"][0]["value"] = "00071"
    result = CrossChecker().verify([claim], evidence)
    assert result["supported"] == []
    assert set(result["rejected"][0]["reasons"]) >= {"kg_value_mismatch", "claim_does_not_match_kg_rendering"}


def test_leading_zero_code_cannot_be_coerced_to_integer(evidence):
    claim = fact_claim(evidence, ["code"])
    claim["fact_checks"][0]["value"] = 70
    result = CrossChecker().verify([claim], evidence)
    assert "kg_value_mismatch" in result["rejected"][0]["reasons"]


def test_adding_unchecked_year_to_otherwise_correct_fact_is_rejected(evidence):
    claim = fact_claim(evidence, ["name"])
    claim["text"] += " Được thành lập năm 1999."
    result = CrossChecker().verify([claim], evidence)
    assert result["status"] == "insufficient_evidence"
    assert "claim_does_not_match_kg_rendering" in result["rejected"][0]["reasons"]


def test_exact_excerpt_accepts_whitespace_normalisation(evidence):
    claim = extract_claim("Di sản B có giá trị\nkiến trúc truyền thống.")
    result = CrossChecker().verify([claim], evidence)
    assert result["status"] == "supported"
    assert result["supported"][0]["source_verified"] is True


def test_citation_does_not_prove_a_paraphrase(evidence):
    claim = extract_claim("Di sản B được UNESCO công nhận vào năm 1999.")
    result = CrossChecker().verify([claim], evidence)
    assert "claim_not_exact_excerpt" in result["rejected"][0]["reasons"]


@pytest.mark.parametrize("text", ["được công nhận vào năm 1999.", "công nhận vào năm 1999."])
def test_exact_substring_cannot_remove_negation(evidence, text):
    evidence[1]["text"] = "Di sản B không được công nhận vào năm 1999."
    result = CrossChecker().verify([extract_claim(text)], evidence)
    assert "claim_not_exact_excerpt" in result["rejected"][0]["reasons"]


def test_sentence_boundary_matching_does_not_splice_inside_words(evidence):
    evidence[1]["text"] = "unregistered"
    result = CrossChecker().verify([extract_claim("registered")], evidence)
    assert result["status"] == "insufficient_evidence"


def test_partly_supported_output_keeps_only_grounded_claims(evidence):
    claims = [extract_claim("Công trình sử dụng vật liệu địa phương."), extract_claim("Công trình có 12 cổng.")]
    result = CrossChecker().verify(claims, evidence)
    assert result["status"] == "partial"
    assert result["supported_count"] == 1
    assert result["rejected_count"] == 1


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda claim: claim.update(evidence_ids=[]), "missing_citations"),
        (lambda claim: claim.update(evidence_ids=["E99"]), "unknown_citation"),
        (lambda claim: claim.update(evidence_ids=["E02", "E02"]), "duplicate_citation"),
        (lambda claim: claim.pop("mode"), "unsupported_claim_mode"),
    ],
)
def test_missing_unknown_duplicate_and_unspecified_citations(evidence, mutate, reason):
    claim = extract_claim("Công trình sử dụng vật liệu địa phương.")
    mutate(claim)
    result = CrossChecker().verify([claim], evidence)
    assert reason in result["rejected"][0]["reasons"]


def test_citation_to_unrelated_extra_record_is_rejected(evidence):
    claim = extract_claim("Công trình sử dụng vật liệu địa phương.", ["E02", "E01"])
    result = CrossChecker().verify([claim], evidence)
    assert "claim_not_exact_excerpt" in result["rejected"][0]["reasons"]


def test_hard_code_conflict_is_rejected_even_when_rag_quote_is_exact(evidence):
    evidence[1]["text"] = "Phường A có mã 00071."
    result = CrossChecker().verify([extract_claim(evidence[1]["text"])], evidence)
    assert "kg_code_conflict" in result["rejected"][0]["reasons"]


def test_effective_date_conflict_with_kg_is_rejected(evidence):
    evidence[1]["text"] = "Phường A có hiệu lực từ 02/07/2025."
    result = CrossChecker().verify([extract_claim(evidence[1]["text"])], evidence)
    assert "kg_date_conflict" in result["rejected"][0]["reasons"]


def test_current_graph_snapshot_can_invalidate_a_previously_retrieved_fact(evidence):
    claim = fact_claim(evidence, ["code"])
    evidence[0]["current_facts"] = dict(evidence[0]["facts"], code="00071")
    result = CrossChecker().verify([claim], evidence)
    assert "kg_snapshot_changed" in result["rejected"][0]["reasons"]


def test_current_graph_entity_name_is_checked_even_when_only_code_is_selected(evidence):
    claim = fact_claim(evidence, ["code"])
    evidence[0]["current_facts"] = dict(evidence[0]["facts"], name="Phường B")
    result = CrossChecker().verify([claim], evidence)
    assert "kg_snapshot_changed" in result["rejected"][0]["reasons"]


def test_model_cannot_forge_an_allowed_claim(evidence):
    evidence[0]["allowed_claims"] = ["Phường A có 17 di sản."]
    claim = fact_claim(evidence, ["name"])
    claim["text"] = evidence[0]["allowed_claims"][0]
    result = CrossChecker().verify([claim], evidence)
    assert "claim_does_not_match_kg_rendering" in result["rejected"][0]["reasons"]


def test_false_count_cannot_be_derived_from_list_length(evidence):
    claim = {
        "mode": "fact",
        "text": "Số thực thể trong kết quả thống kê KG: 1.",
        "evidence_ids": ["E01"],
        "fact_checks": [{"evidence_id": "E01", "field": "count", "value": 1}],
    }
    result = CrossChecker().verify([claim], evidence)
    assert "unknown_kg_field" in result["rejected"][0]["reasons"]


def test_count_requires_actual_aggregate_value(evidence):
    evidence[0]["facts"] = {"count": "34", "type": "https://example.org/vn#Province"}
    result = CrossChecker().verify([fact_claim(evidence, ["type", "count"])], evidence)
    assert result["status"] == "supported"
    with pytest.raises(ValueError):
        render_kg_fact("count", "34.5")


def test_unknown_fields_and_duplicate_checks_are_rejected(evidence):
    claim = fact_claim(evidence, ["code"])
    claim["fact_checks"] *= 2
    result = CrossChecker().verify([claim], evidence)
    assert "duplicate_fact_field" in result["rejected"][0]["reasons"]
    with pytest.raises(ValueError):
        render_fact_claim({"invented_field": "yes"}, ["invented_field"])


@pytest.mark.parametrize("claims", [None, {}, "not JSON", [None] * 31])
def test_malformed_or_unbounded_output_fails_closed(evidence, claims):
    result = CrossChecker().verify(claims, evidence)
    assert result["status"] == "invalid_output"
    assert result["supported"] == []


def test_duplicate_evidence_identity_fails_closed(evidence):
    result = CrossChecker().verify([], evidence + [evidence[0]])
    assert result["status"] == "invalid_output"
    assert result["rejected"][0]["reasons"] == ["duplicate_evidence_id"]


def test_empty_claim_list_has_no_supported_answer(evidence):
    result = CrossChecker().verify([], evidence)
    assert result["status"] == "insufficient_evidence"
    assert result["supported"] == []
