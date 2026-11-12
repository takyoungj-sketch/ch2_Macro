"""토지 회귀 표본 확장 1차. 설계: docs/lab/LAND_REGRESSION_AUGMENT_LAB.md

제품 회귀 화면과 식은 바꾸지 않는다. 성공 지표는 기준 용도×지목의 검증 오차다.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.land_regression import _duan_smearing
from app.regression_missing import categorical_dummies, normalize_categories

SEED = 20261028
N_FOLDS = 5
N_REPEATS = 20
TARGET_N_MIN = 30
TARGET_N_MAX = 60
THIN_N_MAX = 39
GROUP_MIN_N = 15
B_QUOTA_MIN = 15
M5_COLLAPSE_N = 5
TEMPORAL_TEST_MIN = 8
RESIDENTIAL = frozenset({"1전", "2전", "1주", "2주", "3주", "준주"})
GREEN = frozenset({"자녹", "생녹", "보녹"})
MODELS = ("M0", "M1", "M2", "M3", "M4", "M5")


@dataclass(frozen=True)
class CellCount:
    eup_code: str
    eup_name: str
    sido_code: str
    sido_name: str
    sigungu_name: str
    zone: str
    jimok: str
    n: int


class FitError(Exception):
    pass


def apply_assessed_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """제품이 개별공시지가를 켤 때와 같다. 지분 거래와 공시지가가 없는 행을 뺀다."""
    n_before = int(len(frame))
    partial = (
        frame["is_partial_ownership"].fillna(False).astype(bool)
        if "is_partial_ownership" in frame.columns
        else pd.Series(False, index=frame.index)
    )
    price = pd.to_numeric(frame["official_price_won"], errors="coerce") if "official_price_won" in frame.columns else pd.Series(np.nan, index=frame.index)
    keep = (~partial) & price.gt(0)
    out = frame.loc[keep].copy()
    out["official_price_won"] = price.loc[keep].astype(float)
    return out, {
        "n_before": n_before,
        "n_partial": int(partial.sum()),
        "n_after": int(len(out)),
    }


def cell_key(zone: str, jimok: str) -> str:
    return f"{zone}|{jimok}"


def cell_hash(eup_code: str, zone: str, jimok: str, seed: int = SEED) -> str:
    raw = f"{seed}|{eup_code}|{zone}|{jimok}".encode()
    return hashlib.sha256(raw).hexdigest()


def _by_eup(cells: list[CellCount]) -> dict[str, list[CellCount]]:
    out: dict[str, list[CellCount]] = {}
    for cell in cells:
        out.setdefault(cell.eup_code, []).append(cell)
    return out


def _modal(group: list[CellCount]) -> CellCount:
    return sorted(group, key=lambda c: (-c.n, c.zone, c.jimok))[0]


def _pick(cands: list[CellCount], seed: int = SEED) -> CellCount | None:
    if not cands:
        return None
    return min(cands, key=lambda c: (cell_hash(c.eup_code, c.zone, c.jimok, seed), c.eup_code))


def _jeon_dap_center(group: list[CellCount]) -> bool:
    total = sum(c.n for c in group)
    jeon = sum(c.n for c in group if c.jimok == "전")
    dap = sum(c.n for c in group if c.jimok == "답")
    return total > 0 and jeon >= GROUP_MIN_N and dap >= GROUP_MIN_N and (jeon + dap) / total >= 0.5


def _other_zone_ok(group: list[CellCount], cell: CellCount) -> bool:
    return any(
        other.jimok == cell.jimok and other.zone != cell.zone and other.n >= GROUP_MIN_N
        for other in group
    )


def _other_jimok_ok(group: list[CellCount], cell: CellCount) -> bool:
    return any(
        other.zone == cell.zone and other.jimok != cell.jimok and other.n >= GROUP_MIN_N
        for other in group
    )


def _same_cell_elsewhere(cells: list[CellCount], cell: CellCount) -> bool:
    return any(
        other.eup_code != cell.eup_code
        and other.sido_code == cell.sido_code
        and other.zone == cell.zone
        and other.jimok == cell.jimok
        and other.n >= GROUP_MIN_N
        for other in cells
    )


def select_round1(
    cells: list[CellCount], seed: int = SEED
) -> tuple[dict[str, CellCount | None], dict[str, int]]:
    """A→E. 이미 고른 읍면동은 다음 유형에서 뺀다. 가격은 쓰지 않는다."""
    grouped = _by_eup(cells)
    index = {(c.eup_code, c.zone, c.jimok): c for c in cells}
    used: set[str] = set()
    pools: dict[str, list[CellCount]] = {key: [] for key in ("A", "B", "C", "D", "E")}

    for eup, group in grouped.items():
        name = group[0].eup_name
        modal = _modal(group)
        if name.endswith("동") and modal.zone in RESIDENTIAL and modal.jimok == "대":
            if TARGET_N_MIN <= modal.n <= TARGET_N_MAX:
                pools["A"].append(modal)
        if name.endswith("동"):
            res_n = sum(c.n for c in group if c.zone in RESIDENTIAL)
            green_n = sum(c.n for c in group if c.zone in GREEN)
            if res_n >= GROUP_MIN_N and green_n >= GROUP_MIN_N:
                for cell in group:
                    if cell.zone in RESIDENTIAL | GREEN and TARGET_N_MIN <= cell.n <= TARGET_N_MAX:
                        pools["B"].append(cell)
        if (name.endswith("읍") or name.endswith("면")) and _jeon_dap_center(group):
            for cell in group:
                if cell.jimok in {"전", "답"} and TARGET_N_MIN <= cell.n <= TARGET_N_MAX:
                    if _other_jimok_ok(group, cell):
                        pools["C"].append(cell)
        if name.endswith("읍") or name.endswith("면"):
            for cell in group:
                if TARGET_N_MIN <= cell.n <= TARGET_N_MAX and _other_zone_ok(group, cell):
                    pools["D"].append(cell)
        for cell in group:
            if TARGET_N_MIN <= cell.n <= THIN_N_MAX and _same_cell_elsewhere(cells, cell):
                pools["E"].append(cell)

    counts = {key: len(pool) for key, pool in pools.items()}
    chosen: dict[str, CellCount | None] = {}
    for key in ("A", "B", "C", "D", "E"):
        cands = [c for c in pools[key] if c.eup_code not in used and (c.eup_code, c.zone, c.jimok) in index]
        pick = _pick(cands, seed)
        chosen[key] = pick
        if pick is not None:
            used.add(pick.eup_code)
    return chosen, counts


def pick_twin(
    cells: list[CellCount],
    anchor: CellCount,
) -> tuple[CellCount, float] | None:
    """같은 시도, 같은 용도×지목 15건 이상. 거리는 건수 비중만. 1위."""
    from app.land_lab.land_twin import js_divergence_base2, share_vector

    by_eup: dict[str, dict[str, int]] = {}
    meta: dict[str, CellCount] = {}
    eligible: set[str] = set()
    for cell in cells:
        if cell.sido_code != anchor.sido_code:
            continue
        by_eup.setdefault(cell.eup_code, {})[cell_key(cell.zone, cell.jimok)] = cell.n
        if cell.eup_code == anchor.eup_code:
            continue
        if cell.zone == anchor.zone and cell.jimok == anchor.jimok and cell.n >= GROUP_MIN_N:
            eligible.add(cell.eup_code)
            meta[cell.eup_code] = cell
    anchor_counts = by_eup.get(anchor.eup_code)
    if not anchor_counts or not eligible:
        return None
    vocab = sorted(set().union(*by_eup.values()))
    anchor_share = share_vector(anchor_counts, vocab)
    best: tuple[CellCount, float] | None = None
    for eup in eligible:
        dist = js_divergence_base2(anchor_share, share_vector(by_eup[eup], vocab))
        cand = meta[eup]
        if best is None or (dist, cand.eup_code) < (best[1], best[0].eup_code):
            best = (cand, dist)
    return best


def assign_folds(frame: pd.DataFrame, n_folds: int = N_FOLDS, seed: int = SEED) -> pd.Series:
    """기준 칸만 0..n_folds-1. 추가 거래는 -1. 같은 시드면 같은 번호."""
    folds = pd.Series(-1, index=frame.index, dtype=int)
    target = frame.index[frame["is_target"].to_numpy()]
    if len(target) == 0:
        return folds
    years = frame.loc[target, "contract_year"].astype(int)
    counts = years.value_counts().to_dict()
    ordered = sorted(counts)
    stratum: dict[int, int] = {}
    for year in ordered:
        if counts[year] >= 2:
            stratum[year] = year
            continue
        later = [item for item in ordered if item > year]
        earlier = [item for item in ordered if item < year]
        stratum[year] = later[0] if later else (earlier[-1] if earlier else year)
    labels = years.map(stratum)
    rng = np.random.default_rng(seed)
    for key in sorted(labels.unique()):
        idx = labels.index[labels == key].to_numpy()
        order = rng.permutation(len(idx))
        for pos, row_i in enumerate(order):
            folds.loc[idx[row_i]] = int(pos % n_folds)
    return folds


def _collapse_series(values: pd.Series, reference: str, min_count: int) -> pd.Series:
    counts = values.value_counts()
    out = values.copy()
    for level, count in counts.items():
        if level == reference or int(count) >= min_count:
            continue
        out = out.mask(out == level, "기타")
    return out


def _design(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    level: pd.Series | None,
    level_ref: str | None,
    collapse_at: int,
    use_assessed: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """학습·검증 설계행렬. 검증 행의 True는 도로·거래유형이 학습에 없음."""
    year_mean = float(train["contract_year"].astype(float).mean())
    parts_train: list[pd.Series] = []
    parts_test: list[pd.Series] = []

    log_area_tr = np.log(train["area_sqm"].astype(float))
    log_area_te = np.log(test["area_sqm"].astype(float))
    parts_train.append(pd.Series(log_area_tr, index=train.index, name="log_area"))
    parts_test.append(pd.Series(log_area_te, index=test.index, name="log_area"))
    year_tr = train["contract_year"].astype(float) - year_mean
    year_te = test["contract_year"].astype(float) - year_mean
    if float(year_tr.std(ddof=0)) > 0:
        parts_train.append(year_tr.rename("year_trend"))
        parts_test.append(year_te.rename("year_trend"))
    if use_assessed:
        assessed_tr = np.log(train["official_price_won"].astype(float))
        assessed_te = np.log(test["official_price_won"].astype(float))
        parts_train.append(pd.Series(assessed_tr, index=train.index, name="log_assessed_land_price"))
        parts_test.append(pd.Series(assessed_te, index=test.index, name="log_assessed_land_price"))

    unseen = np.zeros(len(test), dtype=bool)
    for column, prefix in (("road_condition", "road"), ("deal_type", "deal")):
        train_norm = normalize_categories(train[column])
        test_norm = normalize_categories(test[column])
        dummies, levels, _ref = categorical_dummies(train_norm, prefix)
        known = set(levels)
        unseen |= ~test_norm.isin(known).to_numpy()
        parts_train.append(dummies)
        mapped = []
        for col in dummies.columns:
            label = col[len(prefix) + 1 :]
            mapped.append(pd.Series((test_norm == label).astype(float).to_numpy(), index=test.index, name=col))
        if mapped:
            parts_test.append(pd.concat(mapped, axis=1))

    if level is not None and level_ref is not None:
        train_level = _collapse_series(level.loc[train.index].astype(str), level_ref, collapse_at)
        test_level = _collapse_series(level.loc[test.index].astype(str), level_ref, collapse_at)
        # 붕괴 기준은 학습 건수. 검증은 학습에서 정한 묶음만 따른다.
        train_counts = level.loc[train.index].astype(str).value_counts()
        rare = {name for name, count in train_counts.items() if name != level_ref and int(count) < collapse_at}
        test_level = test_level.mask(level.loc[test.index].astype(str).isin(rare), "기타")
        dummy_src = train_level.rename("_level")
        dummies, _levels, _ref = categorical_dummies(dummy_src, "lv", reference=level_ref)
        parts_train.append(dummies)
        mapped = []
        for col in dummies.columns:
            label = col[len("lv") + 1 :]
            mapped.append(pd.Series((test_level == label).astype(float).to_numpy(), index=test.index, name=col))
        if mapped:
            parts_test.append(pd.concat(mapped, axis=1))

    x_train = pd.concat(parts_train, axis=1) if parts_train else pd.DataFrame(index=train.index)
    x_test = pd.concat(parts_test, axis=1) if parts_test else pd.DataFrame(index=test.index)
    x_train = x_train.loc[:, x_train.std(ddof=0).fillna(0) > 0]
    x_test = x_test.reindex(columns=x_train.columns, fill_value=0.0)
    return x_train, x_test, unseen


def _level_series(frame: pd.DataFrame, model: str, anchor: CellCount) -> tuple[pd.Series | None, str | None, int]:
    if model == "M0":
        return None, None, 0
    if model == "M1":
        added = str(frame["m1_key"].iloc[0]) if "m1_key" in frame.columns and len(frame) else ""
        if not added:
            return None, None, 0
        values = np.where(frame["cell_key"].to_numpy() == added, "추가", "기준")
        return pd.Series(values, index=frame.index), "기준", 0
    if model == "M2":
        values = np.where(frame["zone"].to_numpy() == anchor.zone, frame["jimok"].to_numpy(), "밖")
        return pd.Series(values, index=frame.index), anchor.jimok, 0
    if model == "M3":
        values = np.where(frame["jimok"].to_numpy() == anchor.jimok, frame["zone"].to_numpy(), "밖")
        return pd.Series(values, index=frame.index), anchor.zone, 0
    if model == "M4":
        values = np.where(frame["eup_code"].to_numpy() == anchor.eup_code, "기준", "쌍둥이")
        return pd.Series(values, index=frame.index), "기준", 0
    if model == "M5":
        zone = frame["zone"].astype(str)
        jimok = frame["jimok"].astype(str)
        values = zone + "|" + jimok
        # 주효과 둘. 열 이름은 zone / jimok 으로 따로 만든다.
        return None, None, M5_COLLAPSE_N
    raise FitError(f"알 수 없는 모형 {model}")


def _m5_parts(train: pd.DataFrame, test: pd.DataFrame, anchor: CellCount) -> tuple[pd.DataFrame, pd.DataFrame]:
    def one(column: str, reference: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        raw = _collapse_series(train[column].astype(str), reference, M5_COLLAPSE_N)
        counts = train[column].astype(str).value_counts()
        rare = {name for name, count in counts.items() if name != reference and int(count) < M5_COLLAPSE_N}
        test_values = test[column].astype(str).mask(test[column].astype(str).isin(rare), "기타")
        dummies, _levels, _ref = categorical_dummies(raw, column[:2], reference=reference)
        mapped = []
        for col in dummies.columns:
            label = col.split("_", 1)[1]
            mapped.append((test_values == label).astype(float).rename(col))
        test_df = pd.concat(mapped, axis=1) if mapped else pd.DataFrame(index=test.index)
        return dummies, test_df

    zone_tr, zone_te = one("zone", anchor.zone)
    jimok_tr, jimok_te = one("jimok", anchor.jimok)
    return pd.concat([zone_tr, jimok_tr], axis=1), pd.concat([zone_te, jimok_te], axis=1)


def _fit_fold(
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    model: str,
    anchor: CellCount,
    with_level: bool,
    use_assessed: bool = False,
) -> tuple[np.ndarray, np.ndarray, dict[str, float], float]:
    if with_level and model not in {"M0", "M5"}:
        level, ref, _collapse = _level_series(pd.concat([train, test], axis=0), model, anchor)
    else:
        level, ref = None, None
    x_train, x_test, unseen = _design(
        train,
        test,
        level=level,
        level_ref=ref,
        collapse_at=0,
        use_assessed=use_assessed,
    )
    if with_level and model == "M5":
        extra_tr, extra_te = _m5_parts(train, test, anchor)
        x_train = pd.concat([x_train, extra_tr], axis=1)
        x_test = pd.concat([x_test, extra_te], axis=1)
        x_train = x_train.loc[:, x_train.std(ddof=0).fillna(0) > 0]
        x_test = x_test.reindex(columns=x_train.columns, fill_value=0.0)
    if x_train.empty or len(train) <= x_train.shape[1] + 1:
        raise FitError("학습 행이 열보다 적습니다.")
    y = np.log(train["unit_price_per_sqm"].astype(float).to_numpy())
    x_const = sm.add_constant(x_train.to_numpy(dtype=float), has_constant="add")
    try:
        fitted = sm.OLS(y, x_const, missing="drop").fit()
    except Exception as exc:
        raise FitError("추정에 실패했습니다.") from exc
    if not np.isfinite(fitted.params).all():
        raise FitError("계수가 유한하지 않습니다.")
    smear = _duan_smearing(fitted.resid)
    test_const = sm.add_constant(x_test.to_numpy(dtype=float), has_constant="add")
    if test_const.shape[1] != x_const.shape[1]:
        raise FitError("검증 열 수가 학습과 다릅니다.")
    pred = np.exp(test_const @ np.asarray(fitted.params, dtype=float)) * smear
    names = ["const", *list(x_train.columns)]
    coefs = {name: float(value) for name, value in zip(names, fitted.params)}
    return pred, unseen, coefs, float(fitted.rsquared_adj)


def _metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    ok = np.isfinite(actual) & np.isfinite(pred) & (actual != 0) & (pred > 0)
    if not np.any(ok):
        raise FitError("채점할 검증 거래가 없습니다.")
    ape = np.abs(pred[ok] - actual[ok]) / np.abs(actual[ok]) * 100.0
    signed = (pred[ok] - actual[ok]) / np.abs(actual[ok]) * 100.0
    return {
        "mape": float(np.mean(ape)),
        "mdape": float(np.median(ape)),
        "bias": float(np.mean(signed)),
        "n_test": int(ok.sum()),
    }


def _pool_mask(frame: pd.DataFrame, model: str, anchor: CellCount) -> pd.Series:
    target = frame["is_target"]
    if model == "M0":
        return target
    if model == "M1":
        key = str(frame["m1_key"].iloc[0]) if "m1_key" in frame.columns and len(frame) else ""
        if not key:
            return pd.Series(False, index=frame.index)
        return target | (frame["cell_key"] == key)
    if model == "M2":
        return (frame["eup_code"] == anchor.eup_code) & (frame["zone"] == anchor.zone) & frame["group_ok_m2"]
    if model == "M3":
        return (frame["eup_code"] == anchor.eup_code) & (frame["jimok"] == anchor.jimok) & frame["group_ok_m3"]
    if model == "M4":
        twin = str(frame["twin_code"].iloc[0]) if "twin_code" in frame.columns and len(frame) else ""
        if not twin:
            return pd.Series(False, index=frame.index)
        same = (frame["eup_code"] == twin) & (frame["zone"] == anchor.zone) & (frame["jimok"] == anchor.jimok)
        return target | same
    if model == "M5":
        return frame["eup_code"] == anchor.eup_code
    return pd.Series(False, index=frame.index)


def prepare_frame(frame: pd.DataFrame, anchor: CellCount, twin_code: str | None, m1_key: str | None) -> pd.DataFrame:
    out = frame.copy()
    out["cell_key"] = out["zone"].astype(str) + "|" + out["jimok"].astype(str)
    out["is_target"] = (
        (out["eup_code"] == anchor.eup_code)
        & (out["zone"] == anchor.zone)
        & (out["jimok"] == anchor.jimok)
    )
    counts = out.loc[out["eup_code"] == anchor.eup_code].groupby(["zone", "jimok"]).size()
    m2_ok = set()
    m3_ok = set()
    for (zone, jimok), count in counts.items():
        if zone == anchor.zone and int(count) >= GROUP_MIN_N:
            m2_ok.add(jimok)
        if jimok == anchor.jimok and int(count) >= GROUP_MIN_N:
            m3_ok.add(zone)
    m2_ok.add(anchor.jimok)
    m3_ok.add(anchor.zone)
    out["group_ok_m2"] = out["jimok"].isin(m2_ok) | out["is_target"]
    out["group_ok_m3"] = out["zone"].isin(m3_ok) | out["is_target"]
    out["m1_key"] = m1_key or ""
    out["twin_code"] = twin_code or ""
    return out


def _modal_other_key(frame: pd.DataFrame, anchor: CellCount) -> str | None:
    """기준 칸이 최다이거나 동률이면 추가하지 않는다."""
    local = frame.loc[frame["eup_code"] == anchor.eup_code]
    if "cell_key" not in local.columns:
        local = local.copy()
        local["cell_key"] = local["zone"].astype(str) + "|" + local["jimok"].astype(str)
    counts = local.groupby("cell_key").size().sort_index().sort_values(ascending=False, kind="mergesort")
    if counts.empty:
        return None
    target = cell_key(anchor.zone, anchor.jimok)
    target_n = int(counts.get(target, 0))
    if target_n >= int(counts.max()):
        return None
    others = counts.drop(labels=[target], errors="ignore")
    top = str(others.index[0])
    if int(others.iloc[0]) < GROUP_MIN_N:
        return None
    return top


def _score_once(
    frame: pd.DataFrame,
    folds: pd.Series,
    *,
    model: str,
    anchor: CellCount,
    with_level: bool,
    add_index: pd.Index | None = None,
    use_assessed: bool = False,
) -> dict:
    pool = _pool_mask(frame, model, anchor)
    if model != "M0" and not bool((pool & ~frame["is_target"]).any()):
        return {"status": "unavailable", "reason": "보탤 거래가 없습니다."}
    fold_rows = []
    for fold in range(N_FOLDS):
        test_mask = (folds == fold) & frame["is_target"]
        test_idx = frame.index[test_mask.fillna(False).to_numpy()]
        if add_index is not None and model != "M0":
            train_mask = (frame["is_target"] & ~frame.index.isin(test_idx)) | (
                frame.index.isin(add_index) & ~frame["is_target"]
            )
        else:
            train_mask = pool & ~frame.index.isin(test_idx)
        train_idx = frame.index[train_mask.fillna(False).to_numpy()]
        if len(test_idx) == 0 or len(train_idx) == 0:
            raise FitError("폴드 학습 또는 검증이 비었습니다.")
        train = frame.loc[train_idx]
        test = frame.loc[test_idx]
        pred, unseen, coefs, adj = _fit_fold(
            train, test, model=model, anchor=anchor, with_level=with_level, use_assessed=use_assessed
        )
        bad = unseen | ~np.isfinite(pred) | (pred <= 0)
        fold_rows.append((test, pred, bad, coefs, adj, len(train)))
    # 한 모형 안에서 도로·유형이 없는 행은 그 모형만 뺀다. 비교 분모는 호출부가 맞춘다.
    return {"status": "estimated", "folds": fold_rows}


def _align_and_summarize(scored: dict[str, dict]) -> dict[str, dict]:
    """추정된 모형이 공통으로 채점하는 검증 행만 남긴다."""
    estimated = {name: row for name, row in scored.items() if row.get("status") == "estimated"}
    if not estimated:
        return scored
    out: dict[str, dict] = {name: dict(row) for name, row in scored.items()}
    summaries: dict[str, dict] = {}
    n_folds = N_FOLDS
    for fold in range(n_folds):
        common_bad = None
        for row in estimated.values():
            _test, _pred, bad, *_rest = row["folds"][fold]
            common_bad = bad if common_bad is None else (common_bad | bad)
        for name, row in estimated.items():
            test, pred, _bad, coefs, adj, n_train = row["folds"][fold]
            actual = test["unit_price_per_sqm"].to_numpy(dtype=float)
            keep = ~common_bad
            if not np.any(keep):
                raise FitError("공통 검증 행이 없습니다.")
            metrics = _metrics(actual[keep], pred[keep])
            summaries.setdefault(name, []).append({**metrics, "coefs": coefs, "adj_r2": adj, "n_train": n_train, "dropped": int(common_bad.sum())})
    for name, folds in summaries.items():
        out[name] = _pack(folds)
    return out


def _pack(folds: list[dict]) -> dict:
    def mean_key(key: str) -> float:
        return float(np.mean([row[key] for row in folds]))

    def coef_stats(name: str) -> tuple[float | None, float | None]:
        vals = [row["coefs"].get(name) for row in folds]
        if any(value is None or not np.isfinite(value) for value in vals):
            return None, None
        arr = np.array(vals, dtype=float)
        sign = float(np.sign(np.mean(arr)))
        sd = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        return sign, sd

    area_sign, area_sd = coef_stats("log_area")
    year_sign, year_sd = coef_stats("year_trend")
    assessed_sign, assessed_sd = coef_stats("log_assessed_land_price")
    return {
        "status": "estimated",
        "reason": None,
        "mape": mean_key("mape"),
        "mdape": mean_key("mdape"),
        "bias": mean_key("bias"),
        "n_test_mean": mean_key("n_test"),
        "n_train_mean": mean_key("n_train"),
        "adj_r2_mean": mean_key("adj_r2"),
        "dropped_unseen": int(sum(row["dropped"] for row in folds)),
        "log_area_sign": area_sign,
        "log_area_sd": area_sd,
        "year_sign": year_sign,
        "year_sd": year_sd,
        "log_assessed_sign": assessed_sign,
        "log_assessed_sd": assessed_sd,
    }


def evaluate_cv(
    frame: pd.DataFrame, anchor: CellCount, *, with_level: bool = True, use_assessed: bool = False
) -> dict[str, dict]:
    folds = assign_folds(frame)
    scored: dict[str, dict] = {}
    for model in MODELS:
        try:
            scored[model] = _score_once(
                frame, folds, model=model, anchor=anchor, with_level=with_level, use_assessed=use_assessed
            )
        except FitError as exc:
            scored[model] = {"status": "unavailable", "reason": str(exc)}
    try:
        return _align_and_summarize(scored)
    except FitError as exc:
        return {model: {"status": "unavailable", "reason": str(exc)} for model in MODELS}


def add_counts(frame: pd.DataFrame, anchor: CellCount) -> dict[str, int]:
    counts = {}
    for model in MODELS:
        if model == "M0":
            counts[model] = int(frame["is_target"].sum())
            continue
        pool = _pool_mask(frame, model, anchor)
        if model != "M0" and not bool((pool & ~frame["is_target"]).any()):
            counts[model] = 0
        else:
            counts[model] = int((pool & ~frame["is_target"]).sum())
    return counts


def experiment_b_quota(counts: dict[str, int]) -> int | None:
    eligible = [counts[model] for model in MODELS if model != "M0" and counts.get(model, 0) > 0]
    if not eligible:
        return None
    quota = min(eligible)
    if quota < B_QUOTA_MIN:
        return None
    return int(quota)


def evaluate_b(
    frame: pd.DataFrame,
    anchor: CellCount,
    quota: int,
    *,
    seed: int = SEED,
    n_repeats: int = N_REPEATS,
    use_assessed: bool = False,
) -> dict[str, dict]:
    folds = assign_folds(frame, seed=seed)
    try:
        m0_scored = _score_once(
            frame, folds, model="M0", anchor=anchor, with_level=True, use_assessed=use_assessed
        )
        m0 = _align_and_summarize({"M0": m0_scored}).get("M0", {})
    except FitError as exc:
        m0_scored = {"status": "unavailable", "reason": str(exc)}
        m0 = m0_scored
    out: dict[str, dict] = {"M0": m0}
    if m0_scored.get("status") != "estimated":
        for model in MODELS:
            if model != "M0":
                out[model] = {"status": "unavailable", "reason": "기준 모형이 없습니다."}
        return out
    for model_i, model in enumerate(model_name for model_name in MODELS if model_name != "M0"):
        pool = _pool_mask(frame, model, anchor)
        extra_idx = frame.index[(pool & ~frame["is_target"]).fillna(False).to_numpy()]
        if len(extra_idx) < quota:
            out[model] = {"status": "unavailable", "reason": "할당량보다 추가 거래가 적습니다."}
            continue
        packed = []
        for repeat in range(n_repeats):
            rng = np.random.default_rng(np.random.SeedSequence([seed, model_i, repeat]))
            chosen = pd.Index(rng.choice(extra_idx.to_numpy(), size=quota, replace=False))
            try:
                scored = _score_once(
                    frame,
                    folds,
                    model=model,
                    anchor=anchor,
                    with_level=True,
                    add_index=chosen,
                    use_assessed=use_assessed,
                )
                aligned = _align_and_summarize({model: scored, "M0": m0_scored})
            except FitError:
                continue
            row = aligned.get(model) or {}
            if row.get("status") != "estimated":
                continue
            base = aligned.get("M0") or {}
            if base.get("mape") is not None:
                row["paired_m0_mape"] = float(base["mape"])
            packed.append(row)
        if not packed:
            out[model] = {"status": "unavailable", "reason": "같은 수량 반복이 추정되지 않았습니다."}
            continue
        out[model] = _average_repeats(packed, n_repeats)
    return out


def _average_repeats(rows: list[dict], n_repeats: int) -> dict:
    def mean_of(key: str) -> float | None:
        vals = [row[key] for row in rows if row.get(key) is not None]
        if not vals:
            return None
        return float(np.mean(vals))

    def sd_of(key: str) -> float | None:
        vals = [row[key] for row in rows if row.get(key) is not None]
        if len(vals) < 2:
            return 0.0 if vals else None
        return float(np.std(vals, ddof=1))

    area_signs = [row.get("log_area_sign") for row in rows if row.get("log_area_sign") is not None]
    year_signs = [row.get("year_sign") for row in rows if row.get("year_sign") is not None]
    return {
        "status": "estimated",
        "reason": None,
        "n_repeats_ok": len(rows),
        "n_repeats": n_repeats,
        "mape": mean_of("mape"),
        "mape_sd": sd_of("mape"),
        "mdape": mean_of("mdape"),
        "bias": mean_of("bias"),
        "n_train_mean": mean_of("n_train_mean"),
        "log_area_sign": float(np.sign(np.mean(area_signs))) if area_signs else None,
        "log_area_sd": sd_of("log_area_sd"),
        "year_sign": float(np.sign(np.mean(year_signs))) if year_signs else None,
        "year_sd": sd_of("year_sd"),
        "adj_r2_mean": mean_of("adj_r2_mean"),
        "paired_m0_mape": mean_of("paired_m0_mape"),
    }


def temporal_split(frame: pd.DataFrame) -> tuple[pd.Index, pd.Index, pd.Timestamp] | None:
    target = frame.loc[frame["is_target"]].sort_values(["contract_date", "id"])
    n_train = int(np.floor(len(target) * 0.7))
    n_test = len(target) - n_train
    if n_test < TEMPORAL_TEST_MIN or n_train < GROUP_MIN_N:
        return None
    train_idx = target.index[:n_train]
    test_idx = target.index[n_train:]
    cutoff = pd.Timestamp(target.loc[test_idx, "contract_date"].min())
    return train_idx, test_idx, cutoff


def evaluate_temporal(frame: pd.DataFrame, anchor: CellCount, *, use_assessed: bool = False) -> dict[str, dict]:
    split = temporal_split(frame)
    if split is None:
        return {model: {"status": "unavailable", "reason": "시간순 검증 거래가 8건 미만입니다."} for model in MODELS}
    train_target, test_idx, cutoff = split
    dates = pd.to_datetime(frame["contract_date"])
    out: dict[str, dict] = {}
    fold_bits: dict[str, tuple] = {}
    for model in MODELS:
        pool = _pool_mask(frame, model, anchor)
        extra_all = pool & ~frame["is_target"]
        if model != "M0" and not bool(extra_all.fillna(False).any()):
            out[model] = {"status": "unavailable", "reason": "보탤 거래가 없습니다."}
            continue
        extra = extra_all & (dates < cutoff)
        if model != "M0" and not bool(extra.fillna(False).any()):
            out[model] = {"status": "unavailable", "reason": "절단일 이전 추가 거래가 없습니다."}
            continue
        train_idx = train_target.union(frame.index[extra.fillna(False).to_numpy()])
        try:
            pred, unseen, coefs, adj = _fit_fold(
                frame.loc[train_idx],
                frame.loc[test_idx],
                model=model,
                anchor=anchor,
                with_level=True,
                use_assessed=use_assessed,
            )
        except FitError as exc:
            out[model] = {"status": "unavailable", "reason": str(exc)}
            continue
        bad = unseen | ~np.isfinite(pred) | (pred <= 0)
        fold_bits[model] = (frame.loc[test_idx], pred, bad, coefs, adj, len(train_idx))
        out[model] = {"status": "estimated"}
    if not fold_bits:
        return out
    common = None
    for _test, _pred, bad, *_rest in fold_bits.values():
        common = bad if common is None else (common | bad)
    for model, (test, pred, _bad, coefs, adj, n_train) in fold_bits.items():
        actual = test["unit_price_per_sqm"].to_numpy(dtype=float)
        try:
            metrics = _metrics(actual[~common], pred[~common])
        except FitError as exc:
            out[model] = {"status": "unavailable", "reason": str(exc)}
            continue
        area = coefs.get("log_area")
        year = coefs.get("year_trend")
        out[model] = {
            "status": "estimated",
            "reason": None,
            **metrics,
            "n_train": n_train,
            "adj_r2": adj,
            "dropped_unseen": int(common.sum()),
            "log_area_sign": None if area is None else float(np.sign(area)),
            "year_sign": None if year is None else float(np.sign(year)),
            "log_area_sd": None,
            "year_sd": None,
        }
    return out


def compare_to_m0(rows: dict[str, dict]) -> dict[str, dict]:
    m0 = rows.get("M0") or {}
    base = m0.get("mape") if m0.get("status") == "estimated" else None
    area0 = m0.get("log_area_sign")
    packed = {}
    for model, row in rows.items():
        item = dict(row)
        paired = item.get("paired_m0_mape")
        baseline = paired if paired not in (None, 0) else base
        if item.get("status") == "estimated" and baseline not in (None, 0):
            item["delta_pp"] = float(item["mape"] - baseline)
            item["improvement_rate"] = float((baseline - item["mape"]) / baseline)
            sign = item.get("log_area_sign")
            item["sign_matches_m0"] = sign is not None and area0 is not None and float(sign) == float(area0) and float(area0) != 0.0
        else:
            item["delta_pp"] = None
            item["improvement_rate"] = None
            item["sign_matches_m0"] = None
        packed[model] = item
    return packed


def best_model(rows: dict[str, dict]) -> dict:
    estimated = [
        (row["mape"], model)
        for model, row in rows.items()
        if row.get("status") == "estimated" and row.get("mape") is not None
    ]
    if not estimated:
        return {"mape_winner": None, "adoptable": None}
    estimated.sort()
    winner = estimated[0][1]
    adoptable = None
    for _mape, model in estimated:
        row = rows[model]
        if model == "M0":
            adoptable = "M0"
            break
        if row.get("sign_matches_m0") and row.get("delta_pp") is not None and row["delta_pp"] < 0:
            adoptable = model
            break
    if adoptable is None and rows.get("M0", {}).get("status") == "estimated":
        # 부호가 유지되면서 M0보다 나은 확장이 없으면 기준 칸을 유지한다.
        if rows["M0"].get("log_area_sign") not in (None, 0.0):
            adoptable = "M0"
    return {"mape_winner": winner, "adoptable": adoptable}
