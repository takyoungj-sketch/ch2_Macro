"""집합 회귀 presentation — 회귀식·직관 해석."""

from app.collective.regression.presentation import (
    build_market_interpretation_hints,
    enrich_regression_response,
    format_equation,
    interpret_coefficient,
    short_display_label,
)
from app.collective.schemas import RegressionCoeff


def test_linear_equation_and_effects():
    coefs = [
        RegressionCoeff(name="const", label="절편", coef=50000.0, p=0.01),
        RegressionCoeff(name="exclusive_area", label="전용면적", coef=1200.0, p=0.02),
        RegressionCoeff(name="dong_102", label="동 102", coef=-3000.0, p=0.15),
    ]
    eq = format_equation(coefs, model_type="linear")
    assert "금액(만원)" in eq
    assert "전용면적" in eq
    assert "동 102" not in eq  # p>=0.1 excluded

    assert "1㎡" in interpret_coefficient("exclusive_area", "전용면적", 1200.0, model_type="linear")
    assert "만원" in interpret_coefficient("exclusive_area", "전용면적", 1200.0, model_type="linear")
    dummy = interpret_coefficient("builder_계룡", "시공사 계룡 (기준 대비)", -302.0, model_type="linear")
    assert "기준 대비" in dummy
    assert "1단위" not in dummy
    atype = interpret_coefficient("atype_officetel", "유형 오피스텔 (기준 대비)", -0.2, model_type="log")
    assert "기준 대비" in atype
    assert "%" in atype


def test_log_percent_effects():
    coefs = [
        RegressionCoeff(name="const", label="절편", coef=10.0, p=0.01),
        RegressionCoeff(name="building_age", label="연식", coef=-0.02, p=0.03),
    ]
    eq = format_equation(coefs, model_type="log")
    assert "log(금액)" in eq
    effect = interpret_coefficient("building_age", "연식", -0.02, model_type="log")
    assert "%" in effect

    _, enriched, _ = enrich_regression_response(coefs, model_type="log", model_comparison=None)
    assert enriched[1]["effect_plain"]


def test_short_display_label():
    assert short_display_label("용도지역 제3종일반주거(기준 대비)") == "제3종일반주거"
    assert short_display_label("건축물용도 근린생활시설(기준 대비)") == "근린생활시설"
    assert short_display_label("시공사 계룡건설산업 (기준 대비)") == "계룡건설산업"
    assert short_display_label("구조 SRC (기준 대비)") == "SRC"
    assert short_display_label("유형 오피스텔 (기준 대비)") == "오피스텔"


def test_equation_variable_order():
    coefs = [
        RegressionCoeff(name="const", label="절편", coef=1.0, p=0.0),
        RegressionCoeff(name="dong_102", label="동 102", coef=-3.0, p=0.01),
        RegressionCoeff(name="building_age", label="연식", coef=-0.1, p=0.02),
        RegressionCoeff(name="exclusive_area", label="전용면적", coef=1200.0, p=0.03),
        RegressionCoeff(name="floor_rel_low", label="층 저층", coef=100.0, p=0.04),
    ]
    eq = format_equation(coefs, model_type="linear")
    assert eq.index("전용면적") < eq.index("연식") < eq.index("저층") < eq.index("102")


def test_market_interpretation_hints():
    coefs = [
        RegressionCoeff(
            name="zone_3",
            label="용도지역 제3종일반주거(기준 대비)",
            coef=5000.0,
            p=0.01,
            effect_plain="기준 대비 +5,000만원",
        ),
        RegressionCoeff(name="exclusive_area", label="전용면적", coef=1200.0, p=0.02),
    ]
    hints = build_market_interpretation_hints(coefs, model_type="linear")
    assert len(hints) == 2
    assert "제3종일반주거" in hints[0]
    assert "용도지역" not in hints[0]

