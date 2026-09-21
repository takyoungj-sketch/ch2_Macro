"""2차: 적격칸 모집단에서 비교가능칸만 광평(본)·초소형(보조) vs 몸통 단가 비교.

OLS 반복 아님. 선정은 n만 (단가·Δ·β 금지). 판정은 중위 Δ + 부트스트랩 CI.
재실행 (backend에서):
  python -m app.land_lab.area_elasticity_gap
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import engine
from app.land_lab.area_elasticity import (
    AREA_MAX_SQM,
    LAND_CATEGORIES,
    PHASE2_N_BODY_MIN,
    PHASE2_N_BOOT,
    PHASE2_N_LARGE_MIN,
    PHASE2_N_TINY_MIN,
    REGION_TYPES,
    TINY_FLOOR_SQM,
)
from app.land_lab.area_elasticity_screen import (
    OUT,
    period_bounds_for_window,
    write_payload,
)
from app.ledger_region_sql import beopjungri_eq_or_in, execute_expanding
from app.region_canonical import region_codes_join_on_canonical

DIR_LOWER = "lower"
DIR_NEUTRAL = "neutral"
DIR_HIGHER = "higher"
DIR_SKIP = "skip"


def tiny_floor_sqm(land_category: str) -> float:
    return float(TINY_FLOOR_SQM.get((land_category or "").strip(), 30.0))


def comparable_ok(*, n_body: int, n_large: int) -> bool:
    """본실험 게이트. 단가 없음."""
    return int(n_body) >= PHASE2_N_BODY_MIN and int(n_large) >= PHASE2_N_LARGE_MIN


def tiny_aux_ok(*, n_tiny: int) -> bool:
    return int(n_tiny) >= PHASE2_N_TINY_MIN


def direction_from_ci(lo: float | None, hi: float | None) -> str:
    if lo is None or hi is None:
        return DIR_SKIP
    if hi < 0:
        return DIR_LOWER
    if lo > 0:
        return DIR_HIGHER
    return DIR_NEUTRAL


def delta_mean(tail: np.ndarray, body: np.ndarray) -> float | None:
    if tail.size == 0 or body.size == 0:
        return None
    mb = float(np.mean(body))
    if mb <= 0:
        return None
    return float(np.mean(tail) / mb - 1.0)


def delta_median(tail: np.ndarray, body: np.ndarray) -> float | None:
    if tail.size == 0 or body.size == 0:
        return None
    mb = float(np.median(body))
    if mb <= 0:
        return None
    return float(np.median(tail) / mb - 1.0)


def bootstrap_delta_median(
    tail: np.ndarray,
    body: np.ndarray,
    *,
    n_boot: int = PHASE2_N_BOOT,
    rng: np.random.Generator,
) -> tuple[float | None, float | None]:
    if tail.size == 0 or body.size == 0 or n_boot < 1:
        return None, None
    ia = rng.integers(0, tail.size, size=(n_boot, tail.size))
    ib = rng.integers(0, body.size, size=(n_boot, body.size))
    med_t = np.median(tail[ia], axis=1)
    med_b = np.median(body[ib], axis=1)
    ok = med_b > 0
    if not np.any(ok):
        return None, None
    deltas = med_t[ok] / med_b[ok] - 1.0
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    return float(lo), float(hi)


def _quantiles(area: np.ndarray) -> tuple[float, float, float]:
    p25, p75, p90 = np.quantile(area, [0.25, 0.75, 0.90])
    return float(p25), float(p75), float(p90)


def assign_bins(
    area: np.ndarray,
    *,
    land_category: str,
) -> dict[str, Any]:
    """광평 우선. 하한 미만은 초소형·몸통에서 제외하고 n_below_floor만."""
    n = int(area.size)
    if n == 0:
        return {
            "p25": None,
            "p75": None,
            "p90": None,
            "tiny": np.zeros(0, dtype=bool),
            "body": np.zeros(0, dtype=bool),
            "large": np.zeros(0, dtype=bool),
            "n_below_floor": 0,
            "n_tiny": 0,
            "n_body": 0,
            "n_large": 0,
        }
    p25, p75, p90 = _quantiles(area)
    floor = tiny_floor_sqm(land_category)
    large = area >= p90
    below = area < floor
    tiny = (area <= p25) & ~below & ~large
    body = (area > p25) & (area <= p75) & ~below & ~large
    return {
        "p25": p25,
        "p75": p75,
        "p90": p90,
        "tiny": tiny,
        "body": body,
        "large": large,
        "n_below_floor": int(below.sum()),
        "n_tiny": int(tiny.sum()),
        "n_body": int(body.sum()),
        "n_large": int(large.sum()),
    }


def _cell_rng(sigungu_code: str, land_category: str) -> np.random.Generator:
    raw = f"{sigungu_code.strip()}|{land_category.strip()}|20260921".encode()
    seed = int(hashlib.sha256(raw).hexdigest()[:16], 16) % (2**32)
    return np.random.default_rng(seed)


def _round(v: float | None, nd: int = 4) -> float | None:
    if v is None or (isinstance(v, float) and v != v):
        return None
    return round(float(v), nd)


def _pack_arm(
    prices_tail: np.ndarray,
    prices_body: np.ndarray,
    *,
    rng: np.random.Generator,
    n_boot: int,
) -> dict[str, Any]:
    d_mean = delta_mean(prices_tail, prices_body)
    d_med = delta_median(prices_tail, prices_body)
    lo, hi = bootstrap_delta_median(prices_tail, prices_body, n_boot=n_boot, rng=rng)
    direction = direction_from_ci(lo, hi)
    return {
        "delta_mean": _round(d_mean),
        "delta_median": _round(d_med),
        "ci_lo": _round(lo),
        "ci_hi": _round(hi),
        "direction": direction,
        "median_tail": _round(float(np.median(prices_tail)), 2) if prices_tail.size else None,
        "median_body": _round(float(np.median(prices_body)), 2) if prices_body.size else None,
        "mean_tail": _round(float(np.mean(prices_tail)), 2) if prices_tail.size else None,
        "mean_body": _round(float(np.mean(prices_body)), 2) if prices_body.size else None,
    }


def compare_cell(
    rows: list[dict[str, Any]],
    *,
    land_category: str,
    sigungu_code: str = "",
    n_boot: int = PHASE2_N_BOOT,
) -> dict[str, Any]:
    """한 칸. comparable=False 여도 n은 기록 (선정 점검)."""
    area = np.array([float(r["area_sqm"]) for r in rows], dtype=float)
    price = np.array([float(r["unit_price_per_sqm"]) for r in rows], dtype=float)
    ok = np.isfinite(area) & np.isfinite(price) & (area > 0) & (price > 0)
    area, price = area[ok], price[ok]
    bins = assign_bins(area, land_category=land_category)
    n_body, n_large, n_tiny = bins["n_body"], bins["n_large"], bins["n_tiny"]
    comparable = comparable_ok(n_body=n_body, n_large=n_large)
    tiny_ok = tiny_aux_ok(n_tiny=n_tiny)
    out: dict[str, Any] = {
        "n": int(area.size),
        "n_tiny": n_tiny,
        "n_body": n_body,
        "n_large": n_large,
        "n_below_floor": bins["n_below_floor"],
        "area_p25": _round(bins["p25"], 2),
        "area_p75": _round(bins["p75"], 2),
        "area_p90": _round(bins["p90"], 2),
        "comparable": comparable,
        "tiny_aux": False,
        "large": None,
        "tiny": None,
        "skip_reason": None,
    }
    if not comparable:
        reasons = []
        if n_body < PHASE2_N_BODY_MIN:
            reasons.append(f"n_body<{PHASE2_N_BODY_MIN}")
        if n_large < PHASE2_N_LARGE_MIN:
            reasons.append(f"n_large<{PHASE2_N_LARGE_MIN}")
        out["skip_reason"] = ",".join(reasons) or "not_comparable"
        return out

    rng = _cell_rng(sigungu_code, land_category)
    body_p = price[bins["body"]]
    out["large"] = _pack_arm(price[bins["large"]], body_p, rng=rng, n_boot=n_boot)
    if tiny_ok:
        out["tiny_aux"] = True
        out["tiny"] = _pack_arm(price[bins["tiny"]], body_p, rng=rng, n_boot=n_boot)
    else:
        out["tiny"] = {"direction": DIR_SKIP, "reason": f"n_tiny<{PHASE2_N_TINY_MIN}"}
    return out


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"true", "1", "yes"}


def load_eligible_from_csv(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"적격 표 없음: {csv_path}")
    out: list[dict[str, Any]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if _truthy(row.get("eligible")):
                out.append(row)
    return out


def _count_dirs(rows: list[dict[str, Any]], arm: str) -> dict[str, int]:
    c = Counter()
    for r in rows:
        pack = r.get(arm) or {}
        d = pack.get("direction") if isinstance(pack, dict) else None
        if d in {DIR_LOWER, DIR_NEUTRAL, DIR_HIGHER}:
            c[d] += 1
    return {
        "lower": int(c[DIR_LOWER]),
        "neutral": int(c[DIR_NEUTRAL]),
        "higher": int(c[DIR_HIGHER]),
        "n": int(c[DIR_LOWER] + c[DIR_NEUTRAL] + c[DIR_HIGHER]),
    }


def _crosstab(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(str(r.get(key) or ""), []).append(r)
    order = list(REGION_TYPES) if key == "region_type" else sorted(by)
    out: dict[str, dict[str, int]] = {}
    for k in order:
        grp = by.get(k) or []
        if not grp and key == "region_type":
            continue
        d = _count_dirs(grp, "large")
        d["comparable"] = len(grp)
        d["tiny_aux"] = sum(1 for r in grp if r.get("tiny_aux"))
        out[k] = d
    return out


def _median_delta(rows: list[dict[str, Any]], arm: str) -> float | None:
    vals = []
    for r in rows:
        pack = r.get(arm) or {}
        if isinstance(pack, dict) and pack.get("delta_median") is not None:
            vals.append(float(pack["delta_median"]))
    if not vals:
        return None
    return round(float(np.median(vals)), 4)


def summarize_phase2(
    *,
    n_eligible: int,
    n_skip: int,
    skip_reasons: Counter[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    large = _count_dirs(rows, "large")
    tiny_rows = [r for r in rows if r.get("tiny_aux")]
    tiny = _count_dirs(tiny_rows, "tiny")
    large_excl = large["lower"] + large["higher"]
    return {
        "n_eligible": n_eligible,
        "n_comparable": len(rows),
        "n_tiny_aux": len(tiny_rows),
        "n_skip": n_skip,
        "skip_reasons": dict(skip_reasons),
        "large": {
            **large,
            "delta_median_p50": _median_delta(rows, "large"),
            "share_ci_excl_0": round(large_excl / large["n"], 3) if large["n"] else None,
        },
        "tiny": {
            **tiny,
            "delta_median_p50": _median_delta(tiny_rows, "tiny"),
            "share_ci_excl_0": round((tiny["lower"] + tiny["higher"]) / tiny["n"], 3)
            if tiny["n"]
            else None,
        },
        "by_type": _crosstab(rows, "region_type"),
        "by_category": _crosstab(rows, "land_category"),
    }


def build_eligible_fetch_sql(join_sql: str, sigungu_pred: str) -> str:
    cats = ", ".join(f"'{c}'" for c in LAND_CATEGORIES)
    return f"""
        SELECT
            btrim(r.sigungu_code::text) AS sigungu_code,
            btrim(lt.land_category_resolved::text) AS land_category,
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


