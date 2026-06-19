"""분석 탭 설명 메타(spec) + 실행 결과 기반 동적 해석 힌트 — AI Q&A 연동용 fact 레이어."""

from __future__ import annotations

from typing import Any

CONTROL_LABELS: dict[str, str] = {
    "ln_gross_area": "ln(연면적)",
    "ln_exclusive_area": "ln(전용면적)",
    "building_age": "연식(경과연수)",
    "building_use": "건축물용도 더미",
    "relative_floor": "상대 층구간 더미",
    "contract_period": "거래시점(반기) 더미",
    "building_fixed_effects": "단지 고정효과",
}

FLOOR_GROUP_LINES = [
    "B2 이하 → 지하심층",
    "B1 → 지하1층",
    "1층 → 기준층 (더미 없음, 지수 100%)",
    "2층 → 2층",
    "3~4층 → 저층",
    "5~9층 → 중층",
    "10~19층 → 고층",
    "20층 이상 → 초고층",
]

RESIDENTIAL_FLOOR_GROUP_LINES = [
    "1층 → 화면 지수 100% (표시 기준)",
    "회귀 omitted category → 거래 최다 층 구간 (표본 n≥5)",
    "저층부 → 단지 max층 대비 하위 30% (1·최상층 제외)",
    "중층부 → max층 대비 30~70%",
    "고층부 → max층 대비 70% 초과 (최상층 제외)",
    "최상층 → 단지 최고층",
]


def _controls_human(codes: list[str]) -> list[str]:
    return [CONTROL_LABELS.get(c, c) for c in codes]


def _preset_answers_residential_floor_index() -> list[dict[str, str]]:
    return [
        {
            "id": "formula",
            "question": "공식이 어떻게 만들어졌나요?",
            "answer": (
                "종속변수 ln(㎡당단가)에 대해 HC3 강건표준오차 OLS 회귀를 추정합니다. "
                "통제변수는 ln(전용면적), 연식, 거래시점(반기) 더미, (동·면적·권리 탭일 때) 상대 층구간 더미, "
                "(코호트일 때) 단지 고정효과이며, 여기에 분석 차원(층·동·면적형·권리) 더미를 더합니다. "
                "단, 면적형 탭은 면적을 더미로 직접 추정하므로 ln(전용면적)을 통제에서 빼 이중 반영을 막습니다. "
                "거래시점(반기)을 통제해 선택 기간의 시장 추세가 지수에 섞이지 않게 합니다. "
                "층 탭은 회귀 omitted category를 거래 최다 구간으로 두고, 화면 지수는 1층=100%로 환산합니다."
            ),
        },
        {
            "id": "interpret",
            "question": "지수를 어떻게 해석하나요?",
            "answer": (
                "기준 구간 지수는 100%입니다. "
                "예: 고층부 112% → 전용면적·연식 등을 통제한 조건에서 기준(1층) 대비 "
                "㎡당 단가가 약 12% 높은 패턴입니다(반로그 모델). "
                "95% CI·p-value로 불확실성과 유의성을 함께 보세요."
            ),
        },
        {
            "id": "limits",
            "question": "한계점은 무엇인가요?",
            "answer": (
                "① 단지(또는 코호트) 내 거래만 사용합니다. "
                "② 층·동·면적·권리 결측 거래는 해당 탭에서 제외될 수 있습니다. "
                "③ 구간별 n<5 → 해당 더미·지수 미산출, n<15 → 참고용 표시. "
                "④ 인과가 아니라 선택 기간·단지 내 상관 패턴입니다."
            ),
        },
        {
            "id": "vs_regression_tab",
            "question": "회귀 분석 탭과 무엇이 다른가요?",
            "answer": (
                "효용지수 탭은 ln(㎡당단가) 반로그 spec이 고정되어 "
                "한 차원(층·동·면적·권리)의 상대 지수만 산출합니다. "
                "회귀 탭은 금액(만원) 수준 OLS로 변수·층 형식을 바꿀 수 있는 탐색용입니다."
            ),
        },
    ]


