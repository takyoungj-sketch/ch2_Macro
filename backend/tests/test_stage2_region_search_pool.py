"""Stage2 must re-admit region_* blocks when include_region_features=True."""

from __future__ import annotations

from app.built.regression.region_features import region_blocks_for_asset
from app.built.schemas import RegressionSelectionRequest
from app.recommendation.stage2 import Stage2Input, run_stage2_twin


def test_region_blocks_for_commercial_nonempty():
    blocks = region_blocks_for_asset("commercial")
    assert "region_land_p50" in blocks
    assert any(b.startswith("region_") for b in blocks)


def test_stage2_expands_search_pool_with_region_blocks(monkeypatch):
    """Local stage1 pool lacks region_*; stage2 must append them before pooling."""
    captured: dict = {}

    def fake_validate(conn, *, req, admin_level, search_pool, anchor_df):
        captured["search_pool"] = list(search_pool)

        class V:
            twin_codes = ("11110251",)
            neighbors = [{"region_code": "11110251", "similarity_score": 0.9}]
            gate_summary = None

        return V()

    def fake_evaluate(_conn, **kwargs):
        captured["eval_blocks"] = list(kwargs["blocks"])

        class P:
            decision = "local"
            decision_reason = "test"
            candidates = []
            twin_gates = []

        return P()

    monkeypatch.setattr(
        "app.recommendation.stage2.validate_recommend_twin_neighbors",
        fake_validate,
    )
    monkeypatch.setattr(
        "app.recommendation.stage2.evaluate_pooling_candidates",
        fake_evaluate,
    )

    class Fit:
        response_scale = "log"
        cv_mape = 40.0
        blocks = ["gross_area"]

    class Primary:
        fit = Fit()
        blocks = ["gross_area"]

    class Scope:
        anchor_unit = type("U", (), {"code": "11110250"})()

    class Ctx:
        admin_level = "eupmyeondong"
        df = None

    req = RegressionSelectionRequest(
        asset_type="commercial",
        include_region_features=True,
        region_feature_tier="price",
        profile_twin_neighbors=[{"region_code": "11110251"}],
    )
    inp = Stage2Input(
        ctx=Ctx(),  # type: ignore[arg-type]
        req=req,
        blocks=["gross_area", "land_area"],  # no region_*
        primary_raw=Primary(),  # type: ignore[arg-type]
        analysis_scope=Scope(),  # type: ignore[arg-type]
        region_col=None,
    )
    run_stage2_twin(None, inp)
    assert "region_land_p50" in captured["search_pool"]
    assert "region_land_p50" in captured["eval_blocks"]
    assert "region_population" not in captured["search_pool"]
    assert "gross_area" in captured["search_pool"]
