"""Shadow comparison of official-price recovery rules.

Read-only. Chungbuk trades from 2019-01-01. Does not update the ledger, the
slim, or land_transaction_trait_link. Parcel identity stays on rule V1.
A same-price candidate match does not confirm a parcel.

Arms stay separate:
  baseline, strict unique-parcel price, same-price candidates, and a
  year window on the unique parcel only.
"""

from __future__ import annotations

import gc
import json
import sys
import time
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from db_utils import get_engine  # noqa: E402
from parcel_master.cheongju_land_gap_probe import _split_candidates  # noqa: E402
from parcel_master.cheongju_land_label_rule_probe import (  # noqa: E402
    attach_price_detail,
    classify_link_v1,
)
from parcel_master.cheongju_land_link_probe import exclusion_reason  # noqa: E402
from parcel_master.code_history_link_shadow import _merge, _prefixes_for, load_pairs  # noqa: E402
from parcel_master.land_code_history_layer import resolve_beopjungri  # noqa: E402
from parcel_master.land_trait_link_materialize import (  # noqa: E402
    _conflict_views,
    _load_conflict,
    _load_plates,
)
from parcel_master.national_land_link_shadow import PRICE_FROM  # noqa: E402
from parcel_master.trait_link_helpers import area_key  # noqa: E402

REPORT = ROOT / "docs" / "lab" / "land_price_recovery_shadow_20261021.json"
FOLDS = 5
SEED = 20261021
MIN_LEVEL = 30
PAST_OFFSETS = (0, -1, -2)
WINDOW_OFFSETS = (0, -1, 1, -2, 2)


def unique_year_amount(rows, year: int):
    """One positive price, or 'missing'. A conflict or a non-positive price stops."""
    amounts: set[Decimal] = set()
    blocked = False
    for row in rows:
        if int(row[1]) != year:
            continue
        raw = str(row[6] or "").strip()
        if not raw:
            continue
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            blocked = True
            continue
        if amount <= 0:
            blocked = True
            continue
        amounts.add(amount)
    if blocked or len(amounts) > 1:
        return "conflict"
    if len(amounts) == 1:
        return next(iter(amounts))
    return "missing"


def pick_price(rows, contract_year: int, offsets: tuple[int, ...]):
    """First usable year in priority order. A conflict does not fall through."""
    for gap in offsets:
        got = unique_year_amount(rows, contract_year + gap)
        if got == "conflict":
            return None
        if got == "missing":
            continue
        return float(got), gap, gap > 0
    return None


def agree_amount(pnus: list[str], plates, normalized, year: int):
    """Same contract-year price on every candidate. Does not confirm a parcel."""
    if len(pnus) < 2:
        return None, 0
    found: list[Decimal] = []
    for pnu in pnus:
        rows = list(plates.get(pnu, ())) + list(normalized.get(pnu, ()))
        got = unique_year_amount(rows, year)
        if not isinstance(got, Decimal):
            return None, len(pnus)
        found.append(got)
    if len(set(found)) != 1:
        return None, len(pnus)
    return float(found[0]), len(pnus)


def _self_check() -> None:
    same = [("2020-01-01", 2020, 1, "", "", "", "100")]
    assert unique_year_amount(same, 2020) == Decimal("100")
    conflict = same + [("2020-06-01", 2020, 6, "", "", "", "200")]
    assert unique_year_amount(conflict, 2020) == "conflict"
    assert pick_price(conflict, 2020, PAST_OFFSETS) is None
    older = [("2019-01-01", 2019, 1, "", "", "", "90")]
    assert pick_price(older, 2021, PAST_OFFSETS) == (90.0, -2, False)
    future = [("2022-01-01", 2022, 1, "", "", "", "130")]
    assert pick_price(future, 2021, WINDOW_OFFSETS) == (130.0, 1, True)
    assert pick_price(future, 2021, PAST_OFFSETS) is None
    prefer_past = future + [("2020-01-01", 2020, 1, "", "", "", "100")]
    assert pick_price(prefer_past, 2021, WINDOW_OFFSETS) == (100.0, -1, False)


