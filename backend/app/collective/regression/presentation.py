"""회귀 결과 — 읽기 쉬운 회귀식·계수 해석 (집합 주거·비주거 공통)."""

from __future__ import annotations

import math
from typing import Literal, Sequence

ModelType = Literal["log", "linear"]

EQUATION_SIG_P = 0.1


def coefficient_sort_key(name: str) -> tuple[int, int, str]:
    """회귀식·계수표 공통 변수 순서 (면적 → 연식 → 층 → 동 → 기타)."""
    if name == "const":
        return (0, 0, name)
    if name == "exclusive_area":
        return (1, 0, name)
    if name == "gross_area":
        return (1, 1, name)
    if name == "land_area":
        return (1, 2, name)
    if name == "building_age":
        return (2, 0, name)
    if name in ("households", "ln_households"):
        return (2, 1, name)
    if name == "max_floor":
        return (3, -1, name)
    if name == "parking_per_household":
        return (3, -1, name)
    if name.startswith("atype_"):
        return (5, 5, name)
    if name.startswith("struct_"):
        return (6, 4, name)
    if name.startswith("builder_"):
        return (6, 5, name)
    if name == "floor":
        return (3, 0, name)
    if name.startswith("floor_rel_"):
        return (3, 1, name)
    if name.startswith("floor_grp_"):
        return (3, 2, name)
    if name.startswith("floor_"):
        return (3, 3, name)
    if name.startswith("dong_"):
        return (4, 0, name)
    if name.startswith("addr4_"):
        return (4, 1, name)
    if name.startswith("rights_"):
        return (5, 0, name)
    if name.startswith("zone_"):
        return (6, 0, name)
    if name.startswith("use_"):
        return (6, 1, name)
    if name.startswith("roadw_"):
        return (6, 2, name)
    if name == "road_code":
        return (6, 3, name)
    if name.startswith("bld_"):
        return (9, 0, name)
    return (8, 0, name)


def sort_coefficients_for_display(coefficients: Sequence) -> list:
    return sorted(coefficients, key=lambda c: coefficient_sort_key(_coef_attr(c, "name")))

# 연속 변수 컬럼명 (더미·FE 제외)
_CONTINUOUS = frozenset(
    {
        "exclusive_area",
        "gross_area",
        "land_area",
        "building_age",
        "floor",
        "road_code",
        "households",
        "ln_households",
        "max_floor",
        "parking_per_household",
    }
)


def _fmt_num(v: float) -> str:
    av = abs(v)
    if av >= 100:
        return f"{v:,.0f}"
    if av >= 1:
        s = f"{v:,.1f}".rstrip("0").rstrip(".")
        return s
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return s


def _fmt_manwon(v: float) -> str:
    sign = "+" if v >= 0 else "−"
    return f"{sign}{abs(round(v)):,}만원"


def _fmt_pct_from_log(coef: float) -> str:
    pct = (math.exp(coef) - 1.0) * 100.0
    sign = "+" if pct >= 0 else "−"
    return f"{sign}{abs(pct):.1f}%"


def _is_continuous(name: str) -> bool:
    if name in _CONTINUOUS:
        return True
    if name.startswith(
        ("dong_", "rights_", "bld_", "zone_", "use_", "roadw_", "floor_rel", "floor_grp", "floor_", "struct_", "builder_", "atype_")
    ):
        return False
    return name not in ("const",)


def _unit_suffix(name: str) -> str:
    if name in ("exclusive_area", "gross_area", "land_area"):
        return "㎡"
    if name == "building_age":
        return "년"
    if name == "households":
        return "세대"
    if name == "max_floor":
        return "층"
    if name == "parking_per_household":
        return "대"
    if name == "floor":
        return "층"
    if name == "road_code":
        return "m"
    return ""


def _coef_attr(c, attr: str, default=None):
    if isinstance(c, dict):
        return c.get(attr, default)
    return getattr(c, attr, default)


