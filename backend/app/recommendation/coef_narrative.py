"""회귀계수 자연어 해석 — 모형 탐색 R4."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.ai.built_narrative import _human_name, _is_categorical
from app.recommendation.models import CoefficientNarrative

if TYPE_CHECKING:
    from app.built.schemas import RegressionCoeff, ResponseScale


_LOGLOG_ELASTIC = frozenset({"gross_area", "land_area"})


def _narrative_line(
    name: str,
    estimate: float,
    p_value: float | None,
    response_scale: str,
) -> str | None:
    if name == "const":
        return None
    label = _human_name(name)
    sig = p_value is not None and p_value < 0.05
    uses_log_y = response_scale in ("log", "loglog")
    log_x = name == "assessed_land_price" or (response_scale == "loglog" and name in _LOGLOG_ELASTIC)
    categorical = _is_categorical(name) or name.startswith(("struct_", "atype_", "loc_"))
    if log_x:
        change = math.log(1.01)
        condition = f"{label} 1% 증가 시"
    elif categorical:
        change = 1.0
        condition = f"{label}의 기준 범주 대비"
    else:
        change = 1.0
        unit = {"gross_area": "㎡", "land_area": "㎡", "building_age": "년", "road_code": "m"}.get(name, "단위")
        condition = f"{label} 1{unit} 증가 시"
    try:
        effect = math.expm1(estimate * change) * 100 if uses_log_y else estimate * change
    except OverflowError:
        return f"{condition}의 역변환 값이 계산 범위를 넘어 효과를 표시하지 않습니다. 계수와 모형 적합 상태를 확인하세요."
    amount = f"{abs(effect):,.2f}" if abs(effect) >= 0.01 else f"{abs(effect):.3g}"
    unit = "%" if uses_log_y else "만원"
    direction = "높은" if effect >= 0 else "낮은"
    base = f"다른 변수가 같을 때 {condition} 거래금액이 약 {amount}{unit} {direction} 관계입니다."
    if not sig:
        base += " (p<0.05 기준 유의하지 않음)"
    return base


def build_coefficient_narratives(
    coefficients: list,
    *,
    response_scale: str,
    limit: int = 6,
) -> list[CoefficientNarrative]:
    if not coefficients:
        return []

    # 서로 단위가 다른 원계수의 크기를 변수 중요도나 기여도로 해석하지 않는다.
    ordered = sorted((c for c in coefficients if c.name != "const"),
        key=lambda c: (not (c.p_value is not None and c.p_value < 0.05), c.name))

    out: list[CoefficientNarrative] = []
    for c in ordered[:limit]:
        text = _narrative_line(c.name, c.estimate, c.p_value, response_scale)
        if not text:
            continue
        out.append(
            CoefficientNarrative(
                name=c.name,
                label_ko=_human_name(c.name),
                text_ko=text,
                significant=c.p_value is not None and c.p_value < 0.05,
                is_top_contributor=False,
            )
        )
    return out
