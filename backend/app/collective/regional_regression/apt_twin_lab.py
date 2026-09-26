"""아파트 재고만으로 고른 읍면동 쌍둥이의 지역회귀 비교.

설계: docs/lab/APT_TWIN_REGRESSION_LAB.md
제품 지역회귀 식과 지역프로필 점수는 바꾸지 않는다.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.collective.building_stats_query import latest_mart_snapshot, stats_as_of_label
from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN
from app.collective.danji_attributes import ATTRIBUTES_TABLE
from app.collective.regional_regression.engine import (
    _assessed_land_price_sql,
    _eligible_mask,
    _flags,
    _latest_snapshot_ym,
)
from app.collective.regional_regression.schemas import RegionalRegressionVariables

_PIPE = Path(__file__).resolve().parents[4] / "pipeline"
if str(_PIPE) not in sys.path:
    sys.path.insert(0, str(_PIPE))

from region_scope import region_name_of, region_sidoes  # noqa: E402

CORE = (
    "building_age",
    "max_floor",
    "households",
    "parking_per_household",
    "assessed_land_price",
)
CORE_LABEL = {
    "building_age": "연식",
    "max_floor": "최고층",
    "households": "세대수",
    "parking_per_household": "세대당 주차",
    "assessed_land_price": "개별공시지가",
}
STOCK_COLS = (
    "n_complexes",
    "n_tx",
    "age_median",
    "age_iqr",
    "floor_median",
    "floor_iqr",
    "hh_median",
    "hh_iqr",
    "park_median",
    "park_iqr",
)
PRICE_COLS = (
    "price_median",
    "price_iqr",
    "land_median",
    "land_iqr",
)
STRUCT_COLS = STOCK_COLS + ("land_median", "land_iqr")
PRICE_DIST_COLS = (
    "price_p25",
    "price_p50",
    "price_p75",
    "price_mean",
    "price_cv",
)
E4_STRUCT_KEEP = 20
E4_PRICE_KEEP = 10
PRODUCT_TWIN_KEEP = 5
VARS = RegionalRegressionVariables(
    households=True,
    max_floor=True,
    building_age=True,
    parking=True,
    structure=False,
    builder=False,
    asset_type_dummy=False,
    assessed_land_price=True,
)
COSINE_MIN = 0.70
SIGN_MIN = 4
CV_GAIN_MIN = 0.10


def run_pilot_band(conn: Connection, *, addr1: str, selection: str = "stock") -> dict[str, Any]:
    """같은 권역에서 적격 단지 20~40곳인 읍면동을 한 번에 계산한다.

    selection=stock 은 재고 구성만, price 는 재고 구성에 가격 분포를 더한다.
    """
    frame, meta, eligible, profiles = _prepare(conn, addr1)
    cols = _selection_cols(selection)
    band = profiles.loc[(profiles["n_complexes"] >= 20) & (profiles["n_complexes"] <= 40)].sort_values("label")
    rows = [_anchor_result(eligible, profiles, str(region_id), cols) for region_id in band.index]
    return {
        "as_of_label": meta["as_of_label"],
        "region_name": meta["region_name"],
        "selection": selection,
        "n_anchors": len(rows),
        "anchors": rows,
    }


def _prepare(conn: Connection, addr1: str):
    frame, meta = _load_region(conn, addr1.strip())
    if frame.empty:
        raise RuntimeError("이 권역의 아파트 단지 표본이 없습니다")
    return _finish_prepare(conn, frame, meta)


def _prepare_national(conn: Connection):
    """실험 3. 읍면동 단위는 유지하고 후보 범위만 전국으로 연다."""
    frame, meta = _load_apartments(conn, None, region_name="전국")
    if frame.empty:
        raise RuntimeError("전국 아파트 단지 표본이 없습니다")
    return _finish_prepare(conn, frame, meta)


def _finish_prepare(conn: Connection, frame: pd.DataFrame, meta: dict[str, Any]):
    eligible = frame.loc[_eligible_mask(frame, VARS, min_tx=5)].copy()
    _fill_eup_names(conn, eligible)
    return frame, meta, eligible, _profiles(eligible)


def _selection_cols(selection: str) -> tuple[str, ...]:
    if selection == "price":
        return STOCK_COLS + PRICE_COLS
    if selection == "stock":
        return STOCK_COLS
    raise RuntimeError("selection 은 stock 또는 price")


def run_anchor(conn: Connection, *, addr1: str, addr2: str, addr4: str) -> dict[str, Any]:
    frame, meta = _load_region(conn, addr1.strip())
    if frame.empty:
        raise RuntimeError("이 권역의 아파트 단지 표본이 없습니다")
    eligible = frame.loc[_eligible_mask(frame, VARS, min_tx=5)].copy()
    profiles = _profiles(eligible)
    anchor_id = _match_anchor(profiles, addr1=addr1, addr2=addr2, addr4=addr4)
    result = _anchor_result(eligible, profiles, anchor_id, STOCK_COLS)
    return {
        "as_of_label": meta["as_of_label"],
        "region_name": meta["region_name"],
        **result,
        "pilot": _pilot_sample(profiles),
        "rules": {
            "cosine_min": COSINE_MIN,
            "sign_min": SIGN_MIN,
            "cv_gain_min": CV_GAIN_MIN,
        },
    }


def _anchor_result(
    eligible: pd.DataFrame,
    profiles: pd.DataFrame,
    anchor_id: str,
    cols: tuple[str, ...],
) -> dict[str, Any]:
    anchor = profiles.loc[anchor_id]
    twins = _rank_twins(profiles, anchor_id, cols)
    anchor_rows = eligible.loc[eligible["region_id"] == anchor_id].sort_values("building_key").copy()
    n_anchor = int(len(anchor_rows))
    coef_anchor = _std_coefs(anchor_rows) if n_anchor >= 20 else None
    compared = []
    for twin in twins[:5]:
        rows = eligible.loc[eligible["region_id"] == twin["region_id"]].sort_values("building_key")
        coef_t = _std_coefs(rows)
        gate = _gate(coef_anchor, coef_t)
        compared.append({**twin, "n": int(len(rows)), "coefficients": coef_t, "gate": gate})
    passed = [row for row in compared if row["gate"]["pass"]]
    contrast = compared[0] if compared and not compared[0]["gate"]["pass"] else None
    steps = None
    if coef_anchor is not None and n_anchor >= 20:
        if passed:
            chosen = [(row["label"], eligible.loc[eligible["region_id"] == row["region_id"]].sort_values("building_key")) for row in passed[:3]]
            steps = _cumulative(anchor_rows, chosen, role="주 분석")
        elif contrast is not None:
            chosen = [(contrast["label"], eligible.loc[eligible["region_id"] == contrast["region_id"]].sort_values("building_key"))]
            steps = _cumulative(anchor_rows, chosen, role="대조(유사도 미달 1위)")
    return {
        "anchor": {
            "label": str(anchor["label"]),
            "n": n_anchor,
            "in_pilot_band": 20 <= n_anchor <= 40,
            "coefficients": coef_anchor,
        },
        "twins": compared,
        "steps": steps,
    }


def _fill_eup_names(conn: Connection, df: pd.DataFrame) -> None:
    codes = sorted({c for c in df["region_id"].astype(str) if len(c) == 8 and c.isdigit()})
    if not codes:
        return
    rows = []
    stmt = text(
        """
        SELECT DISTINCT ON (eupmyeondong_code)
               eupmyeondong_code, btrim(eupmyeondong_name::text) AS eup_name
        FROM region_codes
        WHERE eupmyeondong_code IN :codes
          AND eupmyeondong_name IS NOT NULL
        ORDER BY eupmyeondong_code, eupmyeondong_name
        """
    ).bindparams(bindparam("codes", expanding=True))
    for start in range(0, len(codes), 400):
        rows.extend(conn.execute(stmt, {"codes": codes[start : start + 400]}).fetchall())
    names = {str(r.eupmyeondong_code).strip(): str(r.eup_name).strip() for r in rows if r.eup_name}
    missing = df["addr4"].isna() | df["addr4"].astype(str).str.strip().isin({"", "nan", "None"})
    df.loc[missing, "addr4"] = df.loc[missing, "region_id"].map(names)
    df["label"] = (
        df["addr1"].fillna("").str.strip()
        + " "
        + df["addr2"].fillna("").str.strip()
        + " "
        + df["addr4"].fillna("").astype(str).str.strip()
    ).str.replace(r"\s+", " ", regex=True).str.strip()


def _load_region(conn: Connection, addr1: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    sido_code = conn.execute(
        text(
            """
            SELECT sido_code
            FROM region_codes
            WHERE btrim(sido_name::text) = :name
            ORDER BY sido_code
            LIMIT 1
            """
        ),
        {"name": addr1},
    ).scalar()
    if not sido_code:
        raise RuntimeError("시도명을 region_codes에서 찾지 못했습니다")
    code = str(sido_code).strip()[:2]
    names = _sido_names(conn, region_sidoes(code))
    if addr1 not in names:
        names.append(addr1)
    return _load_apartments(conn, names, region_name=region_name_of(code) or code)


def _load_apartments(
    conn: Connection,
    sidos: list[str] | None,
    *,
    region_name: str,
    as_of: date | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    latest, _ = latest_mart_snapshot(conn)
    snap = _latest_snapshot_ym(conn)
    if as_of is None:
        as_of = latest
    if as_of is None or not snap:
        raise RuntimeError("집합 단지 스냅샷이 없습니다")
    land_select, land_join = _assessed_land_price_sql(conn)
    sido_sql = "AND btrim(m.addr1::text) IN :sidos" if sidos else ""
    stmt = text(
        f"""
        SELECT m.building_key, m.display_name, m.median, m.count AS n_tx,
               m.building_year, m.addr1, m.addr2, m.addr4, m.asset_type,
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
          AND m.asset_type = 'apartment'
          {sido_sql}
        """
    )
    params: dict[str, Any] = {"as_of": as_of, "snap": snap}
    if sidos:
        stmt = stmt.bindparams(bindparam("sidos", expanding=True))
        params["sidos"] = sidos
    rows = conn.execute(stmt, params).mappings().all()
    df = pd.DataFrame(rows)
    if df.empty:
        return df, {"as_of_label": stats_as_of_label(as_of), "region_name": region_name}
    as_of_year = int(as_of.year)
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
    code8 = df["beopjungri_code"].fillna("").astype(str).str.strip().str[:8]
    named = (
        df["addr1"].fillna("").str.strip()
        + "|"
        + df["addr2"].fillna("").str.strip()
        + "|"
        + df["addr4"].fillna("").str.strip()
    )
    df["region_id"] = np.where(code8.str.len() == 8, code8, named)
    df["label"] = (
        df["addr1"].fillna("").str.strip()
        + " "
        + df["addr2"].fillna("").str.strip()
        + " "
        + df["addr4"].fillna("").str.strip()
    ).str.replace(r"\s+", " ", regex=True).str.strip()
    return df, {"as_of_label": stats_as_of_label(as_of), "region_name": region_name}


def _sido_names(conn: Connection, codes: frozenset[str]) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT btrim(sido_name::text) AS sido_name
            FROM region_codes
            WHERE left(sido_code::text, 2) IN :codes
              AND sido_name IS NOT NULL
            """
        ).bindparams(bindparam("codes", expanding=True)),
        {"codes": list(codes)},
    ).fetchall()
    return [str(r.sido_name) for r in rows if r.sido_name]


