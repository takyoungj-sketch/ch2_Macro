#!/usr/bin/env python3
"""Profile-native Twin (algo 21) 배치·앵커 스모크 — 운영·재빌드 후 게이트.

예:
  cd pipeline
  python verify_profile_twin_smoke.py
  python verify_profile_twin_smoke.py --sido-code 43
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from collective.db_utils import get_collective_engine  # noqa: E402
from db_utils import get_engine  # noqa: E402

PROFILE_VERSION = "v2.1-national"
WINDOW_YEARS = 3
ALGO = 21

# 대표 앵커 (충북·청주)
SAMPLE_EUP = ("43113113", "가경동")
SAMPLE_BEOP = ("4373025034", "옥천읍 마암리")
SAMPLE_SIGUNGU = ("43111", "청주 흥덕구")


def _latest_batch_coll(conn, table: str, *, scope: str | None) -> str | None:
    scope_clause = ""
    params: dict = {"pv": PROFILE_VERSION, "wy": WINDOW_YEARS, "av": ALGO}
    if scope:
        scope_clause = " AND detail_scores->>'scope' = :scope "
        params["scope"] = scope
    row = conn.execute(
        text(
            f"""
            SELECT batch_key
            FROM {table}
            WHERE algorithm_version = :av
              AND detail_scores->>'profile_version' = :pv
              AND (detail_scores->>'window_years')::int = :wy
              {scope_clause}
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC
            LIMIT 1
            """
        ),
        params,
    ).fetchone()
    return str(row[0]) if row else None


def _latest_batch_beop(conn) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT batch_key
            FROM twin_neighbor_v8
            WHERE algorithm_version = :av
              AND region_level = 'beopjungri'
              AND detail_scores->>'profile_version' = :pv
              AND (detail_scores->>'window_years')::int = :wy
              AND detail_scores->>'scope' = 'same_sigungu'
            GROUP BY batch_key
            ORDER BY MAX(computed_at) DESC
            LIMIT 1
            """
        ),
        {"pv": PROFILE_VERSION, "wy": WINDOW_YEARS, "av": ALGO},
    ).fetchone()
    return str(row[0]) if row else None


def _count_anchor(conn, table: str, batch_key: str, anchor_col: str, anchor: str) -> int:
    return int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {table}
                WHERE batch_key = :bk AND {anchor_col} = :ac
                """
            ),
            {"bk": batch_key, "ac": anchor},
        ).scalar()
        or 0
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Profile-native Twin smoke")
    p.add_argument("--sido-code", default=None, help="앵커 시도 prefix 필터(선택)")
    args = p.parse_args()

    coll = get_collective_engine()
    main_db = get_engine()
    errors: list[str] = []

    with coll.connect() as c:
        eup_bk = _latest_batch_coll(c, "twin_eupmyeondong_neighbor_mvp", scope="region")
        sg_bk = _latest_batch_coll(c, "twin_region_neighbor_mvp", scope="national")
        if not eup_bk:
            errors.append("eup batch 없음 (algo 21, scope=region)")
        if not sg_bk:
            errors.append("sigungu batch 없음 (algo 21, scope=national)")
        if eup_bk:
            n = _count_anchor(c, "twin_eupmyeondong_neighbor_mvp", eup_bk, "anchor_eupmyeondong_code", SAMPLE_EUP[0])
            print(f"eup batch={eup_bk} anchor {SAMPLE_EUP[0]}({SAMPLE_EUP[1]}) rows={n}")
            if n < 1:
                errors.append(f"eup anchor {SAMPLE_EUP[0]} twin 없음")
        if sg_bk:
            n = _count_anchor(c, "twin_region_neighbor_mvp", sg_bk, "anchor_sigungu_code", SAMPLE_SIGUNGU[0])
            print(f"sigungu batch={sg_bk} anchor {SAMPLE_SIGUNGU[0]}({SAMPLE_SIGUNGU[1]}) rows={n}")
            if n < 1:
                errors.append(f"sigungu anchor {SAMPLE_SIGUNGU[0]} twin 없음")

    with main_db.connect() as c:
        beop_bk = _latest_batch_beop(c)
        if not beop_bk:
            errors.append("beop batch 없음 (twin_neighbor_v8, algo 21)")
        else:
            n = int(
                c.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM twin_neighbor_v8
                        WHERE batch_key = :bk AND region_level = 'beopjungri'
                          AND anchor_region_code = :ac
                        """
                    ),
                    {"bk": beop_bk, "ac": SAMPLE_BEOP[0]},
                ).scalar()
                or 0
            )
            print(f"beop batch={beop_bk} anchor {SAMPLE_BEOP[0]}({SAMPLE_BEOP[1]}) rows={n}")
            if n < 1:
                errors.append(f"beop anchor {SAMPLE_BEOP[0]} twin 없음")

    if errors:
        for e in errors:
            print("ERROR:", e)
        raise SystemExit(1)
    print("OK - profile-native Twin smoke passed")


if __name__ == "__main__":
    main()
