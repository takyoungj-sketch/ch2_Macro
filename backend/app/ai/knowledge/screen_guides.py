"""기본통계·목록·매트릭스 화면 안내. 숫자 Bundle이 없어도 회피하지 않는다."""

from __future__ import annotations

from typing import Any

from app.ai.schemas import AiContext

# 회귀·추세 Bundle이 아직 없는 「기본 화면」. 여기에서는 표·매트릭스 읽기를 안내한다.
OVERVIEW_PANELS = frozenset(
    {
        "BuildingList",
        "CommercialList",
        "CollectiveLanding",
        "PaidMatrixCell",
        "MatrixCard",
        "RentListCard",
        "RegionalProfile",
        "TwinRegionPanel",
        "ProfilePanel",
    }
)

_ORIENTATION_MARKERS = (
    "이 화면",
    "기본통계",
    "기본 통계",
    "분석 결과를 설명",
    "결과를 설명",
    "결과에 대해 설명",
    "결과가 궁금",
    "지금 결과가",
    "이 표",
    "이 목록",
    "무엇을 보여",
    "화면 설명",
    "열은 무엇",
    "칼럼",
    "컬럼",
)


def is_screen_orientation_question(message: str) -> bool:
    """「이 화면/기본통계를 설명해 달라」— 계수 해석·경로 추천과 구분."""
    m = (message or "").strip()
    if not m:
        return False
    if any(
        k in m
        for k in (
            "적정가",
            "투자",
            "매수",
            "저평가",
            "앞으로 오를",
        )
    ):
        return False
    return any(k in m for k in _ORIENTATION_MARKERS)


def _fmt_num(v: Any, digits: int = 0) -> str:
    if v is None or v == "":
        return "—"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    if digits == 0:
        return f"{n:,.0f}"
    return f"{n:,.{digits}f}"


def _as_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mean_median_comment(
    mean: Any,
    median: Any,
    *,
    std: Any = None,
    price_digits: int = 1,
) -> str:
    """CH2가 준 평균·중위만으로 치우침을 읽는다. 재집계하지 않는다."""
    m = _as_float(mean)
    md = _as_float(median)
    if m is None or md is None or md == 0:
        return ""
    rel = (m - md) / abs(md)
    if abs(rel) < 0.02:
        core = "평균과 중위가 거의 같아, 한두 건이 평균을 크게 당긴 흔적은 작아 보입니다."
    else:
        direction = "높아" if rel > 0 else "낮아"
        if abs(rel) < 0.12:
            size = "그 크기는 크지 않아 보입니다."
        elif abs(rel) < 0.25:
            size = "중위가 더 안정적인 대표값입니다."
        else:
            size = "평균은 이상치에 꽤 흔들렸을 수 있으니 중위를 함께 보세요."
        core = (
            f"평균이 중위보다 {direction} 평균이 이상치에 영향을 받았을 수 있으나, {size}"
        )
    std_n = _as_float(std)
    if std_n is None or m == 0:
        return core
    cv = std_n / abs(m)
    if cv < 0.3:
        spread = "같은 표본 안 단가의 흩어짐은 상대적으로 크지 않습니다."
    elif cv < 0.6:
        spread = "같은 표본 안에서도 단가가 꽤 퍼져 있습니다."
    else:
        spread = "같은 표본 안에서 단가 편차가 큽니다."
    return f"{core} 표준편차 **{_fmt_num(std_n, price_digits)}**만원/㎡로, {spread}"