def _profiles(df: pd.DataFrame) -> pd.DataFrame:
    def _iqr(s: pd.Series) -> float:
        return float(s.quantile(0.75) - s.quantile(0.25))

    rows = []
    for region_id, part in df.groupby("region_id"):
        rows.append(
            {
                "region_id": region_id,
                "label": str(part["label"].mode().iloc[0]) if not part["label"].mode().empty else str(region_id),
                "addr1": str(part["addr1"].iloc[0] or "").strip(),
                "addr2": str(part["addr2"].iloc[0] or "").strip(),
                "addr4": str(part["addr4"].iloc[0] or "").strip(),
                "n_complexes": int(len(part)),
                "n_tx": float(part["n_tx"].sum()),
                "age_median": float(part["building_age"].median()),
                "age_iqr": _iqr(part["building_age"]),
                "floor_median": float(part["max_floor"].median()),
                "floor_iqr": _iqr(part["max_floor"]),
                "hh_median": float(part["households"].median()),
                "hh_iqr": _iqr(part["households"]),
                "park_median": float(part["parking_per_household"].median()),
                "park_iqr": _iqr(part["parking_per_household"]),
                "price_median": float(part["median"].median()),
                "price_iqr": _iqr(part["median"]),
                "price_p25": float(part["median"].quantile(0.25)),
                "price_p50": float(part["median"].median()),
                "price_p75": float(part["median"].quantile(0.75)),
                "price_mean": float(part["median"].mean()),
                "price_cv": _cv(part["median"]),
                "land_median": float(part["assessed_land_price"].median()),
                "land_iqr": _iqr(part["assessed_land_price"]),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    need = list(STOCK_COLS + PRICE_COLS + PRICE_DIST_COLS)
    return out.dropna(subset=need).set_index("region_id")


def _cv(s: pd.Series) -> float:
    mean = float(s.mean())
    if not np.isfinite(mean) or abs(mean) < 1e-8:
        return float("nan")
    return float(s.std(ddof=0) / mean)


def _match_anchor(profiles: pd.DataFrame, *, addr1: str, addr2: str, addr4: str) -> str:
    hit = profiles.index[
        (profiles["addr1"] == addr1.strip())
        & (profiles["addr2"] == addr2.strip())
        & (profiles["addr4"] == addr4.strip())
    ]
    if len(hit) == 0:
        raise RuntimeError("기준 읍면동을 권역 표본에서 찾지 못했습니다. 시군구·읍면동 이름을 확인해 주세요.")
    if len(hit) > 1:
        raise RuntimeError("같은 이름의 읍면동이 둘 이상입니다. 코드를 나눠 지정하는 단계는 아직 없습니다.")
    return str(hit[0])


def _rank_twins(profiles: pd.DataFrame, anchor_id: str, cols: tuple[str, ...] = STOCK_COLS) -> list[dict[str, Any]]:
    pool = profiles.loc[profiles["n_complexes"] >= 20]
    if anchor_id not in pool.index:
        pool = pd.concat([pool, profiles.loc[[anchor_id]]])
    z = pool[list(cols)].apply(lambda s: (s - s.mean()) / (s.std(ddof=0) or 1.0))
    base = z.loc[anchor_id].to_numpy(float)
    dist = np.sqrt(((z.to_numpy(float) - base) ** 2).sum(axis=1))
    order = np.argsort(dist)
    out = []
    for pos in order:
        region_id = str(z.index[pos])
        if region_id == anchor_id:
            continue
        out.append(
            {
                "region_id": region_id,
                "label": str(pool.loc[region_id, "label"]),
                "distance": round(float(dist[pos]), 3),
                "n_stock": int(pool.loc[region_id, "n_complexes"]),
            }
        )
        if len(out) >= 8:
            break
    return out


def _std_coefs(df: pd.DataFrame) -> dict[str, float] | None:
    if len(df) < 20:
        return None
    y = np.log(pd.to_numeric(df["median"], errors="coerce").to_numpy(float))
    x = df.loc[:, list(CORE)].to_numpy(float)
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        return None
    sd = x.std(axis=0, ddof=0)
    if np.any(sd < 1e-8):
        return None
    z = (x - x.mean(axis=0)) / sd
    try:
        fit = sm.OLS(y, sm.add_constant(z, has_constant="add")).fit()
    except (ValueError, np.linalg.LinAlgError):
        return None
    return {name: round(float(fit.params[i + 1]), 4) for i, name in enumerate(CORE)}


def _gate(anchor: dict[str, float] | None, twin: dict[str, float] | None) -> dict[str, Any]:
    if not anchor or not twin:
        return {"pass": False, "reason": "다섯 계수를 추정할 단지가 20곳 미만입니다", "cosine": None, "sign_match": 0}
    a = np.array([anchor[k] for k in CORE], float)
    b = np.array([twin[k] for k in CORE], float)
    sign_match = int(np.sum(np.sign(a) == np.sign(b)))
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    cosine = float(np.dot(a, b) / denom) if denom else None
    ok = sign_match >= SIGN_MIN and cosine is not None and cosine >= COSINE_MIN
    return {
        "pass": ok,
        "reason": "통과" if ok else "부호 4개 미만 또는 코사인 0.70 미만",
        "cosine": None if cosine is None else round(cosine, 3),
        "sign_match": sign_match,
        "rows": [
            {
                "variable": CORE_LABEL[k],
                "anchor": anchor[k],
                "twin": twin[k],
                "same_sign": bool(np.sign(anchor[k]) == np.sign(twin[k])),
                "gap": round(anchor[k] - twin[k], 4),
            }
            for k in CORE
        ],
    }


def _pilot_sample(profiles: pd.DataFrame) -> list[dict[str, Any]]:
    band = profiles.loc[(profiles["n_complexes"] >= 20) & (profiles["n_complexes"] <= 40)].sort_index()
    if band.empty:
        return []
    pick = band.sample(n=min(30, len(band)), random_state=42).sort_values("label")
    return [
        {"addr1": str(row.addr1), "addr2": str(row.addr2), "addr4": str(row.addr4), "label": str(row.label), "n": int(row.n_complexes)}
        for row in pick.itertuples(index=False)
    ]


def _cumulative(anchor: pd.DataFrame, twins: list[tuple[str, pd.DataFrame]], *, role: str) -> dict[str, Any]:
    n = len(anchor)
    k = 5 if n >= 25 else 4
    perm = np.random.default_rng(42).permutation(n)
    folds = [anchor.iloc[fold] for fold in np.array_split(perm, k)]
    trains = [anchor.drop(anchor.index[fold]) for fold in np.array_split(perm, k)]
    local_scores = [_mape(train, test, extras=[]) for train, test in zip(trains, folds)]
    local = _mean(local_scores)
    steps = []
    best = local
    used: list[tuple[str, pd.DataFrame]] = []
    for label, rows in twins:
        used.append((label, rows))
        pool = _mean([_mape(train, test, extras=used, dummy=False) for train, test in zip(trains, folds)])
        dummy = _mean([_mape(train, test, extras=used, dummy=True) for train, test in zip(trains, folds)])
        improved = dummy is not None and best is not None and dummy < best
        steps.append(
            {
                "k": len(used),
                "labels": [name for name, _ in used],
                "pool": pool,
                "dummy": dummy,
                "pool_gain": _gain(local, pool),
                "dummy_gain": _gain(local, dummy),
                "stop": not improved and len(used) > 0,
            }
        )
        if not improved:
            break
        best = dummy
    return {"role": role, "folds": k, "local": local, "steps": steps}


def _mape(
    train: pd.DataFrame,
    test: pd.DataFrame,
    extras: list[tuple[str, pd.DataFrame]],
    *,
    dummy: bool = False,
) -> float | None:
    parts = [train]
    for _, extra in extras:
        if extra is not None and len(extra):
            parts.append(extra)
    fit_df = pd.concat(parts, ignore_index=True)
    y = np.log(fit_df["median"].to_numpy(float))
    x = fit_df.loc[:, list(CORE)].to_numpy(float)
    blocks = [np.ones(len(fit_df)), x]
    if dummy and extras:
        start = len(train)
        for extra in extras:
            col = np.zeros(len(fit_df))
            col[start : start + len(extra[1])] = 1.0
            start += len(extra[1])
            blocks.append(col.reshape(-1, 1))
    design = np.column_stack(blocks)
    try:
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    resid = y - design @ beta
    smear = float(np.mean(np.exp(resid)))
    xt = test.loc[:, list(CORE)].to_numpy(float)
    pieces = [np.ones(len(test)), xt]
    if dummy and extras:
        pieces.extend([np.zeros((len(test), 1)) for _ in extras])
    pred = np.exp(np.column_stack(pieces) @ beta) * smear
    actual = test["median"].to_numpy(float)
    ok = np.isfinite(pred) & (pred > 0) & np.isfinite(actual) & (actual > 0)
    if not ok.any():
        return None
    return float(np.mean(np.abs(actual[ok] - pred[ok]) / actual[ok]) * 100)


def _mean(vals: list[float | None]) -> float | None:
    clean = [v for v in vals if v is not None and np.isfinite(v)]
    return round(float(np.mean(clean)), 2) if clean else None


def _gain(base: float | None, other: float | None) -> float | None:
    if base is None or other is None or base == 0:
        return None
    return round((base - other) / base, 3)


def _feature_dists(pool: pd.DataFrame, anchor: pd.Series, cols: tuple[str, ...]) -> pd.Series:
    """후보 풀의 평균·표준편차로 표준화한 유클리드 거리. 앵커는 풀에 있어도 거리만 계산한다."""
    x = pool.loc[:, list(cols)].astype(float)
    mu = x.mean()
    sd = x.std(ddof=0).replace(0, 1.0)
    z = (x - mu) / sd
    base = ((anchor.loc[list(cols)].astype(float) - mu) / sd).to_numpy(float)
    dist = np.sqrt(((z.to_numpy(float) - base) ** 2).sum(axis=1))
    return pd.Series(dist, index=pool.index)


def _coef_score(anchor: dict[str, float] | None, twin: dict[str, float] | None) -> dict[str, Any]:
    """다섯 표준화 계수의 코사인과 부호 일치 수. 탈락 기준으로 쓰지 않는다."""
    if not anchor or not twin:
        return {"cosine": None, "sign_match": None, "old_gate": False}
    a = np.array([anchor[k] for k in CORE], float)
    b = np.array([twin[k] for k in CORE], float)
    sign_match = int(np.sum(np.sign(a) == np.sign(b)))
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    cosine = float(np.dot(a, b) / denom) if denom else None
    old_gate = sign_match >= SIGN_MIN and cosine is not None and cosine >= COSINE_MIN
    return {
        "cosine": None if cosine is None else round(cosine, 3),
        "sign_match": sign_match,
        "old_gate": old_gate,
    }


def _split_folds(anchor: pd.DataFrame) -> tuple[int, list[pd.DataFrame], list[pd.DataFrame]]:
    anchor = anchor.sort_values("building_key")
    n = len(anchor)
    k = 5 if n >= 25 else 4
    perm = np.random.default_rng(42).permutation(n)
    folds = [anchor.iloc[idx] for idx in np.array_split(perm, k)]
    trains = [anchor.drop(anchor.index[idx]) for idx in np.array_split(perm, k)]
    return k, trains, folds


def experiment4_anchor(
    eligible: pd.DataFrame,
    profiles: pd.DataFrame,
    anchor_id: str,
    *,
    with_cv: bool = True,
) -> dict[str, Any]:
    """실험 4. 전국 구조 20곳 → 가격분포 10곳 → 계수 점수 → 식 이전 CV.

    계수 코사인 0.70은 순위를 자르지 않는다. 쌍둥이 여부는 기준 지역 단지의
    이전 CV-MAPE가 단독보다 줄어드는지로 본다.
    """
    pool = profiles.loc[profiles["n_complexes"] >= 20]
    anchor = profiles.loc[anchor_id]
    struct = _feature_dists(pool, anchor, STRUCT_COLS)
    struct = struct.loc[struct.index.astype(str) != str(anchor_id)]
    price = _feature_dists(pool, anchor, PRICE_DIST_COLS)
    short = struct.nsmallest(E4_STRUCT_KEEP)
    chosen = price.loc[short.index].nsmallest(E4_PRICE_KEEP)
    anchor_rows = eligible.loc[eligible["region_id"] == anchor_id].sort_values("building_key")
    n_anchor = int(len(anchor_rows))
    coef_anchor = _std_coefs(anchor_rows) if n_anchor >= 20 else None
    folds = None
    local = None
    if with_cv and coef_anchor is not None and n_anchor >= 20:
        k, trains, tests = _split_folds(anchor_rows)
        local = _mean([_mape(train, test, extras=[]) for train, test in zip(trains, tests)])
        folds = (trains, tests, k)
    twins = []
    for region_id, price_dist in chosen.items():
        rows = eligible.loc[eligible["region_id"] == region_id].sort_values("building_key")
        score = _coef_score(coef_anchor, _std_coefs(rows))
        transfer = pool_mape = dummy = None
        if folds is not None and len(rows):
            trains, tests, _k = folds
            extra = [(str(profiles.loc[region_id, "label"]), rows)]
            transfer = _mean([_mape(rows, test, extras=[]) for test in tests])
            pool_mape = _mean([_mape(train, test, extras=extra, dummy=False) for train, test in zip(trains, tests)])
            dummy = _mean([_mape(train, test, extras=extra, dummy=True) for train, test in zip(trains, tests)])
        twins.append(
            {
                "region_id": str(region_id),
                "label": str(profiles.loc[region_id, "label"]),
                "addr1": str(profiles.loc[region_id, "addr1"]),
                "n": int(profiles.loc[region_id, "n_complexes"]),
                "struct_distance": round(float(struct.loc[region_id]), 3),
                "price_distance": round(float(price_dist), 3),
                **score,
                "transfer": transfer,
                "pool": pool_mape,
                "dummy": dummy,
                "transfer_gain": _gain(local, transfer),
                "dummy_gain": _gain(local, dummy),
            }
        )
    helpful = [row for row in twins if row["transfer_gain"] is not None and row["transfer_gain"] > 0]
    best = max(helpful, key=lambda row: row["transfer_gain"]) if helpful else None
    return {
        "anchor": {
            "label": str(anchor["label"]),
            "addr1": str(anchor["addr1"]),
            "n": n_anchor,
            "local": local,
        },
        "twins": twins,
        "n_transfer_better": len(helpful),
        "best": None
        if best is None
        else {
            "label": best["label"],
            "addr1": best["addr1"],
            "transfer": best["transfer"],
            "transfer_gain": best["transfer_gain"],
            "dummy": best["dummy"],
            "dummy_gain": best["dummy_gain"],
            "cosine": best["cosine"],
            "old_gate": best["old_gate"],
        },
    }


_NATIONAL_CACHE: dict[tuple[str, str], tuple[pd.DataFrame, dict[str, Any]]] = {}


def rank_display_twins(profiles: pd.DataFrame, anchor_id: str, *, keep: int = PRODUCT_TWIN_KEEP) -> list[str]:
    """제품 목록. 구조 거리 20곳 안에서 가격분포 거리가 짧은 순으로 keep곳.

    후보 풀은 적격 단지가 20곳 이상인 읍면동이다. 기준 지역은 그 풀에 없어도
    거리만 계산하고, 목록에서는 뺀다.
    """
    if anchor_id not in profiles.index:
        raise KeyError(anchor_id)
    pool = profiles.loc[profiles["n_complexes"] >= 20]
    if pool.empty:
        return []
    anchor = profiles.loc[anchor_id]
    struct = _feature_dists(pool, anchor, STRUCT_COLS)
    struct = struct.loc[struct.index.astype(str) != str(anchor_id)]
    struct = struct.replace([np.inf, -np.inf], np.nan).dropna()
    if struct.empty:
        return []
    price = _feature_dists(pool, anchor, PRICE_DIST_COLS)
    short = struct.nsmallest(min(E4_STRUCT_KEEP, int(len(struct))))
    chosen = price.reindex(short.index).replace([np.inf, -np.inf], np.nan).dropna()
    if chosen.empty:
        return []
    return [str(region_id) for region_id in chosen.nsmallest(min(keep, int(len(chosen)))).index]


def _national_profiles(conn: Connection) -> tuple[pd.DataFrame, dict[str, Any]]:
    latest, _ = latest_mart_snapshot(conn)
    snap = _latest_snapshot_ym(conn)
    key = (str(latest), str(snap))
    hit = _NATIONAL_CACHE.get(key)
    if hit is not None:
        return hit
    _frame, meta, _eligible, profiles = _prepare_national(conn)
    _NATIONAL_CACHE.clear()
    _NATIONAL_CACHE[key] = (profiles, meta)
    return profiles, meta


def _profile_public_row(profiles: pd.DataFrame, region_id: str, *, rank: int | None) -> dict[str, Any]:
    row = profiles.loc[region_id]
    addr1 = str(row.addr1).strip()
    addr2 = str(row.addr2).strip()
    addr4 = str(row.addr4).strip()
    if addr2 in {"", "nan", "None"}:
        addr2 = addr1
    label = str(row.label).strip() or " ".join(part for part in (addr1, addr2, addr4) if part)
    return {
        "rank": rank,
        "label": label,
        "addr1": addr1,
        "addr2": addr2,
        "addr4": addr4,
        "region_addr": f"{addr1}|{addr2}|{addr4}",
        "n_complexes": int(row.n_complexes),
    }


def _match_product_anchor(
    profiles: pd.DataFrame,
    *,
    addr1: str,
    addr2: str,
    addr4: str,
    region_code: str,
) -> str:
    code = region_code.strip()
    if len(code) >= 8 and code[:8].isdigit() and code[:8] in profiles.index:
        return code[:8]
    a1, a2, a4 = addr1.strip(), addr2.strip(), addr4.strip()
    if a2 == FLAT_SIDO_ADDR2_TOKEN:
        hit = profiles.index[(profiles["addr1"] == a1) & (profiles["addr4"] == a4)]
    else:
        hit = profiles.index[
            (profiles["addr1"] == a1) & (profiles["addr2"] == a2) & (profiles["addr4"] == a4)
        ]
    if len(hit) == 0:
        raise RuntimeError("이 읍면동의 아파트 재고로 쌍둥이 순위를 만들지 못했습니다. 거래와 핵심 변수가 있는 단지가 필요합니다.")
    if len(hit) > 1:
        raise RuntimeError("같은 이름의 읍면동이 둘 이상입니다. 지도에서 그 지역을 한 곳만 선택한 뒤 다시 여세요.")
    return str(hit[0])


def _scope_anchor_rows(profiles: pd.DataFrame, addr1: str, addr2: str) -> list[dict[str, Any]]:
    hit = profiles.loc[profiles["addr1"] == addr1.strip()]
    if addr2.strip() and addr2.strip() != FLAT_SIDO_ADDR2_TOKEN:
        hit = hit.loc[hit["addr2"] == addr2.strip()]
    if hit.empty:
        return []
    ordered = hit.sort_values("label")
    return [_profile_public_row(profiles, str(region_id), rank=None) for region_id in ordered.index]


def list_display_twins(
    conn: Connection,
    *,
    addr1: str,
    addr2: str = "",
    addr4: str = "",
    region_code: str = "",
) -> dict[str, Any]:
    """쌍둥이지역 탭. 읍면동이 정해지면 1–5위, 아니면 그 시군구의 기준 후보만."""
    profiles, meta = _national_profiles(conn)
    as_of_label = str(meta.get("as_of_label") or "")
    if not addr4.strip() and not region_code.strip():
        return {
            "as_of_label": as_of_label,
            "anchor": None,
            "twins": [],
            "scope_anchors": _scope_anchor_rows(profiles, addr1, addr2),
        }
    anchor_id = _match_product_anchor(
        profiles,
        addr1=addr1,
        addr2=addr2,
        addr4=addr4,
        region_code=region_code,
    )
    twin_ids = rank_display_twins(profiles, anchor_id, keep=PRODUCT_TWIN_KEEP)
    return {
        "as_of_label": as_of_label,
        "anchor": _profile_public_row(profiles, anchor_id, rank=None),
        "twins": [
            _profile_public_row(profiles, region_id, rank=rank)
            for rank, region_id in enumerate(twin_ids, start=1)
        ],
        "scope_anchors": [],
    }
