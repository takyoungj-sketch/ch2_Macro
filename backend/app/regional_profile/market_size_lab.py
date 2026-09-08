"""관리자 실험 — 같은 grain 전국에서 유형 거래규모의 로그 횡단면 관계.

제품 「유형 동조」(비중 r)와 질문을 분리한다. 원장 재수집 없음.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.regional_profile.national_ranks import (
    city_bucket_from_sigungu,
    is_general_gu_code,
    is_legal_dong_without_ri_code,
)

MIX_TYPES = (
    "토지",
    "상가",
    "공장",
    "단독다가구",
    "아파트",
    "오피스텔",
    "연립다세대",
    "분양권",
)

_LEVELS = frozenset({"sigungu", "eupmyeondong", "beopjungri"})
_SCATTER_CAP = 2500
_MIN_WITHIN = 3

# ㎡당 P50. 토지는 유형 단가 마트가 없고 Top1 셀만 있어 단가 실험에서 뺀다.
PRICE_FEATURE: dict[str, str] = {
    "상가": "commercial_median",
    "공장": "factory_median",
    "단독다가구": "detached_median",
    "아파트": "apartment_median",
    "오피스텔": "officetel_median",
    "연립다세대": "rowhouse_median",
    "분양권": "presale_median",
}
PRICE_TYPES = tuple(PRICE_FEATURE.keys())

# as_of 포함 키 → 추출된 벡터. 랩에서 체급·탭을 바꿀 때 JSONB를 다시 풀지 않는다.
_BUNDLE: dict[tuple, dict[str, Any]] = {}
_CORE4 = ("토지", "상가", "단독다가구", "아파트")
_PRICE_JSON_SQL = (
    "jsonb_build_object(\n"
    + ",\n".join(f"        '{t}', r.features->'{col}'" for t, col in PRICE_FEATURE.items())
    + "\n    ) AS prices"
)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = dx = dy = 0.0
    for x, y in zip(xs, ys):
        vx = x - mx
        vy = y - my
        num += vx * vy
        dx += vx * vx
        dy += vy * vy
    if dx <= 0.0 or dy <= 0.0:
        return None
    return num / (dx * dy) ** 0.5


def residualize(ys: Sequence[float], xs: Sequence[float]) -> list[float] | None:
    """y ~ a + b x 잔차. 통제변수 분산 0이면 None."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = dx = 0.0
    for x, y in zip(xs, ys):
        vx = x - mx
        num += vx * (y - my)
        dx += vx * vx
    if dx <= 0.0:
        return None
    b = num / dx
    a = my - b * mx
    return [y - (a + b * x) for x, y in zip(xs, ys)]


def _cell(totals: Any, type_name: str, field: str) -> float:
    if not isinstance(totals, dict):
        return 0.0
    cell = totals.get(type_name) or {}
    if not isinstance(cell, dict):
        return 0.0
    try:
        return float(cell.get(field) or 0)
    except (TypeError, ValueError):
        return 0.0


def _pair_stats(
    left: Sequence[float],
    right: Sequence[float],
    pops: Sequence[float | None],
    *,
    use_log: bool,
) -> dict[str, Any]:
    xs: list[float] = []
    ys: list[float] = []
    px: list[float] = []
    py: list[float] = []
    log_pops: list[float] = []
    for a, b, pop in zip(left, right, pops):
        if a <= 0 or b <= 0:
            continue
        xv = math.log(a) if use_log else a
        yv = math.log(b) if use_log else b
        xs.append(xv)
        ys.append(yv)
        if pop is not None and pop > 0:
            px.append(xv)
            py.append(yv)
            log_pops.append(math.log(pop))
    r = pearson(xs, ys)
    r_pop = None
    n_pop = len(log_pops)
    if n_pop >= 3:
        rx = residualize(px, log_pops)
        ry = residualize(py, log_pops)
        if rx is not None and ry is not None:
            r_pop = pearson(rx, ry)
    return {
        "n": len(xs),
        "r": round(r, 4) if r is not None else None,
        "n_pop": n_pop,
        "r_pop": round(r_pop, 4) if r_pop is not None else None,
    }