def _cite_first_row(facts: dict[str, Any], grain: str) -> str:
    row = facts.get("first_row")
    if not isinstance(row, dict) or not row:
        return ""
    name = str(row.get("name") or row.get("display_name") or row.get("label") or "").strip()
    if not name:
        return ""
    sort = str(facts.get("list_sort") or "count")
    if sort == "count":
        lead = (
            f"지금 표는 거래수 순이라 **첫 행**이 거래가 가장 많은 {grain}입니다. "
            f"**{name}** 기준으로 보면"
        )
    else:
        lead = f"지금 표의 **첫 행**을 예시로 읽으면, {grain} **{name}**입니다."
    bits: list[str] = []
    if row.get("asset_label"):
        bits.append(f"유형 {row['asset_label']}")
    if row.get("count") is not None:
        bits.append(f"거래 **{_fmt_num(row.get('count'))}**건")
    if row.get("mean") is not None:
        bits.append(f"평균 **{_fmt_num(row.get('mean'))}**만원/㎡")
    if row.get("median") is not None:
        bits.append(f"중위 **{_fmt_num(row.get('median'))}**만원/㎡")
    ci_lo, ci_hi = row.get("ci_lower"), row.get("ci_upper")
    if ci_lo is not None and ci_hi is not None:
        bits.append(
            f"평균 95% 신뢰구간 **{_fmt_num(ci_lo)}~{_fmt_num(ci_hi)}**만원/㎡"
        )
    if row.get("building_year"):
        bits.append(f"신축연도 {row['building_year']}")
    extra = row.get("extra")
    if extra:
        bits.append(str(extra))
    paras = [lead + (": " + ", ".join(bits) + "." if bits else ".")]
    comment = _mean_median_comment(
        row.get("mean"), row.get("median"), std=row.get("std"), price_digits=0
    )
    if comment:
        paras.append(comment)
    if row.get("is_reliable") is False:
        paras.append("이 행은 n<15라 중앙·평균이 한두 건에 흔들릴 수 있습니다.")
    return "\n".join(paras)


def _cite_top_cell(facts: dict[str, Any], mode_label: str) -> str:
    cell = facts.get("top_cell")
    if not isinstance(cell, dict) or not cell:
        return ""
    stats = cell["stats"] if isinstance(cell.get("stats"), dict) else cell
    zone = str(cell.get("zone_type") or "").strip()
    cat = str(cell.get("land_category") or "").strip()
    if not zone or not cat:
        return ""
    count = stats.get("count")
    if count is None:
        return ""
    is_top_left = cell.get("is_top_left", True)
    if is_top_left:
        lead = (
            f"행·열은 거래수가 많은 용도지역·{mode_label}부터 놓이므로, "
            f"왼쪽 위 **(1,1)칸**이 이 지역에서 거래가 가장 많은 교차 표본입니다. "
            f"지금 (1,1)은 **{zone} × {cat}**입니다."
        )
    else:
        lead = (
            f"거래수가 가장 많은 칸은 **{zone} × {cat}**입니다."
        )
    bits = [f"거래 **{_fmt_num(count)}**건"]
    if stats.get("mean") is not None:
        bits.append(f"평균 **{_fmt_num(stats.get('mean'), 1)}**만원/㎡")
    if stats.get("median") is not None:
        bits.append(f"중위 **{_fmt_num(stats.get('median'), 1)}**만원/㎡")
    if stats.get("std") is not None:
        bits.append(f"표준편차 **{_fmt_num(stats.get('std'), 1)}**만원/㎡")
    if stats.get("min") is not None:
        bits.append(f"최소 **{_fmt_num(stats.get('min'), 1)}**")
    if stats.get("max") is not None:
        bits.append(f"최대 **{_fmt_num(stats.get('max'), 1)}**")
    ci_lo, ci_hi = stats.get("ci_lower"), stats.get("ci_upper")
    if ci_lo is not None and ci_hi is not None:
        bits.append(
            f"평균 95% 신뢰구간 **{_fmt_num(ci_lo, 1)}~{_fmt_num(ci_hi, 1)}**만원/㎡"
        )
    paras = [lead + " " + ", ".join(bits) + "."]
    comment = _mean_median_comment(
        stats.get("mean"),
        stats.get("median"),
        std=None,
        price_digits=1,
    )
    if comment:
        paras.append(comment)
    std_n = _as_float(stats.get("std"))
    mean_n = _as_float(stats.get("mean"))
    if std_n is not None and mean_n not in (None, 0):
        cv = std_n / abs(mean_n)
        if cv < 0.3:
            spread = "같은 칸 안 단가의 흩어짐은 상대적으로 크지 않습니다."
        elif cv < 0.6:
            spread = "같은 칸 안에서도 단가가 꽤 퍼져 있습니다."
        else:
            spread = "같은 칸 안에서 단가 편차가 큽니다."
        paras.append(f"표준편차가 평균 대비 {'작아' if cv < 0.3 else '커서'}, {spread}")
    if stats.get("is_reliable") is False:
        paras.append("이 칸은 n<15라 한두 건에 흔들릴 수 있습니다.")
    return "\n".join(paras)