def short_display_label(label: str) -> str:
    """화면용 짧은 변수명 — 접두·(기준 대비) 제거."""
    s = str(label).strip()
    for suffix in (" (기준 대비)", "(기준 대비)"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    for prefix in ("용도지역 ", "건축물용도 ", "도로폭 ", "동 ", "권리 ", "단지 ", "시공사 ", "구조 ", "유형 "):
        if s.startswith(prefix) and len(s) > len(prefix):
            s = s[len(prefix):].strip()
            break
    if s.startswith("층 ") and len(s) > 2:
        s = s[2:].strip()
    return s or label


def _effect_magnitude(coef: float, model_type: ModelType) -> float:
    if model_type == "log":
        return abs(math.exp(coef) - 1.0)
    return abs(coef)


def build_market_interpretation_hints(
    coefficients: Sequence,
    *,
    model_type: ModelType,
    limit: int = 4,
) -> list[str]:
    """AI·Explain용 시장 번역 불릿 (유의 변수, 효과 크기 순)."""
    pool = [
        c
        for c in coefficients
        if _coef_attr(c, "name") != "const"
        and not str(_coef_attr(c, "name", "")).startswith("bld_")
        and (_p := _coef_attr(c, "p")) is not None
        and _p < EQUATION_SIG_P
    ]
    pool.sort(
        key=lambda c: _effect_magnitude(float(_coef_attr(c, "coef")), model_type),
        reverse=True,
    )
    out: list[str] = []
    for i, c in enumerate(pool[:limit], start=1):
        label = short_display_label(_coef_attr(c, "label") or _coef_attr(c, "name"))
        plain = _coef_attr(c, "effect_plain")
        if plain:
            out.append(f"시장 해석 {i}: {label} — {plain}.")
        else:
            out.append(f"시장 해석 {i}: {label} — 계수 {round(float(_coef_attr(c, 'coef')), 2)}.")
    return out


def format_equation(
    coefficients: Sequence,
    *,
    model_type: ModelType,
) -> str:
    """유의(p<0.1) 변수만 포함한 회귀식 문자열."""
    dep = "log(금액)" if model_type == "log" else "금액(만원)"
    by_name = {_coef_attr(c, "name"): c for c in coefficients}
    intercept = by_name.get("const")
    if intercept is None:
        return f"{dep} = —"

    ic = float(_coef_attr(intercept, "coef"))
    parts = [f"{dep} = {_fmt_num(ic)}"]
    others = [c for c in coefficients if _coef_attr(c, "name") != "const"]
    sig = [c for c in others if (p := _coef_attr(c, "p")) is not None and p < EQUATION_SIG_P]
    sig = sort_coefficients_for_display(sig)
    for c in sig:
        coef = float(_coef_attr(c, "coef"))
        sign = "+" if coef >= 0 else "−"
        label = short_display_label(_coef_attr(c, "label") or _coef_attr(c, "name"))
        parts.append(f" {sign} {_fmt_num(abs(coef))}·{label}")
    return "".join(parts)


def interpret_coefficient(
    name: str,
    label: str,
    coef: float,
    *,
    model_type: ModelType,
) -> str:
    """변수별 직관적 해석 (만원 또는 %)."""
    if name == "const":
        if model_type == "log":
            approx = math.exp(coef)
            return f"기준 조건 log(금액) 출발점 (대략 {round(approx):,}만원 수준, 다른 변수·기준 범주 전제)"
        return f"기준 조건 출발 수준 약 {round(coef):,}만원 (다른 변수 0·기준 범주 전제)"

    unit = _unit_suffix(name)
    step = f"1{unit} " if unit else "1단위 "

    if model_type == "log":
        pct = _fmt_pct_from_log(coef)
        if _is_continuous(name):
            return f"{step}증가 시 금액 약 {pct}"
        return f"기준 대비 약 {pct}"

    if _is_continuous(name):
        return f"{step}증가 시 {_fmt_manwon(coef)}"
    return f"기준 대비 {_fmt_manwon(coef)}"


def enrich_regression_response(
    coefficients: list,
    *,
    model_type: ModelType,
    model_comparison=None,
    price_adj_r_squared: float | None = None,
) -> tuple[str, list[dict], float | None]:
    """회귀식·effect_plain·금액척도 adj R²."""
    equation = format_equation(coefficients, model_type=model_type)
    enriched = enrich_coefficients(coefficients, model_type=model_type)
    price_adj: float | None = price_adj_r_squared
    if price_adj is None and model_comparison is not None:
        m = model_comparison.log if model_type == "log" else model_comparison.linear
        if m is not None and m.adj_r_squared is not None:
            price_adj = m.adj_r_squared
    return equation, enriched, price_adj


def enrich_coefficients(
    coefficients: Sequence,
    *,
    model_type: ModelType,
) -> list[dict]:
    """계수 목록에 effect_plain 필드를 추가."""
    out: list[dict] = []
    for c in coefficients:
        name = _coef_attr(c, "name")
        label = _coef_attr(c, "label") or name
        coef = float(_coef_attr(c, "coef"))
        row = {
            "name": name,
            "label": label,
            "coef": coef,
            "se": _coef_attr(c, "se"),
            "t": _coef_attr(c, "t"),
            "p": _coef_attr(c, "p"),
            "effect_plain": interpret_coefficient(name, label, coef, model_type=model_type),
        }
        out.append(row)
    return out
