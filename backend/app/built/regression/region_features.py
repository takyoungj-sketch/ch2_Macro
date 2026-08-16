"""거래 행에 지역 프로필 공변량 join (쌍둥이 로직 보강 · R1/RT).

규칙: 각 행의 eupmyeondong_code → 그 지역의 프로필.
앵커 지역 특성을 Twin 행에 복사하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import text

from app.collective.db import get_collective_engine

# block_id == 컬럼명
REGION_BLOCK_IDS: tuple[str, ...] = (
    "region_population",
    "region_land_p50",
    "region_apt_p50",
    "region_apt_n",
    "region_comm_p50",
    "region_comm_n",
)


@dataclass(frozen=True)
class RegionFeatureSpec:
    block_id: str
    label: str
    profile_keys: tuple[str, ...]  # 우선순위 순
    kind: str  # level | activity


REGION_FEATURE_SPECS: tuple[RegionFeatureSpec, ...] = (
    RegionFeatureSpec("region_population", "지역인구", ("population",), "level"),
    RegionFeatureSpec(
        "region_land_p50",
        "지역토지가격",
        (
            # catalog / market_stats 정규 키 (일부 배치에만 존재)
            "land_commercial_median",
            "land_residential_median",
            "land_industrial_median",
            # v2.1-national 실데이터: top-jimok 요약만 적재된 경우가 많음
            "land_top1_mean_manwon_per_sqm",
        ),
        "level",
    ),
    RegionFeatureSpec("region_apt_p50", "지역아파트가격", ("apartment_median",), "level"),
    RegionFeatureSpec("region_apt_n", "지역아파트거래량", ("apartment_count",), "activity"),
    RegionFeatureSpec("region_comm_p50", "지역상가가격", ("commercial_median",), "level"),
    RegionFeatureSpec("region_comm_n", "지역상가거래량", ("commercial_count",), "activity"),
)

_SPEC_BY_ID = {s.block_id: s for s in REGION_FEATURE_SPECS}


def is_region_block(block_id: str) -> bool:
    return block_id in _SPEC_BY_ID


def normalize_region_feature_tier(tier: str | None) -> str:
    """'price' | 'full' (aliases: price+activity → full)."""
    t = (tier or "full").strip().lower().replace(" ", "")
    if t in {"price", "price_only", "level", "p0_price"}:
        return "price"
    if t in {"full", "price+activity", "price_activity", "all", "activity"}:
        return "full"
    return "full"


def region_blocks_for_asset(
    asset_type: str | None,
    *,
    tier: str | None = "full",
) -> list[str]:
    """유형·tier별 region 후보.

    - price: 가격수준만 (land / apt / 유형 p50) — Twin 가격수준 혼입 가설 1차
    - full: price + population + 거래량(n)
    """
    at = (asset_type or "commercial").strip().lower()
    t = normalize_region_feature_tier(tier)
    price = ["region_land_p50", "region_apt_p50"]
    if at == "commercial":
        price = price + ["region_comm_p50"]
    if t == "price":
        return list(price)
    # full
    activity = ["region_population", "region_apt_n"]
    if at == "commercial":
        activity = activity + ["region_comm_n"]
    # price first, then activity (stable order for tests / logs)
    return list(price) + activity


def _norm_eup_code(raw: object) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if len(s) < 8:
        return None
    return s[:8]


def _scalar_from_features(features: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in features:
            continue
        val = features.get(key)
        if val is None:
            continue
        try:
            f = float(val)
        except (TypeError, ValueError):
            continue
        if pd.isna(f):
            continue
        return f
    return None


def fetch_region_feature_map(
    codes: Iterable[str],
    *,
    profile_version: str,
    window_years: int,
    coll_conn=None,
) -> dict[str, dict[str, float | None]]:
    """region_code → {block_id: value}."""
    uniq = sorted({c for c in (_norm_eup_code(x) for x in codes) if c})
    if not uniq:
        return {}

    own_conn = False
    if coll_conn is None:
        eng = get_collective_engine()
        if eng is None:
            return {}
        coll_conn = eng.connect()
        own_conn = True

    try:
        rows = coll_conn.execute(
            text(
                """
                SELECT DISTINCT ON (region_code)
                    region_code, features
                FROM regional_profile
                WHERE region_level = 'eupmyeondong'
                  AND profile_version = :pv
                  AND window_years = :wy
                  AND region_code = ANY(:codes)
                ORDER BY region_code, as_of_month DESC
                """
            ),
            {"pv": profile_version, "wy": int(window_years), "codes": uniq},
        ).mappings().all()
    finally:
        if own_conn:
            coll_conn.close()

    out: dict[str, dict[str, float | None]] = {}
    for row in rows:
        code = _norm_eup_code(row.get("region_code"))
        if not code:
            continue
        feats = row.get("features") or {}
        if not isinstance(feats, dict):
            continue
        mapped: dict[str, float | None] = {}
        for spec in REGION_FEATURE_SPECS:
            mapped[spec.block_id] = _scalar_from_features(feats, spec.profile_keys)
        out[code] = mapped
    return out


def attach_region_features(
    df: pd.DataFrame,
    *,
    profile_version: str = "v2.1-national",
    window_years: int = 3,
    coll_conn=None,
    block_ids: Iterable[str] | None = None,
) -> pd.DataFrame:
    """df 복사본에 region_* 컬럼을 붙인다. join 키 = 각 행 eupmyeondong_code."""
    if df is None or df.empty:
        return df
    if "eupmyeondong_code" not in df.columns:
        return df

    wanted = list(block_ids) if block_ids is not None else list(REGION_BLOCK_IDS)
    wanted = [b for b in wanted if is_region_block(b)]
    if not wanted:
        return df

    out = df.copy()
    codes = out["eupmyeondong_code"].map(_norm_eup_code)
    feat_map = fetch_region_feature_map(
        codes.dropna().unique().tolist(),
        profile_version=profile_version,
        window_years=window_years,
        coll_conn=coll_conn,
    )

    for block_id in wanted:
        out[block_id] = codes.map(
            lambda c, bid=block_id: (feat_map.get(c) or {}).get(bid) if c else None
        )
        out[block_id] = pd.to_numeric(out[block_id], errors="coerce")
    return out
