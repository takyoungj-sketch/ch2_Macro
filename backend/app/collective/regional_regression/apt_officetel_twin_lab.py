"""아파트 순위를 유지한 채, 오피스텔 거리를 더하는 1차 비교.

절차: docs/lab/APT_OFFICETEL_TWIN_LAB.md
제품 순위와 지역회귀 식은 바꾸지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.building_stats_query import latest_mart_snapshot, stats_as_of_label
from app.collective.danji_attributes import ATTRIBUTES_TABLE
from app.collective.db import get_collective_engine
from app.collective.regional_regression.apt_twin_lab import (
    PRICE_DIST_COLS,
    PRODUCT_TWIN_KEEP,
    STRUCT_COLS,
    _cv,
    _feature_dists,
    _fill_eup_names,
    _flags,
    _latest_snapshot_ym,
    _match_product_anchor,
    _prepare_national,
    _profile_public_row,
    _profile_text,
    _scope_anchor_rows,
    rank_display_twins,
)
from app.collective.regional_regression.engine import _assessed_land_price_sql, _eligible_mask
from app.collective.regional_regression.schemas import RegionalRegressionVariables

W_CAP = 0.5
OFF_GAIN_MIN = 0.10
APT_GAIN_FLOOR = -0.05
HOLD_FRAC = 0.25
SEED = 42
BAND_KEEP = 40
STRUCT_KEEP = 20
TOP_KEEP = 5
OFF_MIN = 5
THIN_MAX = 14
FIT_COLS = ("building_age", "max_floor", "households", "assessed_land_price")
OFF_DIST_COLS = ("n_complexes", "age_median", "age_iqr", "floor_median", "floor_iqr")
OFF_TWIN_STRUCT = (
    "n_complexes",
    "n_tx",
    "age_median",
    "age_iqr",
    "floor_median",
    "floor_iqr",
    "hh_median",
    "hh_iqr",
    "land_median",
    "land_iqr",
)
_OFF_TWIN_CACHE: dict[tuple[str, str], tuple[pd.DataFrame, dict[str, Any]]] = {}
PRIMARY = "share"
REFERENCE = ("half", "sqrt")
OUT_PATH = Path(__file__).resolve().parents[4] / "docs" / "lab" / "apt_officetel_twin_lab.json"

OFF_VARS = RegionalRegressionVariables(
    households=True,
    max_floor=True,
    building_age=True,
    parking=False,
    structure=False,
    builder=False,
    asset_type_dummy=True,
    assessed_land_price=True,
)


def anchor_weight(n_apt: int, n_off: int, scheme: str) -> float:
    """기준 지역 가중치. 후보 단지 수는 넣지 않는다."""
    if scheme == "apartment":
        return 0.0
    if scheme == "half":
        return 0.5
    apt = max(int(n_apt), 0)
    off = max(int(n_off), 0)
    if scheme == "share":
        denom = apt + off
        if denom <= 0:
            return 0.0
        return float(min(off / denom, W_CAP))
    if scheme == "sqrt":
        denom = float(np.sqrt(apt) + np.sqrt(off))
        if denom <= 0:
            return 0.0
        return float(np.sqrt(off) / denom)
    raise RuntimeError("scheme 은 apartment, share, half, sqrt")


def _z(values: pd.Series) -> pd.Series:
    clean = values.astype(float)
    mu = float(clean.mean(skipna=True))
    sd = float(clean.std(ddof=0, skipna=True))
    if not np.isfinite(sd) or sd < 1e-8:
        sd = 1.0
    if not np.isfinite(mu):
        mu = 0.0
    return (clean - mu) / sd


def combine_distances(d_apt: pd.Series, d_off: pd.Series, w: float) -> pd.Series:
    """거리를 각각 표준화한 뒤 가중. 오피스텔 거리가 없으면 아파트 거리만."""
    weight = float(np.clip(w, 0.0, 1.0))
    z_apt = _z(d_apt)
    aligned = d_off.reindex(d_apt.index)
    z_off = _z(aligned)
    mixed = (1.0 - weight) * z_apt + weight * z_off
    return mixed.where(z_off.notna(), z_apt)


def rank_joint_twins(
    apt_profiles: pd.DataFrame,
    off_profiles: pd.DataFrame,
    anchor_id: str,
    *,
    w: float,
    keep: int = TOP_KEEP,
) -> list[str]:
    """구조 거리는 가중 결합, 5위는 아파트 가격분포."""
    if anchor_id not in apt_profiles.index:
        raise KeyError(anchor_id)
    pool = apt_profiles.loc[apt_profiles["n_complexes"] >= 20]
    if pool.empty:
        return []
    anchor = apt_profiles.loc[anchor_id]
    d_apt = _feature_dists(pool, anchor, STRUCT_COLS)
    d_apt = d_apt.loc[d_apt.index.astype(str) != str(anchor_id)]
    d_apt = d_apt.replace([np.inf, -np.inf], np.nan).dropna()
    if d_apt.empty:
        return []
    d_off = _officetel_dists(d_apt.index, off_profiles, anchor_id)
    combined = combine_distances(d_apt, d_off, w)
    combined = combined.replace([np.inf, -np.inf], np.nan).dropna()
    if combined.empty:
        return []
    short = combined.nsmallest(min(STRUCT_KEEP, int(len(combined))))
    price = _feature_dists(pool, anchor, PRICE_DIST_COLS)
    chosen = price.reindex(short.index).replace([np.inf, -np.inf], np.nan).dropna()
    if chosen.empty:
        return []
    return [str(region_id) for region_id in chosen.nsmallest(min(keep, int(len(chosen)))).index]


def _officetel_dists(index: pd.Index, off_profiles: pd.DataFrame, anchor_id: str) -> pd.Series:
    out = pd.Series(np.nan, index=index, dtype=float)
    if off_profiles.empty or str(anchor_id) not in set(off_profiles.index.astype(str)):
        return out
    known = set(off_profiles.index.astype(str))
    labels = [idx for idx in index if str(idx) in known and str(idx) != str(anchor_id)]
    if not labels:
        return out
    sub = off_profiles.loc[labels]
    dist = _feature_dists(sub, off_profiles.loc[str(anchor_id)], OFF_DIST_COLS)
    return out.combine_first(dist.replace([np.inf, -np.inf], np.nan))


def load_officetel_frame(conn: Connection) -> tuple[pd.DataFrame, dict[str, Any]]:
    latest, _ = latest_mart_snapshot(conn)
    snap = _latest_snapshot_ym(conn)
    if latest is None or not snap:
        raise RuntimeError("집합 단지 스냅샷이 없습니다")
    land_select, land_join = _assessed_land_price_sql(conn)
    rows = conn.execute(
        text(
            f"""
            SELECT m.building_key, m.display_name, m.median, m.count AS n_tx,
                   m.building_year, m.addr1, m.addr2, m.addr3, m.addr4, m.asset_type,
                   m.beopjungri_code,
                   a.match_tier, a.match_rule, a.households, a.max_floor, a.parking_per_household,
                   a.approved_year, a.structure_group, a.builder_group, a.attr_quality_flags,
                   {land_select}
            FROM collective_building_stats m
            LEFT JOIN {ATTRIBUTES_TABLE} a
              ON a.building_key = m.building_key
             AND a.asset_type = m.asset_type
             AND a.snapshot_ym = :snap
            {land_join}
            WHERE m.as_of_month = :as_of
              AND m.window_years = 3
              AND m.asset_type = 'officetel'
            """
        ),
        {"as_of": latest, "snap": snap},
    ).mappings().all()
    df = pd.DataFrame(rows)
    meta = {"as_of_label": stats_as_of_label(latest), "snapshot_ym": str(snap)}
    if df.empty:
        return df, meta
    as_of_year = int(latest.year)
    vintage = pd.to_numeric(df["approved_year"], errors="coerce").fillna(
        pd.to_numeric(df["building_year"], errors="coerce")
    )
    df["building_age"] = as_of_year - vintage
    df.loc[(df["building_age"] < 0) | (df["building_age"] > 80), "building_age"] = np.nan
    for col in ("households", "max_floor", "parking_per_household", "assessed_land_price", "median"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["n_tx"] = pd.to_numeric(df["n_tx"], errors="coerce").fillna(0)
    flags = df["attr_quality_flags"].map(_flags)
    df.loc[flags.map(lambda s: "hh_zero" in s or "scale_inconsistent" in s), "households"] = np.nan
    df.loc[flags.map(lambda s: "floor_implausible" in s or "scale_inconsistent" in s), "max_floor"] = np.nan
    df.loc[flags.map(lambda s: "parking_implausible" in s), "parking_per_household"] = np.nan
    _null_nonpositive_scale(df)
    code8 = df["beopjungri_code"].fillna("").astype(str).str.strip().str[:8]
    named = (
        df["addr1"].fillna("").str.strip()
        + "|"
        + df["addr2"].fillna("").str.strip()
        + "|"
        + df["addr4"].fillna("").str.strip()
    )
    df["region_id"] = np.where(code8.str.len() == 8, code8, named)
    return df, meta


def officetel_profiles(eligible: pd.DataFrame) -> pd.DataFrame:
    if eligible.empty:
        return pd.DataFrame()

    def _iqr(series: pd.Series) -> float:
        return float(series.quantile(0.75) - series.quantile(0.25))

    rows = []
    for region_id, part in eligible.groupby("region_id"):
        rows.append(
            {
                "region_id": str(region_id),
                "n_complexes": int(len(part)),
                "n_tx": float(part["n_tx"].sum()),
                "age_median": float(part["building_age"].median()),
                "age_iqr": _iqr(part["building_age"]),
                "floor_median": float(part["max_floor"].median()),
                "floor_iqr": _iqr(part["max_floor"]),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.dropna(subset=list(OFF_DIST_COLS)).set_index("region_id")


def officetel_twin_profiles(eligible: pd.DataFrame) -> pd.DataFrame:
    """오피스텔 쌍둥이 프로필. 세대당 주차는 넣지 않는다."""
    if eligible.empty:
        return pd.DataFrame()

    def _iqr(series: pd.Series) -> float:
        return float(series.quantile(0.75) - series.quantile(0.25))

    rows = []
    for region_id, part in eligible.groupby("region_id"):
        price = part["median"]
        rows.append(
            {
                "region_id": str(region_id),
                "label": str(part["label"].mode().iloc[0]) if not part["label"].mode().empty else str(region_id),
                "addr1": str(part["addr1"].iloc[0] or "").strip(),
                "addr2": str(part["addr2"].iloc[0] or "").strip(),
                "addr3": _profile_text(part, "addr3"),
                "addr4": str(part["addr4"].iloc[0] or "").strip(),
                "n_complexes": int(len(part)),
                "n_tx": float(part["n_tx"].sum()),
                "age_median": float(part["building_age"].median()),
                "age_iqr": _iqr(part["building_age"]),
                "floor_median": float(part["max_floor"].median()),
                "floor_iqr": _iqr(part["max_floor"]),
                "hh_median": float(part["households"].median()),
                "hh_iqr": _iqr(part["households"]),
                "land_median": float(part["assessed_land_price"].median()),
                "land_iqr": _iqr(part["assessed_land_price"]),
                "price_p25": float(price.quantile(0.25)),
                "price_p50": float(price.median()),
                "price_p75": float(price.quantile(0.75)),
                "price_mean": float(price.mean()),
                "price_cv": _cv(price),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    need = list(OFF_TWIN_STRUCT + PRICE_DIST_COLS)
    return out.dropna(subset=need).set_index("region_id")


def _null_nonpositive_scale(df: pd.DataFrame) -> None:
    """회귀와 같이 0 이하 세대수·최고층은 결측이다."""
    df.loc[df["households"] <= 0, "households"] = np.nan
    df.loc[df["max_floor"] <= 0, "max_floor"] = np.nan


def _officetel_twin_national(conn: Connection) -> tuple[pd.DataFrame, dict[str, Any]]:
    latest, _ = latest_mart_snapshot(conn)
    snap = _latest_snapshot_ym(conn)
    key = (str(latest), str(snap))
    hit = _OFF_TWIN_CACHE.get(key)
    if hit is not None:
        return hit
    raw, meta = load_officetel_frame(conn)
    eligible = raw.loc[_eligible_mask(raw, OFF_VARS, min_tx=5)].copy() if not raw.empty else raw
    if not eligible.empty:
        _fill_eup_names(conn, eligible)
        eligible["region_id"] = eligible["region_id"].astype(str)
        if "label" not in eligible.columns:
            eligible["label"] = (
                eligible["addr1"].fillna("").astype(str).str.strip()
                + " "
                + eligible["addr2"].fillna("").astype(str).str.strip()
                + " "
                + eligible["addr4"].fillna("").astype(str).str.strip()
            ).str.replace(r"\s+", " ", regex=True).str.strip()
    profiles = _as_str_index(officetel_twin_profiles(eligible))
    _OFF_TWIN_CACHE.clear()
    _OFF_TWIN_CACHE[key] = (profiles, meta)
    return profiles, meta


def list_officetel_display_twins(
    conn: Connection,
    *,
    addr1: str,
    addr2: str = "",
    addr4: str = "",
    region_code: str = "",
    addr3_list: list[str] | None = None,
) -> dict[str, Any]:
    """오피스텔만 선택한 쌍둥이지역 탭. 아파트 순위는 쓰지 않는다."""
    profiles, meta = _officetel_twin_national(conn)
    as_of_label = str(meta.get("as_of_label") or "")
    if profiles.empty:
        return {"as_of_label": as_of_label, "anchor": None, "twins": [], "scope_anchors": []}
    if not addr4.strip() and not region_code.strip():
        return {
            "as_of_label": as_of_label,
            "anchor": None,
            "twins": [],
            "scope_anchors": _scope_anchor_rows(profiles, addr1, addr2, addr3_list),
        }
    anchor_id = _match_product_anchor(
        profiles,
        addr1=addr1,
        addr2=addr2,
        addr4=addr4,
        region_code=region_code,
        stock_name="오피스텔",
    )
    twin_ids = rank_display_twins(
        profiles,
        anchor_id,
        keep=PRODUCT_TWIN_KEEP,
        struct_cols=OFF_TWIN_STRUCT,
    )
    return {
        "as_of_label": as_of_label,
        "anchor": _profile_public_row(profiles, anchor_id, rank=None),
        "twins": [
            _profile_public_row(profiles, region_id, rank=rank)
            for rank, region_id in enumerate(twin_ids, start=1)
        ],
        "scope_anchors": [],
    }


def holdout_mask(df: pd.DataFrame, *, seed: int = SEED, frac: float = HOLD_FRAC) -> pd.Series:
    """유형별로 같은 시드의 25%. 검증 행이 학습을 비우면 그 유형은 남기지 않는다."""
    mask = pd.Series(False, index=df.index)
    rng = np.random.default_rng(seed)
    for _, idx in df.groupby("asset_type").groups.items():
        ordered = df.loc[list(idx)].sort_values("building_key")
        n = int(len(ordered))
        n_test = int(round(n * frac))
        if n_test >= n:
            n_test = n - 1
        if n_test < 1:
            continue
        picked = rng.choice(n, size=n_test, replace=False)
        mask.loc[ordered.index.to_numpy()[picked]] = True
    return mask


def _design(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    y = np.log(pd.to_numeric(df["median"], errors="coerce").to_numpy(float))
    x = df.loc[:, list(FIT_COLS)].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    dummy = (df["asset_type"].astype(str) == "officetel").to_numpy(float).reshape(-1, 1)
    return y, np.column_stack([np.ones(len(df)), x, dummy])


def fit_holdout(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
    """기준 지역 검증 MAPE와 학습 표본의 유형 계수. 지역 더미는 없다."""
    empty = {"mape_apt": None, "mape_off": None, "type_coef": None, "type_se": None, "n_fit_apt": 0, "n_fit_off": 0}
    if train.empty or test.empty:
        return empty
    y, design = _design(train)
    ok = np.isfinite(y) & np.isfinite(design).all(axis=1)
    if int(ok.sum()) < len(FIT_COLS) + 2:
        return empty
    y = y[ok]
    design = design[ok]
    train_ok = train.iloc[np.flatnonzero(ok)]
    try:
        model = sm.OLS(y, design).fit()
        beta = np.asarray(model.params, float)
        se = float(model.bse[-1])
        coef = float(beta[-1])
    except (ValueError, np.linalg.LinAlgError):
        return empty
    resid = y - design @ beta
    smear = float(np.mean(np.exp(resid)))
    y_t, design_t = _design(test)
    pred = np.exp(design_t @ beta) * smear
    actual = pd.to_numeric(test["median"], errors="coerce").to_numpy(float)
    types = test["asset_type"].astype(str).to_numpy()
    mapes: dict[str, float | None] = {}
    for key, label in (("mape_apt", "apartment"), ("mape_off", "officetel")):
        picked = (
            (types == label)
            & np.isfinite(pred)
            & (pred > 0)
            & np.isfinite(actual)
            & (actual > 0)
            & np.isfinite(y_t)
        )
        mapes[key] = None if not picked.any() else float(np.mean(np.abs(actual[picked] - pred[picked]) / actual[picked]) * 100)
    return {
        **mapes,
        "type_coef": coef,
        "type_se": se if np.isfinite(se) else None,
        "n_fit_apt": int((train_ok["asset_type"].astype(str) == "apartment").sum()),
        "n_fit_off": int((train_ok["asset_type"].astype(str) == "officetel").sum()),
    }


def _region_rows(apt: pd.DataFrame, off: pd.DataFrame, region_id: str) -> pd.DataFrame:
    parts = []
    if not apt.empty:
        parts.append(apt.loc[apt["region_id"].astype(str) == str(region_id)])
    if not off.empty:
        parts.append(off.loc[off["region_id"].astype(str) == str(region_id)])
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["asset_type", "building_key"])


def _supply(off_profiles: pd.DataFrame, region_id: str | None) -> tuple[int | None, float | None]:
    if not region_id or off_profiles.empty or region_id not in off_profiles.index:
        return 0, 0.0
    row = off_profiles.loc[region_id]
    return int(row["n_complexes"]), float(row["n_tx"])


def _jaccard(left: list[str], right: list[str]) -> float | None:
    a, b = set(left), set(right)
    if not a and not b:
        return None
    return float(len(a & b) / len(a | b))


def _gain(base: float | None, other: float | None) -> float | None:
    if base is None or other is None or base == 0:
        return None
    return float((base - other) / base)


def _median(vals: list[float | None]) -> float | None:
    clean = [float(v) for v in vals if v is not None and np.isfinite(v)]
    if not clean:
        return None
    return float(np.median(clean))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if value is None or isinstance(value, str):
        return value
    return str(value)


def select_anchors(apt_profiles: pd.DataFrame, off_profiles: pd.DataFrame) -> pd.DataFrame:
    apt_n = apt_profiles["n_complexes"].astype(int)
    off_n = off_profiles["n_complexes"].astype(int) if not off_profiles.empty else pd.Series(dtype=int)
    rows = []
    for region_id in apt_profiles.index.astype(str):
        n_apt = int(apt_n.loc[region_id]) if region_id in apt_n.index else 0
        n_off = int(off_n.loc[region_id]) if region_id in off_n.index else 0
        if n_apt < 20 or n_off < OFF_MIN or region_id not in off_profiles.index:
            continue
        profile = apt_profiles.loc[region_id]
        rows.append(
            {
                "region_id": region_id,
                "label": str(profile["label"]),
                "n_apt": n_apt,
                "n_off": n_off,
                "n_tx_off": float(off_profiles.loc[region_id, "n_tx"]),
                "band": "thin" if n_off <= THIN_MAX else "thick",
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    picked = []
    for band in ("thin", "thick"):
        part = frame.loc[frame["band"] == band].sort_values("region_id")
        if part.empty:
            continue
        take = part.sample(n=min(BAND_KEEP, len(part)), random_state=SEED).sort_values("region_id")
        picked.append(take)
    return pd.concat(picked, ignore_index=True)


def evaluate_anchor(
    apt_profiles: pd.DataFrame,
    off_profiles: pd.DataFrame,
    apt_rows: pd.DataFrame,
    off_rows: pd.DataFrame,
    anchor: dict[str, Any],
) -> dict[str, Any]:
    region_id = str(anchor["region_id"])
    base_ids = rank_display_twins(apt_profiles, region_id, keep=TOP_KEEP)
    schemes = {
        "apartment": 0.0,
        "share": anchor_weight(int(anchor["n_apt"]), int(anchor["n_off"]), "share"),
        "half": 0.5,
        "sqrt": anchor_weight(int(anchor["n_apt"]), int(anchor["n_off"]), "sqrt"),
    }
    anchor_rows = _region_rows(apt_rows, off_rows, region_id)
    mask = holdout_mask(anchor_rows)
    test = anchor_rows.loc[mask]
    train_anchor = anchor_rows.loc[~mask]
    methods: dict[str, Any] = {}
    for name, weight in schemes.items():
        if name == "apartment":
            top = base_ids
        else:
            top = rank_joint_twins(apt_profiles, off_profiles, region_id, w=weight)
        rank1 = top[0] if top else None
        donor = _region_rows(apt_rows, off_rows, rank1) if rank1 else pd.DataFrame()
        train = train_anchor if donor.empty else pd.concat([train_anchor, donor], ignore_index=True)
        fit = fit_holdout(train, test)
        n_off, n_tx = _supply(off_profiles, rank1)
        methods[name] = {
            "w": weight,
            "top5": top,
            "rank1": rank1,
            "jaccard_vs_apartment": 1.0 if name == "apartment" else _jaccard(base_ids, top),
            "donor_off_n": n_off,
            "donor_off_tx": n_tx,
            **fit,
        }
    base = methods["apartment"]
    for name, row in methods.items():
        row["gain_apt"] = _gain(base["mape_apt"], row["mape_apt"])
        row["gain_off"] = _gain(base["mape_off"], row["mape_off"])
    return {
        "region_id": region_id,
        "label": str(anchor["label"]),
        "band": str(anchor["band"]),
        "n_apt": int(anchor["n_apt"]),
        "n_off": int(anchor["n_off"]),
        "n_tx_off": float(anchor["n_tx_off"]),
        "methods": methods,
    }


def _band_summary(rows: list[dict[str, Any]], band: str) -> dict[str, Any]:
    part = [row for row in rows if row["band"] == band]
    def col(scheme: str, key: str) -> list[float | None]:
        return [row["methods"][scheme].get(key) for row in part]

    primary = "share"
    gain_off = col(primary, "gain_off")
    gain_apt = col(primary, "gain_apt")
    med_off = _median(gain_off)
    med_apt = _median(gain_apt)
    passed = med_off is not None and med_apt is not None and med_off >= OFF_GAIN_MIN and med_apt > APT_GAIN_FLOOR
    out: dict[str, Any] = {
        "n": len(part),
        "primary_passes_gate": passed if band == "thin" else None,
        "median_jaccard_share": _median(col("share", "jaccard_vs_apartment")),
        "median_donor_off_n_apartment": _median(col("apartment", "donor_off_n")),
        "median_donor_off_n_share": _median(col("share", "donor_off_n")),
        "median_donor_off_tx_apartment": _median(col("apartment", "donor_off_tx")),
        "median_donor_off_tx_share": _median(col("share", "donor_off_tx")),
        "median_mape_apt_apartment": _median(col("apartment", "mape_apt")),
        "median_mape_off_apartment": _median(col("apartment", "mape_off")),
        "median_gain_apt_share": med_apt,
        "median_gain_off_share": med_off,
        "median_type_coef_share": _median(col("share", "type_coef")),
        "median_type_se_share": _median(col("share", "type_se")),
    }
    for scheme in REFERENCE:
        out[f"median_jaccard_{scheme}"] = _median(col(scheme, "jaccard_vs_apartment"))
        out[f"median_gain_off_{scheme}"] = _median(col(scheme, "gain_off"))
        out[f"median_gain_apt_{scheme}"] = _median(col(scheme, "gain_apt"))
        out[f"median_donor_off_n_{scheme}"] = _median(col(scheme, "donor_off_n"))
    return out


def _available_anchor_count(apt_profiles: pd.DataFrame, off_profiles: pd.DataFrame) -> dict[str, int]:
    apt_n = apt_profiles["n_complexes"].astype(int)
    off_n = off_profiles["n_complexes"].astype(int) if not off_profiles.empty else pd.Series(dtype=int)
    thin = thick = 0
    for region_id in apt_profiles.index.astype(str):
        n_apt = int(apt_n.loc[region_id]) if region_id in apt_n.index else 0
        n_off = int(off_n.loc[region_id]) if region_id in off_n.index else 0
        if n_apt < 20 or n_off < OFF_MIN or region_id not in off_profiles.index:
            continue
        if n_off <= THIN_MAX:
            thin += 1
        else:
            thick += 1
    return {"thin": thin, "thick": thick}


def _as_str_index(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.index = out.index.astype(str)
    return out


def run_comparison(conn: Connection) -> dict[str, Any]:
    _frame, meta, apt_rows, apt_profiles = _prepare_national(conn)
    off_raw, off_meta = load_officetel_frame(conn)
    off_eligible = off_raw.loc[_eligible_mask(off_raw, OFF_VARS, min_tx=5)].copy() if not off_raw.empty else off_raw
    if not off_eligible.empty:
        _fill_eup_names(conn, off_eligible)
        off_eligible["region_id"] = off_eligible["region_id"].astype(str)
    apt_profiles = _as_str_index(apt_profiles)
    off_profiles = _as_str_index(officetel_profiles(off_eligible))
    apt_rows = apt_rows.copy()
    apt_rows["region_id"] = apt_rows["region_id"].astype(str)
    available = _available_anchor_count(apt_profiles, off_profiles)
    anchors = select_anchors(apt_profiles, off_profiles)
    records = [
        evaluate_anchor(apt_profiles, off_profiles, apt_rows, off_eligible, row)
        for row in anchors.to_dict(orient="records")
    ]
    return {
        "as_of_label": meta.get("as_of_label"),
        "officetel_as_of_label": off_meta.get("as_of_label"),
        "rules": {
            "primary": PRIMARY,
            "w_cap": W_CAP,
            "off_gain_min": OFF_GAIN_MIN,
            "apt_gain_floor": APT_GAIN_FLOOR,
            "reference_schemes": list(REFERENCE),
            "off_dist": list(OFF_DIST_COLS),
            "fit": list(FIT_COLS) + ["atype_officetel"],
        },
        "n_apt_profiles": int(len(apt_profiles)),
        "n_off_profiles": int(len(off_profiles)),
        "n_anchors_available": available,
        "n_anchors_run": {
            "thin": int((anchors["band"] == "thin").sum()) if not anchors.empty else 0,
            "thick": int((anchors["band"] == "thick").sum()) if not anchors.empty else 0,
        },
        "bands": {"thin": _band_summary(records, "thin"), "thick": _band_summary(records, "thick")},
        "apply_to_product": False,
        "gate_note": "얇은 대역 본안이 문턱을 넘어도 같은 창 검증이라 화면은 바꾸지 않는다.",
        "anchors": records,
    }


def main() -> None:
    eng = get_collective_engine()
    if eng is None:
        raise SystemExit("COLLECTIVE_DATABASE_URL 없음")
    with eng.connect() as conn:
        payload = _jsonable(run_comparison(conn))
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_PATH)
    print(json.dumps({"bands": payload["bands"], "available": payload["n_anchors_available"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
