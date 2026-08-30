"""같은 grain 전국 순위 조회 (D-053). regional_profile JSONB 를 라이브 정렬하지 않는다."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

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

    rows = db.execute(
        text(
            """
            SELECT region_code, name_short, population, amount_3y, count_3y,
                   rank_amount, rank_count, rank_per_capita
            FROM regional_profile_rank
            WHERE profile_version = :pv
              AND window_years = :wy
              AND region_level = :level
              AND as_of_month = :as_of
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
        "universe_n": int(mix["universe_n"]),
        "n_per_capita": int(mix["n_per_capita"]),
        "row_fields": list(ROW_FIELDS),
        "national_share_by_type": {
            "count": share_count or {},
            "amount": share_amount or {},
        },
        "type_corr": type_corr if isinstance(type_corr, dict) else {},
        "rows": packed,
        "computed_at": mix.get("computed_at"),
    }