def _scope_line(context: AiContext) -> str:
    facts = context.facts or {}
    label = context.scope.region_label or facts.get("region_label") or facts.get("scope_label")
    window = facts.get("window_years") or (context.scope.filters or {}).get("window_years")
    list_n = facts.get("list_n")
    tx = facts.get("tx_count")
    parts: list[str] = []
    if label:
        parts.append(f"선택 지역: **{label}**")
    if window:
        parts.append(f"롤링 창 **{window}년**")
    if list_n is not None:
        parts.append(f"목록 { _fmt_num(list_n) }개")
    if tx is not None:
        parts.append(f"거래 { _fmt_num(tx) }건")
    if not parts:
        return ""
    return " · ".join(parts)


def _collective_residential(context: AiContext) -> str:
    facts = context.facts or {}
    scope = _scope_line(context)
    first = _cite_first_row(facts, "단지")
    lines = [
        "### 이 화면은",
        "국토부 **집합 주거 실거래**를 단지(`building_key`)로 묶어, 선택한 유형·지역·롤링 창(3·5·7년)의 **단지별 거래 요약**을 보여 줍니다. "
        "회귀 화면이 아니라 기본통계 표입니다.",
    ]
    if scope:
        lines.extend(["", scope])
    lines.extend(
        [
            "",
            "### 데이터가 어떻게 만들어지나",
            "국토부 실거래 공개분 → 정제·단지 키 매칭 → 창 안의 거래를 단지별로 집계합니다. "
            "해제·중복·단가 미산출 행은 빠질 수 있어 원본 건수와 다를 수 있습니다.",
            "",
            "### 표 열을 어떻게 읽나",
            "- **유형**: 아파트·연립·오피스텔·분양권. 여러 유형을 같이 고르면 한 표에 섞입니다.",
            "- **건물명**: 단지 표시명. 행을 클릭하면 모달이 열립니다.",
            "- **거래수**: 지금 창에서 그 단지의 매매 건수.",
            "- **중앙(만원/㎡)**: 창 안 거래의 ㎡당 단가 중앙값. 평균보다 이상치에 덜 흔들립니다.",
            "- **평균(만원/㎡)**: 같은 표본의 산술평균.",
            "- **신뢰구간**(넓은 표): 평균의 95% 구간. n이 작으면 넓어집니다.",
            "- **신축연도**: 실거래에 적힌 건축연도.",
            "- **세대수**: K-apt 단지 전체(없으면 표제부). **이 유형 재고가 아닙니다.**",
            "- **시공사·지번**: 단지 식별용. 공동시공은 「첫 회사+외」.",
        ]
    )
    if first:
        lines.extend(["", "### 예시 — 첫 행", first])
    lines.extend(
        [
            "",
            "### 다음으로 할 수 있는 것",
            "- **행을 클릭**하면 모달에서 과거 추세·장기추세선·단지 회귀·층 지수를 볼 수 있습니다.",
            "- **지역회귀**(아파트·통계분석 이후): 단지가 아니라 **이 지역 아파트 단지 전체**로 규모·연식 효과를 봅니다.",
            "- 여러 단지를 코호트로 묶고 유형을 2개 이상 넣으면, 면적·연식을 통제한 **아파트 vs 오피스텔** 격차를 볼 수 있습니다.",
            "",
            "### 한계",
            "표의 중앙·평균은 비교용 시장통계이며 시세·적정가가 아닙니다. "
            "거래가 적은 단지는 한두 건에 흔들립니다. n<15 표시가 있으면 특히 조심해서 읽으세요.",
        ]
    )
    return "\n".join(lines)


