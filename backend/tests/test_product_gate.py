"""D-080 경로 분류. DB는 쓰지 않는다."""

from app.product_gate import is_default_land_rolling, needs_macro


def test_basic_stats_five_years_open():
    assert needs_macro("GET", "/api/free/v2/stats/1111010100", {"window_years": "5"}) is False
    assert needs_macro("GET", "/api/free/v2/stats/1111010100", {}) is False
    assert needs_macro("GET", "/api/paid/upper-stats/sigungu/11110", {"window_years": "5"}) is False


def test_window_3_and_7_need_macro():
    assert needs_macro("GET", "/api/free/v2/stats/1111010100", {"window_years": "3"}) is True
    assert needs_macro("GET", "/api/free/v2/stats/1111010100", {"window_years": "7"}) is True
    assert needs_macro("POST", "/api/free/v2/stats/bulk", {}, {"window_years": 7}) is True
    assert needs_macro("POST", "/api/free/v2/stats/bulk", {}, {"window_years": 5}) is False


def test_default_rolling_open_and_filtered_closed():
    body = {
        "rolling_bucket_count": 5,
        "rolling_matrix_period_start": "2021-10-01",
        "rolling_matrix_period_end": "2026-09-30",
        "exclude_partial": False,
        "exclude_outlier": False,
        "road_conditions": None,
        "base_cache_key": "abc",
    }
    assert is_default_land_rolling(body) is True
    assert needs_macro("POST", "/api/paid/matrix-yearly", {}, body) is False
    filtered = dict(body)
    filtered["exclude_outlier"] = True
    assert needs_macro("POST", "/api/paid/matrix-yearly", {}, filtered) is True
    short = dict(body)
    short["rolling_matrix_period_start"] = "2023-10-01"
    assert needs_macro("POST", "/api/paid/matrix-yearly", {}, short) is True


def test_paid_analysis_and_other_apps_closed():
    assert needs_macro("POST", "/api/paid/analyze", {}, {}) is True
    assert needs_macro("POST", "/api/paid/long-term-trend", {}, {}) is True
    assert needs_macro("GET", "/api/built/regions", {}) is True
    assert needs_macro("GET", "/api/rent/meta", {}) is True
    assert needs_macro("GET", "/api/regional-profile/x", {}) is True
    assert needs_macro("GET", "/api/insight/faq", {}) is True
    assert needs_macro("POST", "/api/ai/chat", {}, {}) is True


def test_collective_list_and_rolling():
    assert needs_macro("GET", "/api/collective/buildings", {"window_years": "5", "addr2": "흥덕구"}) is False
    assert needs_macro(
        "GET",
        "/api/collective/buildings",
        {"window_years": "5", "contract_year_from": "2020"},
    ) is True
    assert needs_macro(
        "GET",
        "/api/collective/buildings/abc/stats/rolling",
        {"window_years": "5"},
    ) is False
    assert needs_macro(
        "GET",
        "/api/collective/buildings/abc/stats/rolling",
        {"window_years": "3"},
    ) is True
    assert needs_macro("GET", "/api/collective/buildings/abc/transactions", {}) is True
    assert needs_macro("GET", "/api/collective/commercial/clusters", {"window_years": "5"}) is False
    assert needs_macro("POST", "/api/collective/buildings/map-points", {}, {}) is False
    assert needs_macro("POST", "/api/collective/analysis/cohort/histogram", {}, {}) is True


def test_catalog_map_and_lab_stay_open():
    assert needs_macro("GET", "/api/free/v2/regions", {"search": "복대"}) is False
    assert needs_macro("GET", "/api/map/boundaries", {}) is False
    assert needs_macro("GET", "/api/auth/status", {}) is False
    assert needs_macro("GET", "/api/built/lab/twin-experiments", {}) is False
    assert needs_macro("GET", "/health", {}) is False
