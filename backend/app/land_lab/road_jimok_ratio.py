"""도로 지목 상대가격 — 읍면동×용도 칸의 중앙단가 비.

1차는 관찰이다. 면적·도로조건·창 안 연도는 통제하지 않는다.
회귀와 연도별 r은 여기 없다. 제품 토지 식도 바꾸지 않는다.

지목·용도 코드는 pipeline/constants.py 축약과 같다.
대는 개발 지목군, 도로는 인프라 지목군에 들어 있으므로 지목군으로 대체하지 않는다.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

ROAD = "도"
BASES = ("대", "전", "답")
JIMOKS = (ROAD, *BASES)
PRIMARY_MIN_N = 10
SENSITIVITY_MIN_N = (5, 10, 20)
THIRD_TICK = 1.0 / 3.0

# 도시: 주거·상업·공업·녹지. 비도시: 관리·농림·보전. 개발제한구역은 둘 다 아님.
URBAN_ZONES = frozenset(
    {
        "1전",
        "2전",
        "1주",
        "2주",
        "3주",
        "준주",
        "근상",
        "유상",
        "일상",
        "중상",
        "전공",
        "일공",
        "준공",
        "자녹",
        "생녹",
        "보녹",
    }
)
NONURBAN_ZONES = frozenset({"계관", "보관", "생관", "농림", "자보"})
GREENBELT_ZONES = frozenset({"개제"})

ZONE_ALIAS = {
    "제1종전용주거지역": "1전",
    "제2종전용주거지역": "2전",
    "제1종일반주거지역": "1주",
    "제2종일반주거지역": "2주",
    "제3종일반주거지역": "3주",
    "준주거지역": "준주",
    "근린상업지역": "근상",
    "유통상업지역": "유상",
    "일반상업지역": "일상",
    "중심상업지역": "중상",
    "전용공업지역": "전공",
    "일반공업지역": "일공",
    "준공업지역": "준공",
    "자연녹지지역": "자녹",
    "생산녹지지역": "생녹",
    "보전녹지지역": "보녹",
    "계획관리지역": "계관",
    "보전관리지역": "보관",
    "생산관리지역": "생관",
    "개발제한구역": "개제",
    "농림지역": "농림",
    "자연환경보전지역": "자보",
    "도로": ROAD,
}

ZONE_LABEL = {
    "1전": "1종전용주거",
    "2전": "2종전용주거",
    "1주": "1종일반주거",
    "2주": "2종일반주거",
    "3주": "3종일반주거",
    "준주": "준주거",
    "근상": "근린상업",
    "유상": "유통상업",
    "일상": "일반상업",
    "중상": "중심상업",
    "전공": "전용공업",
    "일공": "일반공업",
    "준공": "준공업",
    "자녹": "자연녹지",
    "생녹": "생산녹지",
    "보녹": "보전녹지",
    "계관": "계획관리",
    "보관": "보전관리",
    "생관": "생산관리",
    "개제": "개발제한",
    "농림": "농림",
    "자보": "자연환경보전",
}

# 도시에는 도로/대만. 비도시는 대·전·답을 풀지 않고 따로.
BANDS = (
    ("urban_dae", "도시 · 도로/대", "urban", "대"),
    ("nonurban_dae", "비도시 · 도로/대", "nonurban", "대"),
    ("nonurban_jeon", "비도시 · 도로/전", "nonurban", "전"),
    ("nonurban_dap", "비도시 · 도로/답", "nonurban", "답"),
)
BAND_BY_KEY = {(klass, base): (bid, title) for bid, title, klass, base in BANDS}


def canonical_zone(raw: str | None) -> str:
    z = (raw or "").strip()
    return ZONE_ALIAS.get(z, z)


def zone_class(raw: str | None) -> str | None:
    z = canonical_zone(raw)
    if z in URBAN_ZONES:
        return "urban"
    if z in NONURBAN_ZONES:
        return "nonurban"
    if z in GREENBELT_ZONES:
        return "greenbelt"
    return None


def canonical_jimok(raw: str | None) -> str:
    j = (raw or "").strip()
    return ZONE_ALIAS.get(j, j)


def percentile_cont(values: Iterable[float], p: float) -> float | None:
    xs = sorted(float(v) for v in values)
    if not xs:
        return None
    if len(xs) == 1 or p <= 0:
        return xs[0]
    if p >= 1:
        return xs[-1]
    k = (len(xs) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return xs[lo]
    w = k - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def _f(v: Any, nd: int = 4) -> float | None:
    if v is None:
        return None
    x = float(v)
    if not math.isfinite(x):
        return None
    return round(x, nd)


def _side(row: dict[str, Any]) -> dict[str, Any] | None:
    n = int(row.get("n") or 0)
    p50 = row.get("p50")
    mean_px = row.get("mean_px")
    if n < 1 or p50 is None or mean_px is None:
        return None
    p50_f = float(p50)
    mean_f = float(mean_px)
    if p50_f <= 0 or mean_f <= 0 or not math.isfinite(p50_f) or not math.isfinite(mean_f):
        return None
    return {"n": n, "p50": p50_f, "mean": mean_f}


def _cut_summary(rs: list[float], r_means: list[float], n_roads: list[int], n_bases: list[int], *, n_candidates: int, n_road_only: int) -> dict[str, Any]:
    n_pass = len(rs)
    below = sum(1 for r in rs if r < THIRD_TICK)
    return {
        "n_cells": n_pass,
        "n_candidates": n_candidates,
        "n_dropped": n_candidates - n_pass,
        "n_road_only": n_road_only,
        "r_p25": _f(percentile_cont(rs, 0.25)),
        "r_p50": _f(percentile_cont(rs, 0.50)),
        "r_p75": _f(percentile_cont(rs, 0.75)),
        "r_mean_p50": _f(percentile_cont(r_means, 0.50)),
        "n_road_p50": _f(percentile_cont(n_roads, 0.50), 1),
        "n_base_p50": _f(percentile_cont(n_bases, 0.50), 1),
        "n_below_third": below,
    }


def build_screen(
    aggs: Iterable[dict[str, Any]],
    *,
    as_of_month: str,
    period_start: str,
    period_end: str,
    window_years: int = 5,
) -> dict[str, Any]:
    """집계 행(읍×용도×지목)을 네 분포와 1차 칸 표로 만든다."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in aggs:
        eup = str(row.get("eup_code") or "").strip()
        zone = canonical_zone(str(row.get("zone_type") or ""))
        jimok = canonical_jimok(str(row.get("land_category") or ""))
        if not eup or not zone or jimok not in JIMOKS:
            continue
        side = _side(row)
        if side is None:
            continue
        key = (eup, zone)
        g = groups.get(key)
        if g is None:
            g = {
                "sido_name": str(row.get("sido_name") or "").strip(),
                "sigungu_name": str(row.get("sigungu_name") or "").strip(),
                "eup_code": eup,
                "eup_name": str(row.get("eup_name") or "").strip(),
                "zone": zone,
                "sides": {},
            }
            groups[key] = g
        g["sides"][jimok] = side

    buckets: dict[str, dict[int, dict[str, list]]] = {
        bid: {cut: {"r": [], "rm": [], "nr": [], "nb": [], "cells": []} for cut in SENSITIVITY_MIN_N}
        for bid, _, _, _ in BANDS
    }
    candidates = {bid: 0 for bid, _, _, _ in BANDS}
    road_only = {bid: 0 for bid, _, _, _ in BANDS}
    greenbelt = {"n_groups": 0, "n_road_trades": 0, "n_base_trades": 0}
    unknown_groups = 0

    for g in groups.values():
        klass = zone_class(g["zone"])
        sides: dict[str, dict[str, Any]] = g["sides"]
        if klass == "greenbelt":
            greenbelt["n_groups"] += 1
            if ROAD in sides:
                greenbelt["n_road_trades"] += int(sides[ROAD]["n"])
            for base in BASES:
                if base in sides:
                    greenbelt["n_base_trades"] += int(sides[base]["n"])
            continue
        if klass is None:
            unknown_groups += 1
            continue
        road = sides.get(ROAD)
        bases = ("대",) if klass == "urban" else BASES
        for base in bases:
            bid, _title = BAND_BY_KEY[(klass, base)]
            other = sides.get(base)
            if road is None or other is None:
                if road is not None and other is None:
                    road_only[bid] += 1
                continue
            candidates[bid] += 1
            r_med = float(road["p50"]) / float(other["p50"])
            r_mean = float(road["mean"]) / float(other["mean"])
            cell = {
                "sido_name": g["sido_name"],
                "sigungu_name": g["sigungu_name"],
                "eup_name": g["eup_name"],
                "eup_code": g["eup_code"],
                "zone": g["zone"],
                "zone_label": ZONE_LABEL.get(g["zone"], g["zone"]),
                "band": bid,
                "base_jimok": base,
                "n_road": int(road["n"]),
                "n_base": int(other["n"]),
                "r_med": round(r_med, 4),
                "r_mean": round(r_mean, 4),
            }
            for cut in SENSITIVITY_MIN_N:
                if cell["n_road"] >= cut and cell["n_base"] >= cut:
                    slot = buckets[bid][cut]
                    slot["r"].append(r_med)
                    slot["rm"].append(r_mean)
                    slot["nr"].append(cell["n_road"])
                    slot["nb"].append(cell["n_base"])
                    if cut == PRIMARY_MIN_N:
                        slot["cells"].append(cell)

    bands = []
    cells: list[dict[str, Any]] = []
    for bid, title, _klass, base in BANDS:
        cuts = {}
        for cut in SENSITIVITY_MIN_N:
            slot = buckets[bid][cut]
            cuts[str(cut)] = _cut_summary(
                slot["r"],
                slot["rm"],
                slot["nr"],
                slot["nb"],
                n_candidates=candidates[bid],
                n_road_only=road_only[bid],
            )
        cells.extend(buckets[bid][PRIMARY_MIN_N]["cells"])
        bands.append({"id": bid, "title": title, "base_jimok": base, "cuts": cuts})

    cells.sort(key=lambda c: (c["band"], c["r_med"], c["sido_name"], c["eup_name"], c["zone"]))
    return {
        "status": "ready",
        "question": "도로 지목 토지의 거래단가는 비교 지목 토지의 몇 % 수준인가",
        "as_of_month": as_of_month,
        "period_start": period_start,
        "period_end": period_end,
        "window_years": window_years,
        "price_unit": "만원/㎡",
        "primary_min_n": PRIMARY_MIN_N,
        "sensitivity_min_n": list(SENSITIVITY_MIN_N),
        "third_tick": round(THIRD_TICK, 4),
        "grain": "읍면동 × 용도지역 × (도로 대 비교 지목 하나)",
        "controls": "면적·도로조건·창 안 연도는 1차에서 통제하지 않는다. 이건 1차의 성격이다.",
        "note": "네 분포는 한 숫자로 합치지 않는다. 1/3은 눈금이고 채택 기준이 아니다.",
        "unknown_groups": unknown_groups,
        "greenbelt": {
            **greenbelt,
            "note": "개발제한구역은 분포에 넣지 않는다. 건수만 남긴다.",
        },
        "bands": bands,
        "cells": cells,
    }


