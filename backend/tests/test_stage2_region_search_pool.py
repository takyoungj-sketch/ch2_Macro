"""Stage2 Twin1: Local 식 고정 + 쌍둥이 1위 + region_leaf 강제."""

from __future__ import annotations

from app.built.regression.region_features import region_blocks_for_asset
from app.built.schemas import PoolingCandidateMetrics, RegressionSelectionRequest
from app.recommendation.stage2 import Stage2Input, run_stage2_twin


def _stage2_input(**req_kw) -> Stage2Input:
    class Fit:
        response_scale = "log"
        cv_mape = 40.0
        blocks = ["gross_area"]
        n = 10

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
        **req_kw,
    )
    return Stage2Input(
        ctx=Ctx(),  # type: ignore[arg-type]
        req=req,
        blocks=["gross_area", "land_area"],
        primary_raw=Primary(),  # type: ignore[arg-type]
        analysis_scope=Scope(),  # type: ignore[arg-type]
        region_col=None,
    )


def _metrics(candidate_id: str, prefix_k: int, *, n: int, cv: float = 40.0) -> PoolingCandidateMetrics:
    return PoolingCandidateMetrics(
        candidate_id=candidate_id,
        label=candidate_id,
        n=n,
        region_codes=["11110250"] + [f"t{i}" for i in range(prefix_k)],
        cv_mape=cv,
        confirm_cv_mape=None,
        blocks=["gross_area"],
        response_scale="log",
        prefix_k=prefix_k,
        key_coefficients={"gross_area": 12.0},
    )


def _patch_validate(monkeypatch, captured: dict | None = None):
    def fake_validate(conn, *, req, admin_level, search_pool, anchor_df):
        if captured is not None:
            captured["search_pool"] = list(search_pool)

        class V:
            twin_codes = ("11110251", "11110252")
            neighbors = [
                {"region_code": "11110251", "similarity_score": 0.9},
                {"region_code": "11110252", "similarity_score": 0.8},
            ]
            gate_summary = None

        return V()

    monkeypatch.setattr(
        "app.recommendation.stage2.validate_recommend_twin_neighbors",
        fake_validate,
    )


def test_region_blocks_for_commercial_nonempty():
    blocks = region_blocks_for_asset("commercial")
    assert "region_land_p50" in blocks
    assert any(b.startswith("region_") for b in blocks)


def test_stage2_twin1_uses_rank1_and_adds_region_leaf(monkeypatch):
    captured: dict = {}
    _patch_validate(monkeypatch, captured)

    def fake_evaluate(_conn, **kwargs):
        captured["eval_blocks"] = list(kwargs["blocks"])
        captured["twin_blocks"] = list(kwargs.get("twin_blocks") or [])
        captured["twin_region_codes"] = tuple(kwargs["twin_region_codes"])
        captured["twin_region_col"] = kwargs.get("twin_region_col")
        captured["mode"] = kwargs.get("mode")
        captured["scale"] = kwargs.get("fixed_response_scale")

        class P:
            decision = "local"
            decision_reason = "test"
            candidates = []
            twin_gates = []

        return P()

    monkeypatch.setattr(
        "app.recommendation.stage2.evaluate_pooling_candidates",
        fake_evaluate,
    )
    run_stage2_twin(None, _stage2_input())
    assert captured["eval_blocks"] == ["gross_area"]
    assert captured["twin_blocks"] == ["gross_area", "region_leaf"]
    assert captured["twin_region_codes"] == ("11110251",)
    assert captured["twin_region_col"] == "addr3"
    assert captured["mode"] == "diagnose"
    assert captured["scale"] == "log"
    assert "region_land_p50" not in captured["eval_blocks"]
    assert "region_land_p50" not in captured["twin_blocks"]
    assert "region_land_p50" not in captured["search_pool"]


