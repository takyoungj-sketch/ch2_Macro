"""랩 Twin 벤치: 구조 1위 게이트 실패 시 Twin 열을 비운다."""

from __future__ import annotations

from app.built.lab_recommend_twin_bench import pick_rank1_passed
from app.built.schemas import TwinGateResult


def test_pick_rank1_uses_first_even_if_later_passed():
    gates = [
        TwinGateResult(region_code="t1", accepted=False, reasons=["인접 시도 아님"]),
        TwinGateResult(region_code="t2", accepted=True, reasons=[]),
    ]
    code, reason = pick_rank1_passed(["t1", "t2"], gates)
    assert code is None
    assert reason is not None
    assert "t1" in reason


def test_pick_rank1_ok_when_first_passes():
    gates = [
        TwinGateResult(region_code="t1", accepted=True, reasons=[]),
        TwinGateResult(region_code="t2", accepted=True, reasons=[]),
    ]
    code, reason = pick_rank1_passed(["t1", "t2"], gates)
    assert code == "t1"
    assert reason is None


def test_pick_rank1_empty():
    code, reason = pick_rank1_passed([], [])
    assert code is None
    assert reason is not None


def test_bench_uses_rank1_and_adds_region_leaf_on_dummy(monkeypatch):
    import pandas as pd

    from app.built.lab_recommend_twin_bench import run_recommend_twin_bench
    from app.built.schemas import PoolingCandidateMetrics, RegressionSelectionRequest, TwinGateResult

    captured: dict = {"fit_blocks": [], "research_pools": []}

    class Fit:
        response_scale = "log"
        cv_mape = 40.0
        n = 20
        adj_r_squared = 0.5
        mape = 30.0
        cv_folds = 3
        confirm_cv_mape = 42.0
        confirm_cv_folds = 1
        aic = 100.0
        bic = 110.0
        joint_f_tests = {}
        model = None

    class PrimaryRaw:
        fit = Fit()
        blocks = ["gross_area"]

    class Scope:
        admin_level = "eupmyeondong"
        anchor_unit = type("U", (), {"code": "43130118"})()

    class Ctx:
        admin_level = "eupmyeondong"
        unified = False
        df = pd.DataFrame({"price": [10000.0, 12000.0, 9000.0]})

    class Bundle:
        ctx = Ctx()
        pool = ["gross_area", "land_area"]
        primary_raw = PrimaryRaw()
        region_col = None

    def fake_stage1(_conn, _req):
        return Scope(), None, None, None, None, Bundle(), []

    def fake_validate(_conn, **_k):
        class V:
            neighbors = [
                {"region_code": "11110251", "similarity_score": 0.9},
                {"region_code": "11110252", "similarity_score": 0.8},
            ]
            gate_summary = None

        return V()

    def fake_filter(_conn, **_k):
        return [
            TwinGateResult(region_code="11110251", accepted=True, reasons=[]),
            TwinGateResult(region_code="11110252", accepted=True, reasons=[]),
        ], ["11110251", "11110252"]

    def fake_fit(_conn, **kwargs):
        captured["fit_blocks"].append(list(kwargs["blocks"]))
        captured.setdefault("twin_codes", kwargs["twin_codes"])
        return PoolingCandidateMetrics(
            candidate_id="x",
            label="x",
            n=30,
            cv_mape=38.0,
            confirm_cv_mape=41.0,
            blocks=list(kwargs["blocks"]),
            response_scale="log",
            prefix_k=1,
        )

    def fake_research(_conn, **kwargs):
        captured["research_pools"].append(list(kwargs["search_pool"]))
        return PoolingCandidateMetrics(
            candidate_id="y",
            label="y",
            n=30,
            cv_mape=36.0,
            confirm_cv_mape=40.0,
            blocks=["gross_area", "land_area"],
            response_scale="log",
            prefix_k=1,
        )

    monkeypatch.setattr("app.built.lab_recommend_twin_bench._build_stage1", fake_stage1)
    monkeypatch.setattr(
        "app.built.lab_recommend_twin_bench.validate_recommend_twin_neighbors",
        fake_validate,
    )
    monkeypatch.setattr(
        "app.built.lab_recommend_twin_bench.filter_twins_by_hard_gates",
        fake_filter,
    )
    monkeypatch.setattr("app.built.lab_recommend_twin_bench._fit_pool_variant", fake_fit)
    monkeypatch.setattr("app.built.lab_recommend_twin_bench._research_pool_variant", fake_research)
    monkeypatch.setattr(
        "app.built.lab_recommend_twin_bench._attach_search_confirm_cv",
        lambda m, *_a, **_k: m,
    )
    monkeypatch.setattr(
        "app.built.lab_recommend_twin_bench._predict_column",
        lambda *_a, **kw: kw["col"],
    )

    req = RegressionSelectionRequest(
        asset_type="commercial",
        region_codes=["43130118"],
        region_code_level="eupmyeondong",
        profile_twin_neighbors=[{"region_code": "11110251"}],
    )
    out = run_recommend_twin_bench(None, req=req, scenario={"gross_area": 120})
    assert captured["twin_codes"] == ("11110251",)
    assert ["gross_area"] in captured["fit_blocks"]
    assert ["gross_area", "region_leaf"] in captured["fit_blocks"]
    assert "region_leaf" in captured["research_pools"][1]
    assert out["rank1_region_code"] == "11110251"
    ids = [c["id"] for c in out["columns"]]
    assert ids == ["local", "twin1", "twin1_dummy", "twin2", "twin2_dummy"]