def _load_trades(engine, code: str) -> list[dict]:
    sql = text(
        """
        SELECT transaction_hash, contract_date, beopjungri_code, land_category, zone_type,
               area_sqm, unit_price_per_sqm, road_condition, deal_type,
               is_partial_ownership, is_cancelled, is_valid, lot_display
        FROM land_transactions
        WHERE sigungu_code = :code AND contract_date >= :start
        """
    )
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        fetched = connection.execute(sql, {"code": code, "start": PRICE_FROM}).mappings().all()
    return [dict(row) for row in fetched]


def _plate_rows(pnu: str, plates, normalized) -> list:
    return list(plates.get(pnu, ())) + list(normalized.get(pnu, ()))


def _recover(code: str, plates, index, pairs, fetched: list[dict]) -> list[dict]:
    prepared = []
    targets: set[str] = set()
    for row in fetched:
        if exclusion_reason(row) or len(str(row["beopjungri_code"]).strip()) != 10:
            continue
        if len(str(row["transaction_hash"] or "").strip()) != 64:
            continue
        unit = row["unit_price_per_sqm"]
        area = row["area_sqm"]
        if unit is None or area is None:
            continue
        unit_value = float(unit)
        area_value = float(area)
        if unit_value <= 0 or area_value <= 0:
            continue
        day = str(row["contract_date"])[:10]
        original = str(row["beopjungri_code"]).strip()
        resolved, _reason = resolve_beopjungri(original, day, pairs)
        jimok = str(row["land_category"] or "").strip()
        area_text = area_key(row["area_sqm"]) or ""
        zone = str(row["zone_type"] or "")
        prior, later = _split_candidates(
            resolved, jimok, area_text, zone, row["lot_display"], day, index, plates
        )
        if len(prior) == 1:
            targets.add(prior[0])
        elif len(later) == 1:
            targets.add(later[0])
        prepared.append(
            {
                "year": int(day[:4]),
                "day": day,
                "match_jimok": jimok,
                "match_area": area_text,
                "match_zone": zone,
                "jimok": jimok or "미상",
                "zone": zone or "미상",
                "road": str(row["road_condition"] or "").strip() or "미상",
                "deal": str(row["deal_type"] or "").strip() or "중개거래",
                "area": area_value,
                "unit_price": unit_value,
                "prior": prior,
                "later": later,
                "sigungu": code,
            }
        )
    grouped: dict = defaultdict(list)
    for prefix in _prefixes_for(code, pairs):
        for key, variants in _load_conflict(prefix, targets).items():
            grouped[key].extend(variants)
    normalized, conflict_asofs, substantive_asofs = _conflict_views(grouped)
    records = []
    for row in prepared:
        kind, price_pnu = classify_link_v1(
            day=row["day"],
            jimok=row["match_jimok"],
            area=row["match_area"],
            zone=row["match_zone"],
            prior=row["prior"],
            later=row["later"],
            plates=plates,
            normalized=normalized,
            conflict_asofs=conflict_asofs,
            substantive_asofs=substantive_asofs,
        )
        strict = None
        strict_gap = None
        if price_pnu:
            status, amount, price_year = attach_price_detail(
                _plate_rows(price_pnu, plates, normalized), row["year"]
            )
            if status in {"same_year", "previous_year"} and amount is not None and amount > 0 and price_year:
                strict = float(amount)
                strict_gap = int(price_year) - row["year"]
        agree = None
        agree_n = 0
        if kind == "multiple_candidates":
            agree, agree_n = agree_amount(row["prior"], plates, normalized, row["year"])
        past = None
        past_gap = None
        window = None
        window_gap = None
        window_post = False
        if price_pnu:
            picked = pick_price(_plate_rows(price_pnu, plates, normalized), row["year"], PAST_OFFSETS)
            if picked:
                past, past_gap, _post = picked
            picked = pick_price(_plate_rows(price_pnu, plates, normalized), row["year"], WINDOW_OFFSETS)
            if picked:
                window, window_gap, window_post = picked
        records.append(
            {
                "sigungu": code,
                "year": row["year"],
                "jimok": row["jimok"],
                "zone": row["zone"],
                "road": row["road"],
                "deal": row["deal"],
                "area": row["area"],
                "unit_price": row["unit_price"],
                "link": kind,
                "strict": strict,
                "strict_gap": strict_gap,
                "agree": agree,
                "agree_n": agree_n,
                "past2": past,
                "past_gap": past_gap,
                "pm2": window,
                "pm2_gap": window_gap,
                "pm2_post": bool(window_post),
            }
        )
    return records