def fetch_eligible_transactions(
    db: Session,
    *,
    sigungu_codes: list[str],
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """적격 시군구 거래 1회. sigungu `=` / expanding `IN`. beopjungri ANY 금지."""
    codes = sorted({str(c).strip() for c in sigungu_codes if str(c).strip()})
    if not codes:
        return []
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    pred, extra = beopjungri_eq_or_in(
        codes,
        column="btrim(r.sigungu_code::text)",
    )
    sql = build_eligible_fetch_sql(join_sql, pred)
    params: dict[str, Any] = {
        "p_start": period_start,
        "p_end": period_end,
        "area_max": AREA_MAX_SQM,
        **extra,
    }
    rows = execute_expanding(db, sql, params).mappings().all()
    return [dict(r) for r in rows]


def _group_trades(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    by: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        key = (str(r["sigungu_code"]).strip(), str(r["land_category"]).strip())
        by.setdefault(key, []).append(
            {"area_sqm": r["area_sqm"], "unit_price_per_sqm": r["unit_price_per_sqm"]}
        )
    return by


def run_phase2(
    payload: dict[str, Any],
    *,
    engine_bind: Engine,
    cells: list[dict[str, Any]],
    n_boot: int = PHASE2_N_BOOT,
    limit: int | None = None,
) -> dict[str, Any]:
    as_of = date.fromisoformat(str(payload["as_of_month"]))
    window = int(payload["window_years"])
    period_start, period_end = period_bounds_for_window(as_of, window)
    eligible = list(cells)
    if limit is not None:
        eligible = eligible[: int(limit)]
    SessionLocal = sessionmaker(bind=engine_bind, autocommit=False, autoflush=False)
    db: Session = SessionLocal()
    comparable: list[dict[str, Any]] = []
    n_skip = 0
    skip_reasons: Counter[str] = Counter()
    try:
        codes = [str(c["sigungu_code"]) for c in eligible]
        print(f"fetch trades sigungu={len(set(codes))}", flush=True)
        grouped = _group_trades(
            fetch_eligible_transactions(
                db,
                sigungu_codes=codes,
                period_start=period_start,
                period_end=period_end,
            )
        )
        print(f"grouped cells_with_trades={len(grouped)}", flush=True)
    finally:
        db.close()

    total = len(eligible)
    for i, cell in enumerate(eligible, start=1):
        sg = str(cell["sigungu_code"]).strip()
        cat = str(cell["land_category"]).strip()
        rows = grouped.get((sg, cat), [])
        rec = compare_cell(rows, land_category=cat, sigungu_code=sg, n_boot=n_boot)
        head = {
            "sido_name": cell.get("sido_name"),
            "sigungu_name": cell.get("sigungu_name"),
            "sigungu_code": sg,
            "land_category": cat,
            "region_type": cell.get("region_type"),
            "n_screen": int(float(cell.get("n") or rec["n"])),
        }
        rec = {**head, **rec}
        if rec["comparable"]:
            comparable.append(rec)
        else:
            n_skip += 1
            skip_reasons[rec.get("skip_reason") or "not_comparable"] += 1
        if i % 50 == 0 or i == total:
            print(
                f"phase2 {i}/{total} comparable={len(comparable)} skip={n_skip}",
                flush=True,
            )

    summary = summarize_phase2(
        n_eligible=len(cells) if limit is None else len(eligible),
        n_skip=n_skip,
        skip_reasons=skip_reasons,
        rows=comparable,
    )
    if limit is None:
        summary["n_eligible"] = len(cells)
    out = dict(payload)
    out["status"] = "phase2_gap"
    out["phase2"] = summary
    out["phase2_rows"] = comparable
    return out


def _phase2_csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for r in rows:
        large = r.get("large") or {}
        tiny = r.get("tiny") or {}
        flat.append(
            {
                "sido_name": r.get("sido_name"),
                "sigungu_name": r.get("sigungu_name"),
                "sigungu_code": r.get("sigungu_code"),
                "land_category": r.get("land_category"),
                "region_type": r.get("region_type"),
                "n": r.get("n"),
                "n_tiny": r.get("n_tiny"),
                "n_body": r.get("n_body"),
                "n_large": r.get("n_large"),
                "n_below_floor": r.get("n_below_floor"),
                "area_p25": r.get("area_p25"),
                "area_p75": r.get("area_p75"),
                "area_p90": r.get("area_p90"),
                "tiny_aux": r.get("tiny_aux"),
                "delta_mean_large": large.get("delta_mean"),
                "delta_median_large": large.get("delta_median"),
                "ci_lo_large": large.get("ci_lo"),
                "ci_hi_large": large.get("ci_hi"),
                "direction_large": large.get("direction"),
                "delta_mean_tiny": tiny.get("delta_mean"),
                "delta_median_tiny": tiny.get("delta_median"),
                "ci_lo_tiny": tiny.get("ci_lo"),
                "ci_hi_tiny": tiny.get("ci_hi"),
                "direction_tiny": tiny.get("direction"),
            }
        )
    return flat


def write_phase2_csv(rows: list[dict[str, Any]], path: Path) -> None:
    flat = _phase2_csv_rows(rows)
    if not flat:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)


def mark_plan_after_phase2(payload: dict[str, Any]) -> dict[str, Any]:
    nxt = list(payload.get("next") or [])
    for item in nxt:
        if item.get("id") == "price-gap":
            item["status"] = "done"
    payload = dict(payload)
    payload["next"] = nxt
    payload["resume"] = {
        "next_id": "gap-where",
        "title": "차이 패턴의 지역 구성(3차)",
        "say": "2차는 비교가능칸의 광평 vs 몸통 중위 차이+CI다. 3차는 그 방향이 유형·지목에 모이는지 본다. |Δ|·단가로 다시 고르지 않는다.",
        "do_not": "2차 방향을 |Δ|나 시군구 단가로 재선정하지 않는다. Δ를 할인율이라 부르지 않는다. 제품 식을 바꾸지 않는다.",
        "how": "계획 SSOT docs/lab/LAND_AREA_ELASTICITY_LAB.md §12. 관리자 ?tool=area-elasticity → 2차 단가.",
    }
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description="토지 면적 탄성 2차 단가 비교")
    p.add_argument("--screen", default=str(OUT), help="1차 스냅샷 JSON")
    p.add_argument("--limit", type=int, default=0, help="적격칸 앞 n개만 (스모크)")
    p.add_argument("--boot", type=int, default=PHASE2_N_BOOT)
    args = p.parse_args()
    path = Path(args.screen)
    payload = json.loads(path.read_text(encoding="utf-8"))
    csv_path = path.with_suffix(".csv")
    if payload.get("cells_csv"):
        csv_path = path.parent / str(payload["cells_csv"])
    cells = load_eligible_from_csv(csv_path)
    limit = int(args.limit) if args.limit else None
    print(f"eligible={len(cells)} limit={limit or 'all'}", flush=True)
    payload = run_phase2(
        payload,
        engine_bind=engine,
        cells=cells,
        n_boot=int(args.boot),
        limit=limit,
    )
    if limit is None:
        payload = mark_plan_after_phase2(payload)
    csv2 = path.parent / "land_area_elasticity_phase2.csv"
    write_phase2_csv(payload.get("phase2_rows") or [], csv2)
    payload["phase2_csv"] = csv2.name
    write_payload(payload, path)
    s = payload["phase2"]
    lg = s["large"]
    print(
        f"comparable={s['n_comparable']} skip={s['n_skip']} "
        f"large lower/neutral/higher={lg['lower']}/{lg['neutral']}/{lg['higher']} "
        f"tiny_aux={s['n_tiny_aux']}",
        flush=True,
    )
    print(f"wrote {path}", flush=True)
    print(f"csv {csv2}", flush=True)


if __name__ == "__main__":
    main()
