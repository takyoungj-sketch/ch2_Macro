"""시군구 토지 쌍둥이 선정. 설계: docs/lab/LAND_TWIN_LAB.md

지목 거래비중으로 후보 20곳을 고른 뒤, 같은 후보에서 세 순위를 같이 매긴다.
A는 가격형태만, B는 지목 전체 비중과 가격형태, C는 용도지역 비중을 더한다.
D는 C의 지목 가격 대신 공통 용도×지목 칸의 가격형태를 쓴다.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

STRUCT_KEEP = 20
PRICE_KEEP = 5
PRICE_MIN_N = 15
PRICE_MIN_SHARED = 5
WINDOW_YEARS = 5
E_KEEP = 20
BASKET: tuple[tuple[str, str], ...] = (
    ("2주", "대"),
    ("1주", "대"),
    ("계관", "전"),
    ("계관", "대"),
    ("계관", "임"),
    ("자녹", "임"),
    ("자녹", "전"),
    ("자녹", "대"),
    ("일상", "대"),
    ("농림", "답"),
)

_CACHE: dict[tuple, dict] = {}


def js_divergence_base2(p: np.ndarray, q: np.ndarray) -> float:
    """젠슨-섀넌 발산. 밑 2. 같은 분포면 0, 서로 겹치지 않으면 1."""
    m = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0
        if not np.any(mask):
            return 0.0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def share_vector(counts: dict[str, int], vocab: list[str]) -> np.ndarray:
    total = sum(counts.get(name, 0) for name in vocab)
    if total <= 0:
        return np.zeros(len(vocab), dtype=float)
    return np.array([counts.get(name, 0) / total for name in vocab], dtype=float)


def price_shape(
    anchor: dict[str, tuple[int, float]],
    other: dict[str, tuple[int, float]],
) -> tuple[float, float, list[str]] | None:
    """공통 지목의 형태 거리, 수준 차(로그), 지목 이름.

    양쪽 거래가 15건 미만이면 빠진다. 남은 지목이 5개 미만이면 가격 순위에 쓰지 않는다.
    """
    shared: list[tuple[str, float, float]] = []
    for name, (n_a, med_a) in anchor.items():
        pair = other.get(name)
        if pair is None:
            continue
        n_b, med_b = pair
        if n_a < PRICE_MIN_N or n_b < PRICE_MIN_N or med_a <= 0 or med_b <= 0:
            continue
        shared.append((name, med_a, med_b))
    if len(shared) < PRICE_MIN_SHARED:
        return None
    log_a = np.log([med_a for _, med_a, _ in shared])
    log_b = np.log([med_b for _, _, med_b in shared])
    shape_a = log_a - float(log_a.mean())
    shape_b = log_b - float(log_b.mean())
    distance = float(np.mean(np.abs(shape_a - shape_b)))
    level_gap = float(log_b.mean() - log_a.mean())
    return distance, level_gap, [name for name, _, _ in shared]


def basket_amounts(cells: dict[str, tuple[int, float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """고정 10칸의 건수, 중위단가, 대표액(건수×중위). 없거나 0이면 0."""
    counts = np.zeros(len(BASKET), dtype=float)
    medians = np.zeros(len(BASKET), dtype=float)
    for index, (zone, cat) in enumerate(BASKET):
        pair = cells.get(f"{zone} {cat}")
        if pair is None:
            continue
        count, median = pair
        if count > 0 and median > 0:
            counts[index] = count
            medians[index] = median
    return counts, medians, counts * medians


def basket_share(amounts: np.ndarray) -> np.ndarray | None:
    total = float(amounts.sum())
    if total <= 0:
        return None
    return amounts / total


def basket_structure_distance(left: np.ndarray, right: np.ndarray) -> float:
    return 0.5 * float(np.abs(left - right).sum())


def basket_price_distance(
    left_share: np.ndarray,
    right_share: np.ndarray,
    left_median: np.ndarray,
    right_median: np.ndarray,
    left_count: np.ndarray,
    right_count: np.ndarray,
) -> tuple[float, int] | None:
    """양쪽 15건 이상인 칸만. 가중치는 양쪽 구성비 평균. 5칸 미만이면 없음."""
    mask = (
        (left_count >= PRICE_MIN_N)
        & (right_count >= PRICE_MIN_N)
        & (left_median > 0)
        & (right_median > 0)
    )
    shared = int(mask.sum())
    if shared < PRICE_MIN_SHARED:
        return None
    raw = left_share[mask] + right_share[mask]
    raw_sum = float(raw.sum())
    weights = np.ones(shared) / shared if raw_sum <= 0 else raw / raw_sum
    distance = float(np.sum(weights * np.abs(np.log(left_median[mask] / right_median[mask]))))
    return distance, shared


def rank_basket_twins(
    anchor_code: str,
    cell_profiles: dict[str, dict[str, tuple[int, float]]],
    names: dict[str, str],
) -> tuple[dict, list[dict]]:
    """전국 시군구를 대표 10칸 구성비로 줄 세운다. 가격과 규모는 순위에 넣지 않는다."""
    left_count, left_median, left_amount = basket_amounts(cell_profiles.get(anchor_code) or {})
    left_share = basket_share(left_amount)
    if left_share is None:
        raise KeyError(anchor_code)
    left_total = float(left_amount.sum())
    rows: list[dict] = []
    for code, label in names.items():
        if code == anchor_code:
            continue
        right_count, right_median, right_amount = basket_amounts(cell_profiles.get(code) or {})
        right_share = basket_share(right_amount)
        if right_share is None:
            continue
        distance = basket_structure_distance(left_share, right_share)
        priced = basket_price_distance(
            left_share, right_share, left_median, right_median, left_count, right_count
        )
        rows.append(
            {
                "region_code": code,
                "label": label,
                "structure_distance": distance,
                "structure_similarity": 100.0 * (1.0 - distance),
                "price_distance": None if priced is None else priced[0],
                "price_cells": 0 if priced is None else priced[1],
                "scale_ratio": float(right_amount.sum()) / left_total,
            }
        )
    rows.sort(key=lambda row: (row["structure_distance"], row["region_code"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    anchor = {
        "basket_total": left_total,
        "shares": [
            {"cell": f"{zone}×{cat}", "share": float(left_share[index]), "count": int(left_count[index])}
            for index, (zone, cat) in enumerate(BASKET)
        ],
    }
    return anchor, rows


def _minmax(values: list[float]) -> list[float]:
    lo = min(values)
    hi = max(values)
    span = hi - lo
    if span <= 1e-12:
        return [0.0 for _ in values]
    return [(value - lo) / span for value in values]


def _assign_blend(rows: list[dict], keys: list[str], rank_key: str, score_key: str) -> None:
    """후보 안에서 거리마다 0~1로 맞춘 뒤 같은 비중으로 평균한다. 작을수록 가깝다.

    필요한 거리가 없는 후보는 그 순위에서 뺀다. 점수가 같으면 지목 JS가 작은 쪽을 앞에 둔다.
    """
    eligible = [row for row in rows if all(row.get(key) is not None for key in keys)]
    if not eligible:
        return
    scaled = {key: _minmax([float(row[key]) for row in eligible]) for key in keys}
    order: list[tuple[float, float, str, dict]] = []
    for index, row in enumerate(eligible):
        score = sum(scaled[key][index] for key in keys) / len(keys)
        order.append((score, float(row["js"]), str(row["region_code"]), row))
    order.sort()
    for rank, (score, _, _, row) in enumerate(order, start=1):
        row[rank_key] = rank
        row[score_key] = score


def rank_land_twins(
    anchor_code: str,
    profiles: dict[str, dict[str, tuple[int, float]]],
    vocab: list[str],
    zone_profiles: dict[str, dict[str, int]] | None = None,
    zone_vocab: list[str] | None = None,
    cell_profiles: dict[str, dict[str, tuple[int, float]]] | None = None,
) -> list[dict]:
    """지목 비중으로 후보 20곳. A~D는 그 후보 안의 순위."""
    anchor = profiles.get(anchor_code)
    if not anchor:
        raise KeyError(anchor_code)
    anchor_share = share_vector({k: v[0] for k, v in anchor.items()}, vocab)
    scored: list[tuple[float, str]] = []
    for code, prof in profiles.items():
        if code == anchor_code:
            continue
        other_share = share_vector({k: v[0] for k, v in prof.items()}, vocab)
        if float(other_share.sum()) <= 0:
            continue
        scored.append((js_divergence_base2(anchor_share, other_share), code))
    scored.sort(key=lambda item: (item[0], item[1]))
    zone_profiles = zone_profiles or {}
    zone_vocab = zone_vocab or []
    cell_profiles = cell_profiles or {}
    anchor_zones = zone_profiles.get(anchor_code)
    anchor_cells = cell_profiles.get(anchor_code) or {}
    rows: list[dict] = []
    for index, (js, code) in enumerate(scored[:STRUCT_KEEP], start=1):
        shaped = price_shape(anchor, profiles[code])
        cells = price_shape(anchor_cells, cell_profiles.get(code) or {})
        similarity = 100.0 * (1.0 - js)
        zone_js = _zone_js(anchor_zones, zone_profiles.get(code), zone_vocab)
        row = {
            "structure_rank": index,
            "price_rank": None,
            "rank_b": None,
            "rank_c": None,
            "rank_d": None,
            "score_b": None,
            "score_c": None,
            "score_d": None,
            "region_code": code,
            "js": js,
            "structure_similarity": similarity,
            "zone_js": zone_js,
            "zone_similarity": None if zone_js is None else 100.0 * (1.0 - zone_js),
            "price_distance": None if shaped is None else shaped[0],
            "level_gap": None if shaped is None else shaped[1],
            "shared_jimok": [] if shaped is None else shaped[2],
            "cell_distance": None if cells is None else cells[0],
            "cell_level_gap": None if cells is None else cells[1],
            "shared_cells": [] if cells is None else cells[2],
        }
        rows.append(row)
    priced = [row for row in rows if row["price_distance"] is not None]
    priced.sort(key=lambda row: (row["price_distance"], row["js"], row["region_code"]))
    for index, row in enumerate(priced[:PRICE_KEEP], start=1):
        row["price_rank"] = index
    _assign_blend(rows, ["js", "price_distance"], "rank_b", "score_b")
    _assign_blend(rows, ["js", "zone_js", "price_distance"], "rank_c", "score_c")
    _assign_blend(rows, ["js", "zone_js", "cell_distance"], "rank_d", "score_d")
    return rows


def _zone_js(
    anchor_zones: dict[str, int] | None,
    other_zones: dict[str, int] | None,
    vocab: list[str],
) -> float | None:
    if not anchor_zones or not other_zones or not vocab:
        return None
    anchor_share = share_vector(anchor_zones, vocab)
    other_share = share_vector(other_zones, vocab)
    if float(anchor_share.sum()) <= 0 or float(other_share.sum()) <= 0:
        return None
    return js_divergence_base2(anchor_share, other_share)


def _load_bundle(db: Session) -> dict:
    as_of = db.execute(
        text(
            """
            SELECT MAX(as_of_month) AS as_of
            FROM land_upper_stats_v2
            WHERE region_level = 'sigungu'
              AND window_years = :window
              AND col_axis = 'category'
            """
        ),
        {"window": WINDOW_YEARS},
    ).scalar()
    if as_of is None:
        raise RuntimeError("시군구 토지 통계가 없습니다.")
    if isinstance(as_of, str):
        as_of = date.fromisoformat(as_of[:10])
    key = (as_of.isoformat(), WINDOW_YEARS, "abcd")
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    stat_rows = db.execute(
        text(
            """
            SELECT btrim(region_code::text) AS region_code,
                   btrim(land_category::text) AS land_category,
                   count,
                   median
            FROM land_upper_stats_v2
            WHERE region_level = 'sigungu'
              AND as_of_month = :as_of
              AND window_years = :window
              AND col_axis = 'category'
              AND zone_type = 'ALL'
              AND btrim(land_category::text) <> 'ALL'
              AND count > 0
            """
        ),
        {"as_of": as_of, "window": WINDOW_YEARS},
    ).mappings().all()
    profiles: dict[str, dict[str, tuple[int, float]]] = {}
    vocab_set: set[str] = set()
    for row in stat_rows:
        code = str(row["region_code"] or "").strip()
        cat = str(row["land_category"] or "").strip()
        if not code or not cat or len(code) != 5:
            continue
        median = row["median"]
        med = float(median) if median is not None else 0.0
        profiles.setdefault(code, {})[cat] = (int(row["count"]), med)
        vocab_set.add(cat)
    vocab = sorted(vocab_set)

    name_rows = db.execute(
        text(
            """
            SELECT btrim(sigungu_code::text) AS code,
                   MAX(btrim(sido_name::text)) AS sido,
                   MAX(btrim(sigungu_name::text)) AS sigungu
            FROM region_codes
            WHERE btrim(sigungu_code::text) ~ '^[0-9]{5}$'
              AND btrim(COALESCE(sigungu_name::text, '')) <> ''
              AND btrim(COALESCE(sido_name::text, '')) <> '세종특별자치시'
            GROUP BY 1
            """
        )
    ).mappings().all()
    names = {
        str(row["code"]): f"{row['sido']} {row['sigungu']}".strip()
        for row in name_rows
        if str(row["code"]) in profiles and "세종" not in str(row["sido"] or "")
    }
    profiles = {code: prof for code, prof in profiles.items() if code in names}
    zone_rows = db.execute(
        text(
            """
            SELECT btrim(region_code::text) AS region_code,
                   btrim(zone_type::text) AS zone_type,
                   count
            FROM land_upper_stats_v2
            WHERE region_level = 'sigungu'
              AND as_of_month = :as_of
              AND window_years = :window
              AND col_axis = 'category'
              AND land_category = 'ALL'
              AND btrim(zone_type::text) <> 'ALL'
              AND count > 0
            """
        ),
        {"as_of": as_of, "window": WINDOW_YEARS},
    ).mappings().all()
    zone_profiles: dict[str, dict[str, int]] = {}
    zone_vocab_set: set[str] = set()
    for row in zone_rows:
        code = str(row["region_code"] or "").strip()
        zone = str(row["zone_type"] or "").strip()
        if code not in names or not zone:
            continue
        zone_profiles.setdefault(code, {})[zone] = int(row["count"])
        zone_vocab_set.add(zone)
    cell_rows = db.execute(
        text(
            """
            SELECT btrim(region_code::text) AS region_code,
                   btrim(zone_type::text) AS zone_type,
                   btrim(land_category::text) AS land_category,
                   count,
                   median
            FROM land_upper_stats_v2
            WHERE region_level = 'sigungu'
              AND as_of_month = :as_of
              AND window_years = :window
              AND col_axis = 'category'
              AND btrim(zone_type::text) <> 'ALL'
              AND btrim(land_category::text) <> 'ALL'
              AND count > 0
            """
        ),
        {"as_of": as_of, "window": WINDOW_YEARS},
    ).mappings().all()
    cell_profiles: dict[str, dict[str, tuple[int, float]]] = {}
    for row in cell_rows:
        code = str(row["region_code"] or "").strip()
        zone = str(row["zone_type"] or "").strip()
        cat = str(row["land_category"] or "").strip()
        if code not in names or not zone or not cat:
            continue
        median = row["median"]
        med = float(median) if median is not None else 0.0
        cell_profiles.setdefault(code, {})[f"{zone} {cat}"] = (int(row["count"]), med)
    period = db.execute(
        text(
            """
            SELECT MIN(period_start)::text AS period_start,
                   MAX(period_end)::text AS period_end
            FROM land_upper_stats_v2
            WHERE region_level = 'sigungu'
              AND as_of_month = :as_of
              AND window_years = :window
              AND col_axis = 'category'
              AND zone_type = 'ALL'
              AND land_category = 'ALL'
            """
        ),
        {"as_of": as_of, "window": WINDOW_YEARS},
    ).mappings().one()
    bundle = {
        "as_of": as_of.isoformat(),
        "window_years": WINDOW_YEARS,
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "profiles": profiles,
        "vocab": vocab,
        "zone_profiles": zone_profiles,
        "zone_vocab": sorted(zone_vocab_set),
        "cell_profiles": cell_profiles,
        "names": names,
    }
    _CACHE[key] = bundle
    return bundle


def list_sigungu(db: Session) -> dict:
    bundle = _load_bundle(db)
    regions = [
        {"region_code": code, "label": bundle["names"][code]}
        for code in sorted(bundle["names"], key=lambda c: bundle["names"][c])
    ]
    return {
        "as_of_month": bundle["as_of"],
        "window_years": bundle["window_years"],
        "period_start": bundle["period_start"],
        "period_end": bundle["period_end"],
        "regions": regions,
    }


def _level_phrase(level_gap: float | None) -> str | None:
    if level_gap is None or not math.isfinite(level_gap):
        return None
    ratio = math.exp(level_gap)
    return f"기준 대비 {ratio:.2f}배"


def run_sigungu(db: Session, region_code: str) -> dict:
    code = str(region_code or "").strip()
    bundle = _load_bundle(db)
    if code not in bundle["profiles"]:
        raise KeyError(code)
    ranked = rank_land_twins(
        code,
        bundle["profiles"],
        bundle["vocab"],
        zone_profiles=bundle["zone_profiles"],
        zone_vocab=bundle["zone_vocab"],
        cell_profiles=bundle["cell_profiles"],
    )
    try:
        basket_anchor, basket_all = rank_basket_twins(code, bundle["cell_profiles"], bundle["names"])
        basket_note = None
    except KeyError:
        basket_anchor, basket_all = {"basket_total": 0.0, "shares": []}, []
        basket_note = "대표 10칸 거래가 없습니다."
    anchor = bundle["profiles"][code]
    anchor_zones = bundle["zone_profiles"].get(code, {})
    rows = []
    for row in ranked:
        other = bundle["profiles"][row["region_code"]]
        other_zones = bundle["zone_profiles"].get(row["region_code"], {})
        rows.append(
            {
                **row,
                "label": bundle["names"].get(row["region_code"], row["region_code"]),
                "n_tx": sum(n for n, _ in other.values()),
                "shared_count": len(row["shared_jimok"]),
                "zone_count": sum(1 for n in other_zones.values() if n > 0),
                "shared_cell_count": len(row["shared_cells"]),
                "cell_level_phrase": _level_phrase(row["cell_level_gap"]),
                "level_phrase": _level_phrase(row["level_gap"]),
            }
        )
    return {
        "as_of_month": bundle["as_of"],
        "window_years": bundle["window_years"],
        "period_start": bundle["period_start"],
        "period_end": bundle["period_end"],
        "anchor": {
            "region_code": code,
            "label": bundle["names"].get(code, code),
            "n_tx": sum(n for n, _ in anchor.values()),
            "n_jimok": len(anchor),
            "n_zone": sum(1 for n in anchor_zones.values() if n > 0),
            "basket_total": basket_anchor["basket_total"],
            "basket_shares": basket_anchor["shares"],
        },
        "rows": rows,
        "basket_note": basket_note,
        "basket_rows": [
            {**row, "scale_phrase": _level_phrase(math.log(row["scale_ratio"])) if row["scale_ratio"] > 0 else None}
            for row in basket_all[:E_KEEP]
        ],
    }
