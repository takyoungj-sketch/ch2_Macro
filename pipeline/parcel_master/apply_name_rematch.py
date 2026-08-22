"""시공사 없는 T/Z 단지를 법정동 안 유일 단지명으로 K-apt에 붙인다.

지번이 달라도 이름이 그 동에 하나면 A·B·E. 재건축·묶음은 건너뛴다.

    python -m parcel_master.apply_name_rematch
    python -m parcel_master.apply_name_rematch --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
from sqlalchemy import text

_PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PIPELINE))

from build_collective_building_attributes import (  # noqa: E402
    TIER_RULE_MAP,
    build_kapt_indexes,
    match_one,
    norm_name,
    norm_name_core,
    parse_approved_year,
    parse_int,
)
from collective.apply_danji_dictionary import (  # noqa: E402
    _derive,
    _load,
    _load_display_names,
    _write,
)
from parcel_master.apply_pnu_unique import (  # noqa: E402
    INSERT_SQL,
    UPDATE_SQL,
    master_to_attrs,
)
from parcel_master.db_utils import get_collective_engine  # noqa: E402
from parcel_master.pnu_unique import pnu_unique_skip_reason  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OPEN_TIERS = frozenset({"T", "Z"})
E_MIN_NAME = 6


def _e_name_long_enough(tx_name: object, kapt_name: object) -> bool:
    a, b = norm_name(tx_name), norm_name(kapt_name)
    shorter = a if len(a) <= len(b) else b
    return len(shorter) >= E_MIN_NAME


def _master_indexed(conn, snapshot_ym: str) -> pd.DataFrame:
    df = pd.read_sql(
        text(
            """
            SELECT danji_code, danji_name, beopjungri_code, lot_key, approved_date,
                   builder_raw, developer_raw, structure_raw, households, households_sale,
                   households_rent, dong_count, max_floor, parking_total, danji_class,
                   supply_type
            FROM builder_master
            WHERE snapshot_ym = :ym
              AND beopjungri_code IS NOT NULL
              AND btrim(beopjungri_code) <> ''
            """
        ),
        conn,
        params={"ym": snapshot_ym},
    )
    if df.empty:
        return df
    df = df.reset_index(drop=True)
    df["name_key"] = df["danji_name"].map(norm_name)
    df["name_core"] = df["danji_name"].map(norm_name_core)
    df["lot_key"] = df["lot_key"].fillna("").astype(str)
    return df


def _open_candidates(conn, snapshot_ym: str) -> pd.DataFrame:
    buildings = pd.read_sql(
        text(
            """
            SELECT building_key, MAX(display_name) AS display_name,
                   MODE() WITHIN GROUP (ORDER BY beopjungri_code) AS beopjungri_code,
                   MODE() WITHIN GROUP (ORDER BY lot_number) AS lot_number,
                   COUNT(*) AS n_tx,
                   MAX(building_year) AS building_year
            FROM collective_transactions
            WHERE is_valid AND asset_type = 'apartment'
            GROUP BY building_key
            """
        ),
        conn,
    )
    attrs = pd.read_sql(
        text(
            """
            SELECT building_key, match_tier, match_rule, danji_code
            FROM collective_building_attributes
            WHERE snapshot_ym = :ym AND asset_type = 'apartment'
            """
        ),
        conn,
        params={"ym": snapshot_ym},
    )
    merged = buildings.merge(attrs, on="building_key", how="left")
    merged["has_attr_row"] = merged["match_tier"].notna()
    tier = merged["match_tier"].fillna("Z").astype(str)
    return merged.loc[tier.isin(OPEN_TIERS)].copy()


def classify_name_fills(cands: pd.DataFrame, kapt: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"fill": [], "skip": [], "rebuild": [], "bundle": []}
    if kapt.empty or cands.empty:
        return out
    kapt = kapt[kapt["beopjungri_code"].astype(str).str.strip() != ""].reset_index(drop=True)
    if kapt.empty:
        return out
    by_lot, by_name, by_core, names_in_bj = build_kapt_indexes(kapt)
    for cand in cands.itertuples(index=False):
        row = SimpleNamespace(
            beopjungri_code=cand.beopjungri_code,
            display_name=cand.display_name,
            lot_number=cand.lot_number,
        )
        tier_key, kapt_idxs = match_one(
            row, by_lot=by_lot, by_name=by_name, by_core=by_core, names_in_bj=names_in_bj
        )
        kapt_idx = kapt_idxs[0] if len(kapt_idxs) == 1 else None
        match_tier, match_rule = TIER_RULE_MAP[tier_key]
        if match_tier not in {"A", "B", "E"} or kapt_idx is None:
            out["skip"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            continue
        master = kapt.iloc[kapt_idx]
        kapt_name = master["danji_name"]
        if match_tier == "E" and not _e_name_long_enough(cand.display_name, kapt_name):
            out["skip"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            continue
        skip = pnu_unique_skip_reason(
            tx_name=cand.display_name,
            kapt_name=kapt_name,
            approved_year=parse_approved_year(master["approved_date"]),
            building_year=parse_int(cand.building_year),
        )
        if skip == "rebuild":
            out["rebuild"].append(
                {"building_key": cand.building_key, "tx_name": cand.display_name, "kapt_name": kapt_name}
            )
            continue
        if skip == "bundle":
            out["bundle"].append(
                {"building_key": cand.building_key, "tx_name": cand.display_name, "kapt_name": kapt_name}
            )
            continue
        rec = _fill_from_master(cand, master, match_tier=match_tier, match_rule=match_rule)
        out["fill"].append(rec)
    return out


def _fill_from_master(cand: Any, master: Any, *, match_tier: str, match_rule: str) -> dict[str, Any]:
    ns = master if hasattr(master, "danji_code") else SimpleNamespace(**dict(master))
    attrs = master_to_attrs(ns)
    building_year = parse_int(cand.building_year)
    approved = attrs["approved_year"]
    year_diff = None
    if approved is not None and building_year is not None:
        year_diff = approved - building_year
    return {
        "building_key": cand.building_key,
        "danji_code": attrs["danji_code"],
        "match_tier": match_tier,
        "match_rule": match_rule,
        "approved_year": approved,
        "building_year": building_year,
        "year_diff": year_diff,
        "builder_raw": attrs["builder_raw"],
        "developer_raw": attrs["developer_raw"],
        "structure_raw": attrs["structure_raw"],
        "structure_group": attrs["structure_group"],
        "households": attrs["households"],
        "households_sale": attrs["households_sale"],
        "households_rent": attrs["households_rent"],
        "dong_count": attrs["dong_count"],
        "max_floor": attrs["max_floor"],
        "parking_total": attrs["parking_total"],
        "parking_per_household": attrs["parking_per_household"],
        "danji_class": attrs["danji_class"],
        "supply_type": attrs["supply_type"],
        "n_tx": int(cand.n_tx),
        "tx_name": cand.display_name,
        "kapt_name": attrs["kapt_name"],
        "has_attr_row": bool(cand.has_attr_row),
    }


def _write_fills(conn, snapshot_ym: str, fills: list[dict[str, Any]]) -> tuple[int, int]:
    n_upd = 0
    n_ins = 0
    for rec in fills:
        payload = {k: rec[k] for k in rec if k not in {"tx_name", "kapt_name", "has_attr_row"}}
        payload["snapshot_ym"] = snapshot_ym
        pph = payload.get("parking_per_household")
        if isinstance(pph, Decimal):
            payload["parking_per_household"] = float(pph)
        if rec["has_attr_row"]:
            conn.execute(UPDATE_SQL, payload)
            n_upd += 1
        else:
            conn.execute(INSERT_SQL, payload)
            n_ins += 1
    return n_upd, n_ins


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="T/Z: unique-name K-apt fill")
    p.add_argument("--snapshot-ym", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-dictionary", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    engine = get_collective_engine()
    with engine.connect() as conn:
        snapshot_ym = args.snapshot_ym or conn.execute(
            text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")
        ).scalar()
        if not snapshot_ym:
            raise SystemExit("collective_building_attributes 가 비어 있습니다")
        snapshot_ym = str(snapshot_ym).strip()
        kapt = _master_indexed(conn, snapshot_ym)
        cands = _open_candidates(conn, snapshot_ym)

    log.info("snapshot_ym=%s  kapt_indexed=%s  T/Z=%s", snapshot_ym, len(kapt), len(cands))
    classified = classify_name_fills(cands, kapt)
    fills = classified["fill"]
    log.info(
        "fill=%s  skip=%s  rebuild=%s  bundle=%s",
        len(fills),
        len(classified["skip"]),
        len(classified["rebuild"]),
        len(classified["bundle"]),
    )
    for rec in fills[:40]:
        log.info(
            "  %s %s → %s  %s",
            rec["match_tier"],
            rec["tx_name"],
            rec["kapt_name"],
            rec.get("builder_raw"),
        )
    if len(fills) > 40:
        log.info("  ... %s more", len(fills) - 40)

    if args.dry_run:
        log.info("dry-run: DB not changed")
        return

    with engine.begin() as conn:
        n_upd, n_ins = _write_fills(conn, snapshot_ym, fills)
    log.info("updated=%s  inserted=%s", n_upd, n_ins)

    if args.skip_dictionary or not fills:
        return
    with engine.begin() as conn:
        df = _load(conn, snapshot_ym)
        names = _load_display_names(conn, df["building_key"].astype(str).tolist())
        derived = _derive(df, names)
        n_dict = _write(conn, derived)
    log.info("dictionary rows=%s", n_dict)


if __name__ == "__main__":
    main()