def _collective_commercial(context: AiContext) -> str:
    facts = context.facts or {}
    scope = _scope_line(context)
    first = _cite_first_row(facts, "도로 cluster")
    lines = [
        "### 이 화면은",
        "국토부 **집합상가·집합공장** 실거래를 **도로명 cluster**로 묶어 보여 줍니다. "
        "주거 단지 표와 같은 UX이지만 분석 단위가 건물·K-apt가 아닙니다.",
    ]
    if scope:
        lines.extend(["", scope])
    lines.extend(
        [
            "",
            "### 데이터가 어떻게 만들어지나",
            "국토부 집합 상업·공장 거래 → 도로명으로 cluster를 만들고 창 안 거래를 집계합니다.",
            "",
            "### 표 열을 어떻게 읽나",
            "- **유형**: 집합상가 또는 집합공장.",
            "- **도로명**: cluster 표시명. 행을 클릭하면 모달이 열립니다.",
            "- **거래수·중앙·평균(만원/㎡)**: 창 안 그 도로의 거래 요약. 주거 표와 같은 읽기입니다.",
            "- **구·동**: cluster가 걸친 행정 위치.",
            "- **n<15**: 표본이 얇아 중앙·평균이 불안정할 수 있습니다.",
        ]
    )
    if first:
        lines.extend(["", "### 예시 — 첫 행", first])
    lines.extend(
        [
            "",
            "### 다음으로 할 수 있는 것",
            "- **행을 클릭**하면 모달에서 추세·회귀·층·면적 지수를 볼 수 있습니다.",
            "- 비교할 도로를 코호트에 더하면 같은 화면 패턴으로 묶어서 봅니다.",
            "",
            "### 한계",
            "도로 cluster ≠ 개별 호실 시세. 주거 단지 플레이북(아파트 vs 오피스텔)을 여기에 그대로 쓰지 않습니다.",
        ]
    )
    return "\n".join(lines)


def _collective_landing(_context: AiContext) -> str:
    return "\n".join(
        [
            "### 이 화면은",
            "집합부동산의 **갈래 선택**입니다. 주거(단지)와 상업·업무(도로 cluster)는 통계 단위가 다릅니다.",
            "",
            "### 다음으로",
            "- **주거형 통계**: 아파트·연립·오피스텔·분양권. 행정구역 → 「통계분석」 → 단지 목록.",
            "- **상업·업무 통계**: 집합상가·집합공장. 같은 흐름이지만 목록의 한 행은 도로입니다.",
            "",
            "평균 매매 흐름만 보려면 목록에서 대상을 클릭해 추세 탭을 열면 됩니다. "
            "면적·연식을 통제해 유형 격차를 보려면 그다음 회귀·코호트입니다.",
        ]
    )