def _preset_answers_residential_regression(*, asset_type: str, cohort: bool) -> list[dict[str, str]]:
    scope = "코호트(복수 단지)" if cohort else "단일 단지"
    age_note = "연식·" if asset_type != "presale" else ""
    dong_note = "동·" if asset_type in ("apartment", "rowhouse") else ""
    rights_note = "권리·" if asset_type == "presale" else ""
    return [
        {
            "id": "formula",
            "question": "공식이 어떻게 만들어졌나요?",
            "answer": (
                f"종속변수 금액(만원)에 대해 OLS 회귀입니다({scope}). "
                f"체크한 변수(전용면적, {age_note}층, {dong_note}{rights_note} 등)만 독립변수로 들어갑니다. "
                "범주형 변수는 더미화(drop_first)되어 기준 범주 대비 계수로 표시됩니다. "
                "코호트는 거래 최다 단지를 기준으로 단지 고정효과를 둘 수 있습니다."
            ),
        },
        {
            "id": "interpret",
            "question": "계수를 어떻게 해석하나요?",
            "answer": (
                "전용면적·연식·층(선형) 등 연속 변수: 계수 1단위 증가 시 금액(만원) 변화량. "
                "더미 변수: 기준 범주 대비 금액 차이(만원). "
                "R²는 모델이 가격 변동을 얼마나 설명하는지의 참고 지표입니다. "
                "예측은 회귀 적합 후 입력값으로 개별 거래 금액·95% 구간을 추정합니다."
            ),
        },
        {
            "id": "limits",
            "question": "한계점은 무엇인가요?",
            "answer": (
                "변수 선택·층 형식(relative/dummy/grouped/linear)에 따라 결과가 달라지는 탐색용 분석입니다. "
                "ln(㎡당)·고정 spec의 층·동·면적 지수는 「층·동·면적 효용지수」 탭을 참고하세요. "
                "단지·기간 내 표본 — 외삽·인과·투자 판단용 아님."
            ),
        },
        {
            "id": "vs_floor_index",
            "question": "효용지수 탭과 무엇이 다른가요?",
            "answer": (
                "회귀 탭은 금액(만원) 수준 OLS이고, 효용지수 탭은 ln(㎡당단가) 반로그로 "
                "한 차원의 상대 지수(%)만 고정 spec으로 산출합니다. "
                "수치·계수가 일치하지 않는 것이 정상입니다."
            ),
        },
    ]


def _preset_answers_regression_floor() -> list[dict[str, str]]:
    return [
        {
            "id": "formula",
            "question": "공식이 어떻게 만들어졌나요?",
            "answer": (
                "종속변수 ln(㎡당단가)에 대해 OLS(최소자승) 회귀를 추정합니다. "
                "독립변수는 ln(연면적), 연식, 건축물용도 더미, 층 구간 더미입니다. "
                "1층은 거래가 많아 기준층으로 두고 더미를 넣지 않습니다. "
                "각 층 구간의 계수 γ에 대해 지수 = exp(γ) × 100 을 산출합니다."
            ),
        },
        {
            "id": "interpret",
            "question": "지수를 어떻게 해석하나요?",
            "answer": (
                "기준층(1층) 지수는 100%입니다. "
                "예: 2층 지수 87% → 연면적·연식·용도가 비슷한 조건에서 1층 대비 "
                "㎡당 단가 수준이 약 13% 낮다는 뜻입니다(반로그 모델). "
                "p-value가 0.05 미만이면 통계적으로 유의한 차이로 볼 수 있습니다."
            ),
        },
        {
            "id": "limits",
            "question": "한계점은 무엇인가요?",
            "answer": (
                "① 도로(cluster) 단위 집계로, 같은 도로 안 건물·용도가 섞입니다. "
                "② 층 정보가 없는 거래는 제외됩니다. "
                "③ 구간별 표본이 5건 미만이면 해당 층 지수를 추정하지 않습니다. "
                "④ 인과관계가 아니라 선택 구간·도로 내 상관 패턴입니다. "
                "⑤ 투자·매매 판단의 유일한 근거로 쓰기엔 부족합니다."
            ),
        },
        {
            "id": "vs_regression_tab",
            "question": "회귀 분석 탭과 무엇이 다른가요?",
            "answer": (
                "효용지수 탭은 층 구간·통제변수·반로그(㎡당) spec이 고정되어 "
                "층별 상대 가치만 비교하기 위한 전용 모델입니다. "
                "회귀 탭은 금액(만원) 수준 OLS로 변수·층 형식을 사용자가 바꿀 수 있는 탐색용입니다."
            ),
        },
    ]


