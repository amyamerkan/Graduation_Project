from vn_assistant.router import QuestionRouter, extract_query_plan


def test_rule_fallback_selects_kg_for_code(tmp_path):
    router = QuestionRouter(tmp_path / "missing.joblib")
    result = router.classify("Đơn vị có mã 00070 là gì?")
    plan = extract_query_plan(result.question, result)
    assert result.route == "kg"
    assert plan["kg"]["query"] == "03_unit_by_code"
    assert plan["kg"]["params"]["code"] == "00070"

