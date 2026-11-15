#!/usr/bin/env python3
"""집합 매매 × 주거 임대 정확 키 맵. 보조 층 없음. 원장 UPDATE 없음.

집합 2단계 C-2(Codex 검토): 매매는 C-2 로 같은 법정동 동명 다른 건물을 조각으로 나누지만 임대는 나누지 않는다.
그래서 C-2 판정 표의 split 키(본 조각 = 옛 키)와 연결표의 C-2 조각 키는 exact 연결을 만들지 않고 보류한다
(임대 키가 여러 건물을 합친 상태라 한 매매 조각에 붙이면 틀린 연결이 된다). 화면은 기존 「연결되지 않음」 안내를 쓴다.
보류 건수는 출력하고, 리허설 c7 이 보고한다.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))

from collective.db_utils import get_collective_engine  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402

KEYS_SQL = """
SELECT DISTINCT building_key, asset_type
FROM {table}
WHERE is_valid = true
  AND asset_type IN ('apartment', 'rowhouse', 'officetel')
  AND NULLIF(btrim(building_key::text), '') IS NOT NULL
"""


def _keys(engine, table: str) -> set[tuple[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(text(KEYS_SQL.format(table=table))).all()
    return {(str(r[1]), str(r[0]).strip()) for r in rows}


def c2_hold_keys(conn) -> set[str]:
    """C-2 판정 표 split 본 키 + 연결표 C-2 조각 키(reason 에 c2). 표가 없으면 빈 집합."""
    out: set[str] = set()
    if conn.execute(text("SELECT to_regclass('public.collective_building_key_c2_units') IS NOT NULL")).scalar():
        out |= {str(r[0]).strip() for r in conn.execute(text(
            "SELECT DISTINCT base_key FROM collective_building_key_c2_units WHERE decision = 'split'"))}
    if conn.execute(text("SELECT to_regclass('public.collective_building_key_map') IS NOT NULL")).scalar():
        for o, n, reason in conn.execute(text(
                "SELECT old_key, new_key, reason FROM collective_building_key_map WHERE reason LIKE '%c2%'")):
            out.add(str(n).strip())
            if reason in ("c2_split", "c2_chain"):      # 본 조각이 옛 키를 그대로 쓰는 경우만(사라진 옛 키는 연결 대상이 아님)
                out.add(str(o).strip())
    return out


def exact_links(sale: set[tuple[str, str]], rent: set[tuple[str, str]], hold: set[str]) -> tuple[set, set]:
    """(만들 exact 연결, 보류한 연결) — 둘 다 (asset_type, key)."""
    both = sale & rent
    held = {x for x in both if x[1] in hold}
    return both - held, held


def main() -> None:
    ceng = get_collective_engine()
    sale = _keys(ceng, "collective_transactions")
    rent = _keys(get_rent_engine(), "rent_transactions")
    with ceng.connect() as conn:
        hold = c2_hold_keys(conn)
    exact, held = exact_links(sale, rent, hold)
    today = date.today()
    rows = [
        {
            "sale_building_key": bk,
            "rent_building_key": bk,
            "asset_type": at,
            "tier": "exact",
            "built_on": today,
        }
        for at, bk in exact
    ]
    eng = get_rent_engine()
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rent_sale_building_map (
                    sale_building_key   CHAR(64)     NOT NULL,
                    rent_building_key   CHAR(64)     NOT NULL,
                    asset_type          VARCHAR(20)  NOT NULL,
                    tier                VARCHAR(16)  NOT NULL DEFAULT 'exact',
                    built_on            DATE         NOT NULL DEFAULT CURRENT_DATE,
                    PRIMARY KEY (sale_building_key, asset_type)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_rent_sale_map_rent
                    ON rent_sale_building_map (rent_building_key, asset_type)
                """
            )
        )
        conn.execute(text("TRUNCATE rent_sale_building_map"))
        if rows:
            conn.execute(
                text(
                    """
                    INSERT INTO rent_sale_building_map
                      (sale_building_key, rent_building_key, asset_type, tier, built_on)
                    VALUES
                      (:sale_building_key, :rent_building_key, :asset_type, :tier, :built_on)
                    """
                ),
                rows,
            )
        counts = conn.execute(
            text(
                """
                SELECT asset_type, count(*)::int
                FROM rent_sale_building_map
                GROUP BY 1
                ORDER BY 1
                """
            )
        ).all()
    print(f"exact={len(rows)} c2_held={len(held)}")
    for at, n in counts:
        print(f"  {at} {n}")


if __name__ == "__main__":
    main()
