"""지역×유형×창 전월세전환율 — CH2 원장 자체 산출 (4후보)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

# 건물 풀: 전세·반전세 각각 최소 건수
MIN_BUILDING_JEONSE = 3
MIN_BUILDING_MIXED = 3
# 시군구 게이트
MIN_REGION_BUILDINGS = 5
MIN_REGION_JEONSE = 30
MIN_REGION_MIXED = 30
# 읍면동 게이트 (조회 단위가 동이므로 시군구보다 낮춤)
MIN_DONG_BUILDINGS = 3
MIN_DONG_JEONSE = 15
MIN_DONG_MIXED = 15
# 비현실 r 제외 (%)
R_MIN_PCT = 1.0
R_MAX_PCT = 15.0
DEFAULT_METHOD = "mean_simple"

METHOD_KEYS = {
    "mean_simple": "r_mean_simple",
    "mean_weighted": "r_mean_weighted",
    "ols_origin": "r_ols_origin",
    "ols_weighted": "r_ols_weighted",
}


@dataclass(frozen=True)
class BuildingRateObs:
    building_key: str
    j_m2: float  # 전세 보증금/㎡ P50
    d_m2: float  # 반전세 보증금/㎡ P50
    m_m2: float  # 반전세 월세/㎡ P50
    n_jeonse: int
    n_mixed: int

    @property
    def x(self) -> float:
        return self.j_m2 - self.d_m2

    @property
    def y(self) -> float:
        return 12.0 * self.m_m2

    @property
    def r_building(self) -> float | None:
        if self.x <= 0 or self.m_m2 <= 0:
            return None
        return self.y / self.x * 100.0

    @property
    def weight(self) -> float:
        return float(min(self.n_jeonse, self.n_mixed))


def _median(vals: Sequence[float]) -> float | None:
    arr = np.asarray(vals, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return None
    return float(np.median(arr))


def building_obs_from_rows(rows: Iterable[dict]) -> BuildingRateObs | None:
    """rent_transactions 행 목록(한 건물) → J,D,M."""
    jeonse_dep: list[float] = []
    mixed_dep: list[float] = []
    mixed_mon: list[float] = []
    for r in rows:
        dep = r.get("deposit_per_m2")
        mon = r.get("monthly_per_m2")
        if dep is None or not np.isfinite(float(dep)):
            continue
        dep_f = float(dep)
        mon_f = float(mon) if mon is not None and np.isfinite(float(mon)) else 0.0
        if mon_f <= 0:
            jeonse_dep.append(dep_f)
        elif dep_f > 0 and mon_f > 0:
            mixed_dep.append(dep_f)
            mixed_mon.append(mon_f)
    if len(jeonse_dep) < MIN_BUILDING_JEONSE or len(mixed_dep) < MIN_BUILDING_MIXED:
        return None
    j = _median(jeonse_dep)
    d = _median(mixed_dep)
    m = _median(mixed_mon)
    if j is None or d is None or m is None or j <= d or m <= 0:
        return None
    return BuildingRateObs(
        building_key=str(rows[0].get("building_key") or ""),
        j_m2=j,
        d_m2=d,
        m_m2=m,
        n_jeonse=len(jeonse_dep),
        n_mixed=len(mixed_dep),
    )


def _clip_r(r: float | None) -> float | None:
    if r is None or not np.isfinite(r):
        return None
    if r < R_MIN_PCT or r > R_MAX_PCT:
        return None
    return round(float(r), 4)


def candidate_rates(obs: Sequence[BuildingRateObs]) -> dict[str, float | None]:
    """4후보 r (%)."""
    valid = [o for o in obs if o.r_building is not None and _clip_r(o.r_building) is not None]
    if not valid:
        return {
            "r_mean_simple": None,
            "r_mean_weighted": None,
            "r_ols_origin": None,
            "r_ols_weighted": None,
        }
    rs = [_clip_r(o.r_building) for o in valid]
    rs_clean = [r for r in rs if r is not None]
    w = np.array([o.weight for o in valid], dtype=float)

    r_simple = _clip_r(float(np.mean(rs_clean))) if rs_clean else None

    if w.sum() > 0:
        r_wmean = _clip_r(float(np.average(rs_clean, weights=w[: len(rs_clean)])))
    else:
        r_wmean = None

    x = np.array([o.x for o in valid], dtype=float)
    y = np.array([o.y for o in valid], dtype=float)
    xx = float(np.dot(x, x))
    if xx > 0:
        r_ols = _clip_r(float(np.dot(y, x) / xx * 100.0))
    else:
        r_ols = None

    wxx = float(np.dot(w * x, x))
    if wxx > 0:
        r_wols = _clip_r(float(np.dot(w * y, x) / wxx * 100.0))
    else:
        r_wols = None

    return {
        "r_mean_simple": r_simple,
        "r_mean_weighted": r_wmean,
        "r_ols_origin": r_ols,
        "r_ols_weighted": r_wols,
    }


def region_gate(obs: Sequence[BuildingRateObs], *, level: str = "sigungu") -> tuple[bool, int, int, int]:
    n_b = len(obs)
    n_j = sum(o.n_jeonse for o in obs)
    n_m = sum(o.n_mixed for o in obs)
    if level == "dong":
        ok = n_b >= MIN_DONG_BUILDINGS and n_j >= MIN_DONG_JEONSE and n_m >= MIN_DONG_MIXED
    else:
        ok = (
            n_b >= MIN_REGION_BUILDINGS
            and n_j >= MIN_REGION_JEONSE
            and n_m >= MIN_REGION_MIXED
        )
    return ok, n_b, n_j, n_m


def errors_vs_jeonse(obs: Sequence[BuildingRateObs], r_pct: float | None) -> dict[str, float | None]:
    """반전세 (D,M)을 r로 전세환산한 값과 전세 P50(J)의 오차 (만원/㎡)."""
    if r_pct is None or r_pct <= 0:
        return {"n": 0, "mae": None, "mape": None, "median_ae": None}
    aes: list[float] = []
    apes: list[float] = []
    for o in obs:
        pred = jeonse_equiv_per_m2(deposit_per_m2=o.d_m2, monthly_per_m2=o.m_m2, r_pct=r_pct)
        if pred is None or o.j_m2 <= 0:
            continue
        ae = abs(pred - o.j_m2)
        aes.append(ae)
        apes.append(ae / o.j_m2 * 100.0)
    if not aes:
        return {"n": 0, "mae": None, "mape": None, "median_ae": None}
    arr = np.asarray(aes, dtype=float)
    return {
        "n": int(len(aes)),
        "mae": round(float(np.mean(arr)), 4),
        "mape": round(float(np.mean(apes)), 4),
        "median_ae": round(float(np.median(arr)), 4),
    }


def select_rate(candidates: dict[str, float | None], *, method: str = DEFAULT_METHOD) -> float | None:
    key = METHOD_KEYS.get(method, method)
    return candidates.get(key)


def jeonse_equiv_per_m2(
    *,
    deposit_per_m2: float | None,
    monthly_per_m2: float | None,
    r_pct: float,
) -> float | None:
    """계약 1건 → 전세환산/㎡ (만원/㎡)."""
    if r_pct <= 0:
        return None
    r = r_pct / 100.0
    dep = float(deposit_per_m2 or 0)
    mon = float(monthly_per_m2 or 0)
    if mon <= 0:
        return dep if dep > 0 else None
    if dep <= 0:
        return 12.0 * mon / r if mon > 0 else None
    return dep + 12.0 * mon / r


def monthly_equiv_per_m2(
    *,
    deposit_per_m2: float | None,
    monthly_per_m2: float | None,
    r_pct: float,
) -> float | None:
    """계약 1건 → 월세환산/㎡."""
    if r_pct <= 0:
        return None
    r = r_pct / 100.0
    dep = float(deposit_per_m2 or 0)
    mon = float(monthly_per_m2 or 0)
    if mon <= 0 and dep <= 0:
        return None
    if mon <= 0:
        return dep * r / 12.0 if dep > 0 else None
    if dep <= 0:
        return mon
    return mon + dep * r / 12.0


def compare_methods(rows: list[dict]) -> dict:
    """시군구×유형별 4후보 비교 요약 (리포트용)."""
    by_key: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        key = (r["addr1"], r["addr2"], r["asset_type"])
        by_key.setdefault(key, []).append(r)
    out = []
    for (a1, a2, at), group in sorted(by_key.items()):
        by_bld: dict[str, list[dict]] = {}
        for r in group:
            bk = str(r.get("building_key") or "")
            if not bk:
                continue
            by_bld.setdefault(bk, []).append(r)
        obs = []
        for brows in by_bld.values():
            o = building_obs_from_rows(brows)
            if o:
                obs.append(o)
        ok, nb, nj, nm = region_gate(obs)
        cand = candidate_rates(obs)
        out.append(
            {
                "addr1": a1,
                "addr2": a2,
                "asset_type": at,
                "n_buildings": nb,
                "n_jeonse": nj,
                "n_mixed": nm,
                "gate_passed": ok,
                **cand,
            }
        )
    return {"regions": out}
