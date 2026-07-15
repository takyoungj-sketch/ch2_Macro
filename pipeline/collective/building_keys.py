"""Building identity for collective stats aggregation."""

from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

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


def attach_building_identity(df: pd.DataFrame, asset_type: str) -> pd.DataFrame:
    """building_key·display_name 컬럼을 벡터 연산으로 추가.

    display_name / building_name 원문 성격은 유지하고,
    building_key 만 (분양권 시) 정규화된 단지명을 사용한다.
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
