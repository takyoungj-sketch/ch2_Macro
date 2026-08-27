"""표제부 동 합산(세대수·층·구조)을 단지 속성에 채운다.

조인 키는 PNU다. 아파트는 K-apt 없는 Z만. D·F·A·B·C·E·P 는 건드리지 않는다.
연립·오피스텔: 행이 없으면 INSERT (K-apt 대상이 아님). 시공사 없음.
한 필지에 아파트 동과 다세대 동이 둘 다 있으면 유형별로 나눈다.
유형 글자가 없어도 집합 표제부 본체 동이 있으면 붙인다.

    python -m parcel_master.apply_title_fill
    python -m parcel_master.apply_title_fill --dry-run
    python -m parcel_master.apply_title_fill --new-keys-only
    python -m parcel_master.apply_title_fill --refresh-t
    python -m parcel_master.apply_title_fill --types rowhouse,officetel
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

_PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PIPELINE))

from parcel_master.db_utils import get_collective_engine, get_parcel_engine  # noqa: E402
from parcel_master.pnu import pick_incheon_old_bjd, pnu_from_tx  # noqa: E402
from parcel_master.title_fill import (  # noqa: E402
    TitleKind,
    aggregate_title_dongs,
    title_fill_skip_reason,
    title_rows_for_pnu,
)
from build_collective_building_attributes import (  # noqa: E402
    load_buildings,
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

BLOCKED_TIERS = frozenset({"A", "B", "C", "D", "E", "F", "P"})
DEFAULT_TYPES: tuple[TitleKind, ...] = ("apartment", "rowhouse", "officetel")
BATCH = 500

TITLE_SQL = """
SELECT pnu, main_purpose, purpose_detail, households, ho_cnt, parking_total,
       floors_above, structure_name, approve_date
FROM building
WHERE snapshot = (SELECT MAX(snapshot) FROM building)
  AND ledger_kind = '집합'
