"""기존 D·F 행에 복수 K-apt 합산(세대수)과 첫 시공사+외를 채운다.

전국 재빌드 없이 snapshot 의 builder_master 로 후보를 다시 붙인다.
첫째 행을 대표값으로 쓰지 않는다. 재건축·묶음 Z 행은 건드리지 않는다.

    python -m parcel_master.apply_multi_kapt
    python -m parcel_master.apply_multi_kapt --dry-run
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
_REPO = _PIPELINE.parent
sys.path.insert(0, str(_PIPELINE))

from build_collective_building_attributes import (  # noqa: E402
    MULTI_ATTR_TIERS,
    TIER_RULE_MAP,
    build_kapt_indexes,
    match_one,
    multi_fill_allowed,
    multi_kapt_row_to_attrs,
    norm_name,
    norm_name_core,
    parse_int,
)
from collective.apply_danji_dictionary import (  # noqa: E402
    _derive,
    _load,
    _load_display_names,
    _write,
)
from parcel_master.db_utils import get_collective_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

UPDATE_SQL = text(
    """
    UPDATE collective_building_attributes SET
        danji_code = :danji_code,
        match_danji_codes = :match_danji_codes,
        approved_year = :approved_year,
        building_year = :building_year,
        year_diff = :year_diff,
        builder_raw = :builder_raw,
        developer_raw = :developer_raw,
        structure_raw = :structure_raw,
        structure_group = :structure_group,
        households = :households,
        households_sale = :households_sale,
        households_rent = :households_rent,
        dong_count = :dong_count,
        max_floor = :max_floor,
        parking_total = :parking_total,
        parking_per_household = :parking_per_household,
        danji_class = :danji_class,
        supply_type = :supply_type,
        n_tx = :n_tx
    WHERE snapshot_ym = :snapshot_ym
      AND asset_type = 'apartment'
      AND building_key = :building_key
      AND match_tier IN ('D', 'F')
    """
)


def _apply_ddl(conn) -> None:
    ddl = (_REPO / "db" / "066_cba_match_danji_codes.sql").read_text(encoding="utf-8")
    for stmt in ddl.split(";"):
        s = stmt.strip()
        if s:
            conn.execute(text(s))


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
    df["beopjungri_code"] = df["beopjungri_code"].astype(str)
    return df


def _df_candidates(conn, snapshot_ym: str) -> pd.DataFrame:
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
            SELECT building_key, match_tier, match_rule
            FROM collective_building_attributes
            WHERE snapshot_ym = :ym
              AND asset_type = 'apartment'
              AND match_tier IN ('D', 'F')
            """
        ),
        conn,
        params={"ym": snapshot_ym},
    )
    if attrs.empty:
        return attrs
    return buildings.merge(attrs, on="building_key", how="inner")


def classify_multi_fills(cands: pd.DataFrame, kapt: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"fill": [], "skip": []}
    if kapt.empty or cands.empty:
        return out
    kapt = kapt[kapt["beopjungri_code"].astype(str).str.strip() != ""].reset_index(drop=True)
    if kapt.empty:
        return out
    by_lot, by_name, by_core, names_in_bj, by_road = build_kapt_indexes(kapt)
    for cand in cands.itertuples(index=False):
        row = SimpleNamespace(
            beopjungri_code=cand.beopjungri_code,
            display_name=cand.display_name,
            lot_number=cand.lot_number,
            road_name=getattr(cand, "road_name", None),
        )
        tier_key, kapt_idxs = match_one(
            row,
            by_lot=by_lot,
            by_name=by_name,
            by_core=by_core,
            names_in_bj=names_in_bj,
            by_road=by_road,
        )
        match_tier, match_rule = TIER_RULE_MAP[tier_key]
        if match_tier not in MULTI_ATTR_TIERS or len(kapt_idxs) < 2:
            out["skip"].append(
                {
                    "building_key": cand.building_key,
                    "tx_name": cand.display_name,
                    "stored": cand.match_tier,
                    "got": match_tier,
                }
            )
            continue
        if not multi_fill_allowed(match_tier, cand.display_name, kapt, kapt_idxs):
            out["skip"].append(
                {
                    "building_key": cand.building_key,
                    "tx_name": cand.display_name,
                    "stored": cand.match_tier,
                    "got": match_tier,
                    "reason": "f_guard",
                }
            )
            continue
        attrs = multi_kapt_row_to_attrs(kapt, kapt_idxs)
        if not attrs.get("danji_code"):
            out["skip"].append(
                {"building_key": cand.building_key, "tx_name": cand.display_name, "got": match_tier}
            )
            continue
        building_year = parse_int(cand.building_year)
        approved = attrs.get("approved_year")
        year_diff = None
        if approved is not None and building_year is not None:
            year_diff = int(approved) - building_year
        rec = {
            "building_key": cand.building_key,
            "match_tier": match_tier,
            "match_rule": match_rule,
            "tx_name": cand.display_name,
            "n_tx": int(cand.n_tx),
            "building_year": building_year,
            "year_diff": year_diff,
            **attrs,
        }
        rec.pop("danji_name", None)
        out["fill"].append(rec)
    return out


_UPDATE_KEYS = (
    "building_key",
    "danji_code",
    "match_danji_codes",
    "approved_year",
    "building_year",
    "year_diff",
    "builder_raw",
    "developer_raw",
    "structure_raw",
    "structure_group",
    "households",
    "households_sale",
    "households_rent",
    "dong_count",
    "max_floor",
    "parking_total",
    "parking_per_household",
    "danji_class",
    "supply_type",
    "n_tx",
)


def _write_fills(conn, snapshot_ym: str, fills: list[dict[str, Any]]) -> int:
    n = 0
    for rec in fills:
        payload = {k: rec.get(k) for k in _UPDATE_KEYS}
        payload["snapshot_ym"] = snapshot_ym
        pph = payload.get("parking_per_household")
        if isinstance(pph, Decimal):
            payload["parking_per_household"] = float(pph)
        conn.execute(UPDATE_SQL, payload)
        n += 1
    return n


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D/F: sum K-apt households, first builder + 외")
    p.add_argument("--snapshot-ym", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-dictionary", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    engine = get_collective_engine()
    with engine.begin() as conn:
        _apply_ddl(conn)
        snapshot_ym = args.snapshot_ym or conn.execute(
            text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")
        ).scalar()
        if not snapshot_ym:
            raise SystemExit("collective_building_attributes 가 비어 있습니다")
        snapshot_ym = str(snapshot_ym).strip()
        kapt = _master_indexed(conn, snapshot_ym)
        cands = _df_candidates(conn, snapshot_ym)

    log.info("snapshot_ym=%s  kapt_indexed=%s  D/F=%s", snapshot_ym, len(kapt), len(cands))
    classified = classify_multi_fills(cands, kapt)
    fills = classified["fill"]
    log.info("fill=%s  skip=%s", len(fills), len(classified["skip"]))
    for rec in fills[:40]:
        log.info(
            "  %s %s hh=%s builder=%s codes=%s",
            rec["match_tier"],
            rec["tx_name"],
            rec.get("households"),
            rec.get("builder_raw"),
            rec.get("match_danji_codes"),
        )
    if len(fills) > 40:
        log.info("  ... %s more", len(fills) - 40)

    if args.dry_run:
        log.info("dry-run: DB not changed")
        return

    with engine.begin() as conn:
        n_upd = _write_fills(conn, snapshot_ym, fills)
    log.info("updated=%s", n_upd)

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