def _share_pair(left: Sequence[float], right: Sequence[float], others_sum: Sequence[float]) -> dict[str, Any]:
    """지역 합=1 비중 상관. others_sum = 두 유형을 포함한 8유형 합."""
    xs: list[float] = []
    ys: list[float] = []
    for a, b, tot in zip(left, right, others_sum):
        if tot <= 0:
            continue
        xs.append(a / tot)
        ys.append(b / tot)
    r = pearson(xs, ys)
    return {"n": len(xs), "r": round(r, 4) if r is not None else None}


def _pop_type_stats(values: Sequence[float], pops: Sequence[float | None], *, use_log: bool) -> dict[str, Any]:
    xs: list[float] = []
    ys: list[float] = []
    for v, pop in zip(values, pops):
        if pop is None or pop <= 0 or v <= 0:
            continue
        xs.append(math.log(pop))
        ys.append(math.log(v) if use_log else v)
    r = pearson(xs, ys)
    return {"n": len(xs), "r": round(r, 4) if r is not None else None}


def _parent_sigungu(region_level: str, code: str) -> str:
    c = str(code or "").strip()
    if region_level in ("eupmyeondong", "beopjungri") and len(c) >= 5 and c[:5].isdigit():
        return c[:5]
    return ""


def _presence(amounts: dict[str, list[float]], n: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in MIX_TYPES:
        n_pos = sum(1 for v in amounts[t] if v > 0)
        out.append({"type": t, "n_pos": n_pos, "pct": round(n_pos / n, 4) if n else 0.0})
    return out


def _core_all_positive(amounts: dict[str, list[float]], types: Sequence[str]) -> int:
    n = len(next(iter(amounts.values()), []))
    k = 0
    for i in range(n):
        if all(amounts[t][i] > 0 for t in types):
            k += 1
    return k


def _within_pair_stats(
    left: Sequence[float],
    right: Sequence[float],
    parents: Sequence[str],
    pops: Sequence[float | None],
    *,
    use_log: bool,
) -> dict[str, Any]:
    groups: dict[str, list[tuple[float, float, float | None]]] = {}
    for a, b, parent, pop in zip(left, right, parents, pops):
        if not parent or a <= 0 or b <= 0:
            continue
        xa = math.log(a) if use_log else a
        xb = math.log(b) if use_log else b
        groups.setdefault(parent, []).append((xa, xb, pop))
    xs: list[float] = []
    ys: list[float] = []
    xs_p: list[float] = []
    ys_p: list[float] = []
    n_parents = 0
    for rows in groups.values():
        if len(rows) < _MIN_WITHIN:
            continue
        n_parents += 1
        mx = sum(r[0] for r in rows) / len(rows)
        my = sum(r[1] for r in rows) / len(rows)
        for xa, xb, _pop in rows:
            xs.append(xa - mx)
            ys.append(xb - my)
        pop_ok = [(xa, xb, math.log(pop)) for xa, xb, pop in rows if pop is not None and pop > 0]
        if len(pop_ok) < _MIN_WITHIN:
            continue
        lpx = [p[0] for p in pop_ok]
        lpy = [p[1] for p in pop_ok]
        lp = [p[2] for p in pop_ok]
        rx = residualize(lpx, lp)
        ry = residualize(lpy, lp)
        if rx is None or ry is None:
            continue
        mrx = sum(rx) / len(rx)
        mry = sum(ry) / len(ry)
        for va, vb in zip(rx, ry):
            xs_p.append(va - mrx)
            ys_p.append(vb - mry)
    r = pearson(xs, ys)
    r_pop = pearson(xs_p, ys_p)
    return {
        "n": len(xs),
        "n_parents": n_parents,
        "r": round(r, 4) if r is not None else None,
        "n_pop": len(xs_p),
        "r_pop": round(r_pop, 4) if r_pop is not None else None,
    }


def _price_pair_stats(left: Sequence[float | None], right: Sequence[float | None]) -> dict[str, Any]:
    xs: list[float] = []
    ys: list[float] = []
    for a, b in zip(left, right):
        if a is None or b is None or a <= 0 or b <= 0:
            continue
        xs.append(math.log(a))
        ys.append(math.log(b))
    r = pearson(xs, ys)
    return {"n": len(xs), "r": round(r, 4) if r is not None else None}


def _within_price_pair_stats(
    left: Sequence[float | None],
    right: Sequence[float | None],
    parents: Sequence[str],
) -> dict[str, Any]:
    groups: dict[str, list[tuple[float, float]]] = {}
    for a, b, parent in zip(left, right, parents):
        if not parent or a is None or b is None or a <= 0 or b <= 0:
            continue
        groups.setdefault(parent, []).append((math.log(a), math.log(b)))
    xs: list[float] = []
    ys: list[float] = []
    n_parents = 0
    for rows in groups.values():
        if len(rows) < _MIN_WITHIN:
            continue
        n_parents += 1
        mx = sum(r[0] for r in rows) / len(rows)
        my = sum(r[1] for r in rows) / len(rows)
        for xa, xb in rows:
            xs.append(xa - mx)
            ys.append(xb - my)
    r = pearson(xs, ys)
    return {
        "n": len(xs),
        "n_parents": n_parents,
        "r": round(r, 4) if r is not None else None,
    }


def _missing_price_types(prices: dict[str, list[float | None]]) -> list[str]:
    """P50가 한 건도 없는 유형. 리 grain에서 상가·공장·단독이 여기에 해당한다."""
    out: list[str] = []
    for t in PRICE_TYPES:
        vals = prices.get(t) or []
        if not any(v is not None for v in vals):
            out.append(t)
    return out


def _parse_opt_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v


def _load_bundle(
    db: Session,
    *,
    profile_version: str,
    window_years: int,
    region_level: str,
) -> dict[str, Any]:
    latest = db.execute(
        text(
            """
            SELECT as_of_month
            FROM regional_profile
            WHERE profile_version = :pv
              AND window_years = :wy
              AND region_level = :level
            GROUP BY as_of_month
            ORDER BY COUNT(*) DESC, as_of_month DESC
            LIMIT 1
            """
        ),
        {"pv": profile_version, "wy": window_years, "level": region_level},
    ).scalar()
    if latest is None:
        raise LookupError("프로필 행 없음")

    rows = db.execute(
        text(
            f"""
            SELECT r.region_code,
                   rk.name_short,
                   r.features->'yearly_mix'->'totals_by_type' AS totals,
                   NULLIF(btrim(r.features->>'population'), '') AS pop_raw,
                   {_PRICE_JSON_SQL}
            FROM regional_profile r
            LEFT JOIN regional_profile_rank rk
              ON rk.profile_version = r.profile_version
             AND rk.as_of_month = r.as_of_month
             AND rk.window_years = r.window_years
             AND rk.region_level = r.region_level
             AND rk.region_code = r.region_code
            WHERE r.profile_version = :pv
              AND r.window_years = :wy
              AND r.region_level = :level
              AND r.as_of_month = :as_of
            """
        ),
        {"pv": profile_version, "wy": window_years, "level": region_level, "as_of": latest},
    ).mappings().all()

    codes: list[str] = []
    names: list[str] = []
    pops: list[float | None] = []
    amounts: dict[str, list[float]] = {t: [] for t in MIX_TYPES}
    counts: dict[str, list[float]] = {t: [] for t in MIX_TYPES}
    tot_a: list[float] = []
    tot_c: list[float] = []
    parents: list[str] = []
    prices: dict[str, list[float | None]] = {t: [] for t in PRICE_TYPES}
    def append_row(r: Any) -> None:
        code = str(r["region_code"] or "").strip()
        totals = r["totals"] or {}
        if isinstance(totals, str):
            return
        codes.append(code)
        names.append(str(r["name_short"] or "").strip() or code)
        parents.append(_parent_sigungu(region_level, code))
        raw_pop = r["pop_raw"]
        pop: float | None
        try:
            pop = float(raw_pop) if raw_pop is not None else None
        except (TypeError, ValueError):
            pop = None
        if pop is not None and pop <= 0:
            pop = None
        pops.append(pop)
        sa = sc = 0.0
        for t in MIX_TYPES:
            a = _cell(totals, t, "amount")
            c = _cell(totals, t, "count")
            amounts[t].append(a)
            counts[t].append(c)
            sa += a
            sc += c
        tot_a.append(sa)
        tot_c.append(sc)
        raw_prices = r["prices"] or {}
        if isinstance(raw_prices, str):
            raw_prices = {}
        for t in PRICE_TYPES:
            prices[t].append(_parse_opt_float(raw_prices.get(t)))

    dropped_dong = 0
    added_city = 0
    gu_parents: set[str] = set()
    for r in rows:
        code = str(r["region_code"] or "").strip()
        if region_level == "beopjungri" and is_legal_dong_without_ri_code(code):
            dropped_dong += 1
            continue
        if region_level == "sigungu" and is_general_gu_code(code):
            parent = city_bucket_from_sigungu(code)
            if parent:
                gu_parents.add(parent)
        append_row(r)

    if region_level == "sigungu" and gu_parents:
        have = set(codes)
        need = [p for p in sorted(gu_parents) if p not in have]
        if need:
            city_rows = db.execute(
                text(
                    f"""
                    SELECT r.region_code,
                           rk.name_short,
                           r.features->'yearly_mix'->'totals_by_type' AS totals,
                           NULLIF(btrim(r.features->>'population'), '') AS pop_raw,
                           {_PRICE_JSON_SQL}
                    FROM regional_profile r
                    LEFT JOIN regional_profile_rank rk
                      ON rk.profile_version = r.profile_version
                     AND rk.as_of_month = r.as_of_month
                     AND rk.window_years = r.window_years
                     AND rk.region_level = r.region_level
                     AND rk.region_code = r.region_code
                    WHERE r.profile_version = :pv
                      AND r.window_years = :wy
                      AND r.region_level = 'city'
                      AND r.as_of_month = :as_of
                      AND r.region_code IN :codes
                    """
                ).bindparams(bindparam("codes", expanding=True)),
                {
                    "pv": profile_version,
                    "wy": window_years,
                    "as_of": latest,
                    "codes": need,
                },
            ).mappings().all()
            for r in city_rows:
                append_row(r)
                added_city += 1

    return {
        "as_of_month": latest,
        "universe_n": len(rows),
        "n": len(codes),
        "dropped_dong": dropped_dong,
        "added_city": added_city,
        "codes": codes,
        "names": names,
        "pops": pops,
        "amounts": amounts,
        "counts": counts,
        "prices": prices,
        "parents": parents,
        "tot_amount": tot_a,
        "tot_count": tot_c,
    }


def get_bundle(
    db: Session,
    *,
    profile_version: str,
    window_years: int,
    region_level: str,
) -> dict[str, Any]:
    lv = region_level.strip().lower()
    if lv not in _LEVELS:
        raise ValueError("region_level은 sigungu / eupmyeondong / beopjungri")
    key = (profile_version, window_years, lv, "exp14")
    cached = _BUNDLE.get(key)
    if cached is not None:
        return cached
    bundle = _load_bundle(
        db, profile_version=profile_version, window_years=window_years, region_level=lv
    )
    _BUNDLE[key] = bundle
    return bundle


def _scatter_points(
    bundle: dict[str, Any],
    *,
    left: Sequence[float],
    right: Sequence[float],
    use_log: bool,
) -> list[dict[str, Any]]:
    pts: list[dict[str, Any]] = []
    codes: list[str] = bundle["codes"]
    names: list[str] = bundle["names"]
    pops: list[float | None] = bundle["pops"]
    for i, (a, b) in enumerate(zip(left, right)):
        if a <= 0 or b <= 0:
            continue
        pts.append(
            {
                "code": codes[i],
                "name": names[i],
                "x": math.log(a) if use_log else a,
                "y": math.log(b) if use_log else b,
                "x_raw": a,
                "y_raw": b,
                "population": pops[i],
            }
        )
    if len(pts) <= _SCATTER_CAP:
        return pts
    step = len(pts) / _SCATTER_CAP
    picked = [pts[int(i * step)] for i in range(_SCATTER_CAP)]
    return picked


def compute_market_size(
    db: Session,
    *,
    profile_version: str,
    window_years: int,
    region_level: str,
    scatter_a: str | None = None,
    scatter_b: str | None = None,
    scatter_metric: str = "amount",
) -> dict[str, Any]:
    bundle = get_bundle(
        db,
        profile_version=profile_version,
        window_years=window_years,
        region_level=region_level,
    )
    amounts: dict[str, list[float]] = bundle["amounts"]
    counts: dict[str, list[float]] = bundle["counts"]
    pops: list[float | None] = bundle["pops"]
    tot_a: list[float] = bundle["tot_amount"]
    tot_c: list[float] = bundle["tot_count"]
    parents: list[str] = bundle.get("parents") or [""] * len(bundle["codes"])
    prices: dict[str, list[float | None]] = bundle.get("prices") or {t: [] for t in PRICE_TYPES}

    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(MIX_TYPES):
        for b in MIX_TYPES[i + 1 :]:
            amt = _pair_stats(amounts[a], amounts[b], pops, use_log=True)
            cnt = _pair_stats(counts[a], counts[b], pops, use_log=True)
            share_a = _share_pair(amounts[a], amounts[b], tot_a)
            share_c = _share_pair(counts[a], counts[b], tot_c)
            within_amt = _within_pair_stats(amounts[a], amounts[b], parents, pops, use_log=True)
            within_cnt = _within_pair_stats(counts[a], counts[b], parents, pops, use_log=True)
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "amount": amt,
                    "count": cnt,
                    "share_amount": share_a,
                    "share_count": share_c,
                    "within_amount": within_amt,
                    "within_count": within_cnt,
                }
            )

    price_pairs: list[dict[str, Any]] = []
    for i, a in enumerate(PRICE_TYPES):
        for b in PRICE_TYPES[i + 1 :]:
            price_pairs.append(
                {
                    "a": a,
                    "b": b,
                    "price": _price_pair_stats(prices[a], prices[b]),
                    "within_price": _within_price_pair_stats(prices[a], prices[b], parents),
                }
            )

    pop_axis: list[dict[str, Any]] = []
    for t in MIX_TYPES:
        pop_axis.append(
            {
                "type": t,
                "amount": _pop_type_stats(amounts[t], pops, use_log=True),
                "count": _pop_type_stats(counts[t], pops, use_log=True),
            }
        )

    scatter = None
    sa = (scatter_a or "").strip()
    sb = (scatter_b or "").strip()
    metric = scatter_metric if scatter_metric in ("amount", "count") else "amount"
    if sa in MIX_TYPES and sb in MIX_TYPES and sa != sb:
        src = amounts if metric == "amount" else counts
        scatter = {
            "a": sa,
            "b": sb,
            "metric": metric,
            "log": True,
            "points": _scatter_points(bundle, left=src[sa], right=src[sb], use_log=True),
            "n_positive": sum(1 for x, y in zip(src[sa], src[sb]) if x > 0 and y > 0),
        }

    as_of = bundle["as_of_month"]
    price_missing = _missing_price_types(prices)
    return {
        "lab": "market_size",
        "note": "로그 거래규모 횡단면. 단가는 ㎡당 P50(인구 보정 없음). 동조·인과가 아님.",
        "profile_version": profile_version,
        "window_years": window_years,
        "region_level": region_level,
        "as_of_month": as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of),
        "universe_n": bundle["universe_n"],
        "n": bundle["n"],
        "dropped_dong": bundle["dropped_dong"],
        "added_city": bundle.get("added_city", 0),
        "types": list(MIX_TYPES),
        "price_types": list(PRICE_TYPES),
        "price_missing_types": price_missing,
        "price_note": "㎡당 P50. 상가=일반상가 commercial_median. 토지 단가 마트 없음. 인구 보정 안 함.",
        "presence": _presence(amounts, len(bundle["codes"])),
        "core4_n": _core_all_positive(amounts, _CORE4),
        "pairs": pairs,
        "price_pairs": price_pairs,
        "population_axis": pop_axis,
        "scatter": scatter,
    }
