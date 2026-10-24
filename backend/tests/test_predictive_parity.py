"""예측형 순위의 1.0%p 성능 유사와 해석 후보."""

from __future__ import annotations

from app.built.schemas import ModelCandidate, ModelMetrics, RegressionCoeff, RegressionVariableSpec
from app.recommendation.ranks import annotate_predictive_band


def _cand(
    rank: int,
    blocks: list[str],
    cv: float | None,
    coefs: list[RegressionCoeff] | None = None,
    scale: str = "loglog",
) -> ModelCandidate:
    return ModelCandidate(
        rank=rank,
        blocks=blocks,
        variables=RegressionVariableSpec(),
        response_scale=scale,  # type: ignore[arg-type]
        metrics=ModelMetrics(model_type=scale, cv_mape=cv),  # type: ignore[arg-type]
        coefficients=coefs or [],
    )


def _coef(name: str, estimate: float, p: float) -> RegressionCoeff:
    return RegressionCoeff(name=name, estimate=estimate, p_value=p)


def test_band_is_one_point_on_the_same_sample():
    rows = [
        _cand(1, ["gross_area", "road_width", "zone_type"], 35.08),
        _cand(2, ["gross_area", "zone_type"], 35.10),
        _cand(3, ["gross_area", "road_width", "zone_type", "building_use"], 36.08),
        _cand(4, ["gross_area"], 36.09),
    ]
    judgments, notes = annotate_predictive_band(rows, ns=[69, 69, 69, 69])
    assert [j.label for j in judgments] == ["예측 최소", "성능 유사", "성능 유사", "비교 후보"]
    assert judgments[0].cv_gap_pp == 0.0
    assert judgments[1].cv_gap_pp == 0.02
    assert judgments[3].cv_gap_pp == 1.01
    assert any("1.0%p" in note for note in notes)
    assert not any("해석 후보로 둡니다" in note for note in notes)


def test_age_superset_with_negative_significant_coef_is_interpretive():
    base = ["gross_area", "road_width", "zone_type"]
    rows = [
        _cand(1, base, 35.08),
        _cand(
            2,
            base + ["building_age"],
            35.10,
            [_coef("building_age", -0.01, 0.04)],
        ),
    ]
    judgments, notes = annotate_predictive_band(rows, ns=[69, 69])
    assert judgments[1].label == "성능 유사 · 해석 후보"
    assert any("연식" in note and "해석 후보로 둡니다" in note for note in notes)
    assert any("AIC" in note for note in notes)


def test_weak_or_wrong_sign_is_not_interpretive():
    base = ["gross_area", "road_width", "zone_type"]
    weak = [
        _cand(1, base, 35.0),
        _cand(2, base + ["building_age"], 35.2, [_coef("building_age", -0.01, 0.4)]),
    ]
    labels, notes = annotate_predictive_band(weak, ns=[69, 69])
    assert labels[1].label == "성능 유사"
    assert any("해석 후보로 두지 않았습니다" in note for note in notes)

    flipped = [
        _cand(1, base, 35.0),
        _cand(2, base + ["building_age"], 35.2, [_coef("building_age", 0.02, 0.01)]),
    ]
    labels, notes = annotate_predictive_band(flipped, ns=[69, 69])
    assert labels[1].label == "성능 유사"
    assert not any("해석 후보로 둡니다" in note for note in notes)


def test_land_positive_inside_band_is_interpretive():
    base = ["gross_area", "road_width", "zone_type"]
    rows = [
        _cand(1, base, 35.0),
        _cand(
            2,
            base + ["land_area"],
            35.8,
            [_coef("land_area", 0.4, 0.09)],
        ),
    ]
    judgments, notes = annotate_predictive_band(rows, ns=[69, 69])
    assert judgments[1].label == "성능 유사 · 해석 후보"
    assert any("대지면적 계수는 양" in note for note in notes)


def test_different_n_or_extra_block_stays_out_of_interpretive():
    base = ["gross_area", "road_width", "zone_type"]
    other_n = [
        _cand(1, base, 35.0),
        _cand(2, base + ["building_age"], 35.2, [_coef("building_age", -0.01, 0.01)]),
    ]
    judgments, notes = annotate_predictive_band(other_n, ns=[69, 70])
    assert judgments[1].label == "비교 후보"
    assert any("표본 수" in note for note in notes)

    mixed = [
        _cand(1, base, 35.0),
        _cand(
            2,
            base + ["building_age", "building_use"],
            35.2,
            [_coef("building_age", -0.01, 0.01)],
        ),
    ]
    judgments, notes = annotate_predictive_band(mixed, ns=[69, 69])
    assert judgments[1].label == "성능 유사"
    assert not any("해석 후보로 둡니다" in note for note in notes)


def test_missing_cv_has_no_band():
    rows = [_cand(1, ["gross_area"], None)]
    judgments, notes = annotate_predictive_band(rows, ns=[10])
    assert judgments[0].label == "비교 후보"
    assert judgments[0].cv_gap_pp is None
    assert notes == []
