"""Building identity for collective stats aggregation."""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# 집합 2단계(D-084·Phase A 결정): 다른 단지가 한 이름 키로 묶인 키만 동 단위로 나눈다.
# 목록 밖 키는 기존 문자열 그대로 → 해시 불변.
SPLIT_UNITS_PATH = Path(__file__).resolve().parent / "data" / "p2_split_units.csv"
SPLIT_SUFFIX = "|emd:"

# 분양·입주권(building_key 전용). 원본 building_name / display_name 은 유지.
_PRESALE_KEY_ASSET = "presale"

# 보수적 브랜드 alias — 키 정규화에만 사용
_BRAND_ALIAS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"I[\s\-]?PARK", re.IGNORECASE), "아이파크"),
)

_JE_DANJI_RE = re.compile(r"제(\d+)단지")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(s: str | None) -> str:
    """주소·표시용 가벼운 정규화(공백 축소). 원문 형태를 크게 바꾸지 않음."""
    if not s:
        return ""
    t = str(s).strip()
    t = _WHITESPACE_RE.sub(" ", t)
    return t


def normalize_building_name_for_key(s: str | None, *, asset_type: str) -> str:
    """building_key 에 넣는 단지명.

    분양권만 강한 규칙(공백 제거·영문 브랜드 alias·단지번호).
    그 외 유형은 normalize_name 과 동일(기존 키 호환).
    """
    base = normalize_name(s)
    if not base:
        return ""
    if asset_type != _PRESALE_KEY_ASSET:
        return base
    return _normalize_presale_name_for_key(base)


def _normalize_presale_name_for_key(name: str) -> str:
    t = unicodedata.normalize("NFC", name)
    t = _WHITESPACE_RE.sub("", t)
    for pat, repl in _BRAND_ALIAS_PATTERNS:
        t = pat.sub(repl, t)
    t = _JE_DANJI_RE.sub(r"\1단지", t)
    return t