def _preset_answers_simple_area() -> list[dict[str, str]]:
    return [
        {
            "id": "formula",
            "question": "공식이 어떻게 만들어졌나요?",
            "answer": (
                "연면적을 30㎡ 구간으로 묶은 뒤, 각 구간의 ㎡당 단가 평균을 "
                "도로(cluster) 전체 ㎡당 단가 중앙값으로 나누어 ×100 한 비율입니다. "
                "별도 통제변수(연식·용도 등)는 사용하지 않습니다."
            ),
        },
        {
            "id": "interpret",
            "question": "지수를 어떻게 해석하나요?",
            "answer": (
                "100% = 도로 전체 중앙값 수준. "
                "120%면 해당 면적 구간 평균 단가가 중앙값보다 약 20% 높다는 단순 비교입니다. "
                "면적대별로 연식·층 구성이 다르면 왜곡될 수 있습니다."
            ),
        },
        {
            "id": "limits",
            "question": "한계점은 무엇인가요?",
            "answer": (
                "통제변수 없이 단순 평균 비교이므로, "
                "면적대 간 연식·층·용도 차이를 반영하지 못합니다. "
                "층별 탭(집합상가)의 회귀 효용지수와 혼동하지 마세요."
            ),
        },
    ]


def _preset_answers_simple_floor() -> list[dict[str, str]]:
    return [
        {
            "id": "formula",
            "question": "공식이 어떻게 만들어졌나요?",
            "answer": (
                "층별(또는 면적형별) ㎡당 단가 평균을 도로(cluster) 중앙값으로 나눈 ×100 입니다. "
                "회귀·통제변수는 사용하지 않습니다."
            ),
        },
        {
            "id": "interpret",
            "question": "지수를 어떻게 해석하나요?",
            "answer": "100% = 도로 중앙값. 각 층(구간) 평균이 중앙 대비 얼마나 높거나 낮은지의 단순 비교입니다.",
        },
        {
            "id": "limits",
            "question": "한계점은 무엇인가요?",
            "answer": (
                "면적·연식·용도 차이를 통제하지 않습니다. "
                "집합상가 층별 탭은 회귀 기반 spec을 사용하며, 공장 등은 이 단순 방식을 씁니다."
            ),
        },
    ]


def _preset_answers_commercial_regression(*, is_shop: bool) -> list[dict[str, str]]:
    dv = "금액(만원, 수준)"
    extra = "도로폭 라벨" if is_shop else "도로폭(m)"
    return [
        {
            "id": "formula",
            "question": "공식이 어떻게 만들어졌나요?",
            "answer": (
                f"종속변수 {dv}에 대해 OLS 회귀입니다. "
                "체크한 변수(연면적, 연식, 층, 용도지역, 건축물용도, "
                f"{extra} 등)만 독립변수로 들어갑니다. "
                "범주형 변수는 더미화(drop_first)되어 기준 범주 대비 계수로 표시됩니다."
            ),
        },
        {
            "id": "interpret",
            "question": "계수를 어떻게 해석하나요?",
            "answer": (
                "연면적·연식·층(선형) 등 연속 변수: 계수 1단위 증가 시 금액(만원) 변화량. "
                "더미 변수: 기준 범주 대비 금액 차이(만원). "
                "R²는 모델이 가격 변동을 얼마나 설명하는지의 참고 지표입니다."
            ),
        },
        {
            "id": "limits",
            "question": "한계점은 무엇인가요?",
            "answer": (
                "도로(cluster) 내 표본만 사용합니다. "
                "변수 선택·층 형식에 따라 결과가 달라지는 탐색용 분석입니다. "
                "㎡당 반로그·층 구간 고정 spec은 「층·면적 효용지수」 탭을 참고하세요."
            ),
        },
    ]