_URBAN_JU = frozenset({"1전", "2전", "1주", "2주", "3주", "준주"})
_URBAN_NOK = frozenset({"자녹", "생녹", "보녹"})
_URBAN_SANG = frozenset({"근상", "유상", "일상", "중상"})
_URBAN_GONG = frozenset({"전공", "일공", "준공"})


def _rs_summary(values: list[float]) -> dict[str, Any]:
    return {
        "n": len(values),
        "p25": _f(percentile_cont(values, 0.25)),
        "p50": _f(percentile_cont(values, 0.50)),
        "p75": _f(percentile_cont(values, 0.75)),
        "n_below_third": sum(1 for r in values if r < THIRD_TICK),
    }


def _cell_rs(cells: list[dict[str, Any]], *, band: str, zones: frozenset[str] | None = None) -> list[float]:
    out = []
    for c in cells:
        if c.get("band") != band:
            continue
        if zones is not None and c.get("zone") not in zones:
            continue
        r = c.get("r_med")
        if r is None:
            continue
        out.append(float(r))
    return out


def _band_cut(payload: dict[str, Any], band_id: str, cut: str = "10") -> dict[str, Any]:
    for band in payload.get("bands") or []:
        if band.get("id") == band_id:
            return (band.get("cuts") or {}).get(cut) or {}
    return {}


