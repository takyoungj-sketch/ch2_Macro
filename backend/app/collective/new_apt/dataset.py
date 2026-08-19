"""단지 × 연도 데이터셋 — 트랙 A. 품질지수 Q 없음."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.collective.hedonic.enrichment import (
    discover_ald155_dirs,
    load_ald155_uqa,
    norm_lot,
)
from app.collective.hedonic.stage2 import vintage_bin
from app.collective.new_apt.constants import (
    COARSE_UQA_CODES,
    DEFAULT_ASSET_TYPE,
    LAND_THIN_N,
    LAND_WINDOW_YEARS,
    MATCH_TIERS,
    MIN_TX_PER_CELL,
    NEW_AGE_MAX,
    SIDO_DAEJEON,
    ZONE_TYPE_COMPACT_MAP,
)


def pick_ald155_dirs(raw_root: Path, sido: str) -> list[Path]:
    """같은 시도면 토이계(최신)를 우선하고, raw addition과 이중 스캔하지 않는다."""
    all_dirs = discover_ald155_dirs(raw_root)
    dirs = [d for d in all_dirs if f"_{sido}_" in d.name or d.name.startswith(f"AL_D155_{sido}")]
    if not dirs:
        dirs = [d for d in all_dirs if sido in d.name]
    preferred = [d for d in dirs if "토이계" in str(d)]
    return preferred or dirs


def _keep_lots_from_buildings(buildings: pd.DataFrame) -> set[tuple[str, str]]:
    keep: set[tuple[str, str]] = set()
    if buildings.empty:
        return keep
    for rec in buildings[["beopjungri_code", "lot_number"]].itertuples(index=False):
        code = str(rec.beopjungri_code).zfill(10) if pd.notna(rec.beopjungri_code) else ""
        lot = norm_lot(rec.lot_number)
        if code and lot:
            keep.add((code, lot))
    return keep

log = logging.getLogger(__name__)

CELL_SQL = """
SELECT
    building_key,
    sigungu_code,
    sido_code,
    MAX(beopjungri_code) AS beopjungri_code,
    MAX(lot_number) AS lot_number,
    contract_year AS calendar_year,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY unit_price) AS y_median_unit_price,
    AVG(unit_price) AS y_mean_unit_price,
    COUNT(*)::int AS n_tx,
    MAX(building_year) AS building_year
FROM collective_transactions
WHERE is_valid = true
  AND asset_type = :asset_type
  AND unit_price IS NOT NULL AND unit_price > 0
  AND sido_code = :sido
  AND contract_year IS NOT NULL
GROUP BY building_key, sigungu_code, sido_code, contract_year
HAVING COUNT(*) >= :min_tx
"""

ATTR_SQL = """
SELECT building_key, match_tier, builder_group, structure_group,
       households, max_floor, parking_per_household, approved_year,
       building_year AS attr_building_year, danji_class, attr_quality_flags
