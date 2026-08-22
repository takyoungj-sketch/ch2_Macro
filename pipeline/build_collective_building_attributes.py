#!/usr/bin/env python3
"""
집합(주거) 단지 속성 보강 P1 — K-apt → builder_master + collective_building_attributes.

설계: docs/COLLECTIVE_RESIDENTIAL_VALUATION_EXPANSION_REVIEW.md §3
매칭 레퍼런스: backend/_tmp_collective_enrich_probe.py
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import sys
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from parcel_master.pnu import pnu_from_tx  # noqa: E402
from parcel_master.pnu_unique import pnu_unique_skip_reason  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

DEFAULT_CHUNK = 500
_WS = re.compile(r"\s+")
_IPARK = re.compile(r"I[\s\-]?PARK", re.IGNORECASE)
_JE = re.compile(r"제(\d+)단지")
_PAREN = re.compile(r"\(.*?\)")
_LOT_IN_ADDR = re.compile(r"(?:^|\s)(\d+(?:-\d+)?)-?(?=\s|$)")

TIER_RULE_MAP: dict[str, tuple[str, str]] = {
    "A_name_exact": ("A", "name_exact"),
    "B_name_core": ("B", "name_core"),
    "C_lot_exact": ("C", "lot_exact"),
    "D_lot_multi": ("D", "lot_multi"),
    "E_contains_unique": ("E", "contains_unique"),
    "F_contains_multi": ("F", "contains_multi"),
    "P_pnu_unique": ("P", "pnu_unique"),
    "no_match": ("Z", "no_match"),
}

ATTR_TIERS = frozenset({"A", "B", "C", "E", "P"})
MULTI_ATTR_TIERS = frozenset({"D", "F"})
# F는 부분일치라 짧은 실거래명(부평·석수)이 동 안 단지를 전부 삼킨다.
F_MIN_NAME = 6
F_MAX_CANDS = 4

BUILDING_SQL = """
SELECT
    building_key,
    asset_type,
    MAX(display_name) AS display_name,
    MODE() WITHIN GROUP (ORDER BY beopjungri_code) AS beopjungri_code,
    MODE() WITHIN GROUP (ORDER BY lot_number) AS lot_number,
    COUNT(*) AS n_tx,
    MAX(building_year) AS building_year
FROM collective_transactions
WHERE is_valid = true
  AND asset_type = :asset_type