def _preset_answers_factory_area() -> list[dict[str, str]]:
    return [
        {
            "id": "formula",
            "question": "공식이 어떻게 만들어졌나요?",
            "answer": (
                "연면적을 100/300/1000㎡ 구간(100㎡ 미만, 100~300㎡, 300~1000㎡, 1000㎡ 이상)으로 묶은 뒤, "
                "각 구간의 ㎡당 단가 평균을 상품군(cluster) 중앙값으로 나눈 ×100 비율입니다. "
                "통제변수(연식·대지면적 등)는 사용하지 않습니다."
            ),
        },
        {
            "id": "interpret",
            "question": "지수를 어떻게 해석하나요?",
            "answer": (
                "100% = 이 상품군(cluster) 전체 ㎡당 단가 중앙값. "
                "면적대별 평균 단가가 중앙 대비 얼마나 높거나 낮은지의 단순 비교입니다. "
                "집합공장 분석의 1차 지표로 면적대 탭을 권장합니다."
            ),
        },
        {
            "id": "limits",
            "question": "한계점은 무엇인가요?",
            "answer": (
                "상품군 cluster(도로·용도·연식·면적대) 내 비교이며, "
                "대지면적·용도지역·입지 차이는 반영되지 않습니다. "
                "회귀 탭에서 대지면적·연식 등을 통제한 탐색 분석을 병행하세요."
            ),
        },
    ]


def _cluster_scope_label(asset_type: str) -> str:
    if asset_type == "collective_factory":
        return "상품군(cluster)"
    return "도로(cluster)"


def _floor_index_hints(raw: dict, *, asset_type: str = "collective_shop") -> list[str]:
    hints: list[str] = []
    n_reg = raw.get("n_regression") or 0
    n_total = raw.get("n_total") or 0
    r2 = raw.get("r_squared")
    ref = raw.get("reference_floor") or "1층"
    reg_ref = raw.get("regression_reference_floor")

    if raw.get("method") == "regression_semilog":
        if n_reg:
            line = f"이번 회귀 표본 n={n_reg}건(층·연면적 유효 거래), 전체 n={n_total}건"
            if r2 is not None:
                line += f", R²={round(float(r2), 3)}"
            hints.append(line + "입니다.")
        if reg_ref and reg_ref != ref:
            hints.append(f"회귀 omitted category는 {reg_ref}(표본 최다)이며, 화면 지수는 {ref}=100% 기준입니다.")
        for cell in raw.get("cells") or []:
            if cell.get("is_reference"):
                hints.append(f"{ref} 지수 100% — 기준 구간(더미 미포함).")
                continue
            idx = cell.get("index")
            if idx is None:
                label = cell.get("label", "")
                cnt = cell.get("count", 0)
                if cnt:
                    hints.append(f"{label}: n={cnt} — 표본 부족 등으로 회귀 지수 미산출.")
                continue
            label = cell.get("label", "")
            diff = round(abs(100 - float(idx)), 1)
            direction = "낮" if float(idx) < 100 else "높"
            hint = (
                f"{label} 지수 {idx}%: {ref} 대비 "
                f"{'면적·연식·용도' if asset_type in ('collective_shop', 'collective_factory') else '전용면적·연식'} 통제 후 "
                f"약 {diff}% {direction}은 수준"
            )
            p = cell.get("p_value")
            if p is not None:
                if p < 0.05:
                    hint += f" (p={p}, 유의)"
                else:
                    hint += f" (p={p}, 유의하지 않음 — 참고용)"
            hints.append(hint + ".")
    else:
        baseline = raw.get("baseline_median")
        scope = _cluster_scope_label(asset_type)
        hints.append(
            f"{scope} ㎡당 단가 중앙값 {baseline} 만원/㎡를 100%로 두고, "
            f"각 구간 평균 대비 비율을 표시합니다 (통제 없음, n={n_total})."
        )
        for cell in raw.get("cells") or []:
            idx = cell.get("index")
            if idx is None:
                continue
            hints.append(f"{cell.get('label')}: 지수 {idx}% (평균 {cell.get('mean_unit_price')} 만원/㎡, n={cell.get('count')}).")

    for w in raw.get("warnings") or []:
        hints.append(f"⚠ {w}")

    return hints