FROM collective_building_attributes
WHERE snapshot_ym = :snap AND asset_type = :asset_type
"""


def zone_compact(label: object) -> str | None:
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return None
    s = str(label).strip().replace(" ", "")
    return ZONE_TYPE_COMPACT_MAP.get(s)


ZONE_PRIORITY = (
    "3주",
    "2주",
    "1주",
    "준주",
    "2전",
    "1전",
    "일상",
    "근상",
    "중상",
    "유상",
    "준공",
    "일공",
    "전공",
    "자녹",
    "생녹",
    "보녹",
    "계관",
    "보관",
    "생관",
    "개제",
    "농림",
    "자보",
)


def pick_specific_uqa(group: pd.DataFrame) -> pd.Series:
    sub = group[~group["uqa_code"].astype(str).str.upper().isin(COARSE_UQA_CODES)].copy()
    if sub.empty:
        return pd.Series(
            {"uqa_code": None, "uqa_label": None, "zone_resolution": "coarse_only"}
        )
    sub["zone_compact"] = sub["uqa_label"].map(zone_compact)
    mapped = sub[sub["zone_compact"].notna()]
    if mapped.empty:
        return pd.Series(
            {"uqa_code": None, "uqa_label": None, "zone_resolution": "unmapped"}
        )
    compact_n = mapped["zone_compact"].nunique()
    if compact_n == 1:
        top_c = mapped["zone_compact"].iloc[0]
        row = mapped[mapped["zone_compact"] == top_c].iloc[0]
        return pd.Series(
            {
                "uqa_code": row["uqa_code"],
                "uqa_label": row["uqa_label"],
                "zone_resolution": "exact" if mapped["uqa_code"].nunique() == 1 else "majority",
            }
        )
    vc = mapped["zone_compact"].value_counts()
    if len(vc) > 1 and int(vc.iloc[0]) > int(vc.iloc[1]):
        top_c = str(vc.index[0])
        resolution = "majority"
    else:
        present = [z for z in ZONE_PRIORITY if z in set(mapped["zone_compact"])]
        if not present:
            return pd.Series(
                {"uqa_code": None, "uqa_label": None, "zone_resolution": "mixed"}
            )
        top_c = present[0]
        resolution = "priority_tie"
    row = mapped[mapped["zone_compact"] == top_c].iloc[0]
    return pd.Series(
        {"uqa_code": row["uqa_code"], "uqa_label": row["uqa_label"], "zone_resolution": resolution}
    )


def resolve_uqa_specific(buildings: pd.DataFrame, ald155: pd.DataFrame) -> pd.DataFrame:
    work = buildings.copy()
    work["lot_number"] = work["lot_number"].map(norm_lot)
    work["beopjungri_code"] = work["beopjungri_code"].astype(str)
    if ald155.empty:
        work["uqa_code"] = None
        work["uqa_label"] = None
        work["zone_resolution"] = "missing"
        return work
    ald = ald155.copy()
    ald["lot_number"] = ald["lot_number"].map(norm_lot)
    merged = work.merge(ald, on=["beopjungri_code", "lot_number"], how="left")
    rows: list[dict] = []
    for bk, grp in merged.groupby("building_key"):
        hit = grp.dropna(subset=["uqa_code"])
        if hit.empty:
            rows.append(
                {
                    "building_key": bk,
                    "uqa_code": None,
                    "uqa_label": None,
                    "zone_resolution": "missing",
                }
            )
            continue
        picked = pick_specific_uqa(hit)
        rows.append({"building_key": bk, **picked.to_dict()})
    return work.drop(columns=["uqa_code", "uqa_label"], errors="ignore").merge(
        pd.DataFrame(rows), on="building_key", how="left"
    )


def load_cells(coll_engine: Engine, sido: str = SIDO_DAEJEON) -> pd.DataFrame:
    return pd.read_sql(
        text(CELL_SQL),
        coll_engine,
        params={"asset_type": DEFAULT_ASSET_TYPE, "sido": sido, "min_tx": MIN_TX_PER_CELL},
    )


def load_attributes(coll_engine: Engine) -> pd.DataFrame:
    with coll_engine.connect() as conn:
        snap = conn.execute(text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")).scalar()
    if not snap:
        return pd.DataFrame()
    return pd.read_sql(
        text(ATTR_SQL),
        coll_engine,
        params={"snap": snap, "asset_type": DEFAULT_ASSET_TYPE},
    )


def load_sigungu_sale_p50(coll_engine: Engine, sido: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT sigungu_code, contract_year AS calendar_year,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY unit_price) AS sale_p50
        FROM collective_transactions
        WHERE is_valid AND asset_type = :at AND sido_code = :sido
          AND unit_price > 0 AND contract_year IS NOT NULL
        GROUP BY sigungu_code, contract_year
        """
    )
    return pd.read_sql(sql, coll_engine, params={"at": DEFAULT_ASSET_TYPE, "sido": sido})


def load_sigungu_rent_p50(rent_engine: Engine, sido: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT sigungu_code, contract_year AS calendar_year,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY deposit_per_m2) AS rent_p50
        FROM rent_transactions
        WHERE is_valid AND asset_type = :at AND sido_code = :sido
          AND deposit_per_m2 > 0 AND contract_year IS NOT NULL
          AND (monthly_rent_manwon IS NULL OR monthly_rent_manwon = 0)
        GROUP BY sigungu_code, contract_year
        """
    )
    try:
        return pd.read_sql(sql, rent_engine, params={"at": DEFAULT_ASSET_TYPE, "sido": sido})
    except Exception as exc:  # noqa: BLE001
        log.warning("rent_transactions 조회 실패: %s", exc)
        return pd.DataFrame(columns=["sigungu_code", "calendar_year", "rent_p50"])


def load_land_zone_p50(land_engine: Engine, sido: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT region_code AS eup_code, zone_type, as_of_month, median AS land_p50, count AS land_n
        FROM land_upper_stats_v2
        WHERE region_level = 'eupmyeondong'
          AND region_code LIKE :pref
          AND land_category = '대'
          AND window_years = :wy
          AND zone_type <> 'ALL'
          AND median IS NOT NULL
        """
    )
    return pd.read_sql(
        sql, land_engine, params={"pref": f"{sido}%", "wy": LAND_WINDOW_YEARS}
    )