def _land_matrix(context: AiContext) -> str:
    facts = context.facts or {}
    scope = _scope_line(context)
    mode = facts.get("matrix_mode")
    mode_label = "지목군" if mode == "group" else "지목"
    lines = [
        "### 이 화면은",
        "국토부 **토지 실거래**를 용도지역 × "
        f"**{mode_label}** 칸으로 집계한 기본통계입니다. 개별 건물 OLS가 아닙니다.",
    ]
    if scope:
        lines.extend(["", scope])
    lines.extend(
        [
            "",
            "### 데이터가 어떻게 만들어지나",
            "국토부 토지 실거래 CSV → `land_transactions` 정제(유효·해제 제외·중복 정리) → "
            "V2 스냅샷(as_of_month) + 롤링 3·5·7년 창으로 매트릭스·연도 표를 만듭니다. "
            "기본통계 단계에서는 도로·면적·지분·IQR 필터를 아직 적용하지 않습니다.",
            "",
            "### 숫자를 어떻게 읽나",
            "- **행**: 용도지역. **열**: "
            + mode_label
            + ".",
            "- 각 칸: 그 교차 표본의 **거래수**와 **평균 단가(만원/㎡)**. 칸 안 5행은 최소·평균·중위·분위·신뢰구간입니다.",
            "- 행·열 머리의 건수·평균은 그 용도 또는 "
            + mode_label
            + " 전체 한계입니다.",
            "- n≥15 칸은 상대적으로 읽기 쉽고, n<5는 흐리게 두어 한두 건에 흔들릴 수 있음을 표시합니다.",
            "- 상단 **연도별 표**는 같은 창·같은 표본을 달력 연도로 잘라 본 것입니다.",
        ]
    )
    example = _cite_top_cell(facts, mode_label)
    if example:
        lines.extend(["", "### 예시 — (1,1)칸", example])
    lines.extend(
        [
            "",
            "### 다음으로 할 수 있는 것",
            "- **칸을 클릭**하면 그 용도×"
            + mode_label
            + "의 **연도별·장기추세** 모달이 열립니다.",
            "- **필터 분석 실행**은 연도 칩·도로·면적·지분·이상치를 적용한 live 집계입니다. 기본통계와 표본이 달라집니다.",
            "- 유료 칸에서는 필지 회귀·예측도 이어서 볼 수 있습니다.",
            "",
            "### 한계",
            "거래액 합이나 건수 합이 가격지수가 아닙니다. "
            "여러 칸을 한 OLS에 억지로 넣지 않습니다. 시군구에 M2·금리를 붙이지 않습니다.",
        ]
    )
    return "\n".join(lines)


def _built_basic(context: AiContext) -> str:
    scope = _scope_line(context)
    lines = [
        "### 이 화면은",
        "복합(단독·일반상가·일반공장) **개별 건물 거래**의 기본통계입니다. "
        "유형과 지역을 고른 뒤 **「통계분석」**을 누르면 거래 요약과 회귀 카드가 나옵니다.",
    ]
    if scope:
        lines.extend(["", scope])
    lines.extend(
        [
            "",
            "### 데이터가 어떻게 만들어지나",
            "국토부 상업업무·공장창고·단독다가구 CSV 중 유형=일반(단독은 전량). "
            "집합상가·집합공장은 이 앱에 없습니다.",
            "",
            "### 결과를 어떻게 읽나",
            "통계분석을 실행하면 표본 n, 회귀 계수, Adj R²·MAPE, 산점도가 카드로 붙습니다. "
            "유형을 2개 이상 고르면 통합회귀가 되고 **유형 더미**가 기준 유형 대비 가격수준입니다.",
            "",
            "### 다음으로 할 수 있는 것",
            "- 아직 실행 전이면 지역·유형을 확인하고 「통계분석」을 누르세요.",
            "- 읍면동 표본이 얇으면 **상위지역 분석**에서 같은 식을 시군구에 반복합니다.",
            "- Macro 탐색에서 Local vs Twin을 볼 수 있습니다. 적정가·채택 강제가 아닙니다.",
            "",
            "### 한계",
            "계수는 조건부 연관입니다. 예측값 ≠ 감정·투자 판단.",
        ]
    )
    return "\n".join(lines)