def _norm_series(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def _sha256_series(raw: pd.Series) -> pd.Series:
    return raw.map(lambda x: hashlib.sha256(x.encode("utf-8")).hexdigest())


def building_key_raw_series(df: pd.DataFrame, asset_type: str) -> pd.Series:
    """attach_building_identity 와 같은 키 원문 문자열(해시 전)."""
    out = df
    a1 = _norm_series(out["addr1"]) if "addr1" in out.columns else pd.Series("", index=out.index)
    a2 = _norm_series(out["addr2"]) if "addr2" in out.columns else pd.Series("", index=out.index)
    a3 = _norm_series(out["addr3"]) if "addr3" in out.columns else pd.Series("", index=out.index)
    a4 = _norm_series(out["addr4"]) if "addr4" in out.columns else pd.Series("", index=out.index)
    lot = _norm_series(out["lot_number"]) if "lot_number" in out.columns else pd.Series("", index=out.index)
    road = _norm_series(out["road_name"]) if "road_name" in out.columns else pd.Series("", index=out.index)
    name = _norm_series(out["building_name"]) if "building_name" in out.columns else pd.Series("", index=out.index)
    if asset_type == _PRESALE_KEY_ASSET:
        name_for_key = name.map(lambda n: normalize_building_name_for_key(n, asset_type=asset_type))
    else:
        name_for_key = name
    has_name = name != ""
    raw_named = asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|name:" + name_for_key
    raw_unnamed = asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|" + a4 + "|" + lot + "|" + road
    return raw_named.where(has_name, raw_unnamed)


def split_key_from_raw(raw: str, unit_emd8: str) -> str:
    """분할 대상 키의 동 단위 새 키 = sha256(기존 원문 + '|emd:' + 동 단위 대표 법정동8)."""
    return hashlib.sha256((raw + SPLIT_SUFFIX + unit_emd8).encode("utf-8")).hexdigest()


@lru_cache(maxsize=4)
def load_split_units(path: str | None = None) -> dict[str, tuple[dict[str, str], str]]:
    """base_key → ({법정동8: 조각 대표 법정동8}, 코드 없는 행이 갈 1조각 대표 법정동8).

    decision=split 행만 읽는다. 환경변수 CH2_COLLECTIVE_KEY_SPLIT=0 이면 빈 목록(비상 해제용).
    """
    if os.environ.get("CH2_COLLECTIVE_KEY_SPLIT", "1") == "0":
        return {}
    p = Path(path) if path else SPLIT_UNITS_PATH
    if not p.is_file():
        return {}
    units: dict[str, dict[str, str]] = {}
    part1: dict[str, str] = {}
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("decision") != "split":
                continue
            bk = row["base_key"]
            units.setdefault(bk, {})[row["emd8"]] = row["unit_emd8"]
            if str(row.get("part")) == "1":
                part1[bk] = row["unit_emd8"]
    return {bk: (m, part1.get(bk) or sorted(m.values())[0]) for bk, m in units.items()}


def resolve_split_unit(units: tuple[dict[str, str], str], emd8: str | None) -> str:
    """행의 법정동8 → 조각 대표 법정동8. 처음 보는 동이면 그 동 자체가 새 조각, 코드 없으면 1조각."""
    m, default = units
    e = (emd8 or "").strip()[:8]
    if not e:
        return default
    return m.get(e, e)


def apply_building_key_split(
    df: pd.DataFrame,
    asset_type: str,
    *,
    split_units: dict[str, tuple[dict[str, str], str]] | None = None,
    code_col: str = "beopjungri_code",
) -> pd.DataFrame:
    """법정동 코드가 붙은 뒤 호출. 분할 목록의 키만 동 단위 새 키로 바꾼다(그 밖은 그대로)."""
    units_all = load_split_units() if split_units is None else split_units
    if not units_all or df.empty or "building_key" not in df.columns:
        return df
    hit = df["building_key"].isin(units_all.keys())
    if not hit.any():
        return df
    out = df.copy()
    sub = out.loc[hit]
    raw = building_key_raw_series(sub, asset_type)
    same = _sha256_series(raw) == sub["building_key"]
    if not same.all():
        log.warning("split: 원문 재현 불일치 %d행 — 키 유지", int((~same).sum()))
    codes = sub[code_col] if code_col in sub.columns else pd.Series("", index=sub.index)
    new_keys = [
        split_key_from_raw(r, resolve_split_unit(units_all[k], "" if c is None or c != c else str(c)))
        if ok else k
        for r, k, c, ok in zip(raw, sub["building_key"], codes, same)
    ]
    out.loc[hit, "building_key"] = new_keys
    return out


def attach_building_identity(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    """building_key·display_name 컬럼을 벡터 연산으로 추가.

    display_name / building_name 원문 성격은 유지하고,
    building_key 만 (분양권 시) 정규화된 단지명을 사용한다.
    분할 목록 키는 법정동 코드가 붙은 뒤 apply_building_key_split 으로 나눈다.
    """
    out = df.copy()
    a1 = _norm_series(out["addr1"]) if "addr1" in out.columns else pd.Series("", index=out.index)
    a2 = _norm_series(out["addr2"]) if "addr2" in out.columns else pd.Series("", index=out.index)
    a3 = _norm_series(out["addr3"]) if "addr3" in out.columns else pd.Series("", index=out.index)
    a4 = _norm_series(out["addr4"]) if "addr4" in out.columns else pd.Series("", index=out.index)
    lot = _norm_series(out["lot_number"]) if "lot_number" in out.columns else pd.Series("", index=out.index)
    road = _norm_series(out["road_name"]) if "road_name" in out.columns else pd.Series("", index=out.index)
    name = _norm_series(out["building_name"]) if "building_name" in out.columns else pd.Series("", index=out.index)

    if asset_type == _PRESALE_KEY_ASSET:
        name_for_key = name.map(lambda n: normalize_building_name_for_key(n, asset_type=asset_type))
    else:
        name_for_key = name

    has_name = name != ""
    raw_named = asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|name:" + name_for_key
    raw_unnamed = (
        asset_type + "|" + a1 + "|" + a2 + "|" + a3 + "|" + a4 + "|" + lot + "|" + road
    )
    out["building_key"] = _sha256_series(raw_named.where(has_name, raw_unnamed))

    addr3_lot = (a3 + " " + lot).str.strip()
    out["display_name"] = name.where(
        has_name,
        addr3_lot.where(addr3_lot != "", road).replace("", "(주소 미상)"),
    )
    return out


def derive_display_name(
    *,
    building_name: str | None,
    addr3: str | None,
    lot_number: str | None,
    road_name: str | None,
) -> str:
    name = normalize_name(building_name)
    if name:
        return name
    parts = [normalize_name(addr3), normalize_name(lot_number)]
    label = " ".join(p for p in parts if p)
    if label:
        return label
    return normalize_name(road_name) or "(주소 미상)"


def derive_building_key(
    *,
    asset_type: str,
    addr1: str | None,
    addr2: str | None,
    addr3: str | None,
    addr4: str | None,
    building_name: str | None,
    lot_number: str | None,
    road_name: str | None,
) -> str:
    a1 = normalize_name(addr1)
    a2 = normalize_name(addr2)
    a3 = normalize_name(addr3)
    a4 = normalize_name(addr4)
    name = normalize_building_name_for_key(building_name, asset_type=asset_type)
    if name:
        raw = f"{asset_type}|{a1}|{a2}|{a3}|name:{name}"
    else:
        raw = "|".join(
            [
                asset_type,
                a1,
                a2,
                a3,
                a4,
                normalize_name(lot_number),
                normalize_name(road_name),
            ]
        )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
