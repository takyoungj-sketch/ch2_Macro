"""이전 전 key 기준 검증. 판정 파일, 적재, 이전 로직은 여기 두지 않는다."""
from __future__ import annotations

from sqlalchemy import text


def _lot(expr: str) -> str:
    return (
        "CASE WHEN split_part(btrim(" + expr + "), '-', 1) ~ '^[0-9]+$'"
        " THEN coalesce(nullif(ltrim(split_part(btrim(" + expr + "), '-', 1), '0'), ''), '0')"
        " ELSE btrim(split_part(btrim(" + expr + "), '-', 1)) END"
    )


def _flags(expected_updated: int | None, **values: int) -> dict[str, int]:
    out = {
        "part0_base_changed": values["part0_base_changed"],
        "non_base_changed": values["non_base_changed"],
        "nonzero_key_differ": values["nonzero_key_differ"],
        "changed_ne_file": values["changed_ne_file"],
    }
    if expected_updated is not None:
        out["changed_ne_given"] = values["changed_ne_given"]
    return out


def key_scope_checks(conn, *, expected_updated: int | None = None) -> dict:
    """보존 표를 id로 이어 ①~④를 센다. flags 값은 통과면 0이다."""
    before = conn.execute(text("SELECT to_regclass('public.rent_transactions_rc2_before')")).scalar()
    units = conn.execute(text("SELECT to_regclass('public.rent_building_key_c2_units')")).scalar()
    if not before or not units:
        flags = _flags(
            expected_updated,
            part0_base_changed=1,
            non_base_changed=1,
            nonzero_key_differ=1,
            changed_ne_file=1,
            changed_ne_given=1,
        )
        return {"flags": flags, "changed_n": -1, "expected_n": -1}
    conn.execute(text("SET LOCAL enable_nestloop = off"))
    tx_lot = _lot("t.lot_number")
    unit_lot = _lot("u.main_lot")
    changed = conn.execute(text(
        f"""
        WITH changed AS (
            SELECT t.asset_type,
                   left(t.beopjungri_code, 10) AS bjd,
                   {tx_lot} AS lot,
                   rtrim(b.building_key) AS pre_key
            FROM rent_transactions_rc2_before b
            JOIN rent_transactions t ON t.id = b.id
            WHERE rtrim(t.building_key) IS DISTINCT FROM rtrim(b.building_key)
        ),
        bases AS (
            SELECT DISTINCT rtrim(base_key) AS k FROM rent_building_key_c2_units
        )
        SELECT
            (
                SELECT count(*)::bigint FROM changed c
                JOIN rent_building_key_c2_units u
                  ON u.decision = 'split' AND u.part = 0
                 AND rtrim(u.base_key) = c.pre_key
                 AND u.asset_type = c.asset_type
                 AND left(u.beopjungri_code, 10) = c.bjd
                 AND {unit_lot} = c.lot
            ),
            (
                SELECT count(*)::bigint FROM changed c
                WHERE NOT EXISTS (SELECT 1 FROM bases WHERE k = c.pre_key)
            ),
            (SELECT count(*)::bigint FROM changed)
        """
    )).one()
    population = conn.execute(text(
        f"""
        WITH piece AS (
            SELECT rtrim(old_key) AS old_key,
                   asset_type,
                   split_part,
                   min(rtrim(new_key)) AS new_key,
                   count(DISTINCT rtrim(new_key)) AS nkeys
            FROM rent_building_key_map
            WHERE reason = 'c2_split'
            GROUP BY 1, 2, 3
        )
        SELECT count(*)::bigint,
               count(*) FILTER (
                   WHERE p.nkeys IS DISTINCT FROM 1
                      OR rtrim(t.building_key) IS DISTINCT FROM p.new_key
               )::bigint
        FROM rent_transactions t
        LEFT JOIN rent_transactions_rc2_before b ON b.id = t.id
        JOIN rent_building_key_c2_units u
          ON u.decision = 'split' AND u.part > 0
         AND rtrim(u.base_key) = coalesce(rtrim(b.building_key), rtrim(t.building_key))
         AND t.asset_type = u.asset_type
         AND left(t.beopjungri_code, 10) = left(u.beopjungri_code, 10)
         AND {tx_lot} = {unit_lot}
        LEFT JOIN piece p
          ON p.old_key = rtrim(u.base_key)
         AND p.asset_type = u.asset_type
         AND p.split_part = u.part
        """
    )).one()
    changed_n = int(changed[2])
    expected_n = int(population[0])
    flags = _flags(
        expected_updated,
        part0_base_changed=int(changed[0]),
        non_base_changed=int(changed[1]),
        nonzero_key_differ=int(population[1]),
        changed_ne_file=0 if changed_n == expected_n else 1,
        changed_ne_given=0 if changed_n == expected_updated else 1,
    )
    return {"flags": flags, "changed_n": changed_n, "expected_n": expected_n}