def _rent_list(context: AiContext) -> str:
    facts = context.facts or {}
    scope = _scope_line(context)
    r_sel = facts.get("r_selected")
    lines = [
        "### 이 화면은",
        "주거 **전월세 건물 목록**입니다. 전환율은 CH2 분석용 **단순평균**이며 한국부동산원 공표 전월세전환율이 아닙니다.",
    ]
    if scope:
        lines.extend(["", scope])
    if r_sel is not None:
        lines.append(f"지금 적용 전환율(선택 창)은 **{_fmt_num(float(r_sel) * 100 if float(r_sel) < 1 else r_sel, 2)}%** 근처로 표시됩니다.")
    lines.extend(
        [
            "",
            "### 표 열을 어떻게 읽나",
            "- **전세보증금·월세·매매가**: 창 안 ㎡당 평균(만원/㎡).",
            "- **전세가율**: 전세 / 매매.",
            "- **전세환산값**(넓은 표): 반전세를 적용 전환율로 전세처럼 환산한 비교값. 시세가 아닙니다.",
            "- 행을 클릭하면 건물 모달에서 흐름을 봅니다.",
            "",
            "### 다음으로",
            "상업 임대료·공실은 이 표가 아니라 **상권분석** 모달(부동산원 상권 공표)입니다. 주거 원장과 한 표에 섞지 않습니다.",
            "",
            "### 한계",
            "환산 P50 ≠ 적정 전세. 읍면동 게이트 미달이면 시군구 전환율로 대체합니다.",
        ]
    )
    return "\n".join(lines)


def _profile(context: AiContext) -> str:
    scope = _scope_line(context)
    lines = [
        "### 이 화면은",
        "한 지역의 **거래 구성·Twin 유사지역·전국 순위**입니다. 단지·건물 회귀 결과가 아닙니다.",
    ]
    if scope:
        lines.extend(["", scope])
    lines.extend(
        [
            "",
            "### 어떻게 읽나",
            "구성은 최근 3년 창의 유형 믹스입니다. Twin은 구조가 닮은 지역 목록이지 투자 추천이 아닙니다.",
            "",
            "### 다음으로",
            "단지별 추세·회귀는 **집합** 앱에서 행정구역 → 통계분석 → 단지 클릭 순입니다. "
            "개별 건물 회귀는 **복합** 앱입니다.",
        ]
    )
    return "\n".join(lines)


def _insight(context: AiContext) -> str:
    facts = context.facts or {}
    as_of = facts.get("as_of")
    start = facts.get("period_start")
    end = facts.get("period_end")
    lines = [
        "### 이 화면은",
        "Macro Insight 1번입니다. 금리와 유동성(M2)의 변화가 전국 부동산 거래와 어떤 관계를 보이는지 월별 자료로 살펴봅니다.",
        "통계 기초만 있는 사람에게 쉬운 말로 설명합니다.",
    ]
    if start and end:
        lines.append(f"기간은 {start}부터 {end}까지, 전국 달력 월입니다.")
    if as_of:
        lines.append(f"자료 기준일은 {as_of}입니다.")
    lines.extend(
        [
            "",
            "### 어떻게 읽나",
            "- 앞의 네 그래프는 시장의 흐름입니다. 여기서 관계를 해석하지 않습니다.",
            "- 관계는 전년동월 변화와 아래 상관계수 표로 봅니다.",
            "- 전체 거래(합계)는 유형별 규모가 달라 개별 유형을 그대로 대표하지 않습니다.",
            "- 표에 없는 숫자를 만들지 않습니다.",
            "",
            "### 한계",
            "상관계수는 함께 나타난 정도입니다. 인과나 미래 예측이 아닙니다. 자세한 내용은 화면의 「이 분석의 한계」를 따릅니다.",
        ]
    )
    return "\n".join(lines)