def test_stage2_twin1_does_not_duplicate_existing_region_leaf(monkeypatch):
    captured: dict = {}
    _patch_validate(monkeypatch, captured)

    def fake_evaluate(_conn, **kwargs):
        captured["twin_blocks"] = list(kwargs.get("twin_blocks") or [])

        class P:
            decision = "local"
            decision_reason = "test"
            candidates = []
            twin_gates = []

        return P()

    monkeypatch.setattr(
        "app.recommendation.stage2.evaluate_pooling_candidates",
        fake_evaluate,
    )
    inp = _stage2_input()
    inp.primary_raw.blocks = ["gross_area", "region_leaf"]  # type: ignore[attr-defined]
    inp.primary_raw.fit.blocks = ["gross_area", "region_leaf"]  # type: ignore[attr-defined]
    run_stage2_twin(None, inp)
    assert captured["twin_blocks"] == ["gross_area", "region_leaf"]


def test_inspect_pool_is_rank1_even_when_local_wins(monkeypatch):
    _patch_validate(monkeypatch)

    def fake_evaluate(_conn, **kwargs):
        class P:
            decision = "local"
            decision_reason = "test"
            candidates = [
                _metrics("local", 0, n=10, cv=40.0),
                _metrics("twin_prefix_k1", 1, n=20, cv=38.0),
                _metrics("twin_prefix_k2", 2, n=40, cv=37.0),
            ]
            twin_gates = []

        return P()

    monkeypatch.setattr(
        "app.recommendation.stage2.evaluate_pooling_candidates",
        fake_evaluate,
    )
    monkeypatch.setattr(
        "app.recommendation.stage2.research_full_twin_pool",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("research must not run")),
    )
    out = run_stage2_twin(None, _stage2_input())
    assert out.inspect_pool is not None
    assert out.inspect_pool.prefix_k == 1
    assert out.inspect_pool.n == 20
    assert [p.prefix_k for p in out.pools] == [1]
    assert out.decision == "local"
    assert out.primary is None
    assert out.research_ran is False
    assert out.research is None


def test_stage2_research_uses_stage1_block_pool(monkeypatch):
    captured: dict = {}
    _patch_validate(monkeypatch)

    def fake_evaluate(_conn, **kwargs):
        class P:
            decision = "local"
            decision_reason = "test"
            candidates = [
                _metrics("local", 0, n=10),
                _metrics("twin_prefix_k1", 1, n=20, cv=38.0),
            ]
            twin_gates = []

        return P()

    def fake_research(_conn, **kwargs):
        captured["search_pool"] = list(kwargs["search_pool"])
        return _metrics("twin_research", 1, n=20, cv=33.0)

    monkeypatch.setattr(
        "app.recommendation.stage2.evaluate_pooling_candidates",
        fake_evaluate,
    )
    monkeypatch.setattr(
        "app.recommendation.stage2.research_full_twin_pool",
        fake_research,
    )
    out = run_stage2_twin(None, _stage2_input(run_stage2_research=True))
    assert captured["search_pool"] == ["gross_area", "land_area"]
    assert out.research_ran is True
    assert out.research is not None
    assert out.research.candidate_id == "twin_research"
    assert out.research.n == 20
    assert out.inspect_pool is not None
    assert out.inspect_pool.prefix_k == 1


def test_research_uses_only_rank1_passed_twin(monkeypatch):
    captured: dict = {}

    def fake_filter(_conn, **_kwargs):
        return [], ["t1", "t2", "t3"]

    def fake_variant(_conn, **kwargs):
        captured["twin_codes"] = kwargs["twin_codes"]
        captured["prefix_k"] = kwargs["prefix_k"]
        captured["label"] = kwargs["label"]
        return _metrics("twin_research", 1, n=20, cv=33.0)

    monkeypatch.setattr(
        "app.built.regression.selection.pooling.filter_twins_by_hard_gates",
        fake_filter,
    )
    monkeypatch.setattr(
        "app.built.regression.selection.pooling._research_pool_variant",
        fake_variant,
    )
    from app.built.regression.selection.pooling import research_full_twin_pool

    out = research_full_twin_pool(
        None,
        local_ctx=type("C", (), {"admin_level": "eupmyeondong"})(),
        req=RegressionSelectionRequest(asset_type="commercial"),
        search_pool=["gross_area"],
        anchor_region_codes=("anchor",),
        twin_region_codes=("t1", "t2", "t3"),
        admin_level="eupmyeondong",
        region_col=None,
    )
    assert captured["twin_codes"] == ("t1",)
    assert captured["prefix_k"] == 1
    assert "1위" in captured["label"]
    assert out is not None
    assert out.prefix_k == 1
