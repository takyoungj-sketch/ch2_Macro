"""토지 회귀 표본 확장 1차 실행.

backend에서:
  python -m app.land_lab.regression_augment_run

제품 회귀는 바꾸지 않는다. 명단 JSON을 회귀 전에 먼저 쓴다.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.db import SessionLocal
from app.land_lab.area_elasticity_screen import latest_as_of_month, period_bounds_for_window
from app.land_lab.regression_augment import (
    SEED,
    CellCount,
    add_counts,
    apply_assessed_rows,
    best_model,
    compare_to_m0,
    evaluate_b,
    evaluate_cv,
    evaluate_temporal,
    experiment_b_quota,
    pick_twin,
    prepare_frame,
    select_round1,
    _modal_other_key,
)
from app.land_lab.road_jimok_ratio import canonical_jimok, canonical_zone
from app.ledger_region_sql import beopjungri_eq_or_in, execute_expanding
from app.region_canonical import region_codes_join_on_canonical
from app.region_sido import is_retired_sido_code, is_retired_sido_name

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "land_regression_augment_round1.json"
OUT_ASSESSED = ROOT / "docs" / "lab" / "land_regression_augment_assessed.json"


def _cells_sql(join_sql: str) -> str:
    return f"""
        SELECT
            btrim(r.eupmyeondong_code::text) AS eup_code,
            btrim(r.eupmyeondong_name::text) AS eup_name,
            btrim(r.sido_code::text) AS sido_code,
            btrim(r.sido_name::text) AS sido_name,
            btrim(r.sigungu_name::text) AS sigungu_name,
            btrim(lt.zone_type_resolved::text) AS zone_type,
            btrim(lt.land_category_resolved::text) AS land_category,
            COUNT(*)::int AS n
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND lt.contract_date IS NOT NULL
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.unit_price_per_sqm > 0
          AND btrim(COALESCE(lt.zone_type_resolved::text, '')) <> ''
          AND btrim(COALESCE(lt.land_category_resolved::text, '')) <> ''
          AND btrim(COALESCE(r.eupmyeondong_code::text, '')) <> ''
        GROUP BY 1, 2, 3, 4, 5, 6, 7
    """


def _tx_sql(join_sql: str, eup_pred: str) -> str:
    return f"""
        SELECT
            lt.id::bigint AS id,
            lt.contract_date::date AS contract_date,
            lt.contract_year::int AS contract_year,
            btrim(r.eupmyeondong_code::text) AS eup_code,
            btrim(lt.zone_type_resolved::text) AS zone_type,
            btrim(lt.land_category_resolved::text) AS land_category,
            lt.area_sqm::float8 AS area_sqm,
            lt.unit_price_per_sqm::float8 AS unit_price_per_sqm,
            lt.road_condition AS road_condition,
            lt.deal_type AS deal_type
        FROM land_transactions_resolved lt
        {join_sql}
        WHERE {eup_pred}
          AND lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND lt.contract_date IS NOT NULL
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.unit_price_per_sqm > 0
          AND btrim(COALESCE(lt.zone_type_resolved::text, '')) <> ''
          AND btrim(COALESCE(lt.land_category_resolved::text, '')) <> ''
    """


def fetch_cells(db, period_start: date, period_end: date) -> list[CellCount]:
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    rows = db.execute(
        text(_cells_sql(join_sql)),
        {"p_start": period_start, "p_end": period_end},
    ).mappings().all()
    bucket: dict[tuple, CellCount] = {}
    for row in rows:
        if is_retired_sido_code(str(row["sido_code"] or "")):
            continue
        if is_retired_sido_name(str(row["sido_name"] or "")):
            continue
        zone = canonical_zone(row["zone_type"])
        jimok = canonical_jimok(row["land_category"])
        if not zone or not jimok:
            continue
        key = (row["eup_code"], zone, jimok)
        prev = bucket.get(key)
        n = int(row["n"])
        if prev is None:
            bucket[key] = CellCount(
                eup_code=str(row["eup_code"]),
                eup_name=str(row["eup_name"] or ""),
                sido_code=str(row["sido_code"] or ""),
                sido_name=str(row["sido_name"] or ""),
                sigungu_name=str(row["sigungu_name"] or ""),
                zone=zone,
                jimok=jimok,
                n=n,
            )
        else:
            bucket[key] = CellCount(
                eup_code=prev.eup_code,
                eup_name=prev.eup_name,
                sido_code=prev.sido_code,
                sido_name=prev.sido_name,
                sigungu_name=prev.sigungu_name,
                zone=prev.zone,
                jimok=prev.jimok,
                n=prev.n + n,
            )
    return list(bucket.values())


def fetch_transactions(db, codes: list[str], period_start: date, period_end: date) -> pd.DataFrame:
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    pred, params = beopjungri_eq_or_in(codes, column="btrim(r.eupmyeondong_code::text)")
    params.update({"p_start": period_start, "p_end": period_end})
    rows = execute_expanding(db, _tx_sql(join_sql, pred), params).mappings().all()
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return frame
    frame["zone"] = frame["zone_type"].map(lambda v: canonical_zone(str(v)))
    frame["jimok"] = frame["land_category"].map(lambda v: canonical_jimok(str(v)))
    frame["contract_date"] = pd.to_datetime(frame["contract_date"])
    frame["road_condition"] = frame["road_condition"].fillna("")
    frame["deal_type"] = frame["deal_type"].fillna("")
    return frame


def _public_cell(cell: CellCount, twin: tuple[CellCount, float] | None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "eup_code": cell.eup_code,
        "eup_name": cell.eup_name,
        "sido_name": cell.sido_name,
        "sigungu_name": cell.sigungu_name,
        "zone": cell.zone,
        "jimok": cell.jimok,
        "n": cell.n,
    }
    if twin is None:
        item["twin"] = None
    else:
        other, dist = twin
        item["twin"] = {
            "eup_code": other.eup_code,
            "eup_name": other.eup_name,
            "sigungu_name": other.sigungu_name,
            "n_same_cell": other.n,
            "js_divergence": round(float(dist), 4),
        }
    return item


def _json_ready(value: Any) -> Any:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return round(value, 4)
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


def _write(payload: dict[str, Any], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _region_block(kind: str, frame: pd.DataFrame, anchor: CellCount, rows: dict) -> dict[str, Any]:
    compared = compare_to_m0(rows)
    counts = add_counts(frame, anchor)
    return {
        "type": kind,
        "n_target": counts.get("M0"),
        "n_add": {model: counts.get(model) for model in counts if model != "M0"},
        "models": compared,
        "reading": best_model(compared),
    }


def run() -> dict[str, Any]:
    db = SessionLocal()
    try:
        db.execute(text("SET statement_timeout = '600000'"))
        as_of = latest_as_of_month(db)
        period_start, period_end = period_bounds_for_window(as_of, 5)
        cells = fetch_cells(db, period_start, period_end)
        chosen, pool_counts = select_round1(cells, SEED)
        twins = {kind: pick_twin(cells, cell) if cell is not None else None for kind, cell in chosen.items()}
        payload: dict[str, Any] = {
            "run_id": "land-regression-augment-round1",
            "protocol": "docs/lab/LAND_REGRESSION_AUGMENT_LAB.md",
            "product_change": False,
            "status": "roster",
            "seed": SEED,
            "as_of_month": as_of.isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "window_years": 5,
            "candidate_counts": pool_counts,
            "roster": {
                kind: None if cell is None else _public_cell(cell, twins[kind])
                for kind, cell in chosen.items()
            },
        }
        _write(payload)
        print("roster written", {k: (None if v is None else v.n) for k, v in chosen.items()}, flush=True)

        needed: list[str] = []
        for kind, cell in chosen.items():
            if cell is None:
                continue
            needed.append(cell.eup_code)
            twin = twins[kind]
            if twin is not None:
                needed.append(twin[0].eup_code)
        tx = fetch_transactions(db, sorted(set(needed)), period_start, period_end)
        experiment_a = []
        experiment_b = []
        temporal = []
        for kind, cell in chosen.items():
            if cell is None:
                block = {"type": kind, "status": "unavailable", "reason": "선정 없음"}
                experiment_a.append(block)
                experiment_b.append(block)
                temporal.append(block)
                continue
            local_codes = {cell.eup_code}
            twin = twins[kind]
            if twin is not None:
                local_codes.add(twin[0].eup_code)
            part = tx.loc[tx["eup_code"].isin(local_codes)].copy()
            m1 = _modal_other_key(part.loc[part["eup_code"] == cell.eup_code], cell)
            frame = prepare_frame(part, cell, None if twin is None else twin[0].eup_code, m1)
            print("fit", kind, cell.eup_name, cell.zone, cell.jimok, "n", int(frame["is_target"].sum()), flush=True)
            natural = evaluate_cv(frame, cell, with_level=True)
            no_dummy = evaluate_cv(frame, cell, with_level=False)
            experiment_a.append(
                {
                    **_region_block(kind, frame, cell, natural),
                    "no_dummy": compare_to_m0(no_dummy),
                }
            )
            counts = add_counts(frame, cell)
            quota = experiment_b_quota(counts)
            if quota is None:
                experiment_b.append({"type": kind, "status": "unavailable", "reason": "공통 할당량이 15건 미만입니다.", "n_add": counts})
            else:
                matched = evaluate_b(frame, cell, quota)
                experiment_b.append({**_region_block(kind, frame, cell, matched), "quota": quota})
            temporal.append(_region_block(kind, frame, cell, evaluate_temporal(frame, cell)))
        payload["status"] = "estimated"
        payload["experiment_a"] = experiment_a
        payload["experiment_b"] = experiment_b
        payload["temporal"] = temporal
        payload["summary"] = _summary(experiment_a)
        _write(payload)
        return payload
    finally:
        db.close()


def _summary(blocks: list[dict]) -> dict[str, Any]:
    winners = []
    improved = {model: 0 for model in ("M1", "M2", "M3", "M4", "M5")}
    adoptable = []
    for block in blocks:
        reading = block.get("reading") or {}
        winners.append({"type": block.get("type"), "mape_winner": reading.get("mape_winner"), "adoptable": reading.get("adoptable")})
        models = block.get("models") or {}
        for model, count_key in improved.items():
            row = models.get(model) or {}
            if row.get("status") == "estimated" and row.get("delta_pp") is not None and row["delta_pp"] < 0:
                improved[model] += 1
        adoptable.append(reading.get("adoptable"))
    return {"by_region": winners, "improved_region_counts": improved, "adoptable_by_region": adoptable}


def _cell_from_roster(item: dict[str, Any]) -> CellCount:
    return CellCount(
        eup_code=str(item["eup_code"]),
        eup_name=str(item["eup_name"]),
        sido_code="",
        sido_name=str(item["sido_name"]),
        sigungu_name=str(item["sigungu_name"]),
        zone=str(item["zone"]),
        jimok=str(item["jimok"]),
        n=int(item["n"]),
    )


def _tx_assessed_sql(join_sql: str, eup_pred: str) -> str:
    return f"""
        SELECT
            lt.id::bigint AS id,
            lt.contract_date::date AS contract_date,
            lt.contract_year::int AS contract_year,
            btrim(r.eupmyeondong_code::text) AS eup_code,
            btrim(lt.zone_type_resolved::text) AS zone_type,
            btrim(lt.land_category_resolved::text) AS land_category,
            lt.area_sqm::float8 AS area_sqm,
            lt.unit_price_per_sqm::float8 AS unit_price_per_sqm,
            lt.road_condition AS road_condition,
            lt.deal_type AS deal_type,
            COALESCE(lt.is_partial_ownership, FALSE) AS is_partial_ownership,
            tl.official_price_won::float8 AS official_price_won
        FROM land_transactions_resolved lt
        {join_sql}
        LEFT JOIN land_transaction_trait_link tl
          ON tl.transaction_hash = lt.transaction_hash
        WHERE {eup_pred}
          AND lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND lt.contract_date IS NOT NULL
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          AND lt.area_sqm > 0
          AND lt.unit_price_per_sqm > 0
          AND btrim(COALESCE(lt.zone_type_resolved::text, '')) <> ''
          AND btrim(COALESCE(lt.land_category_resolved::text, '')) <> ''
    """


def fetch_transactions_assessed(db, codes: list[str], period_start: date, period_end: date) -> pd.DataFrame:
    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)
    pred, params = beopjungri_eq_or_in(codes, column="btrim(r.eupmyeondong_code::text)")
    params.update({"p_start": period_start, "p_end": period_end})
    rows = execute_expanding(db, _tx_assessed_sql(join_sql, pred), params).mappings().all()
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return frame
    frame = frame.drop_duplicates(subset=["id"], keep="first")
    frame["zone"] = frame["zone_type"].map(lambda v: canonical_zone(str(v)))
    frame["jimok"] = frame["land_category"].map(lambda v: canonical_jimok(str(v)))
    frame["contract_date"] = pd.to_datetime(frame["contract_date"])
    frame["road_condition"] = frame["road_condition"].fillna("")
    frame["deal_type"] = frame["deal_type"].fillna("")
    return frame


def run_assessed() -> dict[str, Any]:
    """1차와 같은 다섯 칸에 개별공시지가 로그를 더한 식. 명단은 다시 뽑지 않는다."""
    baseline = json.loads(OUT.read_text(encoding="utf-8"))
    period_start = date.fromisoformat(baseline["period_start"])
    period_end = date.fromisoformat(baseline["period_end"])
    db = SessionLocal()
    try:
        db.execute(text("SET statement_timeout = '600000'"))
        roster = baseline["roster"]
        needed: list[str] = []
        for item in roster.values():
            if not item:
                continue
            needed.append(str(item["eup_code"]))
            twin = item.get("twin") or {}
            if twin.get("eup_code"):
                needed.append(str(twin["eup_code"]))
        tx = fetch_transactions_assessed(db, sorted(set(needed)), period_start, period_end)
        payload: dict[str, Any] = {
            "run_id": "land-regression-augment-assessed",
            "protocol": "docs/lab/LAND_REGRESSION_AUGMENT_LAB.md",
            "baseline_run_id": baseline.get("run_id"),
            "product_change": False,
            "status": "estimated",
            "seed": SEED,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "window_years": 5,
            "formula": "1차 공통식 + log(개별공시지가 원/㎡). 지분 거래와 공시지가가 없는 행은 제외.",
            "roster": roster,
        }
        experiment_a = []
        experiment_b = []
        temporal = []
        for kind, item in roster.items():
            if not item:
                block = {"type": kind, "status": "unavailable", "reason": "선정 없음"}
                experiment_a.append(block)
                experiment_b.append(block)
                temporal.append(block)
                continue
            cell = _cell_from_roster(item)
            twin_code = str((item.get("twin") or {}).get("eup_code") or "") or None
            local_codes = {cell.eup_code}
            if twin_code:
                local_codes.add(twin_code)
            part = tx.loc[tx["eup_code"].isin(local_codes)].copy()
            before = part.loc[
                (part["eup_code"] == cell.eup_code) & (part["zone"] == cell.zone) & (part["jimok"] == cell.jimok)
            ]
            kept, cover = apply_assessed_rows(part)
            frame = prepare_frame(kept, cell, twin_code, _modal_other_key(kept.loc[kept["eup_code"] == cell.eup_code], cell))
            n_target = int(frame["is_target"].sum()) if len(frame) else 0
            print("fit assessed", kind, cell.eup_name, "n", n_target, "cover", cover["n_after"], flush=True)
            coverage = {
                "n_target_before": int(len(before)),
                "n_target_after": n_target,
                "n_rows_before": cover["n_before"],
                "n_rows_after": cover["n_after"],
                "n_partial": cover["n_partial"],
            }
            if n_target < 15:
                block = {"type": kind, "status": "unavailable", "reason": "공시지가가 있는 원래 칸이 15건 미만입니다.", "coverage": coverage}
                experiment_a.append(block)
                experiment_b.append(block)
                temporal.append(block)
                continue
            natural = evaluate_cv(frame, cell, with_level=True, use_assessed=True)
            no_dummy = evaluate_cv(frame, cell, with_level=False, use_assessed=True)
            experiment_a.append(
                {
                    **_region_block(kind, frame, cell, natural),
                    "coverage": coverage,
                    "no_dummy": compare_to_m0(no_dummy),
                }
            )
            counts = add_counts(frame, cell)
            quota = experiment_b_quota(counts)
            if quota is None:
                experiment_b.append({"type": kind, "status": "unavailable", "reason": "공통 할당량이 15건 미만입니다.", "n_add": counts, "coverage": coverage})
            else:
                matched = evaluate_b(frame, cell, quota, use_assessed=True)
                experiment_b.append({**_region_block(kind, frame, cell, matched), "quota": quota, "coverage": coverage})
            temporal.append({**_region_block(kind, frame, cell, evaluate_temporal(frame, cell, use_assessed=True)), "coverage": coverage})
        payload["experiment_a"] = experiment_a
        payload["experiment_b"] = experiment_b
        payload["temporal"] = temporal
        payload["summary"] = _summary(experiment_a)
        _write(payload, OUT_ASSESSED)
        return payload
    finally:
        db.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--assessed", action="store_true")
    args = parser.parse_args()
    if args.assessed:
        payload = run_assessed()
        print("wrote", OUT_ASSESSED, payload.get("status"), flush=True)
    else:
        payload = run()
        print("wrote", OUT, payload.get("status"), flush=True)


if __name__ == "__main__":
    main()
