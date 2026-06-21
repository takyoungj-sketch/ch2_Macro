"""실험 1단계 — 지역 표현(더미 vs Regional Profile)의 회귀 설명력 비교.

CH2 Macro 가설 검증:
  "지역 고정효과(FE)는 가격의 큰 설명변수다. 그리고 Regional Profile(연속형)이
   지역 더미를 대체/보완할 수 있는가? 어느 프로필 블록이 실제로 기여하는가?"

매칭(건축물대장)이 전혀 필요 없는 실험이다. 거래는 지역코드로 profile/dummy 만 붙인다.

심판(KPI): in-sample R²/adjR² 가 아니라 **CV-MAPE / CV-R²(log)** 가 본선이다.
  (읍면동 더미는 자유도를 빨아먹어 in-sample R²를 항상 올리므로 신뢰 불가)

소스:
  collective_shop : 집합상가 (collective_stats.collective_commercial_transactions), y=log(unit_price)
  built           : 복합부동산 (built_stats.built_transactions, 토지+건물), y=log(price)

모델:
  M0_base / M_sgg_dummy / M_emd_dummy / M_prof_sgg / M_prof_emd
  + 프로필 블록 분해: M_prof_emd_pop / _land / _house / _all

사용:
  python collective_commercial/exp_region_vs_profile.py --source built --asset commercial --sido 충청북도
  python collective_commercial/exp_region_vs_profile.py --source collective_shop --sido 충청북도
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COLLECTIVE_URL = "postgresql+psycopg2://postgres:8972@localhost:5432/collective_stats"
BUILT_URL = "postgresql+psycopg2://postgres:8972@localhost:5432/built_stats"

SIDO_CODE_MAP = {
    "서울특별시": "11", "부산광역시": "26", "대구광역시": "27", "인천광역시": "28",
    "광주광역시": "29", "대전광역시": "30", "울산광역시": "31", "세종특별자치시": "36",
    "경기도": "41", "강원특별자치도": "51", "충청북도": "43", "충청남도": "44",
    "전북특별자치도": "52", "전라남도": "46", "경상북도": "47", "경상남도": "48",
    "제주특별자치도": "50",
}

# Regional Profile 블록 (y=건물가격과 다른 자산군 → 누수 없음)
BLOCK_POP = ["population", "population_density"]
BLOCK_LAND = ["land_residential_median", "land_commercial_median", "land_industrial_median"]
BLOCK_HOUSE = ["apartment_median", "rowhouse_median", "officetel_median"]
BLOCK_EXTRA = ["ratio_commercial_zone"]
ALL_KEYS = BLOCK_POP + BLOCK_LAND + BLOCK_HOUSE + BLOCK_EXTRA

RARE_MIN = 10
SEED = 42
N_FOLDS = 5


# ----------------------------------------------------------------------------
def _s(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return str(v).strip()


def load_collective_shop(eng, sido_name: str) -> pd.DataFrame:
    df = pd.read_sql(
        text(
            """
            SELECT addr1, addr2, addr3, addr4,
                   zone_type, building_use, gross_area, building_year, building_age,
                   floor, unit_price, price, contract_year
            FROM collective_commercial_transactions
            WHERE addr1 = :sido AND asset_type = 'collective_shop'
              AND unit_price IS NOT NULL AND unit_price > 0
              AND gross_area IS NOT NULL AND gross_area > 0
            """
        ),
        eng, params={"sido": sido_name},
    )
    df["y_kind"] = "unit_price"
    df["land_area"] = np.nan
    return df


def load_built(eng, sido_name: str, asset: str) -> pd.DataFrame:
    df = pd.read_sql(
        text(
            """
            SELECT addr1, sigungu_code, eupmyeondong_code,
                   zone_type, building_use, gross_area, land_area, building_age,
                   floor, price, contract_year
            FROM built_transactions
            WHERE addr1 = :sido AND asset_type = :asset AND is_valid = true
              AND price IS NOT NULL AND price > 0
              AND gross_area IS NOT NULL AND gross_area > 0
            """
        ),
        eng, params={"sido": sido_name, "asset": asset},
    )
    df["y_kind"] = "price"
    df["building_year"] = np.nan
    return df


def build_region_lookup(eng, sido_name: str):
    rc = pd.read_sql(
        text(
            """
            SELECT DISTINCT sigungu_code, sigungu_name, eupmyeondong_code, eupmyeondong_name
            FROM region_codes WHERE sido_name = :sido
            """
        ),
        eng, params={"sido": sido_name},
    )
    sgg = {}
    emd = {}
    for r in rc.itertuples(index=False):
        if r.sigungu_name and r.sigungu_code:
            sgg.setdefault(str(r.sigungu_name).strip(), str(r.sigungu_code))
    for r in rc.itertuples(index=False):
        if r.eupmyeondong_code and r.eupmyeondong_name:
            emd.setdefault((str(r.sigungu_code), str(r.eupmyeondong_name).strip()), str(r.eupmyeondong_code))
    return sgg, emd


def derive_region_codes_by_name(df: pd.DataFrame, sgg_by_name, emd_by_name) -> pd.DataFrame:
    out = df.copy()

    def _split(row):
        a2, a3, a4 = _s(row.get("addr2")), _s(row.get("addr3")), _s(row.get("addr4"))
        if a3.endswith("구"):
            sgg_name, emd_name = f"{a2} {a3}", a4
        else:
            sgg_name, emd_name = a2, a3
        sgg_code = sgg_by_name.get(sgg_name)
        emd_code = emd_by_name.get((sgg_code, emd_name)) if sgg_code else None
        return pd.Series({"sigungu_code": sgg_code, "eupmyeondong_code": emd_code})

    out[["sigungu_code", "eupmyeondong_code"]] = out.apply(_split, axis=1)
    return out


def load_profiles(coll_eng, sido_code: str, level: str) -> pd.DataFrame:
    rows = pd.read_sql(
        text(
            """
            SELECT DISTINCT ON (region_code) region_code, features
            FROM regional_profile
            WHERE region_level = :level AND profile_version = 'v1.1-national'
              AND region_code LIKE :pfx
            ORDER BY region_code, window_years DESC, as_of_month DESC
            """
        ),
        coll_eng, params={"level": level, "pfx": f"{sido_code}%"},
    )
    recs = []
    for r in rows.itertuples(index=False):
        feats = r.features
        if isinstance(feats, str):
            feats = json.loads(feats)
        if not isinstance(feats, dict):
            continue
        rec = {"region_code": str(r.region_code)}
        for k in ALL_KEYS:
            rec[k] = feats.get(k)
        recs.append(rec)
    return pd.DataFrame(recs)


# ----------------------------------------------------------------------------
def floor_band(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "미상"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "미상"
    if f <= 0:
        return "지하"
    if f < 1.5:
        return "1층"
    return "고층"


def prepare(df: pd.DataFrame, source: str) -> pd.DataFrame:
    out = df.copy()
    if "building_year" in out.columns:
        mask = out["building_age"].isna() & out["building_year"].notna() & out["contract_year"].notna()
        out.loc[mask, "building_age"] = out.loc[mask, "contract_year"].astype(float) - out.loc[mask, "building_year"].astype(float)
    out["building_age"] = pd.to_numeric(out["building_age"], errors="coerce")
    out = out[(out["building_age"] >= 0) & (out["building_age"] <= 120)]

    out["gross_area"] = pd.to_numeric(out["gross_area"], errors="coerce")
    out = out.dropna(subset=["gross_area", "contract_year"])
    out = out[out["gross_area"] > 0]

    if source == "collective_shop":
        out["y_raw"] = pd.to_numeric(out["unit_price"], errors="coerce")
    else:
        out["y_raw"] = pd.to_numeric(out["price"], errors="coerce")
    out = out.dropna(subset=["y_raw"])
    out = out[out["y_raw"] > 0]

    ly = np.log(out["y_raw"].to_numpy(dtype=float))
    lo, hi = np.nanpercentile(ly, 1), np.nanpercentile(ly, 99)
    out = out[(ly >= lo) & (ly <= hi)]

    out["log_y"] = np.log(out["y_raw"].astype(float))
    out["log_gross_area"] = np.log(out["gross_area"].astype(float))
    if source == "built":
        la = pd.to_numeric(out["land_area"], errors="coerce")
        out["log_land_area"] = np.log(la.where(la > 0))
        out["log_land_area"] = out["log_land_area"].fillna(out["log_land_area"].median())
    out["floor_band"] = out["floor"].map(floor_band)
    for c in ("zone_type", "building_use"):
        out[c] = out[c].fillna("미상").astype(str).str.strip().replace("", "미상")
    out["contract_year"] = out["contract_year"].astype(int).astype(str)
    return out.reset_index(drop=True)


def collapse_rare(s: pd.Series, min_count: int = RARE_MIN) -> pd.Series:
    vc = s.value_counts()
    rare = set(vc[vc < min_count].index)
    return s.where(~s.isin(rare), "기타")


def dummies(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    parts = []
    for c in cols:
        s = collapse_rare(df[c].astype(str))
        parts.append(pd.get_dummies(s, prefix=c, drop_first=True, dtype=float))
    return pd.concat(parts, axis=1) if parts else pd.DataFrame(index=df.index)


def base_matrix(df: pd.DataFrame, source: str) -> pd.DataFrame:
    num_cols = ["log_gross_area", "building_age"]
    if source == "built":
        num_cols.insert(1, "log_land_area")
    num = df[num_cols].astype(float)
    cat = dummies(df, ["floor_band", "zone_type", "building_use", "contract_year"])
    return pd.concat([num, cat], axis=1)


def region_dummy_matrix(df: pd.DataFrame, code_col: str) -> pd.DataFrame:
    s = collapse_rare(df[code_col].fillna("미상").astype(str), RARE_MIN)
    return pd.get_dummies(s, prefix=code_col, drop_first=True, dtype=float)


def profile_block_matrix(df: pd.DataFrame, prof: pd.DataFrame, code_col: str, keys: list[str]) -> pd.DataFrame:
    p = prof.copy()
    use = [k for k in keys if k in p.columns]
    cols = []
    for k in use:
        p[k] = pd.to_numeric(p[k], errors="coerce")
        if k.startswith("ratio_"):
            col = k
        else:
            col = f"log_{k}"
            p[col] = np.log1p(p[k].clip(lower=0))
        cols.append(col)
    p = p[["region_code"] + [c for c in cols if c in p.columns]]
    merged = df[[code_col]].merge(p, left_on=code_col, right_on="region_code", how="left")
    feat = merged[[c for c in cols if c in merged.columns]].copy()
    # 전부 결측인 컬럼 제거(예: 시군구에 population_density 없음)
    feat = feat.loc[:, feat.notna().any(axis=0)]
    for c in feat.columns:
        feat[c] = feat[c].fillna(feat[c].median())
        sd = feat[c].std(ddof=0)
        feat[c] = (feat[c] - feat[c].mean()) / sd if sd and sd > 1e-12 else 0.0
    feat.index = df.index
    return feat


# ----------------------------------------------------------------------------
def _design(X: pd.DataFrame) -> np.ndarray:
    return np.column_stack([np.ones(len(X)), X.to_numpy(dtype=float)])


def in_sample(X, y):
    A = _design(X)
    beta, _, rank, _ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    sse, sst, n, k = float(np.sum((y - pred) ** 2)), float(np.sum((y - y.mean()) ** 2)), len(y), int(rank)
    r2 = 1 - sse / sst if sst > 0 else float("nan")
    adj = 1 - (1 - r2) * (n - 1) / (n - k) if n - k > 0 else float("nan")
    aic = n * np.log(sse / n) + 2 * k if sse > 0 else float("nan")
    return {"adj_r2": adj, "aic": aic, "n_params": k}


def cv(X, y_log, y_orig):
    n = len(y_log)
    idx = np.random.default_rng(SEED).permutation(n)
    folds = np.array_split(idx, N_FOLDS)
    A = _design(X)
    mapes, r2s = [], []
    for i in range(N_FOLDS):
        te = folds[i]
        tr = np.concatenate([folds[j] for j in range(N_FOLDS) if j != i])
        beta, _, _, _ = np.linalg.lstsq(A[tr], y_log[tr], rcond=None)
        pl = A[te] @ beta
        pred = np.exp(pl)
        yt = y_orig[te]
        mapes.append(float(np.mean(np.abs(yt - pred) / yt)))
        sse = float(np.sum((y_log[te] - pl) ** 2))
        sst = float(np.sum((y_log[te] - y_log[tr].mean()) ** 2))
        r2s.append(1 - sse / sst if sst > 0 else float("nan"))
    return {"cv_mape": float(np.mean(mapes)), "cv_r2_log": float(np.mean(r2s))}


def evaluate(name, Xextra, base, y_log, y_orig):
    X = base if Xextra is None or Xextra.empty else pd.concat([base, Xextra], axis=1)
    return {"model": name, **in_sample(X, y_log), **cv(X, y_log, y_orig), "n_cols": X.shape[1]}


def vif_report(feat: pd.DataFrame) -> dict:
    out = {}
    M = feat.to_numpy(dtype=float)
    cols = list(feat.columns)
    for j, c in enumerate(cols):
        yj = M[:, j]
        Xj = np.column_stack([np.ones(len(M)), np.delete(M, j, axis=1)])
        beta, _, _, _ = np.linalg.lstsq(Xj, yj, rcond=None)
        pred = Xj @ beta
        sse, sst = np.sum((yj - pred) ** 2), np.sum((yj - yj.mean()) ** 2)
        r2 = 1 - sse / sst if sst > 0 else 0.0
        out[c] = float(1 / (1 - r2)) if r2 < 1 else float("inf")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["collective_shop", "built"], default="built")
    ap.add_argument("--asset", default="commercial", help="built: detached|commercial|factory")
    ap.add_argument("--sido", default="충청북도")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sido_code = SIDO_CODE_MAP.get(args.sido)
    if not sido_code:
        raise SystemExit(f"알 수 없는 시도: {args.sido}")

    coll_eng = create_engine(COLLECTIVE_URL)
    if args.source == "collective_shop":
        eng = coll_eng
        raw = load_collective_shop(eng, args.sido)
        sgg_by_name, emd_by_name = build_region_lookup(coll_eng, args.sido)
        raw = derive_region_codes_by_name(raw, sgg_by_name, emd_by_name)
        title_asset = "집합상가"
    else:
        eng = create_engine(BUILT_URL)
        raw = load_built(eng, args.sido, args.asset)
        title_asset = f"복합부동산:{args.asset}"

    df = prepare(raw, args.source)
    cov_sgg = df["sigungu_code"].notna().mean()
    cov_emd = df["eupmyeondong_code"].notna().mean()

    prof_sgg = load_profiles(coll_eng, sido_code, "sigungu")
    prof_emd = load_profiles(coll_eng, sido_code, "eupmyeondong")

    y_log = df["log_y"].to_numpy(dtype=float)
    y_orig = df["y_raw"].to_numpy(dtype=float)
    base = base_matrix(df, args.source)
    sgg_dum = region_dummy_matrix(df, "sigungu_code")
    emd_dum = region_dummy_matrix(df, "eupmyeondong_code")

    pall_sgg = profile_block_matrix(df, prof_sgg, "sigungu_code", ALL_KEYS)
    pall_emd = profile_block_matrix(df, prof_emd, "eupmyeondong_code", ALL_KEYS)
    ppop = profile_block_matrix(df, prof_emd, "eupmyeondong_code", BLOCK_POP)
    pland = profile_block_matrix(df, prof_emd, "eupmyeondong_code", BLOCK_LAND)
    phouse = profile_block_matrix(df, prof_emd, "eupmyeondong_code", BLOCK_HOUSE)

    results = [
        evaluate("M0_base", None, base, y_log, y_orig),
        evaluate("M_sgg_dummy", sgg_dum, base, y_log, y_orig),
        evaluate("M_emd_dummy", emd_dum, base, y_log, y_orig),
        evaluate("M_prof_sgg(all)", pall_sgg, base, y_log, y_orig),
        evaluate("M_prof_emd(all)", pall_emd, base, y_log, y_orig),
        evaluate("  prof_emd_pop", ppop, base, y_log, y_orig),
        evaluate("  prof_emd_land", pland, base, y_log, y_orig),
        evaluate("  prof_emd_house", phouse, base, y_log, y_orig),
    ]
    vif = vif_report(pall_sgg)

    print(f"\n=== 실험1: 지역 vs Profile — {args.sido} / {title_asset} ===")
    print(f"표본 n={len(df)} (시군구 매칭 {cov_sgg:.1%}, 읍면동 매칭 {cov_emd:.1%}) · y=log({df['y_kind'].iloc[0]})")
    print(f"시군구 더미 {sgg_dum.shape[1]}, 읍면동 더미 {emd_dum.shape[1]}, 프로필(all) {pall_sgg.shape[1]}변수")
    print(f"\n{'model':<18}{'n_cols':>7}{'adjR2':>9}{'AIC':>11}{'CV-MAPE':>10}{'CV-R2log':>10}")
    print("-" * 75)
    for r in results:
        print(f"{r['model']:<18}{r['n_cols']:>7}{r['adj_r2']:>9.3f}{r['aic']:>11.0f}{r['cv_mape']:>9.1%}{r['cv_r2_log']:>10.3f}")
    print("\nProfile(sigungu, all) VIF:")
    for k, v in vif.items():
        print(f"  {k:<30}{v:>7.2f}")

    report = {
        "source": args.source, "asset": args.asset, "sido": args.sido, "n": int(len(df)),
        "coverage": {"sigungu": float(cov_sgg), "eupmyeondong": float(cov_emd)},
        "dummies": {"sigungu": int(sgg_dum.shape[1]), "eupmyeondong": int(emd_dum.shape[1])},
        "results": results, "profile_vif": vif,
        "kpi_note": "심판은 CV-MAPE/CV-R2log. in-sample adjR2는 더미 과적합으로 부풀려질 수 있음.",
    }
    out_path = Path(args.out) if args.out else Path(__file__).with_name(
        f"exp_region_vs_profile_{args.source}_{args.asset}.json")
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n리포트 저장: {out_path}")


if __name__ == "__main__":
    main()