def build_commercial_floor_index_explain(
    *,
    method: str,
    dimension: str,
    asset_type: str,
    raw: dict,
) -> dict[str, Any]:
    controls = raw.get("controls") or []
    controls_h = _controls_human(controls)

    if method == "regression_semilog" and dimension == "floor":
        spec_id = "commercial_floor_index_regression_v1"
        return {
            "spec_id": spec_id,
            "spec_version": "1",
            "title": "회귀 기반 층별 효용지수",
            "summary": (
                "집합상가 도로(cluster) 거래에 반로그 OLS를 적용해, "
                "1층=100% 기준 층 구간별 상대 ㎡당 단가 지수를 산출합니다."
            ),
            "formula": "ln(㎡당단가) = β₀ + ln(연면적) + 연식 + 건축물용도더미 + Σ γ_g·D_g",
            "index_rule": "지수_g = exp(γ_g) × 100  (1층 = 100%, 더미 없음)",
            "reference": raw.get("reference_floor") or "1층",
            "floor_groups": FLOOR_GROUP_LINES,
            "controls": controls_h,
            "interpretation": [
                "지수는 「같은 도로·비슷한 연면적·연식·용도」 조건에서의 층 간 상대 수준입니다.",
                "100%보다 낮을수록 기준층(1층) 대비 ㎡당 단가가 낮은 패턴입니다.",
                "95% CI는 계수 불확실성을 반영한 구간 추정치입니다.",
            ],
            "limitations": [
                "도로 단위 혼합 — 동일 도로 내 건물·max층·입지 차이 잔존",
                "층 정보 결측 거래 제외",
                "구간별 n<5 → 해당 층 더미·지수 미산출",
                "셀 n<15 → 참고용 표시",
                "인과 추론 불가 — 해당 cluster·기간 내 패턴 설명",
            ],
            "interpretation_hints": _floor_index_hints(raw, asset_type=asset_type),
            "presets": _preset_answers_regression_floor(),
        }

    if dimension == "area" and asset_type == "collective_factory":
        spec_id = "commercial_floor_index_factory_area_v1"
        return {
            "spec_id": spec_id,
            "spec_version": "1",
            "title": "면적대별 단순 효용지수 (집합공장)",
            "summary": (
                "연면적을 100/300/1000㎡ 구간으로 묶어, "
                "상품군(cluster) 중앙값 대비 ㎡당 단가 비율(%)을 표시합니다."
            ),
            "formula": "지수 = (면적구간 평균 ㎡당단가 / cluster 중앙값 ㎡당단가) × 100",
            "index_rule": "구간: 100㎡ 미만 · 100~300㎡ · 300~1000㎡ · 1000㎡ 이상",
            "reference": "상품군(cluster) 중앙값",
            "floor_groups": [],
            "controls": [],
            "interpretation": [
                "집합공장 MVP의 핵심 효용지수 — 규모(연면적대)별 단가 수준 비교.",
                "연식·대지면적·용도지역은 반영되지 않습니다.",
            ],
            "limitations": [
                "통제변수 없는 단순 평균 비교",
                "cluster 정의(도로·용도·연식·면적대)에 이미 일부 속성이 고정됨",
                "회귀 탭에서 대지면적·연식 통제 분석 권장",
            ],
            "interpretation_hints": _floor_index_hints(raw, asset_type=asset_type),
            "presets": _preset_answers_factory_area(),
        }

    if dimension == "area":
        spec_id = "commercial_floor_index_simple_area_v1"
        return {
            "spec_id": spec_id,
            "spec_version": "1",
            "title": "면적형별 단순 효용지수",
            "summary": "30㎡ 구간별 평균 ㎡당 단가를 도로 중앙값 대비 비율(%)로 표시합니다.",
            "formula": "지수 = (면적구간 평균 ㎡당단가 / 도로 중앙값 ㎡당단가) × 100",
            "index_rule": "기준 = 도로 전체 ㎡당 단가 중앙값 (100%)",
            "reference": "도로 중앙값",
            "floor_groups": [],
            "controls": [],
            "interpretation": [
                "면적대별 체감 단가 수준의 단순 비교입니다.",
                "연식·층·용도 차이는 반영되지 않습니다.",
            ],
            "limitations": [
                "통제변수 없음",
                "구간 경계(30㎡)에 민감할 수 있음",
                "집합상가 층별 회귀 효용지수와 다른 방법론",
            ],
            "interpretation_hints": _floor_index_hints(raw, asset_type=asset_type),
            "presets": _preset_answers_simple_area(),
        }

    is_factory = asset_type == "collective_factory"
    spec_id = "commercial_floor_index_simple_floor_v1"
    return {
        "spec_id": spec_id,
        "spec_version": "1",
        "title": "층별 단순 효용지수 (참고용)" if is_factory else "층별 단순 효용지수",
        "summary": (
            "층별 평균 ㎡당 단가를 cluster 중앙값 대비 비율(%)로 표시합니다."
            + (" 집합공장은 층 정보 sparse — 면적대 탭을 우선 참고하세요." if is_factory else "")
        ),
        "formula": "지수 = (층별 평균 ㎡당단가 / cluster 중앙값 ㎡당단가) × 100",
        "index_rule": f"기준 = {_cluster_scope_label(asset_type)} ㎡당 단가 중앙값 (100%)",
        "reference": f"{_cluster_scope_label(asset_type)} 중앙값",
        "floor_groups": [],
        "controls": [],
        "interpretation": [
            "단순 평균 비교 — 통제변수 없음",
            *(
                ["집합공장은 1층·단층 위주로 층별 차이가 작을 수 있음"]
                if is_factory
                else []
            ),
        ],
        "limitations": [
            "면적·연식·대지면적·용도 미통제",
            *(
                ["층 결측·sparse — 면적대 탭 권장"]
                if is_factory
                else ["집합상가 층별 탭은 회귀 spec 사용(이 방식 아님)"]
            ),
        ],
        "interpretation_hints": _floor_index_hints(raw, asset_type=asset_type),
        "presets": _preset_answers_simple_floor(),
    }


