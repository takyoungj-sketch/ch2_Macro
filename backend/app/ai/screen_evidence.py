"""Aggregate screen adapters. Never include raw transaction or scatter-point rows."""
from typing import Any


def rows(value):
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def lists(result, raw):
    result.number("목록 대상 수", raw.get("list_n"), "개")
    result.number("분석기간", raw.get("window_years"), "년")
    for row in rows(raw.get("visible_rows"))[:40]:
        name = str(row.get("name") or "대상")[:100]
        result.identifiers.append(name)
        for key, label, unit in (("count", "거래", "건"), ("mean", "평균 단가", "만원/㎡"),
                                 ("median", "중앙단가", "만원/㎡"), ("households", "세대수", "세대")):
            result.number(f"{name} {label}", row.get(key), unit)
    result.notes.append("목록에서 전달된 집계 행만 제공됩니다. 원시 거래 행은 제공하지 않습니다.")


def profile(result, raw):
    result.number("인구", raw.get("population"), "명")
    result.number("3년 거래금액 합계", raw.get("total_amount_3y"), "만원")
    result.notes.append("프로필은 완료된 달력 연도 3년 기준입니다. 거래액 합계는 유형별 정제 기준을 거친 유효 거래의 합이며 지역 전체 자산가치가 아닙니다. 복합의 유효 지분거래는 금액 합계에 포함될 수 있습니다.")
    mix = raw.get("yearly_mix") or {}
    if isinstance(mix, dict):
        result.context["집계연도"] = mix.get("years")
        for kind, cell in (mix.get("totals_by_type") or {}).items():
            if isinstance(cell, dict):
                result.number(f"{kind} 3년 거래", cell.get("count"), "건")
                result.number(f"{kind} 3년 거래금액", cell.get("amount"), "만원")
        for key, label in (("count_share_by_type", "건수 비중"), ("amount_share_by_type", "금액 비중")):
            for kind, value in (mix.get(key) or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    result.number(f"{kind} {label}", value * 100, "%")
    features = raw.get("features") or {}
    if isinstance(features, dict):
        for key, label in (("apartment_count", "아파트 거래"), ("apartment_p25", "아파트 P25"),
                           ("apartment_median", "아파트 중앙단가"), ("apartment_p75", "아파트 P75")):
            result.number(label, features.get(key), "건" if key.endswith("count") else "만원/㎡")
        for i in range(1, 4):
            item = features.get(f"land_top{i}")
            if not isinstance(item, dict):
                item = {"zone": features.get(f"land_top{i}_zone"), "jimok": features.get(f"land_top{i}_jimok"),
                        "count": features.get(f"land_top{i}_count"), "mean_manwon_per_sqm": features.get(f"land_top{i}_mean_manwon_per_sqm")}
            name = f"토지 {item.get('zone') or ''} {item.get('jimok') or ''}".strip()
            result.number(f"{name} 거래", item.get("count"), "건")
            result.number(f"{name} 평균 단가", item.get("mean_manwon_per_sqm"), "만원/㎡")
    rank = raw.get("national_rank")
    if isinstance(rank, list) and len(rank) >= 8:
        for index, label in ((5, "전국 거래금액 순위"), (6, "전국 거래건수 순위"), (7, "전국 인구당 거래액 순위")):
            result.number(label, rank[index], "위")
    for twin in rows(raw.get("twins"))[:5]:
        name = " ".join(str(twin.get(k) or "") for k in ("twin_sido_name", "twin_sigungu_name", "twin_eupmyeondong_name", "twin_beopjungri_name")).strip()
        score = twin.get("similarity_score")
        if isinstance(score, (int, float)):
            result.number(f"{name} 유사도", score * 100, "%")


SANGKWON_KINDS = {"office": "오피스", "mid_retail": "중대형상가", "small_retail": "소규모상가", "strata": "집합상가", "retail_all": "상가 전체"}
SANGKWON_METRICS = {
    "building_count": ("표본 수", "개"), "avg_floors": ("평균 층수", "층"), "avg_area": ("평균 면적", "㎡"),
    "rent": ("임대료", "만원/㎡·년"), "rent_index": ("임대가격지수", ""), "noi_per_m2": ("순영업소득", "만원/㎡·년"),
    "rent_income_share": ("임대수입 구성비", "%"), "other_income_share": ("기타수입 구성비", "%"),
    "opex_share": ("운영경비 구성비", "%"), "noi_pct": ("순영업소득 구성비", "%"), "vacancy": ("공실률", "%"),
    "income_yield": ("소득수익률", "%"), "capital_yield": ("자본수익률", "%"), "investment_yield": ("투자수익률", "%"), "conversion": ("전환율", "%"),
}


def sangkwon(result, raw):
    result.notes.append("상권 통계는 한국부동산원 공표입니다. 임대료·순영업소득은 연간 면적당 금액, 수익률과 구성비는 서로 다른 비율입니다. 주거 거래자료와 섞지 않습니다.")
    result.context["기준기간"] = raw.get("window_label") or raw.get("year")
    annual = raw.get("annual")
    if not isinstance(annual, dict):
        return
    for metric, values in annual.items():
        if not isinstance(values, dict) or metric not in SANGKWON_METRICS:
            continue
        label, unit = SANGKWON_METRICS[metric]
        for kind, name in SANGKWON_KINDS.items():
            result.number(f"{name} {label}", values.get(kind), unit)


def rent_detail(result, raw):
    result.context.update({"화면": raw.get("detail_tab"), "건물": raw.get("display_name"), "기준기간": raw.get("period")})
    result.number("건물 전환율", raw.get("building_rate"), "%")
    result.number("지역 적용 전환율", raw.get("region_rate"), "%")
    result.number("선택 건물 평균 전환율", raw.get("pool_rate"), "%")
    result.notes.append("건물 전환율, 지역 적용 전환율, 선택 건물 평균은 다른 값입니다. 목록 환산에는 지역 적용 전환율을 사용합니다.")
    for name, metric in (raw.get("lease_metrics") or {}).items():
        if isinstance(metric, dict):
            result.number(f"{name} 거래", metric.get("n"), "건")
            unit = "만원/㎡·월" if "월세" in name else "만원/㎡"
            result.number(f"{name} 평균", metric.get("mean"), unit)
            result.number(f"{name} 중앙값", metric.get("median"), unit)
    if raw.get("detail_tab") == "rolling":
        for row in rows(raw.get("rolling_points")):
            label = str(row.get("label") or "구간")
            result.number(f"{label} {raw.get('rolling_metric')} 중앙값", row.get("median"), raw.get("rolling_unit") or "만원/㎡")
            result.number(f"{label} 거래", row.get("count"), "건")
    if raw.get("detail_tab") == "transactions":
        result.number("전체기간 조회 거래", raw.get("transaction_count"), "건")
        result.number("화면에 불러온 거래", raw.get("transaction_loaded"), "건")
        result.notes.append("거래목록은 보유한 전체기간 조회입니다. 목록의 선택기간과 다를 수 있습니다. 개별 거래 행은 제공하지 않습니다.")


def insight(result, ctx):
    raw = ctx.facts
    if ctx.explain:
        result.context["보고서 제목"] = ctx.explain.title
        result.text("보고서 소개", ctx.explain.summary)
        for note in ctx.explain.limitations[:12]:
            result.text("보고서 한계", note)
    report = raw.get("report")
    if isinstance(report, dict):
        result.context["보고서 제목"] = report.get("title") or result.context.get("보고서 제목")
        sections = rows(report.get("sections"))
        truncated = report.get("truncated") or len(sections) > 120 or any(len(str(s.get("text") or "")) > 1800 for s in sections)
        result.context["보고서 전달 범위"] = "일부 생략" if truncated else "현재 본문"
        for section in sections[:120]:
            result.text(str(section.get("heading") or "보고서 본문"), str(section.get("text") or ""))
    result.context["기준월"] = raw.get("as_of") or raw.get("as_of_month")
    result.number("분석 표본", raw.get("n"), "개")
    # Structured aggregates only. Raw scatter points / transaction rows never go
    # to the model. Report prose contains the actual displayed interpretations.
    def visit(value: Any, path: str, depth: int = 0):
        if depth > 7 or len(result.facts) >= 400:
            return
        if isinstance(value, dict):
            label = " × ".join(str(value[k]) for k in ("a", "b") if isinstance(value.get(k), str))
            path = f"{path} {label}".strip()
            for key, item in value.items():
                if key in {"points", "transactions", "items", "rows", "report", "a", "b"}:
                    continue
                visit(item, f"{path} {key}", depth + 1)
        elif isinstance(value, list):
            for item in value[:60]:
                visit(item, path, depth + 1)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            result.number(path.strip(), value)
    for key in ("pairs", "price_pairs", "summary", "results", "metrics", "analysis"):
        if key in raw:
            visit(raw[key], key)
