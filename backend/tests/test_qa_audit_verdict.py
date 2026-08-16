"""QA 판정 — DB 없이 세 칸 대조만."""

from app.qa_audit.verdict import compare_metrics, grade_n, worst


def test_worst_picks_block():
    assert worst("PASS", "REVIEW", "BLOCK") == "BLOCK"
    assert worst("SKIP", "SKIP") == "SKIP"
    assert worst("PASS", "PASS") == "PASS"


def test_n_exact_match_pass():
    g, _ = grade_n(100, 100, 100, specified=True)
    assert g == "PASS"


def test_n_one_off_is_error():
    g, reason = grade_n(1247, 1247, 1246, specified=True)
    assert g == "ERROR"
    assert "불일치" in reason


def test_n_large_gap_is_block():
    g, _ = grade_n(1000, 1000, 900, specified=True)
    assert g == "BLOCK"


def test_n_empty_is_skip():
    g, _ = grade_n(0, 0, 0, specified=True)
    assert g == "SKIP"


def test_compare_all_match_pass():
    l1 = {"n": 10, "sum_price": 100.0, "mean_price": 12.3, "median_price": 11.0, "asset_type": "apartment"}
    l2 = {
        "n_all": 10,
        "n_l1_eligible": 10,
        "n_invalid": 0,
        "n_hash_dup_groups": 0,
        "n_bad_region_code": 0,
        "n_excluded_unit_price": 0,
    }
    out = compare_metrics(l1, dict(l1, available=True), dict(l1, missing=False), l2=l2)
    assert out["verdict"] == "PASS"
    assert out["verdict_ui"] == "PASS"
    assert out["metrics"]["n"]["delta_l1_mart"] == 0
    labels = [c["label"] for c in out["checks"]]
    assert "원장 거래건수" in labels
    assert "기존 Mart 대조" in labels
    assert all(c["grade"] == "PASS" for c in out["checks"])


def test_sum_diff_is_review_not_error():
    l1 = {"n": 10, "sum_price": 100.0, "mean_price": 12.3, "median_price": 11.0}
    mart = {**l1, "sum_price": 250.0, "missing": False}
    out = compare_metrics(l1, dict(l1, available=True), mart, l2={"n_l1_eligible": 10, "n_all": 10})
    assert out["metrics"]["n"]["grade"] == "PASS"
    assert out["metrics"]["sum_price"]["grade"] == "REVIEW"
    assert out["verdict"] == "REVIEW"
    assert out["verdict_ui"] == "REVIEW"


def test_compare_l3_error_block():
    out = compare_metrics({}, {}, {}, l3_error="builder boom")
    assert out["verdict"] == "BLOCK"
    assert out["verdict_ui"] == "ERROR"
    assert out["checks"]


def test_compare_mart_missing_error():
    l1 = {"n": 5, "sum_price": 10.0, "mean_price": 1.0, "median_price": 1.0}
    l3 = {**l1, "available": True}
    mart = {"missing": True}
    out = compare_metrics(l1, l3, mart, l2={})
    assert out["verdict"] in ("ERROR", "BLOCK")
    assert any("마트" in c for c in out["cause_candidates"])


def test_mean_drift_with_pass_n_is_review():
    l1 = {"n": 10, "sum_price": 100.0, "mean_price": 12.3, "median_price": 11.0}
    l3 = dict(l1)
    mart = {**l1, "mean_price": 12.9, "missing": False}
    out = compare_metrics(l1, l3, mart, l2={})
    assert out["verdict"] == "REVIEW"
    assert out["metrics"]["n"]["grade"] == "PASS"
