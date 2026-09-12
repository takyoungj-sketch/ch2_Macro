"""Fingerprint Twin — 공통식 기울기·반응곡선 거리 (D-066 후보 재순위).

읍면동 최적식 계수는 쓰지 않는다. 시군구(5자리)에 log(연면적)+log(대지)+도로더미를
고정 적합하고, 절편을 뺀 가상 물건 ŷ 상관으로 같은 프로필 Twin 목록을 다시 줄 세운다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROAD_LEVELS = ("8m미만", "12m미만", "25m미만", "25m이상")
ROAD_BASE = ROAD_LEVELS[0]
BETA_KEYS = ("ln_gross", "ln_land", "r_12m미만", "r_25m미만", "r_25m이상")
PROBE_GROSS = (80.0, 200.0, 500.0, 1200.0)
PROBE_LAND = (100.0, 300.0, 800.0, 2000.0)
N_MIN_SIGUNGU = 50


def parent_sigungu(region_code: str) -> str:
    code = (region_code or "").strip()
    if len(code) >= 5:
        return code[:5]
    return code


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a, dtype=float) - float(np.mean(a))
    y = np.asarray(b, dtype=float) - float(np.mean(b))
    den = float(np.sqrt(np.dot(x, x) * np.dot(y, y)))
    if den < 1e-12:
        return 0.0
    return float(np.dot(x, y) / den)


def _cosine(u: np.ndarray, v: np.ndarray) -> float:
    den = float(np.linalg.norm(u) * np.linalg.norm(v))
    if den < 1e-12:
        return 0.0
    return float(np.dot(u, v) / den)


def _road_dummies(labels: pd.Series) -> pd.DataFrame:
    cat = pd.Categorical(labels.astype(str), categories=list(ROAD_LEVELS))
    d = pd.get_dummies(cat, prefix="r", drop_first=True, dtype=float)
    d.index = labels.index
    for name in BETA_KEYS[2:]:
        col = name  # r_12m미만 …
        if col not in d.columns:
            d[col] = 0.0
    return d[[k for k in BETA_KEYS if k.startswith("r_")]]


def _probe_design() -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for g in PROBE_GROSS:
        for land in PROBE_LAND:
            for road in ROAD_LEVELS:
                row = {"ln_gross": float(np.log(g)), "ln_land": float(np.log(land))}
                for k in BETA_KEYS[2:]:
                    row[k] = 0.0
                if road != ROAD_BASE:
                    row[f"r_{road}"] = 1.0
                rows.append(row)
    return pd.DataFrame(rows)


_PROBE = _probe_design()


@dataclass(frozen=True)
class Fingerprint:
    sigungu_code: str
    n: int
    beta: dict[str, float]
    intercept: float

    def beta_vector(self) -> np.ndarray:
        return np.array([self.beta.get(k, 0.0) for k in BETA_KEYS], dtype=float)

    def probe_log_price(self) -> np.ndarray:
        x = _PROBE[list(BETA_KEYS)].to_numpy(dtype=float)
        return self.intercept + x @ self.beta_vector()


@dataclass
class FingerprintDistance:
    curve_r: float
    beta_cosine: float
    sign_mismatch: int
    distance: float


def fit_common_spec(df: pd.DataFrame, *, sigungu_code: str, n_min: int = N_MIN_SIGUNGU) -> Fingerprint | None:
    """ln(P) ~ ln(연면적)+ln(대지)+도로. 절편은 지문에 넣지 않고 반응곡선에만 쓴 뒤 평균을 뺀다."""
    work = df.copy()
    for col in ("price", "gross_area", "land_area"):
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work[(work["price"] > 0) & (work["gross_area"] > 0) & (work["land_area"] > 0)]
    if "road_width_label" not in work.columns:
        return None
    work = work[work["road_width_label"].astype(str).isin(ROAD_LEVELS)]
    if len(work) < n_min:
        return None
    y = np.log(work["price"].astype(float))
    X = pd.concat(
        [
            np.log(work["gross_area"].astype(float)).rename("ln_gross"),
            np.log(work["land_area"].astype(float)).rename("ln_land"),
            _road_dummies(work["road_width_label"]),
        ],
        axis=1,
    )
    Xc = sm.add_constant(X.astype(float), has_constant="add")
    try:
        model = sm.OLS(y, Xc).fit()
    except (ValueError, np.linalg.LinAlgError):
        return None
    beta = {k: float(model.params.get(k, 0.0)) for k in BETA_KEYS}
    return Fingerprint(
        sigungu_code=sigungu_code,
        n=int(len(work)),
        beta=beta,
        intercept=float(model.params.get("const", 0.0)),
    )


def fingerprint_distance(a: Fingerprint, b: Fingerprint) -> FingerprintDistance:
    ya = a.probe_log_price()
    yb = b.probe_log_price()
    curve_r = _pearson(ya - ya.mean(), yb - yb.mean())
    beta_cosine = _cosine(a.beta_vector(), b.beta_vector())
    sign_mismatch = 0
    for key in ("ln_gross", "ln_land"):
        sa = np.sign(a.beta.get(key, 0.0))
        sb = np.sign(b.beta.get(key, 0.0))
        if sa != 0 and sb != 0 and sa != sb:
            sign_mismatch += 1
    distance = round(1.0 - float(np.clip(curve_r, -1.0, 1.0)), 6)
    return FingerprintDistance(
        curve_r=round(curve_r, 6),
        beta_cosine=round(beta_cosine, 6),
        sign_mismatch=sign_mismatch,
        distance=distance,
    )


@dataclass
class RankedNeighbor:
    region_code: str
    label: str | None
    profile_score: float | None
    fingerprint_distance: float | None
    curve_r: float | None
    beta_cosine: float | None
    sign_mismatch: int | None
    parent_sigungu: str


def rerank_neighbors(
    *,
    anchor_code: str,
    neighbors: list[dict[str, object]],
    fingerprints: dict[str, Fingerprint],
) -> list[RankedNeighbor]:
    """같은 후보 우주에서 Fingerprint 거리 오름차순. 거리 동률이면 프로필 점수 내림차순."""
    anchor_fp = fingerprints.get(parent_sigungu(anchor_code))
    ranked: list[RankedNeighbor] = []
    for row in neighbors:
        code = str(row.get("region_code") or row.get("twin_region_code") or "").strip()
        if not code:
            continue
        score = row.get("similarity_score")
        sim = float(score) if isinstance(score, (int, float)) else None
        parent = parent_sigungu(code)
        other = fingerprints.get(parent)
        dist = fingerprint_distance(anchor_fp, other) if anchor_fp and other else None
        ranked.append(
            RankedNeighbor(
                region_code=code,
                label=str(row.get("label") or "") or None,
                profile_score=sim,
                fingerprint_distance=dist.distance if dist else None,
                curve_r=dist.curve_r if dist else None,
                beta_cosine=dist.beta_cosine if dist else None,
                sign_mismatch=dist.sign_mismatch if dist else None,
                parent_sigungu=parent,
            )
        )
    ranked.sort(
        key=lambda r: (
            r.fingerprint_distance is None,
            r.fingerprint_distance if r.fingerprint_distance is not None else 9.0,
            -(r.profile_score or 0.0),
        )
    )
    return ranked