def _dimension_title(dim: str) -> str:
    return {
        "floor": "층별",
        "dong": "동별",
        "area": "면적형별",
        "rights": "권리별",
    }.get(dim, dim)


def build_residential_floor_index_explain(*, raw: dict, asset_type: str) -> dict[str, Any]:
    dim = raw.get("dimension") or "floor"
    floor_mode = raw.get("floor_mode") or "relative"
    controls = raw.get("controls") or []
    controls_h = _controls_human(controls)
    ref = raw.get("reference_floor") or "1층"
    dim_title = _dimension_title(dim)
    floor_lines = RESIDENTIAL_FLOOR_GROUP_LINES if dim == "floor" else []
    floor_mode_label = {
        "relative": "상대 층 (1·저·중·고·최상)",
        "dummy": "개별 층 더미",
        "grouped": "절대 구간 (1–5 / 6–15 / 16+)",
    }.get(floor_mode, floor_mode)

    return {
        "spec_id": f"residential_floor_index_regression_{dim}_v1",
        "spec_version": "1",
        "title": f"회귀 기반 {dim_title} 효용지수",
        "summary": (
            f"단지(또는 코호트) 거래에 반로그 OLS를 적용해, "
            f"{ref}=100% 기준 {dim_title} 상대 ㎡당 단가 지수를 산출합니다."
            + (f" (층 형식: {floor_mode_label})" if dim == "floor" else "")
        ),
        "formula": (
            "ln(㎡당단가) = β₀"
            + (" + ln(전용면적)" if "ln_exclusive_area" in controls else "")
            + (" + 연식" if "building_age" in controls else "")
            + (" + 거래시점(반기) 더미" if "contract_period" in controls else "")
            + (" + 상대층 더미" if "relative_floor" in controls else "")
            + (" + 단지 FE" if "building_fixed_effects" in controls else "")
            + " + Σ γ_g·D_g"
        ),
        "index_rule": (
            "회귀: 지수_g = exp(γ_g) × 100 (omitted = 거래 최다 층). "
            "화면(층 탭): 1층=100%로 환산"
            if dim == "floor"
            else f"지수_g = exp(γ_g) × 100  ({ref} = 100%, 더미 없음)"
        ),
        "reference": ref,
        "floor_groups": floor_lines,
        "controls": controls_h,
        "interpretation": [
            (
                f"지수는 「{', '.join(controls_h)}」을(를) 통제한 뒤의 {dim_title} 간 상대 수준입니다."
                if controls_h
                else f"지수는 {dim_title} 간 상대 ㎡당 단가 수준입니다."
            ),
            f"100%보다 낮을수록 기준({ref}) 대비 ㎡당 단가가 낮은 패턴입니다.",
            "95% CI는 HC3 강건표준오차 기반 구간 추정치입니다.",
        ],
        "limitations": [
            "단지·기간 내 패턴 설명 — 인과 추론 불가",
            "구간별 n<5 → 해당 더미·지수 미산출",
            "셀 n<15 → 참고용 표시",
            "층·동·면적·권리 결측 거래는 해당 탭에서 제외될 수 있음",
        ],
        "interpretation_hints": _floor_index_hints(raw, asset_type=asset_type),
        "presets": _preset_answers_residential_floor_index(),
    }