def _fallback(context: AiContext) -> str:
    scope = _scope_line(context)
    lines = [
        "### 이 화면은",
        "CH2 Macro의 시장통계 화면입니다. 숫자는 CH2가 계산하고, 여기서는 그 화면을 어떻게 읽는지만 안내합니다.",
    ]
    if scope:
        lines.extend(["", scope])
    lines.extend(
        [
            "",
            "지역을 고른 뒤 「통계분석」을 실행하면 표·매트릭스·회귀 카드가 채워집니다. "
            "목록이나 칸을 클릭하면 추세·회귀 등 추가 분석을 열 수 있습니다.",
            "",
            "감정평가·적정가·투자 추천은 하지 않습니다.",
        ]
    )
    return "\n".join(lines)


def format_screen_guide(context: AiContext) -> str:
    """LLM 없이 기본 화면을 설명하고 다음 분석을 유도한다."""
    app = context.app
    panel = context.panel or ""
    if panel == "CollectiveLanding":
        return _collective_landing(context)
    if panel == "BuildingList":
        return _collective_residential(context)
    if panel == "CommercialList":
        return _collective_commercial(context)
    if panel in ("PaidMatrixCell", "MatrixCard") or app == "land":
        return _land_matrix(context)
    if panel == "RentListCard" or app == "rent":
        return _rent_list(context)
    if panel in ("RegionalProfile", "TwinRegionPanel", "ProfilePanel") or app == "profile":
        return _profile(context)
    if panel in ("Insight01", "InsightHome") or app == "insight":
        return _insight(context)
    if app == "built":
        return _built_basic(context)
    if app == "collective":
        return _collective_residential(context)
    return _fallback(context)


def screen_guide_followups(context: AiContext) -> list[str]:
    panel = context.panel or ""
    app = context.app
    if panel == "BuildingList" or (app == "collective" and panel == "CollectiveLanding"):
        if panel == "CollectiveLanding":
            return [
                "주거와 상업·업무는 무엇이 다른가요?",
                "통계분석은 어디서 하나요?",
            ]
        return [
            "단지를 클릭하면 무엇이 나오나요?",
            "지역회귀는 언제 쓰나요?",
            "세대수는 어떻게 읽나요?",
            "유형 격차를 보려면 어떻게 하나요?",
        ]
    if panel == "CommercialList":
        return [
            "도로를 클릭하면 무엇이 나오나요?",
            "n이 작으면 어떻게 읽나요?",
            "주거 단지 표와 무엇이 다른가요?",
        ]
    if app == "land" or panel in ("PaidMatrixCell", "MatrixCard"):
        return [
            "칸을 클릭하면 무엇이 나오나요?",
            "필터 분석과 무엇이 다른가요?",
            "n이 작은 칸은 어떻게 읽나요?",
        ]
    if app == "rent":
        return [
            "전환율은 왜 단순평균인가요?",
            "전세환산값은 시세인가요?",
            "상권분석과 무엇이 다른가요?",
        ]
    if app == "profile":
        return [
            "Twin 유사지역은 무엇을 뜻하나요?",
            "단지 추세는 어디서 보나요?",
        ]
    if app == "insight" or panel in ("Insight01", "InsightHome"):
        return [
            "상관계수가 뭔가요?",
            "왜 금액 그래프만 보면 안 되나요?",
            "합계는 모든 부동산인가요?",
            "금리가 거래를 줄인 건가요?",
        ]
    if app == "built":
        return [
            "통계분석을 누르면 무엇이 나오나요?",
            "유형 더미는 어떻게 읽나요?",
            "상위지역 분석은 언제 쓰나요?",
        ]
    return [
        "이 표의 열은 무엇을 뜻하나요?",
        "다음으로 어떤 분석을 할 수 있나요?",
    ]


def should_use_screen_guide(context: AiContext, has_engine_narrative: bool) -> bool:
    """엔진 숫자 해석이 있으면 그걸 쓰고, 기본 화면이면 안내를 쓴다."""
    panel = context.panel or ""
    if panel in OVERVIEW_PANELS:
        return True
    if has_engine_narrative:
        return False
    return True
