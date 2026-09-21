"""3차: 2차 방향 그룹의 구성 + 같은 동 안 광평 vs 몸통.

유형×방향 칸 수는 다시 세지 않는다. 선정은 2차 비교가능칸 전부 (단가·|Δ|로 고르지 않음).
재실행 (backend에서):
  python -m app.land_lab.area_elasticity_where
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import text

from app.db import engine
from app.land_lab.area_elasticity import AREA_MAX_SQM, LAND_CATEGORIES, REGION_TYPES
from app.land_lab.area_elasticity_gap import (
    DIR_HIGHER,
    DIR_LOWER,
    DIR_NEUTRAL,
    DIR_SKIP,
    OUT,
    PHASE2_N_BOOT,
    _cell_rng,
    _pack_arm,
    assign_bins,
)
from app.land_lab.area_elasticity_screen import period_bounds_for_window, write_payload
from app.ledger_region_sql import beopjungri_eq_or_in, execute_expanding
from app.region_canonical import canonical_select_expr, region_codes_join_on_canonical

WITHIN_N_BODY_MIN = 20
WITHIN_N_LARGE_MIN = 10
NON_URBAN_MARKERS = ("농림", "자연환경보전", "보전관리", "생산관리", "계획관리")


def zone_bucket(zone_type: str | None) -> str:
    """거래 용도지역 → 도시계 / 비도시계. 인과 분류가 아니라 구성용."""
    s = (zone_type or "").strip()
    if not s:
        return "unknown"
    if any(m in s for m in NON_URBAN_MARKERS):
        return "non_urban"
    if s in {"관리지역", "비도시지역"}:
        return "non_urban"
    return "urban"


def build_where_fetch_sql(join_sql: str, sigungu_pred: str) -> str:
    cats = ", ".join(f"'{c}'" for c in LAND_CATEGORIES)
    code_expr = canonical_select_expr("lt")
    return f"""
        SELECT
            btrim(r.sigungu_code::text) AS sigungu_code,
            btrim(lt.land_category_resolved::text) AS land_category,
            ({code_expr}) AS beopjungri_code,
            btrim(COALESCE(lt.zone_type_resolved::text, lt.zone_type::text, '')) AS zone_type,
            lt.area_sqm::float8 AS area_sqm,
            lt.unit_price_per_sqm::float8 AS unit_price_per_sqm
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE {sigungu_pred}
          AND lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND COALESCE(lt.is_partial_ownership, FALSE) = FALSE
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.area_sqm < :area_max
          AND lt.unit_price_per_sqm > 0
          AND btrim(lt.land_category_resolved::text) IN ({cats})
    """


def fetch_where_transactions(
    db: Session,
    *,
    sigungu_codes: list[str],
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    codes = sorted({str(c).strip() for c in sigungu_codes if str(c).strip()})
    if not codes:
        return []
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    pred, extra = beopjungri_eq_or_in(codes, column="btrim(r.sigungu_code::text)")
    sql = build_where_fetch_sql(join_sql, pred)
    params: dict[str, Any] = {
        "p_start": period_start,
        "p_end": period_end,
        "area_max": AREA_MAX_SQM,
        **extra,
    }
    rows = execute_expanding(db, sql, params).mappings().all()
    return [dict(r) for r in rows]


def build_population_sql(sigungu_pred: str) -> str:
    return f"""
        SELECT
            btrim(r.sigungu_code::text) AS sigungu_code,
            SUM(ps.total_population)::bigint AS population
        FROM population_stats ps
        JOIN region_codes r
          ON btrim(r.beopjungri_code::text) = btrim(ps.admin_code::text)
        WHERE ps.admin_level = 'beopjungri'
          AND (ps.stats_month = 12 OR ps.stats_month IS NULL)
          AND ps.stats_year = :pop_year
          AND COALESCE(r.is_active, TRUE)
          AND {sigungu_pred}
        GROUP BY btrim(r.sigungu_code::text)
    """


def fetch_sigungu_population(
    db: Session,
    *,
    sigungu_codes: list[str],
    pop_year: int,
) -> dict[str, int]:
    codes = sorted({str(c).strip() for c in sigungu_codes if str(c).strip()})
    if not codes:
        return {}
    pred, extra = beopjungri_eq_or_in(codes, column="btrim(r.sigungu_code::text)")
    sql = build_population_sql(pred)
    params: dict[str, Any] = {"pop_year": int(pop_year), **extra}
    rows = execute_expanding(db, sql, params).mappings().all()
    return {str(r["sigungu_code"]).strip(): int(r["population"]) for r in rows if r["population"] is not None}


def latest_population_year(db: Session) -> int:
    y = db.execute(
        text(
            """
            SELECT MAX(stats_year)::int
            FROM population_stats
            WHERE admin_level = 'beopjungri'
              AND (stats_month = 12 OR stats_month IS NULL)
            """
        )
    ).scalar()
    if y is None:
        raise RuntimeError("population_stats 연말 연도 없음")
    return int(y)


def within_dong_large(
    rows: list[dict[str, Any]],
    *,
    land_category: str,
    sigungu_code: str,
    n_boot: int = PHASE2_N_BOOT,
) -> dict[str, Any]:
    """같은 동에 몸통과 광평이 같이 있는 동만. 칸 P25/P90은 전체 표본."""
    if not rows:
        return {"direction": DIR_SKIP, "reason": "no_trades", "n_dongs_both": 0}
    area = np.array([float(r["area_sqm"]) for r in rows], dtype=float)
    price = np.array([float(r["unit_price_per_sqm"]) for r in rows], dtype=float)
    beop = np.array([str(r.get("beopjungri_code") or "").strip() or "미상" for r in rows])
    ok = np.isfinite(area) & np.isfinite(price) & (area > 0) & (price > 0)
    area, price, beop = area[ok], price[ok], beop[ok]
    bins = assign_bins(area, land_category=land_category)
    body_m = bins["body"]
    large_m = bins["large"]
    dongs_body = set(beop[body_m].tolist())
    dongs_large = set(beop[large_m].tolist())
    both = dongs_body & dongs_large
    both.discard("")
    if not both:
        return {"direction": DIR_SKIP, "reason": "no_overlap_dong", "n_dongs_both": 0}
    in_both = np.array([b in both for b in beop], dtype=bool)
    body_p = price[body_m & in_both]
    large_p = price[large_m & in_both]
    out: dict[str, Any] = {
        "n_dongs_both": int(len(both)),
        "n_body": int(body_p.size),
        "n_large": int(large_p.size),
    }
    if body_p.size < WITHIN_N_BODY_MIN or large_p.size < WITHIN_N_LARGE_MIN:
        out["direction"] = DIR_SKIP
        out["reason"] = "thin_overlap"
        return out
    rng = _cell_rng(sigungu_code, land_category + "|within")
    packed = _pack_arm(large_p, body_p, rng=rng, n_boot=n_boot)
    packed.update(out)
    packed["reason"] = None
    return packed


def urban_share(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    buckets = [zone_bucket(r.get("zone_type")) for r in rows]
    known = [b for b in buckets if b != "unknown"]
    if not known:
        return None
    return float(sum(1 for b in known if b == "urban") / len(known))


def median_price(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    p = np.array([float(r["unit_price_per_sqm"]) for r in rows], dtype=float)
    p = p[np.isfinite(p) & (p > 0)]
    if p.size == 0:
        return None
    return float(np.median(p))


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _median(vals: list[float | None]) -> float | None:
    xs = [float(v) for v in vals if v is not None]
    if not xs:
        return None
    return round(float(np.median(xs)), 4)


def _share(vals: list[bool]) -> float | None:
    if not vals:
        return None
    return round(sum(1 for v in vals if v) / len(vals), 3)


def compose_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_type = {t: 0 for t in REGION_TYPES}
    by_cat: dict[str, int] = {}
    for r in rows:
        rt = str(r.get("region_type") or "")
        if rt in by_type:
            by_type[rt] += 1
        cat = str(r.get("land_category") or "")
        by_cat[cat] = by_cat.get(cat, 0) + 1
    n = len(rows)
    return {
        "n": n,
        "median_n": _median([_f(r.get("n")) for r in rows]),
        "median_p90_p50": _median([_f(r.get("p90_p50")) for r in rows]),
        "median_population": _median([_f(r.get("population")) for r in rows]),
        "median_unit_price": _median([_f(r.get("median_unit_price")) for r in rows]),
        "median_urban_share": _median([_f(r.get("urban_share")) for r in rows]),
        "share_dae": _share([r.get("land_category") == "대" for r in rows]),
        "share_farm": _share([r.get("land_category") in {"전", "답"} for r in rows]),
        "by_type": {k: v for k, v in by_type.items() if v},
        "by_category": by_cat,
    }


def vs_cell_direction(cell_dir: str, within: dict[str, Any]) -> str:
    w = within.get("direction")
    if w == DIR_SKIP:
        return "skip"
    if w == cell_dir:
        return "same"
    if w == DIR_NEUTRAL:
        return "to_neutral"
    return "opposite"


def summarize_within(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tallies: dict[str, dict[str, int]] = {}
    n_ok = 0
    n_skip = 0
    for r in rows:
        w = r.get("within") or {}
        d = str((r.get("large") or {}).get("direction") or "")
        slot = tallies.setdefault(
            d, {"same": 0, "to_neutral": 0, "opposite": 0, "skip": 0}
        )
        vs = vs_cell_direction(d, w)
        slot[vs] = slot.get(vs, 0) + 1
        if w.get("direction") == DIR_SKIP:
            n_skip += 1
        else:
            n_ok += 1
    return {"n_ok": n_ok, "n_skip": n_skip, "vs_cell": tallies}


def tiny_by_type(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for t in REGION_TYPES:
        sub = [r for r in rows if r.get("region_type") == t and r.get("tiny_aux")]
        if not sub:
            continue
        c = {"lower": 0, "neutral": 0, "higher": 0, "n": 0}
        for r in sub:
            d = ((r.get("tiny") or {}) or {}).get("direction")
            if d in {DIR_LOWER, DIR_NEUTRAL, DIR_HIGHER}:
                c[d] += 1
                c["n"] += 1
        out[t] = c
    return out


CROSS_CATEGORIES = ("대", "전", "답")


def type_category_crosstab(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """유형 × 지목 × 광평 방향. 비교가능칸만. 4차 회귀가 아님."""
    out: dict[str, dict[str, Any]] = {}
    for t in REGION_TYPES:
        slot: dict[str, Any] = {}
        for cat in CROSS_CATEGORIES:
            sub = [
                r
                for r in rows
                if r.get("region_type") == t
                and r.get("land_category") == cat
                and ((r.get("large") or {}) or {}).get("direction")
                in {DIR_LOWER, DIR_NEUTRAL, DIR_HIGHER}
            ]
            if not sub:
                continue
            counts = {"n": len(sub), "lower": 0, "neutral": 0, "higher": 0}
            for r in sub:
                d = ((r.get("large") or {}) or {}).get("direction")
                counts[str(d)] += 1
            n = counts["n"]
            counts["share_lower"] = round(counts["lower"] / n, 3) if n else None
            counts["share_higher"] = round(counts["higher"] / n, 3) if n else None
            slot[cat] = counts
        if slot:
            out[t] = slot
    return out


def load_screen_lookup(csv_path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if not csv_path.exists():
        return out
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (str(row.get("sigungu_code") or "").strip(), str(row.get("land_category") or "").strip())
            out[key] = row
    return out


def run_phase3(
    payload: dict[str, Any],
    *,
    engine_bind: Engine,
    screen_csv: Path,
    n_boot: int = PHASE2_N_BOOT,
) -> dict[str, Any]:
    rows = list(payload.get("phase2_rows") or [])
    if not rows:
        raise RuntimeError("phase2_rows 없음. 먼저 area_elasticity_gap 을 실행한다.")
    as_of = date.fromisoformat(str(payload["as_of_month"]))
    window = int(payload["window_years"])
    period_start, period_end = period_bounds_for_window(as_of, window)
    screen = load_screen_lookup(screen_csv)
    codes = [str(r["sigungu_code"]) for r in rows]
    SessionLocal = sessionmaker(bind=engine_bind, autocommit=False, autoflush=False)
    db: Session = SessionLocal()
    try:
        pop_year = latest_population_year(db)
        print(f"fetch trades+zone sigungu={len(set(codes))} pop_year={pop_year}", flush=True)
        trades = fetch_where_transactions(
            db,
            sigungu_codes=codes,
            period_start=period_start,
            period_end=period_end,
        )
        pop = fetch_sigungu_population(db, sigungu_codes=codes, pop_year=pop_year)
    finally:
        db.close()

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in trades:
        key = (str(t["sigungu_code"]).strip(), str(t["land_category"]).strip())
        grouped.setdefault(key, []).append(t)
    print(f"grouped={len(grouped)} trade_rows={len(trades)}", flush=True)

    enriched: list[dict[str, Any]] = []
    for i, cell in enumerate(rows, start=1):
        sg = str(cell["sigungu_code"]).strip()
        cat = str(cell["land_category"]).strip()
        key = (sg, cat)
        cell_trades = grouped.get(key, [])
        look = screen.get(key) or {}
        rec = dict(cell)
        rec["p90_p50"] = _f(look.get("p90_p50"))
        rec["population"] = pop.get(sg)
        rec["pop_year"] = pop_year
        u = urban_share(cell_trades)
        rec["urban_share"] = round(u, 4) if u is not None else None
        mp = median_price(cell_trades)
        rec["median_unit_price"] = round(mp, 2) if mp is not None else None
        rec["within"] = within_dong_large(
            cell_trades, land_category=cat, sigungu_code=sg, n_boot=n_boot
        )
        rec["within_vs_cell"] = vs_cell_direction(
            str((cell.get("large") or {}).get("direction") or ""),
            rec["within"],
        )
        enriched.append(rec)
        if i % 50 == 0 or i == len(rows):
            print(f"phase3 {i}/{len(rows)}", flush=True)

    by_dir: dict[str, list[dict[str, Any]]] = {DIR_LOWER: [], DIR_NEUTRAL: [], DIR_HIGHER: []}
    for r in enriched:
        d = str((r.get("large") or {}).get("direction") or "")
        if d in by_dir:
            by_dir[d].append(r)

    higher_focus = [
        r
        for r in enriched
        if (r.get("large") or {}).get("direction") == DIR_HIGHER
        or r.get("region_type") == "metro_gu"
    ]
    higher_slim = []
    for r in higher_focus:
        w = r.get("within") or {}
        higher_slim.append(
            {
                "sido_name": r.get("sido_name"),
                "sigungu_name": r.get("sigungu_name"),
                "sigungu_code": r.get("sigungu_code"),
                "land_category": r.get("land_category"),
                "region_type": r.get("region_type"),
                "direction_cell": (r.get("large") or {}).get("direction"),
                "delta_median_cell": (r.get("large") or {}).get("delta_median"),
                "direction_within": w.get("direction"),
                "delta_median_within": w.get("delta_median"),
                "ci_lo_within": w.get("ci_lo"),
                "ci_hi_within": w.get("ci_hi"),
                "within_vs_cell": r.get("within_vs_cell"),
                "n_dongs_both": w.get("n_dongs_both"),
                "urban_share": r.get("urban_share"),
                "population": r.get("population"),
                "p90_p50": r.get("p90_p50"),
                "median_unit_price": r.get("median_unit_price"),
            }
        )

    summary = {
        "n_cells": len(enriched),
        "pop_year": pop_year,
        "composition": {
            DIR_LOWER: compose_group(by_dir[DIR_LOWER]),
            DIR_NEUTRAL: compose_group(by_dir[DIR_NEUTRAL]),
            DIR_HIGHER: compose_group(by_dir[DIR_HIGHER]),
        },
        "tiny_by_type": tiny_by_type(enriched),
        "by_type_category": type_category_crosstab(enriched),
        "within_dong": summarize_within(enriched),
        "higher_or_metro": higher_slim,
    }
    out = dict(payload)
    out["status"] = "phase3_where"
    out["phase3"] = summary
    out["_phase3_rows"] = enriched
    return out


def write_phase3_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    flat = []
    for r in rows:
        w = r.get("within") or {}
        large = r.get("large") or {}
        tiny = r.get("tiny") or {}
        flat.append(
            {
                "sido_name": r.get("sido_name"),
                "sigungu_name": r.get("sigungu_name"),
                "sigungu_code": r.get("sigungu_code"),
                "land_category": r.get("land_category"),
                "region_type": r.get("region_type"),
                "direction_large": large.get("direction"),
                "delta_median_large": large.get("delta_median"),
                "direction_tiny": tiny.get("direction"),
                "n": r.get("n"),
                "p90_p50": r.get("p90_p50"),
                "population": r.get("population"),
                "urban_share": r.get("urban_share"),
                "median_unit_price": r.get("median_unit_price"),
                "direction_within": w.get("direction"),
                "delta_median_within": w.get("delta_median"),
                "ci_lo_within": w.get("ci_lo"),
                "ci_hi_within": w.get("ci_hi"),
                "within_vs_cell": r.get("within_vs_cell"),
                "n_dongs_both": w.get("n_dongs_both"),
                "within_reason": w.get("reason"),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)


def mark_plan_after_phase3(payload: dict[str, Any]) -> dict[str, Any]:
    return mark_plan_paused(payload)


def attach_phase3_crosstab(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("phase2_rows") or [])
    phase3 = dict(payload.get("phase3") or {})
    phase3["by_type_category"] = type_category_crosstab(rows)
    out = dict(payload)
    out["phase3"] = phase3
    return out


def mark_plan_paused(payload: dict[str, Any]) -> dict[str, Any]:
    nxt = list(payload.get("next") or [])
    by_id = {item.get("id"): item for item in nxt}
    for item in nxt:
        if item.get("id") in {"gap-where", "type-jimok"}:
            item["status"] = "done"
        if item.get("id") == "zone-split":
            item["status"] = "parked"
            item["gate"] = "3차 랩 닫힘. 재개 시. 4차 회귀 아님."
        if item.get("id") == "turning-floor":
            item["status"] = "parked"
            item["gate"] = "재개 시 초소형 보조열을 본 뒤. 지금은 보류."
        if item.get("id") == "product-formula":
            item["gate"] = (
                "3차까지 랩 기록. Insight는 별도 결정. D-xxx 없음. 지금은 보류."
            )
    if "type-jimok" not in by_id:
        insert_at = next(
            (i + 1 for i, it in enumerate(nxt) if it.get("id") == "gap-where"),
            len(nxt),
        )
        nxt.insert(
            insert_at,
            {
                "id": "type-jimok",
                "status": "done",
                "title": "유형×지목 교차표",
                "ask": "높게가 도시체급×대지인지, 전·답은 체급 불문 낮게인지",
                "gate": "3차 랩 마감. 4차 회귀 아님",
            },
        )
    payload = dict(payload)
    payload["next"] = nxt
    payload["status"] = "paused"
    payload["resume"] = {
        "next_id": "paused",
        "title": "1–3차 정리 · 차후 이어서",
        "say": (
            "교차표까지 닫음. 높게=도시체급×대지(대도시·수도권 대지 높게 ~31%, 군 대지 5%). "
            "전·답은 체급 불문 낮게. Insight·제품 식 보류. 재개는 주거계 vs 농림 대지."
        ),
        "do_not": (
            "4차 회귀를 열지 않는다. 전국 −19.9%를 Insight 헤드라인으로 쓰지 않는다. "
            "대지면 광평이 비싸다로 읽지 않는다. 제품 식을 바꾸지 않는다."
        ),
        "how": (
            "재개 시 docs/lab/LAND_AREA_ELASTICITY_LAB.md §13. "
            "관리자 ?tool=area-elasticity → 3차 교차표."
        ),
    }
    answers = list(payload.get("answers") or [])
    if not any(a.get("q", "").startswith("높게는 어디서") for a in answers):
        answers.append(
            {
                "q": "높게는 어디서, 전·답은?",
                "a": (
                    "높게=도시체급×대지. 대도시·수도권 대지 높게 비율이 군 대지보다 큼. "
                    "전·답은 체급 불문 낮게. P90/P50는 그룹 간 비슷"
                ),
                "evidence": (
                    "3차 유형×지목 교차표. 대지면 광평이 비싸다로 읽지 않음. 4차 회귀 아님."
                ),
            }
        )
    payload["answers"] = answers
    limits = list(payload.get("limits") or [])
    wrap_limit = "3차까지 랩 정리. 이어서는 주거계 vs 농림 대지. Insight·4차 회귀·제품 식은 보류."
    if wrap_limit not in limits:
        limits.append(wrap_limit)
    payload["limits"] = limits
    verdict = dict(payload.get("verdict") or {})
    choices = []
    for ch in verdict.get("choices") or []:
        item = dict(ch)
        if item.get("id") == "product-formula":
            item["why"] = "3차까지 랩 기록. Insight는 별도 결정. D-xxx 없음. 지금은 보류."
        choices.append(item)
    if choices:
        verdict["choices"] = choices
        payload["verdict"] = verdict
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description="토지 면적 탄성 3차 구성")
    p.add_argument("--screen", default=str(OUT))
    p.add_argument("--boot", type=int, default=PHASE2_N_BOOT)
    p.add_argument(
        "--wrap-only",
        action="store_true",
        help="DB 없이 유형×지목 교차표를 붙이고 일시 정리",
    )
    args = p.parse_args()
    path = Path(args.screen)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if args.wrap_only:
        payload = attach_phase3_crosstab(payload)
        payload = mark_plan_paused(payload)
        write_payload(payload, path)
        xt = (payload.get("phase3") or {}).get("by_type_category") or {}
        print(f"wrap-only types={list(xt)}", flush=True)
        print(f"wrote {path}", flush=True)
        return
    csv_path = path.with_suffix(".csv")
    if payload.get("cells_csv"):
        csv_path = path.parent / str(payload["cells_csv"])
    payload = run_phase3(
        payload,
        engine_bind=engine,
        screen_csv=csv_path,
        n_boot=int(args.boot),
    )
    rows = payload.pop("_phase3_rows", [])
    payload = mark_plan_paused(payload)
    csv3 = path.parent / "land_area_elasticity_phase3.csv"
    write_phase3_csv(rows, csv3)
    payload["phase3_csv"] = csv3.name
    write_payload(payload, path)
    s = payload["phase3"]
    wd = s["within_dong"]
    print(
        f"cells={s['n_cells']} within_ok={wd['n_ok']} skip={wd['n_skip']}",
        flush=True,
    )
    print(f"wrote {path}", flush=True)
    print(f"csv {csv3}", flush=True)


if __name__ == "__main__":
    main()
