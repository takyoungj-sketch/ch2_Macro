from app.qa_audit.report import format_report


def test_report_cites_engine_numbers_only():
    run = {
        "verdict": "ERROR",
        "region_name": "세종특별자치시 나성동",
        "region_code": "36110107",
        "region_level": "eupmyeondong",
        "asset_type": "apartment",
        "period_key": "2025",
        "trigger": "specified",
        "engine_version": "1.0.0",
        "l2": {
            "n_needs_review": 0,
            "drop_chain": {
                "n_all": 10,
                "n_invalid": 0,
                "n_excluded_unit_price": 1,
                "n_l1_eligible": 9,
            },
        },
        "diffs": {
            "metrics": {
                "n": {
                    "l1": 9,
                    "l3": 9,
                    "mart": 8,
                    "delta_l1_mart": 1,
                    "grade": "ERROR",
                    "reason": "원장 재집계와 저장 마트 건수 불일치",
                }
            },
            "cause_candidates": ["원천(원장)에는 유효 건이 있으나 통계 마트 행이 없음"],
        },
    }
    text = format_report(run)
    assert "ERROR" in text
    assert "9" in text and "8" in text
    assert "AI 재계산 아님" in text
    assert "검증값을 생성하지 않" in text
    assert "생산 파이프라인" in text