def _reg_cut(payload: dict[str, Any], band_id: str, cut: str = "10") -> dict[str, Any]:
    for band in (payload.get("regression") or {}).get("bands") or []:
        if band.get("id") == band_id:
            return (band.get("cuts") or {}).get(cut) or {}
    return {}


def enrich_public(payload: dict[str, Any]) -> dict[str, Any]:
    """공개 글이 읽을 묶음. 도시 전체를 한 비율로 만들지 않는다."""
    cells = list(payload.get("cells") or [])
    ju = _cell_rs(cells, band="urban_dae", zones=_URBAN_JU)
    nok = _cell_rs(cells, band="urban_dae", zones=_URBAN_NOK)
    ju_zones = {c.get("zone") for c in cells if c.get("band") == "urban_dae" and c.get("zone") in _URBAN_JU}
    nok_jarok = sum(
        1
        for c in cells
        if c.get("band") == "urban_dae" and c.get("zone") == "자녹"
    )
    ju_detail = "일반주거·준주거" if ju_zones <= {"1주", "2주", "3주", "준주"} else "주거지역"
    main = [
        {"id": "ju", "label": "주거지역 대지", "detail": ju_detail, **_rs_summary(ju)},
        {
            "id": "nok",
            "label": "녹지지역 대지",
            "detail": f"자연녹지 {nok_jarok}칸",
            **_rs_summary(nok),
        },
        {
            "id": "gye",
            "label": "계획관리지역 대지",
            "detail": "도시 밖",
            **_rs_summary(_cell_rs(cells, band="nonurban_dae", zones=frozenset({"계관"}))),
        },
    ]
    for bid, label, detail in (
        ("nonurban_jeon", "밭 (지목 전)", "도시 밖"),
        ("nonurban_dap", "논 (지목 답)", "도시 밖"),
    ):
        cut = _band_cut(payload, bid)
        main.append(
            {
                "id": bid,
                "label": label,
                "detail": detail,
                "n": cut.get("n_cells") or 0,
                "p25": cut.get("r_p25"),
                "p50": cut.get("r_p50"),
                "p75": cut.get("r_p75"),
                "n_below_third": cut.get("n_below_third"),
            }
        )
    thin_specs = (
        ("sang", "상업지역 대지", "urban_dae", _URBAN_SANG),
        ("gong", "공업지역 대지", "urban_dae", _URBAN_GONG),
        ("saeng", "생산관리지역 대지", "nonurban_dae", frozenset({"생관"})),
        ("bo", "보전관리지역 대지", "nonurban_dae", frozenset({"보관"})),
        ("nong", "농림지역 대지", "nonurban_dae", frozenset({"농림"})),
    )
    thin = []
    for tid, label, band, zones in thin_specs:
        row = {"id": tid, "label": label, **_rs_summary(_cell_rs(cells, band=band, zones=zones))}
        thin.append(row)
    adjusted = []
    for bid, label in (
        ("nonurban_dae", "도시 밖 대지"),
        ("nonurban_jeon", "도시 밖 밭"),
        ("nonurban_dap", "도시 밖 논"),
    ):
        cut = _band_cut(payload, bid)
        reg = _reg_cut(payload, bid)
        if not reg or reg.get("factor") is None:
            continue
        adjusted.append(
            {
                "id": bid,
                "label": label,
                "n": cut.get("n_cells"),
                "median": cut.get("r_p50"),
                "factor": reg.get("factor"),
                "n_reg_cells": reg.get("n_cells"),
            }
        )
    payload["public"] = {
        "period_start": payload.get("period_start"),
        "period_end": payload.get("period_end"),
        "as_of_month": payload.get("as_of_month"),
        "min_n": payload.get("primary_min_n"),
        "third_tick": payload.get("third_tick"),
        "main": main,
        "thin": thin,
        "adjusted": adjusted,
        "held_back": [
            "도시 전체를 한 비율로 두지 않는다.",
            "주거와 녹지를 따로 맞춘 배수는 없다.",
            "한 해만 자른 표는 공개 본문에 넣지 않는다.",
        ],
    }
    return payload