def build_residential_regression_explain(
    result: Any,
    req: Any,
    *,
    asset_type: str,
    cohort: bool = False,
) -> dict[str, Any]:
    v = req.variables
    active: list[str] = []
    if v.exclusive_area:
        active.append("전용면적")
    if v.building_age and asset_type != "presale":
        active.append("연식")
    if v.floor:
        active.append(f"층 ({v.floor_mode})")
    if v.dong and asset_type in ("apartment", "rowhouse"):
        active.append("동")
    if v.housing_subtype and asset_type == "presale":
        active.append("권리")

    hints: list[str] = [
        f"종속변수: 금액(만원, 수준). 표본 n={result.n}.",
    ]
    if result.r_squared is not None:
        adj = round(result.adj_r_squared, 3) if result.adj_r_squared else "—"
        hints.append(f"R²={round(result.r_squared, 3)}, Adj.R²={adj}.")
    hints.append(f"독립변수: {', '.join(active) if active else '(없음)'}.")

    sig = [c for c in result.coefficients if c.p is not None and c.p < 0.05 and c.name != "const"]
    if sig:
        top = sig[:5]
        hints.append(
            "유의한 변수(p<0.05): "
            + "; ".join(f"{c.label} (계수 {round(c.coef, 2)})" for c in top)
            + (" …" if len(sig) > 5 else "")
            + "."
        )
    else:
        hints.append("p<0.05 유의 변수가 없거나 표본이 적어 참고용으로 보세요.")

    for w in result.warnings or []:
        hints.append(f"⚠ {w}")

    if cohort:
        hints.append("코호트: 거래 최다 단지=단지 FE 기준, n<5 단지는 FE에서 제외됩니다.")

    floor_lines = RESIDENTIAL_FLOOR_GROUP_LINES if v.floor and v.floor_mode == "relative" else []

    return {
        "spec_id": f"residential_regression_explore_{asset_type}_v1",
        "spec_version": "1",
        "title": "단지 회귀 분석 (탐색용)",
        "summary": (
            "선택한 변수로 거래금액(만원) OLS를 추정합니다. "
            "변수·층 형식을 바꿀 수 있는 탐색용 분석이며, "
            "「층·동·면적 효용지수」 탭의 반로그 지수 spec과는 별도입니다."
        ),
        "formula": "금액(만원) = β₀ + Σ β_k·X_k  (OLS, 수준 모델)",
        "index_rule": None,
        "reference": "범주형 변수는 drop_first 기준 범주 대비",
        "floor_groups": floor_lines,
        "controls": active,
        "interpretation": [
            "연속 변수 계수: 해당 변수 1단위 증가 시 금액(만원) 변화.",
            "더미 계수: 기준 범주 대비 금액 차이(만원).",
            "층 relative/dummy/grouped/linear 모드에 따라 층 해석이 달라집니다.",
            "예측: 적합 모형으로 입력 조건의 금액·95% 예측·평균 신뢰구간을 산출합니다.",
        ],
        "limitations": [
            "사용자 변수 선택에 따라 결과 변경",
            "㎡당 반로그·층 구간 고정 spec ≠ 효용지수 탭",
            "단지(또는 코호트) 내 표본 — 외삽 주의",
            "인과·투자 판단용 아님",
        ],
        "interpretation_hints": hints,
        "presets": _preset_answers_residential_regression(asset_type=asset_type, cohort=cohort),
    }


