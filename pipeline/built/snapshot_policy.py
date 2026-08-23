# -*- coding: utf-8 -*-
"""표제부 스냅샷 고르기 — 거래월에 가장 가까운 과거 본, 없으면 이후 가장 이른 본.

A1/A2 규칙은 건드리지 않는다. 어느 대장 위에서 그 규칙을 돌릴지만 정한다.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# 확정 결과에서 스냅샷마다 달라지는 칸. 미상으로 내릴 때 비운다.
# 이름은 match_all() 출력과 같아야 한다.
MATCH_COLS = (
    "tier",
    "fail",
    "parcel",
    "n_range",
    "n_exact",
    "land_src",
    "struct",
    "floors",
    "approve",
    "reg_road",
    "reg_addr",
    "reg_addr_road",
    "reg_use",
    "rival_lots",
    "road_share_range",
    "road_share_rival",
    "approve_share_rival",
    "struct_share_rival",
)


def contract_ym(year: Any, month: Any = None) -> str | None:
    """계약 연·월 → 'YYYY-MM'. 월이 없으면 6월(연 중간)."""
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    if y < 1900 or y > 2100:
        return None
    try:
        m = int(month) if month is not None and str(month) not in ("", "nan", "None") else 6
    except (TypeError, ValueError):
        m = 6
    if m < 1 or m > 12:
        m = 6
    return f"{y:04d}-{m:02d}"


def pick_snapshot(ym: str | None, snaps: list[str]) -> str:
    """ym 이하 스냅샷 중 가장 늦은 것. 없으면 ym 이후 중 가장 이른 것."""
    if not snaps:
        raise ValueError("snaps is empty")
    ordered = sorted(snaps)
    if not ym:
        return ordered[-1]
    past = [s for s in ordered if s <= ym]
    if past:
        return past[-1]
    return ordered[0]


def contract_ym_series(year: pd.Series, month: pd.Series | None) -> pd.Series:
    y = pd.to_numeric(year, errors="coerce")
    if month is None:
        m = pd.Series(6.0, index=year.index)
    else:
        m = pd.to_numeric(month, errors="coerce").fillna(6)
        m = m.where((m >= 1) & (m <= 12), 6)
    ok = y.notna() & (y >= 1900) & (y <= 2100)
    out = pd.Series(pd.NA, index=year.index, dtype=object)
    if ok.any():
        out.loc[ok] = (
            y.loc[ok].astype(int).astype(str).str.zfill(4)
            + "-"
            + m.loc[ok].astype(int).astype(str).str.zfill(2)
        )
    return out


def pick_snapshot_series(ym: pd.Series, snaps: list[str]) -> pd.Series:
    """행마다 pick_snapshot. ym 결측은 최신 본."""
    ordered = sorted(snaps)
    result = pd.Series(ordered[0], index=ym.index, dtype=object)
    for s in ordered:
        result = result.mask(ym.notna() & (ym >= s), s)
    return result.mask(ym.isna(), ordered[-1])


def _pick_among_hits(ym: pd.Series, hit_mat: pd.DataFrame, snaps: list[str]) -> pd.Series:
    """hit_mat(스냅샷 열, bool)에서 거래월에 맞는 본을 고른다. 히트 없으면 NA."""
    ordered = sorted(snaps)
    result = pd.Series(pd.NA, index=ym.index, dtype=object)
    for s in ordered:
        col = hit_mat[s] if s in hit_mat.columns else False
        result = result.mask(col & result.isna(), s)
    for s in ordered:
        col = hit_mat[s] if s in hit_mat.columns else False
        result = result.mask(col & ym.notna() & (ym >= s), s)
    for s in ordered:
        col = hit_mat[s] if s in hit_mat.columns else False
        result = result.mask(col & ym.isna(), s)
    return result


def _is_hit(parcel: Any, tier: Any) -> bool:
    return isinstance(parcel, str) and parcel != "" and pd.notna(tier)


def _blank_match(row: dict[str, Any], fail: str) -> dict[str, Any]:
    out = dict(row)
    for c in MATCH_COLS:
        if c in out:
            out[c] = None
    out["fail"] = fail
    if "n_range" in out:
        out["n_range"] = 0
    if "n_exact" in out:
        out["n_exact"] = 0
    return out


def _copy_from(src: dict[str, Any], snap: str, via: str) -> dict[str, Any]:
    out = dict(src)
    out["snapshot_used"] = snap
    out["snapshot_via"] = via
    return out


def _hit_series(df: pd.DataFrame) -> pd.Series:
    p = df["parcel"]
    t = df["tier"]
    is_str = p.map(lambda x: isinstance(x, str) and x != "")
    return is_str.fillna(False).astype(bool) & t.notna()


def _take_by_chosen(
    indexed: dict[str, pd.DataFrame], chosen: pd.Series, via: str
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for snap, grp in chosen.groupby(chosen, sort=False):
        if not isinstance(snap, str) or snap not in indexed:
            continue
        part = indexed[snap].loc[grp.index].copy()
        part["snapshot_used"] = snap
        part["snapshot_via"] = via
        pieces.append(part)
    if not pieces:
        cols = next(iter(indexed.values())).columns.tolist() + ["snapshot_used", "snapshot_via"]
        return pd.DataFrame(columns=cols)
    out = pd.concat(pieces, axis=0)
    return out.reindex(chosen.index)


def _blank_df(df: pd.DataFrame, fail: str) -> pd.DataFrame:
    out = df.copy()
    for c in MATCH_COLS:
        if c in out.columns:
            out[c] = None
    out["fail"] = fail
    if "n_range" in out.columns:
        out["n_range"] = 0
    if "n_exact" in out.columns:
        out["n_exact"] = 0
    return out


def apply_snapshot_policy(
    by_snap: dict[str, pd.DataFrame],
    *,
    policy: str,
    primary: str,
) -> pd.DataFrame:
    """스냅샷별 매칭 결과를 거래 단위로 한 표로 합친다.

    policy:
      latest        — primary 본만 (지금 코드)
      time          — 거래월에 고른 1본만
      time_fallback — 1본 실패 시에만 다른 본. 필지가 갈리면 미상
      union         — 확정 필지가 하나면 채택, 둘 이상이면 미상
    """
    snaps = list(by_snap)
    if policy not in {"latest", "time", "time_fallback", "union"}:
        raise ValueError(f"unknown policy: {policy}")
    if primary not in by_snap:
        primary = snaps[-1]

    indexed = {s: df.set_index("id", drop=False) for s, df in by_snap.items()}
    ids = indexed[snaps[0]].index
    for s in snaps[1:]:
        if not indexed[s].index.equals(ids):
            indexed[s] = indexed[s].reindex(ids)

    base = indexed[primary]
    year = base["contract_year"] if "contract_year" in base.columns else pd.Series(pd.NA, index=ids)
    month = base["contract_month"] if "contract_month" in base.columns else None
    ym = contract_ym_series(year, month)

    if policy == "latest":
        out = base.copy()
        out["snapshot_used"] = primary
        out["snapshot_via"] = "latest"
        return out.reset_index(drop=True)

    chosen = pick_snapshot_series(ym, snaps)

    if policy == "time":
        return _take_by_chosen(indexed, chosen, "time").reset_index(drop=True)

    hit_mat = pd.concat({s: _hit_series(indexed[s]) for s in snaps}, axis=1)
    parcel_mat = pd.concat({s: indexed[s]["parcel"] for s in snaps}, axis=1)

    if policy == "time_fallback":
        time_rows = _take_by_chosen(indexed, chosen, "time")
        hit = _hit_series(time_rows)
        chosen_oh = pd.DataFrame({s: chosen.eq(s) for s in snaps}, index=ids)
        other_hit = hit_mat & ~chosen_oh
        n_parcels = parcel_mat.where(other_hit).nunique(axis=1, dropna=True)
        miss = ~hit
        fb_ok = miss & (n_parcels == 1)
        conf = miss & (n_parcels > 1)
        still = miss & (n_parcels == 0)

        frames = [time_rows.loc[hit]]
        if fb_ok.any():
            alt = _pick_among_hits(ym, other_hit, snaps)
            frames.append(_take_by_chosen(indexed, alt.loc[fb_ok], "fallback"))
        if conf.any():
            blank = _blank_df(time_rows.loc[conf], "snapshot_conflict")
            blank["snapshot_used"] = chosen.loc[conf]
            blank["snapshot_via"] = "conflict"
            frames.append(blank)
        if still.any():
            frames.append(time_rows.loc[still])
        out = pd.concat(frames).reindex(ids)
        return out.reset_index(drop=True)

    # union
    n_parcels = parcel_mat.where(hit_mat).nunique(axis=1, dropna=True)
    ok = n_parcels == 1
    conf = n_parcels > 1
    miss = n_parcels == 0
    frames = []
    if ok.any():
        alt = _pick_among_hits(ym, hit_mat, snaps)
        frames.append(_take_by_chosen(indexed, alt.loc[ok], "union"))
    if conf.any():
        blank = _blank_df(base.loc[conf], "snapshot_conflict")
        blank["snapshot_used"] = None
        blank["snapshot_via"] = "conflict"
        frames.append(blank)
    if miss.any():
        keep = base.loc[miss].copy()
        keep["snapshot_used"] = primary
        keep["snapshot_via"] = "union_miss"
        frames.append(keep)
    if not frames:
        out = base.copy()
        out["snapshot_used"] = primary
        out["snapshot_via"] = "union_miss"
        return out.reset_index(drop=True)
    out = pd.concat(frames).reindex(ids)
    return out.reset_index(drop=True)


def policy_coverage(df: pd.DataFrame) -> dict[str, Any]:
    n = len(df)
    ok = df["tier"].notna() & df["parcel"].notna() & (df["parcel"] != "")
    n_ok = int(ok.sum())
    via = df.loc[ok, "snapshot_via"].value_counts().to_dict() if "snapshot_via" in df.columns else {}
    used = df.loc[ok, "snapshot_used"].value_counts().to_dict() if "snapshot_used" in df.columns else {}
    return {
        "n": n,
        "confirmed": n_ok,
        "confirmed_pct": round(100.0 * n_ok / n, 1) if n else 0.0,
        "via": {str(k): int(v) for k, v in via.items()},
        "snapshot_used": {str(k): int(v) for k, v in used.items()},
        "a1": int((df["tier"] == "A1").sum()),
        "a2": int((df["tier"] == "A2").sum()),
        "conflict": int((df["fail"] == "snapshot_conflict").sum()),
    }