"""

KAPT_PNU_SQL = """
SELECT DISTINCT pnu
FROM builder_master
WHERE snapshot_ym = :ym AND pnu IS NOT NULL
"""

ATTR_SQL = """
SELECT building_key, match_tier, match_rule, danji_code
FROM collective_building_attributes
WHERE snapshot_ym = :ym AND asset_type = :asset_type
"""

UPDATE_SQL = text(
    """
    UPDATE collective_building_attributes SET
        danji_code = NULL,
        match_tier = 'T',
        match_rule = 'title_pnu',
        approved_year = :approved_year,
        building_year = :building_year,
        year_diff = :year_diff,
        builder_raw = NULL,
        developer_raw = NULL,
        structure_raw = :structure_raw,
        structure_group = :structure_group,
        households = :households,
        households_sale = NULL,
        households_rent = NULL,
        dong_count = :dong_count,
        max_floor = :max_floor,
        parking_total = :parking_total,
        parking_per_household = :parking_per_household,
        danji_class = NULL,
        supply_type = NULL,
        n_tx = :n_tx
    WHERE snapshot_ym = :snapshot_ym
      AND asset_type = :asset_type
      AND building_key = :building_key
    """
)

INSERT_SQL = text(
    """
    INSERT INTO collective_building_attributes (
        snapshot_ym, asset_type, building_key, danji_code, match_tier, match_rule,
        approved_year, building_year, year_diff, structure_raw, structure_group,
        households, dong_count, max_floor, parking_total, parking_per_household, n_tx
    ) VALUES (
        :snapshot_ym, :asset_type, :building_key, NULL, 'T', 'title_pnu',
        :approved_year, :building_year, :year_diff, :structure_raw, :structure_group,
        :households, :dong_count, :max_floor, :parking_total, :parking_per_household, :n_tx
    )
    ON CONFLICT (snapshot_ym, asset_type, building_key) DO NOTHING
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
        structure_raw = NULL,
        structure_group = NULL,
        households = NULL,
        dong_count = NULL,
        max_floor = NULL,
        attr_quality_flags = NULL
    WHERE snapshot_ym = :snapshot_ym
      AND asset_type = :asset_type
      AND building_key = :building_key
      AND match_tier = 'T'
    """
)


def _incheon_current_to_old_bjd(conn) -> dict[str, str]:
    rows = conn.execute(
        text(
            """
            SELECT current.beopjungri_code AS current_code,
                   old.beopjungri_code AS old_code
            FROM region_codes current
            JOIN region_codes old
              ON old.sido_code = '28'
             AND old.eupmyeondong_name = current.eupmyeondong_name
             AND old.beopjungri_name = current.beopjungri_name
             AND LEFT(TRIM(old.beopjungri_code), 5) IN ('28260', '28110', '28140')
            WHERE current.sido_code = '28'
              AND LEFT(TRIM(current.beopjungri_code), 5) IN ('28290', '28275', '28155', '28125')
              AND COALESCE(current.is_active, TRUE)
            """
        )
    ).mappings().all()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        current = str(row["current_code"]).strip()
        old = str(row["old_code"]).strip()
        grouped.setdefault(current, []).append(old)
    mapping: dict[str, str] = {}
    for current, olds in grouped.items():
        old = pick_incheon_old_bjd(current, olds)
        if old:
            mapping[current] = old
    return mapping


def _title_by_pnu(conn) -> dict[str, list[dict[str, Any]]]:
    df = pd.read_sql(text(TITLE_SQL), conn)
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in df.to_dict(orient="records"):
        out[str(rec["pnu"])].append(rec)
    return out


def _fill_record(cand: Any, agg: dict[str, Any]) -> dict[str, Any]:
    building_year = parse_int(cand.building_year)
    approved = agg.get("approved_year")
    year_diff = None
    if approved is not None and building_year is not None:
        year_diff = int(approved) - int(building_year)
    raw = agg.get("structure_raw") or None
    hh = agg.get("households")
    park = agg.get("parking_total")
    pph = None
    if hh and park:
        pph = round(float(park) / float(hh), 3)
    return {
        "building_key": cand.building_key,
        "tx_name": cand.display_name,
        "approved_year": approved,
        "building_year": building_year,
        "year_diff": year_diff,
        "structure_raw": raw[:60] if isinstance(raw, str) else raw,
        "structure_group": structure_group(raw),
        "households": hh,
        "dong_count": agg["dong_count"],
        "max_floor": agg.get("max_floor"),
        "parking_total": park,
        "parking_per_household": pph,
        "n_tx": int(cand.n_tx),
        "has_attr_row": bool(cand.has_attr_row),
    }


def classify(
    cands: pd.DataFrame,
    by_pnu: dict[str, list[dict[str, Any]]],
    kapt_pnus: set[str],
    *,
    kind: TitleKind,
    skip_kapt: bool,
    refresh_t: bool = False,
    current_to_old_bjd: dict[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {
        "fill": [],
        "keep_t": [],
        "revert": [],
        "blocked": [],
        "has_kapt": [],
        "no_title": [],
        "no_housing": [],
        "no_households": [],
        "rebuild": [],
    }
    require_hh = kind != "officetel"
    for cand in cands.itertuples(index=False):
        tier = None if pd.isna(cand.match_tier) else str(cand.match_tier).strip()
        pnu = pnu_from_tx(
            None if pd.isna(cand.beopjungri_code) else str(cand.beopjungri_code),
            None if pd.isna(cand.lot_number) else str(cand.lot_number),
        )
        if tier in BLOCKED_TIERS:
            out["blocked"].append({"building_key": cand.building_key})
            continue
        if skip_kapt and pnu and pnu in kapt_pnus:
            if tier == "T":
                out["revert"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            else:
                out["has_kapt"].append({"building_key": cand.building_key})
            continue
        rows = title_rows_for_pnu(pnu, by_pnu, current_to_old_bjd)
        agg = aggregate_title_dongs(rows, kind=kind) if rows else None
        skip = title_fill_skip_reason(
            agg=agg,
            building_year=parse_int(cand.building_year),
            require_households=require_hh,
        )
        if not rows:
            skip = skip or "no_title"
            if skip == "no_housing":
                skip = "no_title"
        if skip:
            bucket = skip if skip in out else "no_title"
            item = {"building_key": cand.building_key, "tx_name": cand.display_name}
            out[bucket].append(item)
            if tier == "T":
                out["revert"].append(item)
            continue
        if tier == "T" and not refresh_t:
            out["keep_t"].append({"building_key": cand.building_key, "tx_name": cand.display_name})
            continue
        out["fill"].append(_fill_record(cand, agg))  # type: ignore[arg-type]
    return out


def _payloads(fills: list[dict[str, Any]], snapshot_ym: str, asset_type: str) -> tuple[list[dict], list[dict]]:
    upd: list[dict[str, Any]] = []
    ins: list[dict[str, Any]] = []
    for rec in fills:
        payload = {k: rec[k] for k in rec if k not in {"tx_name", "has_attr_row"}}
        payload["snapshot_ym"] = snapshot_ym
        payload["asset_type"] = asset_type
        if rec["has_attr_row"]:
            upd.append(payload)
        else:
            ins.append(payload)
    return upd, ins


def filter_fills_new_keys(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """실거래 달: 속성 행이 없는 키만. A·B·C·T 기존 행은 여기 안 들어온다."""
    return [f for f in fills if not f.get("has_attr_row")]


def _exec_many(conn, sql, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    n = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        conn.execute(sql, chunk)
        n += len(chunk)
    return n


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="표제부 동 합산 → 단지 속성")
    p.add_argument("--snapshot-ym", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-dictionary", action="store_true")
    p.add_argument("--new-keys-only", action="store_true", help="속성 없는 키만 INSERT. A·B·C·기존 T 안 덮음")
    p.add_argument("--refresh-t", action="store_true", help="대장 달: 기존 T를 표제부 신본으로 갱신")
    p.add_argument(
        "--types",
        default=",".join(DEFAULT_TYPES),
        help="comma: apartment,rowhouse,officetel",
    )
    return p.parse_args()


def _parse_types(raw: str) -> tuple[TitleKind, ...]:
    allowed = set(DEFAULT_TYPES)
    out: list[TitleKind] = []
    for part in raw.split(","):
        t = part.strip()
        if not t:
            continue
        if t not in allowed:
            raise SystemExit(f"unknown type {t!r}; use {','.join(DEFAULT_TYPES)}")
        out.append(t)  # type: ignore[arg-type]
    if not out:
        raise SystemExit("no types")
    return tuple(out)


def run(
    *,
    snapshot_ym: str | None = None,
    dry_run: bool = False,
    skip_dictionary: bool = False,
    types: tuple[TitleKind, ...] = DEFAULT_TYPES,
    new_keys_only: bool = False,
    refresh_t: bool = False,
) -> None:
    if new_keys_only and refresh_t:
        raise SystemExit("--new-keys-only 와 --refresh-t 는 같이 쓰지 않는다")
    coll = get_collective_engine()
    parcel = get_parcel_engine()
    from parcel_master.load_title_pilot import apply_schema

    apply_schema(parcel)
    with coll.connect() as conn:
        snapshot_ym = snapshot_ym or conn.execute(
            text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")
        ).scalar()
        if not snapshot_ym:
            raise SystemExit("collective_building_attributes empty")
        snapshot_ym = str(snapshot_ym).strip()
        kapt_pnus = {str(r[0]) for r in conn.execute(text(KAPT_PNU_SQL), {"ym": snapshot_ym})}
        incheon_map = _incheon_current_to_old_bjd(conn)
    with parcel.connect() as conn:
        by_pnu = _title_by_pnu(conn)
    log.info(
        "snapshot_ym=%s  title_pnu=%s  incheon_bjd=%s  types=%s",
        snapshot_ym,
        len(by_pnu),
        len(incheon_map),
        ",".join(types),
    )

    attrs_changed = False
    for kind in types:
        with coll.connect() as conn:
            buildings = load_buildings(conn, kind)
            attrs = pd.read_sql(
                text(ATTR_SQL),
                conn,
                params={"ym": snapshot_ym, "asset_type": kind},
            )
        if attrs.empty:
            merged = buildings.copy()
            merged["match_tier"] = None
            merged["has_attr_row"] = False
        else:
            merged = buildings.merge(attrs, on="building_key", how="left")
            merged["has_attr_row"] = merged["match_tier"].notna()
        classified = classify(
            merged,
            by_pnu,
            kapt_pnus,
            kind=kind,
            skip_kapt=(kind == "apartment"),
            refresh_t=refresh_t,
            current_to_old_bjd=incheon_map,
        )
        fills = classified["fill"]
        if new_keys_only:
            fills = filter_fills_new_keys(fills)
        reverts = [] if new_keys_only else classified["revert"]
        log.info(
            "%s  fill=%s  keep_t=%s  revert=%s  blocked=%s  has_kapt=%s  "
            "no_title=%s  no_housing=%s  no_hh=%s  rebuild=%s",
            kind,
            len(fills),
            len(classified["keep_t"]),
            len(reverts),
            len(classified["blocked"]),
            len(classified["has_kapt"]),
            len(classified["no_title"]),
            len(classified["no_housing"]),
            len(classified["no_households"]),
            len(classified["rebuild"]),
        )
        for rec in fills[:12]:
            log.info(
                "  FILL %s  hh=%s  park=%s  dong=%s  floor=%s  struct=%s",
                rec["tx_name"],
                rec["households"],
                rec.get("parking_total"),
                rec["dong_count"],
                rec["max_floor"],
                rec.get("structure_raw"),
            )
        if len(fills) > 12:
            log.info("  ... %s more", len(fills) - 12)
        if dry_run:
            continue
        upd, ins = _payloads(fills, snapshot_ym, kind)
        if new_keys_only:
            upd = []
        with coll.begin() as conn:
            n_upd = _exec_many(conn, UPDATE_SQL, upd)
            n_ins = _exec_many(conn, INSERT_SQL, ins)
            n_rev = _exec_many(
                conn,
                REVERT_SQL,
                [{"snapshot_ym": snapshot_ym, "asset_type": kind, "building_key": r["building_key"]} for r in reverts],
            )
        log.info("%s  updated=%s  inserted=%s  reverted=%s", kind, n_upd, n_ins, n_rev)
        if fills or reverts:
            attrs_changed = True

    if dry_run:
        log.info("dry-run: DB not changed")
        return
    if skip_dictionary or not attrs_changed:
        return
    with coll.begin() as conn:
        df = _load(conn, snapshot_ym)
        names = _load_display_names(conn, df["building_key"].astype(str).tolist())
        derived = _derive(df, names)
        n_dict = _write(conn, derived)
    log.info("dictionary rows=%s", n_dict)


def main() -> None:
    args = parse_args()
    run(
        snapshot_ym=args.snapshot_ym,
        dry_run=args.dry_run,
        skip_dictionary=args.skip_dictionary,
        types=_parse_types(args.types),
        new_keys_only=args.new_keys_only,
        refresh_t=args.refresh_t,
    )


if __name__ == "__main__":
    main()