GROUP BY building_key, asset_type
"""


def norm_name(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    t = unicodedata.normalize("NFC", str(value)).strip()
    t = _WS.sub("", t)
    t = _IPARK.sub("아이파크", t)
    t = _JE.sub(r"\1단지", t)
    return t


def norm_name_core(value: object) -> str:
    t = norm_name(value)
    return _PAREN.sub("", unicodedata.normalize("NFC", t)).strip()


def norm_lot(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    t = str(value).strip().replace(" ", "")
    t = t.rstrip("-")
    m = re.match(r"^(\d+)(?:-(\d+))?$", t)
    if not m:
        return ""
    main, sub = m.group(1), m.group(2)
    return f"{int(main)}-{int(sub)}" if sub else f"{int(main)}"


def lot_from_kapt_addr(addr: object) -> str:
    if addr is None or (isinstance(addr, float) and pd.isna(addr)):
        return ""
    found = _LOT_IN_ADDR.findall(str(addr))
    return norm_lot(found[-1]) if found else ""


def sigungu_variants(sigungu_name: str) -> list[str]:
    base = _WS.sub("", str(sigungu_name or ""))
    out = [base]
    shrunk = re.sub(r"시(?=\S*구$)", "", base)
    if shrunk != base:
        out.append(shrunk)
    return out


def structure_group(raw: object) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s == "철근콘크리트구조":
        return "RC"
    if s in ("철골철근콘크리트구조", "철골콘크리트구조"):
        return "SRC"
    return "기타"


def parse_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_approved_year(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"\D", "", str(value).strip())
    if len(s) >= 4:
        try:
            return int(s[:4])
        except ValueError:
            return None
    return None


def parse_approved_date(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"\D", "", str(value).strip())
    return s[:8] if len(s) >= 8 else (s if s else None)


def db_url() -> str:
    env = dotenv_values(REPO / "backend" / ".env")
    url = str(env.get("COLLECTIVE_DATABASE_URL") or "")
    if not url:
        raise RuntimeError("COLLECTIVE_DATABASE_URL not set in backend/.env")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def infer_snapshot_ym(path: Path) -> str:
    m = re.search(r"(20\d{4})", path.stem)
    if not m:
        raise ValueError(f"cannot infer snapshot_ym from {path.name}")
    return m.group(1)[:6]


def default_kapt_path() -> Path:
    matches = sorted(glob.glob(str(REPO / "raw" / "raw addition" / "*_기본정보.xlsx")))
    if not matches:
        raise FileNotFoundError("K-apt xlsx not found under raw/raw addition/")
    return Path(matches[-1])


def region_map_from_rows(rows) -> dict[tuple[str, str, str], str]:
    """(시도, 시군구, 법정동명) → 10자리 코드.

    세종처럼 동 이름이 시군구 칸에 있고 법정동명이 비면
    (시도, '', 동이름) 키도 넣는다. K-apt 동리는 시군구가 비어 있다.
    """
    out: dict[tuple[str, str, str], str] = {}
    for row in rows:
        sido = _WS.sub("", str(getattr(row, "sido_name", "") or ""))
        sgg_raw = _WS.sub("", str(getattr(row, "sigungu_name", "") or ""))
        bj = _WS.sub("", str(getattr(row, "beopjungri_name", "") or ""))
        code = str(getattr(row, "beopjungri_code", "") or "")
        if not sido or not code:
            continue
        for sgg in sigungu_variants(sgg_raw):
            out.setdefault((sido, sgg, bj), code)
        out.setdefault((sido, "", bj), code)
        if not bj and sgg_raw:
            out.setdefault((sido, "", sgg_raw), code)
            for sgg in sigungu_variants(sgg_raw):
                out.setdefault((sido, sgg, sgg), code)
    return out


def lookup_beopjungri_code(
    region_map: dict[tuple[str, str, str], str],
    *,
    sido: str,
    sigungu: str = "",
    dongri: str = "",
    eupmyeon: str = "",
) -> str:
    sido_k = _WS.sub("", str(sido or ""))
    sgg = _WS.sub("", str(sigungu or ""))
    dong = _WS.sub("", str(dongri or ""))
    eup = _WS.sub("", str(eupmyeon or ""))
    bj = dong or eup
    for key in (
        (sido_k, sgg, bj),
        (sido_k, "", bj),
        (sido_k, bj, ""),
        (sido_k, sgg, dong) if dong else None,
        (sido_k, "", dong) if dong else None,
    ):
        if not key or not key[0]:
            continue
        code = region_map.get(key)
        if code:
            return code
    return ""


def load_region_map(conn) -> dict[tuple[str, str, str], str]:
    df = pd.read_sql(
        text(
            "SELECT sido_name, sigungu_name, beopjungri_name, beopjungri_code"
            " FROM region_codes"
        ),
        conn,
    )
    return region_map_from_rows(df.itertuples(index=False))


def load_kapt(region_map: dict[tuple[str, str, str], str], path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, skiprows=1, dtype=str)
    keep = [
        "시도", "시군구", "읍면", "동리", "단지코드", "단지명", "단지분류",
        "법정동주소", "도로명주소", "분양형태", "사용승인일", "동수", "세대수",
        "분양세대수", "임대세대수", "시공사", "시행사", "건물구조", "총주차대수",
        "지상주차대수", "지하주차대수", "최고층수", "지하층수", "난방방식", "복도유형",
    ]
    df = df[[c for c in keep if c in df.columns]].copy()
    df["source_file"] = path.name
    df["name_key"] = df["단지명"].map(norm_name)
    df["name_core"] = df["단지명"].map(norm_name_core)
    df["lot_key"] = df["법정동주소"].map(lot_from_kapt_addr)

    codes: list[str] = []
    for row in df.itertuples(index=False):
        codes.append(
            lookup_beopjungri_code(
                region_map,
                sido=str(getattr(row, "시도", "") or ""),
                sigungu=str(getattr(row, "시군구", "") or ""),
                dongri=str(getattr(row, "동리", "") or ""),
                eupmyeon=str(getattr(row, "읍면", "") or ""),
            )
        )
    df["beopjungri_code"] = codes
    return df


def load_buildings(conn, asset_type: str) -> pd.DataFrame:
    return pd.read_sql(text(BUILDING_SQL), conn, params={"asset_type": asset_type})


def build_kapt_indexes(kapt: pd.DataFrame) -> tuple[
    dict[tuple[str, str], list[int]],
    dict[tuple[str, str], list[int]],
    dict[tuple[str, str], list[int]],
    dict[str, list[tuple[str, int]]],
]:
    k = kapt[kapt["beopjungri_code"] != ""].copy()
    by_lot: dict[tuple[str, str], list[int]] = {}
    by_name: dict[tuple[str, str], list[int]] = {}
    by_core: dict[tuple[str, str], list[int]] = {}
    names_in_bj: dict[str, list[tuple[str, int]]] = {}
    for idx, row in enumerate(k.itertuples(index=False)):
        bj = str(row.beopjungri_code)
        if row.lot_key:
            by_lot.setdefault((bj, row.lot_key), []).append(idx)
        if row.name_key:
            by_name.setdefault((bj, row.name_key), []).append(idx)
            names_in_bj.setdefault(bj, []).append((row.name_key, idx))
        if row.name_core:
            by_core.setdefault((bj, row.name_core), []).append(idx)
    return by_lot, by_name, by_core, names_in_bj


def build_pnu_index(kapt: pd.DataFrame) -> dict[str, list[int]]:
    by_pnu: dict[str, list[int]] = {}
    if "pnu" not in kapt.columns:
        return by_pnu
    for idx, row in enumerate(kapt.itertuples(index=False)):
        pnu = str(getattr(row, "pnu", "") or "").strip()
        if len(pnu) == 19 and pnu.isdigit():
            by_pnu.setdefault(pnu, []).append(idx)
    return by_pnu


def attach_kapt_pnu(kapt: pd.DataFrame) -> pd.DataFrame:
    out = kapt.copy()
    if "pnu" in out.columns and out["pnu"].notna().any():
        return out
    try:
        from parcel_master.load_kapt_pnu import load_pnu_map

        pnu_df = load_pnu_map()
        pnu_map = dict(zip(pnu_df["danji_code"], pnu_df["pnu"]))
        out["pnu"] = out["단지코드"].map(
            lambda c: pnu_map.get(str(c).strip()) if pd.notna(c) else None
        )
        log.info("attached K-apt pnu rows=%s", int(out["pnu"].notna().sum()))
    except Exception:
        log.exception("K-apt PNU attach skipped")
        out["pnu"] = None
    return out


def match_one(
    row,
    *,
    by_lot: dict[tuple[str, str], list[int]],
    by_name: dict[tuple[str, str], list[int]],
    by_core: dict[tuple[str, str], list[int]],
    names_in_bj: dict[str, list[tuple[str, int]]],
) -> tuple[str, list[int]]:
    bj = str(row.beopjungri_code) if pd.notna(row.beopjungri_code) else ""
    name_key = norm_name(row.display_name)
    name_core = norm_name_core(row.display_name)
    lot_key = norm_lot(row.lot_number)

    if name_key and len(by_name.get((bj, name_key), [])) == 1:
        return "A_name_exact", list(by_name[(bj, name_key)])
    if name_core and len(by_core.get((bj, name_core), [])) == 1:
        return "B_name_core", list(by_core[(bj, name_core)])
    if lot_key and len(by_lot.get((bj, lot_key), [])) == 1:
        return "C_lot_exact", list(by_lot[(bj, lot_key)])
    if lot_key and len(by_lot.get((bj, lot_key), [])) > 1:
        return "D_lot_multi", list(by_lot[(bj, lot_key)])
    cands = names_in_bj.get(bj, [])
    if name_key and cands:
        hits = [i for nm, i in cands if name_key in nm or nm in name_key]
        if len(hits) == 1:
            return "E_contains_unique", hits
        if len(hits) > 1:
            return "F_contains_multi", hits
    return "no_match", []


def _cell(row: pd.Series, *names: str) -> object:
    for name in names:
        if name in row.index:
            val = row[name]
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                return val
    return None


def kapt_row_to_attrs(kapt: pd.DataFrame, idx: int) -> dict[str, Any]:
    row = kapt.iloc[idx]
    households = parse_int(_cell(row, "세대수", "households"))
    parking_total = parse_int(_cell(row, "총주차대수", "parking_total"))
    parking_per = None
    if households and households > 0 and parking_total is not None:
        parking_per = round(Decimal(parking_total) / Decimal(households), 3)
    approved_year = parse_approved_year(_cell(row, "사용승인일", "approved_date"))
    return {
        "danji_code": _str_or_none(_cell(row, "단지코드", "danji_code")),
        "danji_name": _str_or_none(_cell(row, "단지명", "danji_name")),
        "approved_year": approved_year,
        "builder_raw": _str_or_none(_cell(row, "시공사", "builder_raw"), max_len=500),
        "developer_raw": _str_or_none(_cell(row, "시행사", "developer_raw"), max_len=500),
        "structure_raw": _str_or_none(_cell(row, "건물구조", "structure_raw"), max_len=60),
        "structure_group": structure_group(_cell(row, "건물구조", "structure_raw")),
        "households": households,
        "households_sale": parse_int(_cell(row, "분양세대수", "households_sale")),
        "households_rent": parse_int(_cell(row, "임대세대수", "households_rent")),
        "dong_count": parse_int(_cell(row, "동수", "dong_count")),
        "max_floor": parse_int(_cell(row, "최고층수", "max_floor")),
        "parking_total": parking_total,
        "parking_per_household": parking_per,
        "danji_class": _str_or_none(_cell(row, "단지분류", "danji_class")),
        "supply_type": _str_or_none(_cell(row, "분양형태", "supply_type")),
    }


def order_multi_idxs(kapt: pd.DataFrame, idxs: list[int]) -> list[int]:
    """복수 후보는 단지명·코드 순. 파일 순서를 대표값으로 쓰지 않는다."""

    def _key(i: int) -> tuple[str, str]:
        row = kapt.iloc[i]
        name = str(_cell(row, "단지명", "danji_name") or "")
        code = str(_cell(row, "단지코드", "danji_code") or "")
        return (name, code)

    return sorted(idxs, key=_key)


def multi_fill_allowed(tier: str, tx_name: object, kapt: pd.DataFrame, idxs: list[int]) -> bool:
    """D는 같은 지번이라 합산. F는 이름 길이·후보 수 가드가 통과할 때만."""
    if len(idxs) < 2:
        return False
    if tier == "D":
        return True
    if tier != "F" or len(idxs) > F_MAX_CANDS:
        return False
    tx = norm_name(tx_name)
    if len(tx) < F_MIN_NAME:
        return False
    for i in idxs:
        kn = norm_name(_cell(kapt.iloc[i], "단지명", "danji_name"))
        shorter = tx if len(tx) <= len(kn) else kn
        if len(shorter) < F_MIN_NAME:
            return False
    return True


def _sum_int(parts: list[dict[str, Any]], key: str) -> int | None:
    vals = [p.get(key) for p in parts if p.get(key) is not None]
    if not vals:
        return None
    return int(sum(int(v) for v in vals))


def _join_unique(parts: list[dict[str, Any]], key: str, *, max_len: int) -> str | None:
    seen: list[str] = []
    for p in parts:
        s = _str_or_none(p.get(key))
        if s and s not in seen:
            seen.append(s)
    if not seen:
        return None
    return _str_or_none(", ".join(seen), max_len=max_len)


def aggregate_attr_dicts(parts: list[dict[str, Any]]) -> dict[str, Any]:
    """D·F: 세대·동·주차 합산, 최고층 max, 사용승인은 가장 이른 해, 시공사 원문은 병합."""
    parts = [p for p in parts if p.get("danji_code")]
    if not parts:
        return {}
    households = _sum_int(parts, "households")
    parking_total = _sum_int(parts, "parking_total")
    parking_per = None
    if households and households > 0 and parking_total is not None:
        parking_per = round(Decimal(parking_total) / Decimal(households), 3)
    years = [int(p["approved_year"]) for p in parts if p.get("approved_year") is not None]
    groups = {p.get("structure_group") for p in parts if p.get("structure_group")}
    classes = {p.get("danji_class") for p in parts if p.get("danji_class")}
    supplies = {p.get("supply_type") for p in parts if p.get("supply_type")}
    floors = [int(p["max_floor"]) for p in parts if p.get("max_floor") is not None]
    codes = [str(p["danji_code"]) for p in parts]
    return {
        "danji_code": codes[0],
        "match_danji_codes": ",".join(codes),
        "approved_year": min(years) if years else None,
        "builder_raw": _join_unique(parts, "builder_raw", max_len=500),
        "developer_raw": _join_unique(parts, "developer_raw", max_len=500),
        "structure_raw": _join_unique(parts, "structure_raw", max_len=60),
        "structure_group": next(iter(groups)) if len(groups) == 1 else None,
        "households": households,
        "households_sale": _sum_int(parts, "households_sale"),
        "households_rent": _sum_int(parts, "households_rent"),
        "dong_count": _sum_int(parts, "dong_count"),
        "max_floor": max(floors) if floors else None,
        "parking_total": parking_total,
        "parking_per_household": parking_per,
        "danji_class": next(iter(classes)) if len(classes) == 1 else parts[0].get("danji_class"),
        "supply_type": next(iter(supplies)) if len(supplies) == 1 else parts[0].get("supply_type"),
    }


def multi_kapt_row_to_attrs(kapt: pd.DataFrame, idxs: list[int]) -> dict[str, Any]:
    ordered = order_multi_idxs(kapt, idxs)
    parts = [kapt_row_to_attrs(kapt, i) for i in ordered]
    return aggregate_attr_dicts(parts)


def _str_or_none(value: object, *, max_len: int | None = None) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    if max_len is not None and len(s) > max_len:
        return s[:max_len]
    return s


def builder_master_rows(kapt: pd.DataFrame, snapshot_ym: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in kapt.itertuples(index=False):
        rows.append(
            {
                "snapshot_ym": snapshot_ym,
                "danji_code": str(getattr(row, "단지코드", "") or "").strip(),
                "danji_name": _str_or_none(getattr(row, "단지명", None)),
                "sido_name": _str_or_none(getattr(row, "시도", None)),
                "sigungu_name": _str_or_none(getattr(row, "시군구", None)),
                "eupmyeon_name": _str_or_none(getattr(row, "읍면", None)),
                "dongri_name": _str_or_none(getattr(row, "동리", None)),
                "beopjungri_code": _str_or_none(getattr(row, "beopjungri_code", None)),
                "legal_address": _str_or_none(getattr(row, "법정동주소", None), max_len=300),
                "road_address": _str_or_none(getattr(row, "도로명주소", None), max_len=300),
                "lot_key": _str_or_none(getattr(row, "lot_key", None)),
                "danji_class": _str_or_none(getattr(row, "단지분류", None)),
                "supply_type": _str_or_none(getattr(row, "분양형태", None)),
                "approved_date": parse_approved_date(getattr(row, "사용승인일", None)),
                "dong_count": parse_int(getattr(row, "동수", None)),
                "households": parse_int(getattr(row, "세대수", None)),
                "households_sale": parse_int(getattr(row, "분양세대수", None)),
                "households_rent": parse_int(getattr(row, "임대세대수", None)),
                "builder_raw": _str_or_none(getattr(row, "시공사", None)),
                "developer_raw": _str_or_none(getattr(row, "시행사", None)),
                "structure_raw": _str_or_none(getattr(row, "건물구조", None)),
                "max_floor": parse_int(getattr(row, "최고층수", None)),
                "basement_floor": parse_int(getattr(row, "지하층수", None)),
                "parking_total": parse_int(getattr(row, "총주차대수", None)),
                "parking_ground": parse_int(getattr(row, "지상주차대수", None)),
                "parking_underground": parse_int(getattr(row, "지하주차대수", None)),
                "heating_type": _str_or_none(getattr(row, "난방방식", None)),
                "corridor_type": _str_or_none(getattr(row, "복도유형", None)),
                "source_file": _str_or_none(getattr(row, "source_file", None)),
                "pnu": _str_or_none(getattr(row, "pnu", None)),
            }
        )
    return rows


def attributes_rows(
    buildings: pd.DataFrame,
    kapt: pd.DataFrame,
    *,
    snapshot_ym: str,
    asset_type: str,
) -> pd.DataFrame:
    kapt_indexed = kapt[kapt["beopjungri_code"] != ""].reset_index(drop=True)
    by_lot, by_name, by_core, names_in_bj = build_kapt_indexes(kapt_indexed)
    by_pnu = build_pnu_index(kapt_indexed)

    out_rows: list[dict[str, Any]] = []
    for row in buildings.itertuples(index=False):
        tier_key, kapt_idxs = match_one(
            row,
            by_lot=by_lot,
            by_name=by_name,
            by_core=by_core,
            names_in_bj=names_in_bj,
        )
        kapt_idx = kapt_idxs[0] if len(kapt_idxs) == 1 else None
        match_tier, match_rule = TIER_RULE_MAP[tier_key]
        if match_tier not in ATTR_TIERS and match_tier != "D" and by_pnu:
            pnu = pnu_from_tx(
                None if pd.isna(row.beopjungri_code) else str(row.beopjungri_code),
                None if pd.isna(row.lot_number) else str(row.lot_number),
            )
            idxs = by_pnu.get(pnu or "", [])
            if len(idxs) == 1:
                krow = kapt_indexed.iloc[idxs[0]]
                skip = pnu_unique_skip_reason(
                    tx_name=row.display_name,
                    kapt_name=krow.get("단지명"),
                    approved_year=parse_approved_year(krow.get("사용승인일")),
                    building_year=parse_int(row.building_year),
                )
                if skip is None:
                    match_tier, match_rule = TIER_RULE_MAP["P_pnu_unique"]
                    kapt_idx = idxs[0]
        building_year = parse_int(row.building_year)
        rec: dict[str, Any] = {
            "snapshot_ym": snapshot_ym,
            "asset_type": asset_type,
            "building_key": row.building_key,
            "danji_code": None,
            "match_tier": match_tier,
            "match_rule": match_rule,
            "approved_year": None,
            "building_year": building_year,
            "year_diff": None,
            "builder_raw": None,
            "builder_norm": None,
            "builder_group": None,
            "developer_raw": None,
            "brand": None,
            "structure_raw": None,
            "structure_group": None,
            "households": None,
            "households_sale": None,
            "households_rent": None,
            "dong_count": None,
            "max_floor": None,
            "parking_total": None,
            "parking_per_household": None,
            "danji_class": None,
            "supply_type": None,
            "match_danji_codes": None,
            "n_tx": int(row.n_tx),
        }
        if match_tier in ATTR_TIERS and kapt_idx is not None:
            attrs = kapt_row_to_attrs(kapt_indexed, kapt_idx)
            rec.update(attrs)
            rec.pop("danji_name", None)
            if rec["approved_year"] is not None and building_year is not None:
                rec["year_diff"] = rec["approved_year"] - building_year
        elif match_tier in MULTI_ATTR_TIERS and len(kapt_idxs) > 1:
            if multi_fill_allowed(match_tier, row.display_name, kapt_indexed, kapt_idxs):
                attrs = multi_kapt_row_to_attrs(kapt_indexed, kapt_idxs)
                rec.update(attrs)
                rec.pop("danji_name", None)
                if rec["approved_year"] is not None and building_year is not None:
                    rec["year_diff"] = rec["approved_year"] - building_year
        out_rows.append(rec)
    return pd.DataFrame(out_rows)


def apply_ddl(engine) -> None:
    for name in (
        "049_collective_building_attributes.sql",
        "065_builder_master_pnu.sql",
        "066_cba_match_danji_codes.sql",
    ):
        ddl_path = REPO / "db" / name
        ddl = ddl_path.read_text(encoding="utf-8")
        with engine.begin() as conn:
            for stmt in ddl.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        log.info("applied DDL %s", ddl_path.name)


def delete_snapshot(engine, snapshot_ym: str, asset_type: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM collective_building_attributes WHERE snapshot_ym = :ym AND asset_type = :at"),
            {"ym": snapshot_ym, "at": asset_type},
        )
        conn.execute(
            text("DELETE FROM builder_master WHERE snapshot_ym = :ym"),
            {"ym": snapshot_ym},
        )


def insert_builder_master(engine, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    sql = text(
        """
        INSERT INTO builder_master (
            snapshot_ym, danji_code, danji_name, sido_name, sigungu_name,
            eupmyeon_name, dongri_name, beopjungri_code, legal_address, road_address,
            lot_key, danji_class, supply_type, approved_date, dong_count,
            households, households_sale, households_rent, builder_raw, developer_raw,
            structure_raw, max_floor, basement_floor, parking_total, parking_ground,
            parking_underground, heating_type, corridor_type, source_file, pnu
        ) VALUES (
            :snapshot_ym, :danji_code, :danji_name, :sido_name, :sigungu_name,
            :eupmyeon_name, :dongri_name, :beopjungri_code, :legal_address, :road_address,
            :lot_key, :danji_class, :supply_type, :approved_date, :dong_count,
            :households, :households_sale, :households_rent, :builder_raw, :developer_raw,
            :structure_raw, :max_floor, :basement_floor, :parking_total, :parking_ground,
            :parking_underground, :heating_type, :corridor_type, :source_file, :pnu
        )
        """
    )
    for start in range(0, len(rows), DEFAULT_CHUNK):
        chunk = rows[start : start + DEFAULT_CHUNK]
        with engine.begin() as conn:
            for rec in chunk:
                conn.execute(sql, rec)


def _sanitize_record(rec: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in rec.items():
        if v is None:
            out[k] = None
        elif isinstance(v, float) and pd.isna(v):
            out[k] = None
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def insert_attributes(engine, df: pd.DataFrame) -> None:
    if df.empty:
        return
    sql = text(
        """
        INSERT INTO collective_building_attributes (
            snapshot_ym, asset_type, building_key, danji_code, match_tier, match_rule,
            approved_year, building_year, year_diff, builder_raw, builder_norm,
            builder_group, developer_raw, brand, structure_raw, structure_group,
            households, households_sale, households_rent, dong_count, max_floor,
            parking_total, parking_per_household, danji_class, supply_type, n_tx,
            match_danji_codes
        ) VALUES (
            :snapshot_ym, :asset_type, :building_key, :danji_code, :match_tier, :match_rule,
            :approved_year, :building_year, :year_diff, :builder_raw, :builder_norm,
            :builder_group, :developer_raw, :brand, :structure_raw, :structure_group,
            :households, :households_sale, :households_rent, :dong_count, :max_floor,
            :parking_total, :parking_per_household, :danji_class, :supply_type, :n_tx,
            :match_danji_codes
        )
        """
    )
    records = [_sanitize_record(r) for r in df.to_dict(orient="records")]
    for rec in records:
        rec.setdefault("match_danji_codes", None)
        rec.pop("danji_name", None)
    for start in range(0, len(records), DEFAULT_CHUNK):
        chunk = records[start : start + DEFAULT_CHUNK]
        with engine.begin() as conn:
            for rec in chunk:
                conn.execute(sql, rec)


def _tier_label(tier: str) -> str:
    labels = {
        "A": "A name_exact",
        "B": "B name_core",
        "C": "C lot_exact",
        "D": "D lot_multi",
        "E": "E contains_unique",
        "F": "F contains_multi",
        "P": "P pnu_unique",
        "T": "T title_pnu",
        "Z": "Z no_match",
    }
    return labels.get(tier, tier)


def print_report(
    attrs: pd.DataFrame,
    kapt: pd.DataFrame,
    *,
    buildings: pd.DataFrame,
) -> None:
    total_b = len(attrs)
    total_tx = int(attrs["n_tx"].sum())
    kapt_with_bj = int((kapt["beopjungri_code"] != "").sum())
    kapt_total = len(kapt)

    print("\n=== K-apt beopjungri_code conversion ===")
    print(f"  rows: {kapt_total:,}  with beopjungri_code: {kapt_with_bj:,}  ({100 * kapt_with_bj / max(kapt_total, 1):.1f}%)")

    print("\n=== match tier (buildings / tx) ===")
    grp = attrs.groupby("match_tier", sort=False).agg(
        buildings=("building_key", "count"),
        tx=("n_tx", "sum"),
    )
    tier_order = ["A", "B", "C", "D", "E", "F", "P", "T", "Z"]
    abc_tx = 0
    abce_tx = 0
    for tier in tier_order:
        if tier not in grp.index:
            continue
        r = grp.loc[tier]
        b = int(r.buildings)
        tx = int(r.tx)
        if tier in ("A", "B", "C"):
            abc_tx += tx
        if tier in ("A", "B", "C", "E", "P"):
            abce_tx += tx
        print(
            f"  {_tier_label(tier):22s}  {b:>6,} ({100 * b / total_b:5.1f}%)"
            f"  tx {tx:>10,} ({100 * tx / total_tx:5.1f}%)"
        )
    print(f"\n  A+B+C tx-weighted: {100 * abc_tx / total_tx:.1f}%")
    print(f"  A+B+C+E+P tx-weighted: {100 * abce_tx / total_tx:.1f}%")

    print("\n=== year_diff (K-apt approved_year - building_year) ===")
    for tier in ("A", "B", "C", "E", "P"):
        sub = attrs[(attrs["match_tier"] == tier) & attrs["year_diff"].notna()]
        if sub.empty:
            continue
        exact = (sub["year_diff"] == 0).mean() * 100
        within1 = (sub["year_diff"].abs() <= 1).mean() * 100
        over3 = (sub["year_diff"].abs() > 3).mean() * 100
        print(f"  tier {tier}: n={len(sub):,}  exact={exact:.1f}%  within1yr={within1:.1f}%  >3yr={over3:.1f}%")

    print("\n=== building_year bucket matched tx % ===")
    bld = buildings.copy()
    bld["building_year"] = pd.to_numeric(bld["building_year"], errors="coerce")
    merged = attrs.merge(
        bld[["building_key", "building_year"]],
        on="building_key",
        how="left",
        suffixes=("", "_b"),
    )
    merged["matched"] = merged["match_tier"].isin(list(ATTR_TIERS | MULTI_ATTR_TIERS))

    def bucket(y: float | int | None) -> str:
        if y is None or pd.isna(y):
            return "(missing)"
        y = int(y)
        if y <= 1999:
            return "~1999"
        if y <= 2009:
            return "2000-2009"
        if y <= 2019:
            return "2010-2019"
        if y <= 2023:
            return "2020-2023"
        return "2024+"

    merged["year_bucket"] = merged["building_year"].map(bucket)
    for label in ("~1999", "2000-2009", "2010-2019", "2020-2023", "2024+"):
        sub = merged[merged["year_bucket"] == label]
        if sub.empty:
            continue
        tx = int(sub["n_tx"].sum())
        matched_tx = int(sub.loc[sub["matched"], "n_tx"].sum())
        print(f"  {label:12s}  matched tx {100 * matched_tx / max(tx, 1):5.1f}%  (tx {tx:,})")

    print(f"\n  buildings: {total_b:,}  total_tx: {total_tx:,}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="K-apt 단지 속성 → collective_building_attributes")
    p.add_argument("--snapshot-ym", default=None, help="스냅샷 YYYYMM (기본: 파일명에서 유추)")
    p.add_argument("--kapt-file", default=None, help="K-apt xlsx 경로")
    p.add_argument("--asset-type", default="apartment")
    p.add_argument("--replace", action="store_true", help="해당 snapshot_ym 행 삭제 후 재적재")
    p.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 리포트만")
    p.add_argument("--apply-ddl", action="store_true", help="DDL 049 적용 후 실행")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    kapt_path = Path(args.kapt_file) if args.kapt_file else default_kapt_path()
    snapshot_ym = args.snapshot_ym or infer_snapshot_ym(kapt_path)
    log.info("snapshot_ym=%s  kapt=%s  asset_type=%s", snapshot_ym, kapt_path.name, args.asset_type)

    engine = create_engine(db_url(), pool_pre_ping=True)
    if args.apply_ddl:
        apply_ddl(engine)

    with engine.connect() as conn:
        region_map = load_region_map(conn)
        buildings = load_buildings(conn, args.asset_type)

    kapt = attach_kapt_pnu(load_kapt(region_map, kapt_path))
    log.info("K-apt rows=%s  CH2 buildings=%s", len(kapt), len(buildings))

    bm_rows = builder_master_rows(kapt, snapshot_ym)
    attrs = attributes_rows(buildings, kapt, snapshot_ym=snapshot_ym, asset_type=args.asset_type)

    print_report(attrs, kapt, buildings=buildings)

    if args.dry_run:
        log.info("dry-run: skip DB write")
        return

    if args.replace:
        delete_snapshot(engine, snapshot_ym, args.asset_type)

    insert_builder_master(engine, bm_rows)
    insert_attributes(engine, attrs)
    log.info(
        "loaded builder_master=%s  collective_building_attributes=%s",
        len(bm_rows),
        len(attrs),
    )


if __name__ == "__main__":
    main()
