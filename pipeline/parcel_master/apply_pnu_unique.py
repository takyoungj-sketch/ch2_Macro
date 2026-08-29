"""주소 미매칭(T·F·Z) 단지에 PNU 유일 K-apt 속성을 채운다.

전체 K-apt xlsx 재빌드 없이 현재 snapshot 의 builder_master.pnu 를 쓴다.
표제부 단지명 클러스터에 K-apt가 하나면 대표지번이 달라도 같은 단지(title_cluster).
재건축·묶음은 건너뛴다. 지역회귀 USABLE_TIERS 는 건드리지 않는다.

    python -m parcel_master.apply_pnu_unique
    python -m parcel_master.apply_pnu_unique --dry-run
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

from parcel_master.db_utils import get_collective_engine, get_parcel_engine  # noqa: E402
from parcel_master.pnu import pnu_from_tx  # noqa: E402
from parcel_master.pnu_unique import pnu_unique_skip_reason  # noqa: E402
from parcel_master.title_cluster import (  # noqa: E402
    expand_kapt_pnu_map,
    load_title_clusters,
    persist_title_clusters,
)
from build_collective_building_attributes import (  # noqa: E402
    _str_or_none,
    has_danji_code,
    load_buildings,
    parse_approved_year,
    parse_int,
    structure_group,
)
from collective.apply_danji_dictionary import (  # noqa: E402
    _derive,
    _load,
    _load_display_names,
    _write,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def master_to_attrs(row: Any) -> dict[str, Any]:
    households = parse_int(getattr(row, "households", None))
    parking_total = parse_int(getattr(row, "parking_total", None))
    parking_per = None
    if households and households > 0 and parking_total is not None:
        parking_per = round(Decimal(parking_total) / Decimal(households), 3)
    approved_year = parse_approved_year(getattr(row, "approved_date", None))
    return {
        "danji_code": _str_or_none(getattr(row, "danji_code", None)),
        "approved_year": approved_year,
        "builder_raw": _str_or_none(getattr(row, "builder_raw", None), max_len=200),
        "developer_raw": _str_or_none(getattr(row, "developer_raw", None), max_len=200),
        "structure_raw": _str_or_none(getattr(row, "structure_raw", None), max_len=60),
        "structure_group": structure_group(getattr(row, "structure_raw", None)),
        "households": households,
        "households_sale": parse_int(getattr(row, "households_sale", None)),
        "households_rent": parse_int(getattr(row, "households_rent", None)),
        "dong_count": parse_int(getattr(row, "dong_count", None)),
        "max_floor": parse_int(getattr(row, "max_floor", None)),
        "parking_total": parking_total,
        "parking_per_household": parking_per,
        "danji_class": _str_or_none(getattr(row, "danji_class", None)),
        "supply_type": _str_or_none(getattr(row, "supply_type", None)),
        "kapt_name": _str_or_none(getattr(row, "danji_name", None)),
    }


def _unique_pnu_map(conn, snapshot_ym: str) -> dict[str, Any]:
    df = pd.read_sql(
        text(
            """
            SELECT danji_code, danji_name, pnu, approved_date, builder_raw, developer_raw,
                   structure_raw, households, households_sale, households_rent,
                   dong_count, max_floor, parking_total, danji_class, supply_type,
                   sido_name, sigungu_name, beopjungri_code
            FROM builder_master
            WHERE snapshot_ym = :ym AND pnu IS NOT NULL
            """
        ),
        conn,
        params={"ym": snapshot_ym},
    )
    if df.empty:
        return {}
    counts = df.groupby("pnu").size()
    unique = df[df["pnu"].map(lambda p: int(counts[p]) == 1)]
    out: dict[str, Any] = {}
    for r in unique.itertuples(index=False):
        rec = r._asdict()
        pnu = str(rec.get("pnu") or "").strip()
        bj = str(rec.get("beopjungri_code") or "").strip()
        if bj.lower() in {"nan", "none"}:
            bj = ""
        if len(bj) != 10 and len(pnu) == 19:
            rec["beopjungri_code"] = pnu[:10]
        else:
            rec["beopjungri_code"] = bj
        out[pnu] = SimpleNamespace(**rec)
    return out


def _candidates(conn, snapshot_ym: str) -> pd.DataFrame:
    buildings = load_buildings(conn, "apartment")
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
    if attrs.empty:
        merged = buildings.copy()
        merged["match_tier"] = None
        merged["match_rule"] = None
        merged["danji_code"] = None
        merged["has_attr_row"] = False
        return merged
    merged = buildings.merge(attrs, on="building_key", how="left")
    merged["has_attr_row"] = merged["match_tier"].notna()
    keep = ~merged["match_tier"].isin(["A", "B", "C", "E"])
    keep |= merged["match_tier"].isna()
    return merged.loc[keep].copy()


def _fill_record(cand: Any, master: Any, *, match_rule: str = "pnu_unique") -> dict[str, Any]:
    attrs = master_to_attrs(master)
    building_year = parse_int(cand.building_year)
    approved = attrs["approved_year"]
    year_diff = None
    if approved is not None and building_year is not None:
        year_diff = approved - building_year
    rec = {
        "building_key": cand.building_key,
        "danji_code": attrs["danji_code"],
        "match_tier": "P",
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
    return rec


def classify_candidates(
    cands: pd.DataFrame,
    by_pnu: dict[str, Any],
    rules: dict[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {
        "fill": [],
        "keep_p": [],
        "revert": [],
        "rebuild": [],
        "bundle": [],
        "multi_or_none": [],
        "skip_d": [],
    }
    for cand in cands.itertuples(index=False):
        tier = None if pd.isna(cand.match_tier) else str(cand.match_tier).strip()
        if tier in {"D", "F"} and has_danji_code(getattr(cand, "danji_code", None)):
            out["skip_d"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            continue
        pnu = pnu_from_tx(
            None if pd.isna(cand.beopjungri_code) else str(cand.beopjungri_code),
            None if pd.isna(cand.lot_number) else str(cand.lot_number),
        )
        master = by_pnu.get(pnu or "")
        if master is None:
            if tier == "P":
                out["revert"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            else:
                out["multi_or_none"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            continue
        skip = pnu_unique_skip_reason(
            tx_name=cand.display_name,
            kapt_name=getattr(master, "danji_name", None),
            approved_year=parse_approved_year(getattr(master, "approved_date", None)),
            building_year=parse_int(cand.building_year),
        )
        if skip == "rebuild":
            item = {
                "building_key": cand.building_key,
                "tx_name": cand.display_name,
                "kapt_name": getattr(master, "danji_name", None),
            }
            out["rebuild"].append(item)
            if tier == "P":
                out["revert"].append(item)
            continue
        if skip == "bundle":
            item = {
                "building_key": cand.building_key,
                "tx_name": cand.display_name,
                "kapt_name": getattr(master, "danji_name", None),
            }
            out["bundle"].append(item)
            if tier == "P":
                out["revert"].append(item)
            continue
        if tier == "P":
            out["keep_p"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            continue
        rule = (rules or {}).get(pnu or "", "pnu_unique")
        out["fill"].append(_fill_record(cand, master, match_rule=rule))
    return out


UPDATE_SQL = text(
    """
    UPDATE collective_building_attributes SET
        danji_code = :danji_code,
        match_tier = :match_tier,
        match_rule = :match_rule,
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
    """
)

INSERT_SQL = text(
    """
    INSERT INTO collective_building_attributes (
        snapshot_ym, asset_type, building_key, danji_code, match_tier, match_rule,
        approved_year, building_year, year_diff, builder_raw, developer_raw,
        structure_raw, structure_group, households, households_sale, households_rent,
        dong_count, max_floor, parking_total, parking_per_household,
        danji_class, supply_type, n_tx
    ) VALUES (
        :snapshot_ym, 'apartment', :building_key, :danji_code, :match_tier, :match_rule,
        :approved_year, :building_year, :year_diff, :builder_raw, :developer_raw,
        :structure_raw, :structure_group, :households, :households_sale, :households_rent,
        :dong_count, :max_floor, :parking_total, :parking_per_household,
        :danji_class, :supply_type, :n_tx
    )
    """
)

REVERT_SQL = text(
    """
    UPDATE collective_building_attributes SET
        danji_code = NULL,
        match_tier = 'Z',
        match_rule = 'no_match',
        approved_year = NULL,
        year_diff = NULL,
        builder_raw = NULL,
        builder_norm = NULL,
        builder_group = NULL,
        builder_is_joint = NULL,
        builder_is_public = NULL,
        developer_raw = NULL,
        structure_raw = NULL,
        structure_group = NULL,
        households = NULL,
        households_sale = NULL,
        households_rent = NULL,
        dong_count = NULL,
        max_floor = NULL,
        parking_total = NULL,
        parking_per_household = NULL,
        danji_class = NULL,
        supply_type = NULL,
        attr_quality_flags = NULL
    WHERE snapshot_ym = :snapshot_ym
      AND asset_type = 'apartment'
      AND building_key = :building_key
      AND match_tier = 'P'
    """
)


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
    p = argparse.ArgumentParser(description="F/Z buildings: fill unique-PNU K-apt attrs")
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
        by_pnu = _unique_pnu_map(conn, snapshot_ym)
        cands = _candidates(conn, snapshot_ym)
    clusters: dict = {}
    try:
        parcel = get_parcel_engine()
        from parcel_master.load_title_pilot import apply_schema

        apply_schema(parcel)
        with parcel.connect() as pconn:
            clusters = load_title_clusters(pconn)
            snap = pconn.execute(text("SELECT MAX(snapshot) FROM building")).scalar()
        if clusters and not args.dry_run and snap:
            with parcel.begin() as pconn:
                persist_title_clusters(pconn, str(snap).strip(), clusters)
    except Exception:
        log.exception("title clusters skipped (parcel_master 없거나 스키마 실패)")
        clusters = {}
    by_pnu, rules = expand_kapt_pnu_map(by_pnu, clusters)
    log.info(
        "snapshot_ym=%s  unique_pnu=%s  candidates=%s  cluster_alias=%s",
        snapshot_ym,
        sum(1 for r in rules.values() if r == "pnu_unique"),
        len(cands),
        sum(1 for r in rules.values() if r == "title_cluster"),
    )
    classified = classify_candidates(cands, by_pnu, rules)
    fills = classified["fill"]
    reverts = classified["revert"]
    log.info(
        "fill=%s  keep_p=%s  revert=%s  rebuild=%s  bundle=%s  skip_d=%s  multi_or_none=%s",
        len(fills),
        len(classified["keep_p"]),
        len(reverts),
        len(classified["rebuild"]),
        len(classified["bundle"]),
        len(classified["skip_d"]),
        len(classified["multi_or_none"]),
    )
    for rec in fills[:30]:
        log.info("  FILL %s → %s  hh=%s  rule=%s", rec["tx_name"], rec["kapt_name"], rec["households"], rec["match_rule"])
    if len(fills) > 30:
        log.info("  ... %s more", len(fills) - 30)
    for rec in reverts:
        log.info("  REVERT %s → %s", rec.get("tx_name"), rec.get("kapt_name"))
    for rec in classified["rebuild"]:
        log.info("  SKIP rebuild %s ≠ %s", rec["tx_name"], rec.get("kapt_name"))
    for rec in classified["bundle"][:20]:
        log.info("  SKIP bundle %s → %s", rec["tx_name"], rec.get("kapt_name"))

    if args.dry_run:
        log.info("dry-run: DB not changed")
        return

    with engine.begin() as conn:
        n_upd, n_ins = _write_fills(conn, snapshot_ym, fills)
        n_rev = 0
        for rec in reverts:
            conn.execute(
                REVERT_SQL,
                {"snapshot_ym": snapshot_ym, "building_key": rec["building_key"]},
            )
            n_rev += 1
    log.info("updated=%s  inserted=%s  reverted=%s", n_upd, n_ins, n_rev)

    if args.skip_dictionary or (not fills and not reverts):
        return
    with engine.begin() as conn:
        df = _load(conn, snapshot_ym)
        names = _load_display_names(conn, df["building_key"].astype(str).tolist())
        derived = _derive(df, names)
        n_dict = _write(conn, derived)
    log.info("dictionary rows=%s", n_dict)


if __name__ == "__main__":
    main()