def load_eup_population(land_engine: Engine, sido: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT LEFT(admin_code, 8) AS eup_code, SUM(total_population) AS eup_population
        FROM population_stats
        WHERE admin_level = 'beopjungri'
          AND admin_code LIKE :pref
        GROUP BY 1
        """
    )
    try:
        return pd.read_sql(sql, land_engine, params={"pref": f"{sido}%"})
    except Exception as exc:  # noqa: BLE001
        log.warning("population_stats 조회 실패: %s", exc)
        return pd.DataFrame(columns=["eup_code", "eup_population"])


def _attach_land(cells: pd.DataFrame, land: pd.DataFrame) -> pd.DataFrame:
    if land.empty:
        cells["land_p50"] = np.nan
        cells["land_n"] = np.nan
        return cells
    land = land.copy()
    land["as_of_year"] = pd.to_datetime(land["as_of_month"]).dt.year
    land = land.sort_values("as_of_month").drop_duplicates(
        ["eup_code", "zone_type", "as_of_year"], keep="last"
    )
    out_p50: list[float | None] = []
    out_n: list[int | None] = []
    keyed = {
        (str(r["eup_code"]), str(r["zone_type"]), int(r["as_of_year"])): r
        for _, r in land.iterrows()
    }
    latest_year = int(land["as_of_year"].max())
    for _, r in cells.iterrows():
        eup = str(r["beopjungri_code"])[:8] if pd.notna(r.get("beopjungri_code")) else ""
        zc = r.get("zone_compact")
        year = int(r["calendar_year"]) if pd.notna(r.get("calendar_year")) else latest_year
        val, cnt = None, None
        if zc and not (isinstance(zc, float) and pd.isna(zc)):
            for y in (year, year - 1, latest_year):
                row = keyed.get((eup, str(zc), y))
                if row is not None:
                    val = float(row["land_p50"]) if pd.notna(row["land_p50"]) else None
                    cnt = int(row["land_n"]) if pd.notna(row["land_n"]) else None
                    break
        out_p50.append(val)
        out_n.append(cnt)
    cells = cells.copy()
    cells["land_p50"] = out_p50
    cells["land_n"] = out_n
    return cells


def build_complex_year_frame(
    coll_engine: Engine,
    land_engine: Engine,
    rent_engine: Engine | None,
    *,
    sido: str = SIDO_DAEJEON,
    raw_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    cells = load_cells(coll_engine, sido)
    attrs = load_attributes(coll_engine)
    sale = load_sigungu_sale_p50(coll_engine, sido)
    rent = (
        load_sigungu_rent_p50(rent_engine, sido)
        if rent_engine is not None
        else pd.DataFrame(columns=["sigungu_code", "calendar_year", "rent_p50"])
    )
    land = load_land_zone_p50(land_engine, sido)
    pop = load_eup_population(land_engine, sido)

    bld_meta = (
        cells.groupby("building_key", as_index=False)
        .agg(beopjungri_code=("beopjungri_code", "first"), lot_number=("lot_number", "first"))
    )
    dirs = pick_ald155_dirs(raw_root, sido)
    keep_lots = _keep_lots_from_buildings(bld_meta)
    log.info("AL_D155 sido=%s dirs=%s lots=%s", sido, [d.name for d in dirs], len(keep_lots))
    ald = (
        pd.concat(
            [load_ald155_uqa(d, keep_lots=keep_lots) for d in dirs],
            ignore_index=True,
        )
        if dirs
        else pd.DataFrame()
    )
    resolved = resolve_uqa_specific(bld_meta, ald if not ald.empty else pd.DataFrame(columns=["beopjungri_code", "lot_number", "uqa_code", "uqa_label"]))
    resolved["zone_compact"] = resolved["uqa_label"].map(zone_compact)

    work = cells.merge(attrs, on="building_key", how="left")
    work = work.merge(
        resolved[["building_key", "uqa_code", "uqa_label", "zone_compact", "zone_resolution"]],
        on="building_key",
        how="left",
    )
    work["approved_year"] = work["approved_year"].fillna(work.get("attr_building_year"))
    work["age"] = work["calendar_year"] - work["approved_year"].fillna(work["building_year"])
    work["vintage"] = work.apply(
        lambda r: vintage_bin(r.get("approved_year") if pd.notna(r.get("approved_year")) else r.get("building_year")),
        axis=1,
    )
    work["eup_code"] = work["beopjungri_code"].astype(str).str[:8]
    if not pop.empty:
        work = work.merge(pop, on="eup_code", how="left")
    else:
        work["eup_population"] = np.nan

    sale_lag = sale.rename(columns={"calendar_year": "lag_year", "sale_p50": "sigungu_sale_p50_lag"})
    work["lag_year"] = work["calendar_year"] - 1
    work = work.merge(sale_lag, on=["sigungu_code", "lag_year"], how="left")
    if not rent.empty:
        rent_lag = rent.rename(columns={"calendar_year": "lag_year", "rent_p50": "sigungu_rent_p50_lag"})
        work = work.merge(rent_lag, on=["sigungu_code", "lag_year"], how="left")
    else:
        work["sigungu_rent_p50_lag"] = np.nan

    work = _attach_land(work, land)
    work["zone_resolution"] = work["zone_resolution"].fillna("missing")

    report = _phase0_report(work, attrs, sido, dirs)
    return work, report


def _phase0_report(work: pd.DataFrame, attrs: pd.DataFrame, sido: str, dirs: list[Path]) -> dict[str, Any]:
    bld = work.drop_duplicates("building_key")
    abc = bld[bld["match_tier"].isin(MATCH_TIERS)] if "match_tier" in bld.columns else bld.iloc[0:0]
    builder_n = (
        abc["builder_group"].fillna("(null)").value_counts().head(25).to_dict() if not abc.empty else {}
    )
    n_ge30 = int((pd.Series(builder_n) >= 30).sum()) if builder_n else 0
    uqa = bld["zone_resolution"].value_counts().to_dict() if "zone_resolution" in bld.columns else {}
    land_ok = int(bld["land_p50"].notna().sum()) if "land_p50" in bld.columns else 0
    thin = int(((bld["land_n"].fillna(0) < LAND_THIN_N) & bld["land_p50"].notna()).sum()) if "land_n" in bld.columns else 0
    new_cells = work[work["age"].notna() & (work["age"] <= NEW_AGE_MAX)]
    return {
        "sido_code": sido,
        "n_buildings": int(work["building_key"].nunique()),
        "n_cells": int(len(work)),
        "n_cells_age_le5": int(len(new_cells)),
        "n_buildings_abc": int(abc["building_key"].nunique()) if not abc.empty else 0,
        "builder_counts_abc": {str(k): int(v) for k, v in builder_n.items()},
        "builders_ge_30": n_ge30,
        "uqa_resolution": {str(k): int(v) for k, v in uqa.items()},
        "n_buildings_land_p50": land_ok,
        "n_buildings_land_thin": thin,
        "land_join_pct": round(100.0 * land_ok / max(len(bld), 1), 2),
        "ald155_dirs": [str(d) for d in dirs],
        "notes": [
            "UQA001(도시지역)만 있으면 coarse_only — 토지 P50 미부착",
            "시군구 매매/전세 P50은 전년도(lag)",
            "시공사 단지 30 미만은 트랙 B에서 측정 불가",
        ],
    }


def persist_complex_year(engine: Engine, df: pd.DataFrame, *, sido: str, replace: bool) -> int:
    cols = [
        "sido_code",
        "sigungu_code",
        "building_key",
        "calendar_year",
        "asset_type",
        "y_median_unit_price",
        "y_mean_unit_price",
        "n_tx",
        "building_year",
        "approved_year",
        "age",
        "vintage",
        "match_tier",
        "builder_group",
        "structure_group",
        "households",
        "max_floor",
        "parking_per_household",
        "danji_class",
        "attr_quality_flags",
        "beopjungri_code",
        "lot_number",
        "uqa_code",
        "uqa_label",
        "zone_compact",
        "zone_resolution",
        "land_p50",
        "land_n",
        "sigungu_sale_p50_lag",
        "sigungu_rent_p50_lag",
        "eup_population",
    ]
    rows = df.copy()
    rows["asset_type"] = DEFAULT_ASSET_TYPE
    if "sido_code" not in rows.columns:
        rows["sido_code"] = sido
    keep = [c for c in cols if c in rows.columns]
    payload = rows[keep].replace({np.nan: None}).to_dict(orient="records")
    with engine.begin() as conn:
        if replace:
            conn.execute(
                text("DELETE FROM new_apartment_complex_year WHERE sido_code = :sido"),
                {"sido": sido},
            )
        if payload:
            ph = ", ".join(f":{c}" for c in keep)
            sql = text(
                f"INSERT INTO new_apartment_complex_year ({', '.join(keep)}) VALUES ({ph})"
            )
            for i in range(0, len(payload), 400):
                conn.execute(sql, payload[i : i + 400])
    return len(payload)


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