def _codes(engine) -> list[str]:
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = connection.execute(
            text(
                """
                SELECT sigungu_code
                FROM land_transactions
                WHERE contract_date >= :start AND sigungu_code LIKE '43%'
                GROUP BY sigungu_code
                ORDER BY sigungu_code
                """
            ),
            {"start": PRICE_FROM},
        ).all()
    return [str(code).strip() for (code,) in rows if len(str(code).strip()) == 5]


def _bucket(series: pd.Series) -> pd.Series:
    counts = series.value_counts()
    keep = set(counts[counts >= MIN_LEVEL].index)
    return series.where(series.isin(keep), "기타")


def _dummies(series: pd.Series, prefix: str) -> tuple[pd.DataFrame, str]:
    ref = str(series.value_counts().index[0])
    frame = pd.get_dummies(series, prefix=prefix, dtype=float)
    column = f"{prefix}_{ref}"
    if column in frame.columns and len(frame.columns) > 1:
        frame = frame.drop(columns=[column])
    frame.columns = [str(name).replace(" ", "_") for name in frame.columns]
    return frame, ref


def _design(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    parts = [np.log(frame["area"].clip(lower=0.01)).rename("log_area")]
    refs = {}
    for column, prefix in (
        ("zone", "zone"),
        ("jimok", "jimok"),
        ("road", "road"),
        ("deal", "deal"),
        ("sigungu", "sigungu"),
    ):
        grouped = _bucket(frame[column].astype(str))
        dummies, ref = _dummies(grouped, prefix)
        if dummies.shape[1] == 0:
            continue
        parts.append(dummies)
        refs[column] = ref
    design = pd.concat(parts, axis=1)
    design.index = frame.index
    return design, refs


def _fit(y: np.ndarray, year: np.ndarray, design: pd.DataFrame, extra: pd.DataFrame | None):
    center = float(year.mean())
    pieces = [design, pd.Series(year - center, index=design.index, name="year_trend")]
    if extra is not None and len(extra.columns):
        pieces.append(extra)
    x = pd.concat(pieces, axis=1).astype(float)
    keep = [column for column in x.columns if float(x[column].nunique(dropna=False)) > 1]
    x = sm.add_constant(x[keep], has_constant="add")
    protected = {"const", "log_area", "year_trend", "log_assessed", "price_missing"}
    while True:
        try:
            model = sm.OLS(y, x).fit()
            break
        except (np.linalg.LinAlgError, ValueError):
            droppable = [column for column in x.columns if column not in protected]
            if not droppable:
                raise
            x = x.drop(columns=[droppable[-1]])
    return model, center


def _predict(model, year: np.ndarray, design: pd.DataFrame, extra: pd.DataFrame | None, center: float):
    pieces = [design, pd.Series(year - center, index=design.index, name="year_trend")]
    if extra is not None and len(extra.columns):
        pieces.append(extra)
    x = pd.concat(pieces, axis=1).astype(float)
    for column in model.model.exog_names:
        if column == "const":
            continue
        if column not in x.columns:
            x[column] = 0.0
    x = sm.add_constant(x[model.model.exog_names[1:]], has_constant="add")
    x = x[model.model.exog_names]
    return np.asarray(model.predict(x), dtype=float)


def _mape(y_true: np.ndarray, log_pred: np.ndarray, smearing: float) -> float | None:
    yhat = np.exp(log_pred) * smearing
    if not np.isfinite(yhat).all() or not np.isfinite(y_true).all():
        return None
    return float(np.mean(np.abs(yhat - y_true) / y_true) * 100)


def _extra(frame: pd.DataFrame, column: str | None, mode: str) -> pd.DataFrame | None:
    if mode == "none" or column is None:
        return None
    price = pd.to_numeric(frame[column], errors="coerce")
    if mode == "complete":
        return np.log(price).rename("log_assessed").to_frame()
    filled = np.log(price.where(price > 0)).fillna(0.0)
    missing = price.isna() | (price <= 0)
    return pd.DataFrame({"log_assessed": filled, "price_missing": missing.astype(float)}, index=frame.index)


def _cv_mape(frame: pd.DataFrame, design: pd.DataFrame, folds: np.ndarray, column: str | None, mode: str) -> dict:
    work = frame
    if mode == "complete":
        price = pd.to_numeric(frame[column], errors="coerce")
        work = frame.loc[price > 0]
    if len(work) < 100:
        return {"n": int(len(work)), "cv_mape": None, "reason": "too_few_rows"}
    scores = []
    for fold in range(FOLDS):
        test = work.loc[folds[work.index] == fold]
        train = work.loc[folds[work.index] != fold]
        if len(test) < 10 or len(train) < 50:
            continue
        y = np.log(train["unit_price"].to_numpy(dtype=float))
        model, center = _fit(
            y,
            train["year"].to_numpy(dtype=float),
            design.loc[train.index],
            _extra(train, column, mode),
        )
        smearing = float(np.mean(np.exp(np.asarray(model.resid, dtype=float))))
        log_pred = _predict(
            model,
            test["year"].to_numpy(dtype=float),
            design.loc[test.index],
            _extra(test, column, mode),
            center,
        )
        score = _mape(test["unit_price"].to_numpy(dtype=float), log_pred, smearing)
        if score is not None:
            scores.append(score)
    return {
        "n": int(len(work)),
        "folds": len(scores),
        "cv_mape": round(float(np.mean(scores)), 2) if scores else None,
    }


def _coef_fit(frame: pd.DataFrame, design: pd.DataFrame, column: str | None, mode: str) -> dict:
    work = frame
    if mode == "complete":
        price = pd.to_numeric(frame[column], errors="coerce")
        work = frame.loc[price > 0]
    if len(work) < 100:
        return {"n": int(len(work))}
    y = np.log(work["unit_price"].to_numpy(dtype=float))
    model, _center = _fit(
        y,
        work["year"].to_numpy(dtype=float),
        design.loc[work.index],
        _extra(work, column, mode),
    )
    wanted = [name for name in model.params.index if not str(name).startswith("sigungu_")]
    coefficients = {}
    for name in wanted:
        coefficients[str(name)] = {
            "coef": round(float(model.params[name]), 4),
            "pvalue": round(float(model.pvalues[name]), 4),
        }
    return {"n": int(len(work)), "adj_r2": round(float(model.rsquared_adj), 4), "coefficients": coefficients}


def _distribution(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"n": 0}
    jimok = frame["jimok"].value_counts(normalize=True)
    shares = {str(name): round(float(share), 4) for name, share in jimok.items() if share >= 0.01}
    return {
        "n": int(len(frame)),
        "area_p25": round(float(frame["area"].quantile(0.25)), 1),
        "area_p50": round(float(frame["area"].median()), 1),
        "area_p75": round(float(frame["area"].quantile(0.75)), 1),
        "unit_price_p25": round(float(frame["unit_price"].quantile(0.25)), 2),
        "unit_price_p50": round(float(frame["unit_price"].median()), 2),
        "unit_price_p75": round(float(frame["unit_price"].quantile(0.75)), 2),
        "jimok_share_at_least_1pct": shares,
    }


def _arm(frame, design, folds, name, column, mode, note: str) -> dict:
    return {
        "arm": name,
        "note": note,
        "error": _cv_mape(frame, design, folds, column, mode),
        "fit": _coef_fit(frame, design, column, mode),
    }


def run() -> None:
    _self_check()
    engine = get_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            pairs = load_pairs(connection)
        codes = _codes(engine)
        print(f"chungbuk sigungu={len(codes)}", flush=True)
        rows: list[dict] = []
        for index, code in enumerate(codes, start=1):
            started = time.perf_counter()
            plates: dict = defaultdict(list)
            plate_index: dict = defaultdict(set)
            for prefix in _prefixes_for(code, pairs):
                extra_plates, extra_index, _seen = _load_plates(prefix)
                _merge(plates, plate_index, extra_plates, extra_index)
                del extra_plates, extra_index
            for plate_rows in plates.values():
                plate_rows.sort()
            fetched = _load_trades(engine, code)
            recovered = _recover(code, plates, plate_index, pairs, fetched)
            rows.extend(recovered)
            print(
                f"{index}/{len(codes)} {code} rows={len(recovered)} seconds={time.perf_counter() - started:.0f}",
                flush=True,
            )
            del plates, plate_index, fetched, recovered
            gc.collect()
        frame = pd.DataFrame(rows)
        frame["strict_or_agree"] = frame["strict"].where(frame["strict"].notna(), frame["agree"])
        design, refs = _design(frame)
        folds = np.empty(len(frame), dtype=int)
        order = np.random.default_rng(SEED).permutation(len(frame))
        for position, row_index in enumerate(order):
            folds[row_index] = position % FOLDS
        strict = frame["strict"].notna()
        agree_only = frame["agree"].notna() & frame["strict"].isna()
        past_only = frame["past2"].notna() & frame["strict"].isna()
        future_only = frame["pm2_post"] & frame["past2"].isna()
        report = {
            "scope": "충북",
            "not_national": True,
            "contract_date_from": PRICE_FROM,
            "identity_rule_changed": False,
            "parcel_confirmed_by_agree": False,
            "mean_imputation": False,
            "tables_written": [],
            "formula": "log(단가) ~ log(면적) + 연도 + 용도지역 + 지목 + 도로조건 + 거래유형 + 시군구",
            "price_unit": "원/㎡",
            "unit_price_unit": "만원/㎡",
            "cv": {"folds": FOLDS, "seed": SEED, "metric": "Duan smearing CV-MAPE"},
            "reference_levels": refs,
            "sample": {
                "sigungu": len(codes),
                "rows": int(len(frame)),
                "strict": int(strict.sum()),
                "strict_same_year": int(((frame["strict"].notna()) & (frame["strict_gap"] == 0)).sum()),
                "strict_previous_year": int(((frame["strict"].notna()) & (frame["strict_gap"] == -1)).sum()),
                "agree_only": int(agree_only.sum()),
                "agree_candidate_median": (
                    round(float(frame.loc[agree_only, "agree_n"].median()), 1) if agree_only.any() else None
                ),
                "past2_only": int(past_only.sum()),
                "future_only": int(future_only.sum()),
                "still_missing_after_agree": int(frame["strict_or_agree"].isna().sum()),
                "still_missing_after_past2": int(frame["past2"].isna().sum()),
            },
            "distribution": {
                "all": _distribution(frame),
                "strict": _distribution(frame.loc[strict]),
                "agree_only": _distribution(frame.loc[agree_only]),
                "past2_only": _distribution(frame.loc[past_only]),
                "future_only": _distribution(frame.loc[future_only]),
            },
            "models": [
                _arm(frame, design, folds, "baseline", None, "none", "가격 없음. 전체 표본."),
                _arm(
                    frame.loc[strict],
                    design,
                    folds,
                    "baseline_on_strict_rows",
                    None,
                    "none",
                    "같은 검증 칸. 고유 필지 가격이 있는 행만.",
                ),
                _arm(
                    frame.loc[strict],
                    design,
                    folds,
                    "strict_complete",
                    "strict",
                    "complete",
                    "고유 필지. 해당연도, 없으면 전년. 결측은 제외.",
                ),
                _arm(
                    frame,
                    design,
                    folds,
                    "strict_missing_indicator",
                    "strict",
                    "indicator",
                    "고유 필지 가격. 없는 행은 빼지 않고 결측 표시만.",
                ),
                _arm(
                    frame.loc[frame["strict_or_agree"].notna()],
                    design,
                    folds,
                    "baseline_on_agree_rows",
                    None,
                    "none",
                    "같은 검증 칸. 고유 가격 또는 후보 동일가.",
                ),
                _arm(
                    frame.loc[frame["strict_or_agree"].notna()],
                    design,
                    folds,
                    "agree_complete",
                    "strict_or_agree",
                    "complete",
                    "후보 동일가는 해당연도만. 필지 확정 아님. ±년과 섞지 않음.",
                ),
                _arm(
                    frame,
                    design,
                    folds,
                    "agree_missing_indicator",
                    "strict_or_agree",
                    "indicator",
                    "고유 가격 또는 후보 동일가. 나머지는 결측 표시.",
                ),
                _arm(
                    frame.loc[frame["past2"].notna()],
                    design,
                    folds,
                    "baseline_on_past2_rows",
                    None,
                    "none",
                    "같은 검증 칸. 계약 이후 가격은 넣지 않음.",
                ),
                _arm(
                    frame.loc[frame["past2"].notna()],
                    design,
                    folds,
                    "past2_complete",
                    "past2",
                    "complete",
                    "고유 필지만. 해당연도, -1, -2. 후보 동일가와 섞지 않음.",
                ),
                _arm(
                    frame,
                    design,
                    folds,
                    "past2_missing_indicator",
                    "past2",
                    "indicator",
                    "고유 필지 ±2 중 계약 연도 이전만. 결측 표시.",
                ),
                _arm(
                    frame.loc[frame["pm2"].notna()],
                    design,
                    folds,
                    "baseline_on_pm2_rows",
                    None,
                    "none",
                    "같은 검증 칸. 계약 이후 가격이 표본에 포함됨.",
                ),
                _arm(
                    frame.loc[frame["pm2"].notna()],
                    design,
                    folds,
                    "pm2_complete_includes_post_contract",
                    "pm2",
                    "complete",
                    "고유 필지. 해당연도, -1, +1, -2, +2. 검증 행도 계약 이후 값을 쓸 수 있음.",
                ),
            ],
        }
        # Train may see a post-contract price. Test rows are scored with the past-only price.
        hybrid_scores = []
        pm2_rows = frame.loc[frame["pm2"].notna()]
        for fold in range(FOLDS):
            test = pm2_rows.loc[folds[pm2_rows.index] == fold]
            train = pm2_rows.loc[folds[pm2_rows.index] != fold]
            test = test.loc[test["past2"].notna()]
            if len(test) < 10 or len(train) < 50:
                continue
            y = np.log(train["unit_price"].to_numpy(dtype=float))
            model, center = _fit(
                y,
                train["year"].to_numpy(dtype=float),
                design.loc[train.index],
                _extra(train, "pm2", "complete"),
            )
            smearing = float(np.mean(np.exp(np.asarray(model.resid, dtype=float))))
            scored = test.copy()
            scored["pm2"] = scored["past2"]
            log_pred = _predict(
                model,
                scored["year"].to_numpy(dtype=float),
                design.loc[scored.index],
                _extra(scored, "pm2", "complete"),
                center,
            )
            score = _mape(scored["unit_price"].to_numpy(dtype=float), log_pred, smearing)
            if score is not None:
                hybrid_scores.append(score)
        report["models"].append(
            {
                "arm": "pm2_trained_test_uses_past_only",
                "note": "학습은 ±2. 검증 행은 계약 연도 이전 가격만 넣음. 계약 이후만 있는 검증 행은 점수에서 뺌.",
                "error": {
                    "n": int(frame["past2"].notna().sum()),
                    "folds": len(hybrid_scores),
                    "cv_mape": round(float(np.mean(hybrid_scores)), 2) if hybrid_scores else None,
                },
            }
        )
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {REPORT}", flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()