def build_commercial_regression_explain(
    result: Any,
    req: Any,
    *,
    is_shop: bool,
) -> dict[str, Any]:
    v = req.variables
    active: list[str] = []
    if v.gross_area:
        active.append("연면적")
    if getattr(v, "land_area", False):
        active.append("대지면적")
    if v.building_age:
        active.append("연식")
    if v.floor:
        active.append(f"층 ({v.floor_mode})")
    if v.zone_type:
        active.append("용도지역")
    if v.building_use:
        active.append("건축물용도")
    if v.road_width and is_shop:
        active.append("도로폭 라벨")
    if v.road_code and not is_shop:
        active.append("도로폭(m)")
    if v.addr4:
        active.append("동(addr4)")

    hints: list[str] = [
        f"종속변수: 금액(만원, 수준). 표본 n={result.n}.",
    ]
    if result.r_squared is not None:
        hints.append(f"R²={round(result.r_squared, 3)}, Adj.R²={round(result.adj_r_squared, 3) if result.adj_r_squared else '—'}.")
    hints.append(f"독립변수: {', '.join(active) if active else '(없음)'}.")

    sig = [c for c in result.coefficients if c.p is not None and c.p < 0.05 and c.name != "const"]
    if sig:
        top = sig[:5]
        hints.append(
            "유의한 변수(p<0.05): "
            + "; ".join(f"{c.label} (계수 {round(c.coef, 2)})" for c in top)
            + (" …" if len(sig) > 5 else "")
            + "."
        )
    else:
        hints.append("p<0.05 유의 변수가 없거나 표본이 적어 참고용으로 보세요.")

    for w in result.warnings or []:
        hints.append(f"⚠ {w}")

    return {
        "spec_id": "commercial_regression_explore_v1",
        "spec_version": "1",
        "title": "도로(cluster) 회귀 분석 (탐색용)",
        "summary": (
            "선택한 변수로 금액(만원) OLS를 추정합니다. "
            "변수·층 형식을 바꿀 수 있는 탐색용 분석입니다."
        ),
        "formula": "금액(만원) = β₀ + Σ β_k·X_k  (OLS, 수준 모델)",
        "index_rule": None,
        "reference": "범주형 변수는 drop_first 기준 범주 대비",
        "floor_groups": [],
        "controls": active,
        "interpretation": [
            "연속 변수 계수: 해당 변수 1단위 증가 시 금액(만원) 변화.",
            "더미 계수: 기준 범주 대비 금액 차이(만원).",
            "층 relative/dummy/grouped/linear 모드에 따라 층 해석이 달라집니다.",
        ],
        "limitations": [
            "사용자 변수 선택에 따라 결과 변경",
            "㎡당 반로그·층 구간 고정 spec ≠ 효용지수 탭",
            "도로(cluster) 내 표본 — 외삽 주의",
            "인과·투자 판단용 아님",
        ],
        "interpretation_hints": hints,
        "presets": _preset_answers_commercial_regression(is_shop=is_shop),
    }
