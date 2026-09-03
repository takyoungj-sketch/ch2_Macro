"""같은 grain 전국 순위 조회 (D-053). regional_profile JSONB 를 라이브 정렬하지 않는다."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

ROW_FIELDS = (
    "code",
    "name",
    "population",
    "amount_3y",
    "count_3y",
    "rank_amount",
    "rank_count",
    "rank_per_capita",
)


def is_legal_dong_without_ri_code(code: str) -> bool:
    """10자리 끝 `00` = 리가 없는 법정동. 원장 키는 유지하고 리 순위 유니버스에서만 뺀다."""
    c = str(code or "").strip()
    return len(c) == 10 and c.endswith("00")


def competition_ranks_desc(values: Sequence[float]) -> list[int]:
    """SQL RANK() — 동점이면 같은 위, 다음은 건너뛴다 (1,2,2,4)."""
    n = len(values)
    ranks = [0] * n
    if n == 0:
        return ranks
    order = sorted(range(n), key=lambda i: values[i], reverse=True)
    for pos, i in enumerate(order):
        if pos > 0 and values[i] == values[order[pos - 1]]:
            ranks[i] = ranks[order[pos - 1]]
        else:
            ranks[i] = pos + 1
    return ranks


def ranks_per_capita(amounts: Sequence[float], populations: Sequence[int | None]) -> list[int | None]:
    idx = [i for i, p in enumerate(populations) if p is not None and p > 0]
    out: list[int | None] = [None] * len(amounts)
    if not idx:
        return out
    ratios = [amounts[i] / float(populations[i]) for i in idx]  # type: ignore[arg-type]
    sub = competition_ranks_desc(ratios)
    for i, r in zip(idx, sub):
        out[i] = r
    return out


def drop_legal_dongs_from_beop_ranks(
    packed: list[list[Any]],
) -> tuple[list[list[Any]], int, int]:
    """리 순위에서 `…00` 동을 빼고 규모·건수·인구대비 위를 다시 매긴다. 마트는 그대로."""
    kept = [row for row in packed if not is_legal_dong_without_ri_code(str(row[0]))]
    amounts = [float(r[3] or 0) for r in kept]
    counts = [float(r[4] or 0) for r in kept]
    pops: list[int | None] = []
    for r in kept:
        p = r[2]
        if p is None:
            pops.append(None)
        else:
            pops.append(int(p))
    ra = competition_ranks_desc(amounts)
    rc = competition_ranks_desc(counts)
    rp = ranks_per_capita(amounts, pops)
    out: list[list[Any]] = []
    for i, r in enumerate(kept):
        row = list(r)
        row[5] = ra[i]
        row[6] = rc[i]
        row[7] = rp[i]
        out.append(row)
    n_per_capita = sum(1 for p in pops if p is not None and p > 0)
    return out, len(out), n_per_capita


def fetch_national_ranks(
    db: Session,
    *,
    profile_version: str,
    window_years: int,
    region_level: str,
    as_of_month: Optional[date],
) -> dict[str, Any] | None:
    params: dict[str, Any] = {
        "pv": profile_version,
        "wy": window_years,
        "level": region_level,
    }
    as_of = as_of_month
    mix_sql = """
            SELECT as_of_month, universe_n, n_per_capita, share_count, share_amount,
                   computed_at::text AS computed_at
            FROM regional_profile_national_mix
            WHERE profile_version = :pv
              AND window_years = :wy
              AND region_level = :level
            ORDER BY universe_n DESC, as_of_month DESC
            """
    has_corr = db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'regional_profile_national_mix'
              AND column_name = 'type_corr'
            """
        )
    ).scalar()
    if has_corr:
        mix_sql = mix_sql.replace(
            "share_count, share_amount,",
            "share_count, share_amount, type_corr,",
        )
    mix_pick = db.execute(text(mix_sql), params).mappings().all()
    if not mix_pick:
        return None
    best = mix_pick[0]
    chosen = best
    if as_of is not None:
        for m in mix_pick:
            if m["as_of_month"] == as_of:
                # 부분 재빌드(행이 훨씬 적음)면 전국 스냅샷으로 폴백
                if int(m["universe_n"]) >= int(best["universe_n"]) * 0.8:
                    chosen = m
                break
    mix = chosen
    as_of = mix["as_of_month"]
    params["as_of"] = as_of

    dong_filter = ""
    if region_level == "beopjungri":
        # 저비용: 마트는 10자리 전부. 리 목록만 실제 리(끝 00 아님).
        dong_filter = "AND right(btrim(region_code), 2) <> '00'"
    rows = db.execute(
        text(
            f"""
            SELECT region_code, name_short, population, amount_3y, count_3y,
                   rank_amount, rank_count, rank_per_capita
            FROM regional_profile_rank
            WHERE profile_version = :pv
              AND window_years = :wy
              AND region_level = :level
              AND as_of_month = :as_of
              {dong_filter}
            ORDER BY rank_amount ASC, region_code ASC
            """
        ),
        params,
    ).fetchall()

    packed: list[list[Any]] = []
    for r in rows:
        packed.append(
            [
                r[0],
                r[1],
                r[2],
                float(r[3]) if r[3] is not None else 0.0,
                int(r[4] or 0),
                int(r[5]),
                int(r[6]),
                int(r[7]) if r[7] is not None else None,
            ]
        )

    universe_n = int(mix["universe_n"])
    n_per_capita = int(mix["n_per_capita"])
    if region_level == "beopjungri":
        packed, universe_n, n_per_capita = drop_legal_dongs_from_beop_ranks(packed)

    share_count = mix["share_count"]
    share_amount = mix["share_amount"]
    type_corr = mix.get("type_corr")
    if isinstance(share_count, str):
        share_count = json.loads(share_count)
    if isinstance(share_amount, str):
        share_amount = json.loads(share_amount)
    if isinstance(type_corr, str):
        type_corr = json.loads(type_corr)

    return {
        "profile_version": profile_version,
        "as_of_month": as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of),
        "window_years": window_years,
        "region_level": region_level,
        "universe_n": universe_n,
        "n_per_capita": n_per_capita,
        "row_fields": list(ROW_FIELDS),
        "national_share_by_type": {
            "count": share_count or {},
            "amount": share_amount or {},
        },
        "type_corr": type_corr if isinstance(type_corr, dict) else {},
        "rows": packed,
        "computed_at": mix.get("computed_at"),
    }
