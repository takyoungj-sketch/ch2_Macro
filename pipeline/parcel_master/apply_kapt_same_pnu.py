"""같은 지번 아파트와 이름이 같은 오피스텔에 K-apt 시공사·규모를 붙인다.

A/B/C 로 올리지 않는다. match_tier=P, match_rule=kapt_same_pnu.
단지 전체 세대수라 지역회귀 USABLE 에서 이 rule 은 제외한다.

이름이 다른 같은 지번(혼합 단지)은 조인하지 않는다 — 목록 sibling UI 만.
비주거는 도로 cluster 라 K-apt 대응이 없어 여기 없다.

    python -m parcel_master.apply_kapt_same_pnu
    python -m parcel_master.apply_kapt_same_pnu --dry-run
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

_PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PIPELINE))

from parcel_master.apply_pnu_unique import (  # noqa: E402
    _fill_record,
    _unique_pnu_map,
)
from parcel_master.db_utils import get_collective_engine  # noqa: E402
from parcel_master.pnu import pnu_from_tx  # noqa: E402
from build_collective_building_attributes import (  # noqa: E402
    has_danji_code,
    load_buildings,
    names_compatible,
    parse_int,
)
from collective.apply_danji_dictionary import (  # noqa: E402
    _derive,
    _load,
    _load_display_names,
    _write,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MATCH_RULE = "kapt_same_pnu"
DONOR_TIERS = frozenset({"A", "B", "C", "P"})
_TIER_RANK = {"C": 0, "A": 1, "B": 2, "P": 3}
_WS = re.compile(r"\s+")

ATTR_COLS = (
    "danji_code",
    "approved_year",
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
)


def _clean_str(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    t = str(val).strip()
    if t.lower() in {"nan", "none"}:
        return ""
    return t


def compact_display(name: object) -> str:
    return _WS.sub("", _clean_str(name))


def _tx_pnu(beopjungri_code: object, lot_number: object) -> str | None:
    bj = None if beopjungri_code is None or (isinstance(beopjungri_code, float) and pd.isna(beopjungri_code)) else str(beopjungri_code)
    lot = None if lot_number is None or (isinstance(lot_number, float) and pd.isna(lot_number)) else str(lot_number)
    return pnu_from_tx(bj, lot)


def _pick_same_name_donor(donors: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not donors:
        return None
    codes = {str(d.get("danji_code") or "").strip() for d in donors if d.get("danji_code")}
    codes.discard("")
    if len(codes) > 1:
        return None
    donors = sorted(
        donors,
        key=lambda d: (_TIER_RANK.get(str(d.get("match_tier") or ""), 9), str(d.get("building_key") or "")),
    )
    return donors[0]


def classify_kapt_same_pnu(
    officetels: list[dict[str, Any]],
    apartments: list[dict[str, Any]],
    unique_kapt: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """오피스텔 후보를 fill / skip_mismatch / skip_other 로 나눈다."""
    apt_by_pnu: dict[str, list[dict[str, Any]]] = {}
    for apt in apartments:
        pnu = _clean_str(apt.get("pnu"))
        if len(pnu) != 19:
            continue
        if not has_danji_code(apt.get("danji_code")):
            continue
        if _clean_str(apt.get("match_tier")) not in DONOR_TIERS:
            continue
        apt_by_pnu.setdefault(pnu, []).append(apt)

    out: dict[str, list[dict[str, Any]]] = {
        "fill": [],
        "keep": [],
        "skip_mismatch": [],
        "skip_other": [],
    }
    for ot in officetels:
        tier = _clean_str(ot.get("match_tier"))
        rule = _clean_str(ot.get("match_rule"))
        if tier in {"A", "B", "C", "E"}:
            out["keep"].append(ot)
            continue
        if tier in {"D", "F"} and has_danji_code(ot.get("danji_code")):
            out["keep"].append(ot)
            continue
        if tier == "P" and rule == MATCH_RULE:
            out["keep"].append(ot)
            continue
        if tier == "P" and rule in {"pnu_unique", "title_cluster"}:
            out["keep"].append(ot)
            continue
        pnu = _clean_str(ot.get("pnu"))
        if len(pnu) != 19:
            out["skip_other"].append(ot)
            continue
        ot_name = compact_display(ot.get("display_name"))
        same = [
            a
            for a in apt_by_pnu.get(pnu, [])
            if ot_name and compact_display(a.get("display_name")) == ot_name
        ]
        if same:
            donor = _pick_same_name_donor(same)
            if donor is None:
                out["skip_mismatch"].append(ot)
                continue
            out["fill"].append(_fill_from_donor(ot, donor))
            continue
        if apt_by_pnu.get(pnu):
            out["skip_mismatch"].append(ot)
            continue
        master = unique_kapt.get(pnu)
        if master is not None and names_compatible(ot.get("display_name"), getattr(master, "danji_name", None)):
            cand = _cand_ns(ot)
            out["fill"].append(_fill_record(cand, master, match_rule=MATCH_RULE))
            continue
        out["skip_other"].append(ot)
    return out


def _cand_ns(ot: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(
        building_key=ot["building_key"],
        display_name=ot.get("display_name"),
        n_tx=int(ot.get("n_tx") or 0),
        building_year=ot.get("building_year"),
        has_attr_row=bool(ot.get("has_attr_row")),
        beopjungri_code=ot.get("beopjungri_code"),
        lot_number=ot.get("lot_number"),
        match_tier=ot.get("match_tier"),
        danji_code=ot.get("danji_code"),
    )


def _fill_from_donor(ot: dict[str, Any], donor: dict[str, Any]) -> dict[str, Any]:
    building_year = parse_int(ot.get("building_year"))
    approved = parse_int(donor.get("approved_year"))
    year_diff = None
    if approved is not None and building_year is not None:
        year_diff = approved - building_year
    rec: dict[str, Any] = {
        "building_key": ot["building_key"],
        "match_tier": "P",
        "match_rule": MATCH_RULE,
        "building_year": building_year,
        "year_diff": year_diff,
        "n_tx": parse_int(ot.get("n_tx")) or 0,
        "tx_name": ot.get("display_name"),
        "kapt_name": donor.get("kapt_name") or donor.get("display_name"),
        "has_attr_row": bool(ot.get("has_attr_row"))
        if not (isinstance(ot.get("has_attr_row"), float) and pd.isna(ot.get("has_attr_row")))
        else False,
    }
    for col in ATTR_COLS:
        rec[col] = donor.get(col)
    rec["danji_code"] = donor.get("danji_code")
    return rec


def _load_apartment_donors(conn, snapshot_ym: str) -> list[dict[str, Any]]:
    buildings = load_buildings(conn, "apartment")
    attrs = pd.read_sql(
        text(
            f"""
            SELECT building_key, match_tier, match_rule, danji_code,
                   {", ".join(c for c in ATTR_COLS if c != "danji_code")}
            FROM collective_building_attributes
            WHERE snapshot_ym = :ym AND asset_type = 'apartment'
            """
        ),
        conn,
        params={"ym": snapshot_ym},
    )
    if buildings.empty or attrs.empty:
        return []
    merged = buildings.merge(attrs, on="building_key", how="inner")
    records = merged.to_dict("records")
    for d in records:
        d["pnu"] = _tx_pnu(d.get("beopjungri_code"), d.get("lot_number"))
    return records


def _load_officetel_cands(conn, snapshot_ym: str) -> list[dict[str, Any]]:
    buildings = load_buildings(conn, "officetel")
    attrs = pd.read_sql(
        text(
            """
            SELECT building_key, match_tier, match_rule, danji_code
            FROM collective_building_attributes
            WHERE snapshot_ym = :ym AND asset_type = 'officetel'
            """
        ),
        conn,
        params={"ym": snapshot_ym},
    )
    if buildings.empty:
        return []
    if attrs.empty:
        merged = buildings.copy()
        merged["match_tier"] = None
        merged["match_rule"] = None
        merged["danji_code"] = None
        merged["has_attr_row"] = False
    else:
        merged = buildings.merge(attrs, on="building_key", how="left")
        merged["has_attr_row"] = merged["match_tier"].notna()
    records = merged.to_dict("records")
    for d in records:
        d["pnu"] = _tx_pnu(d.get("beopjungri_code"), d.get("lot_number"))
    return records


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
      AND asset_type = 'officetel'
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
        :snapshot_ym, 'officetel', :building_key, :danji_code, :match_tier, :match_rule,
        :approved_year, :building_year, :year_diff, :builder_raw, :developer_raw,
        :structure_raw, :structure_group, :households, :households_sale, :households_rent,
        :dong_count, :max_floor, :parking_total, :parking_per_household,
        :danji_class, :supply_type, :n_tx
    )
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
    p = argparse.ArgumentParser(description="Officetel: copy K-apt from same-lot same-name apartment")
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
        unique_kapt = _unique_pnu_map(conn, snapshot_ym)
        apts = _load_apartment_donors(conn, snapshot_ym)
        ots = _load_officetel_cands(conn, snapshot_ym)
    classified = classify_kapt_same_pnu(ots, apts, unique_kapt)
    fills = classified["fill"]
    log.info(
        "snapshot_ym=%s  apt_donors=%s  ot=%s  fill=%s  keep=%s  skip_mismatch=%s  skip_other=%s",
        snapshot_ym,
        len(apts),
        len(ots),
        len(fills),
        len(classified["keep"]),
        len(classified["skip_mismatch"]),
        len(classified["skip_other"]),
    )
    for rec in fills[:40]:
        log.info(
            "  FILL %s → %s  hh=%s  builder=%s",
            rec.get("tx_name"),
            rec.get("kapt_name"),
            rec.get("households"),
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
