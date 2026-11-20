"""임대 C-2 영향표. 읽기만 하고, 지역 이름과 전환율 전후만 적는다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ALARM_PP = 0.5


def _key(row: dict) -> tuple:
    return (
        row.get("window_years"),
        row.get("addr1") or "",
        row.get("addr2") or "",
        row.get("addr3") or "",
        row.get("asset_type") or "",
    )


def _region(row: dict) -> str:
    parts = [row.get("addr1") or "", row.get("addr2") or "", row.get("addr3") or ""]
    return " ".join(p for p in parts if p)


def rate_alarms(before: list[dict], after: list[dict]) -> list[dict]:
    left = {_key(r): r for r in before}
    right = {_key(r): r for r in after}
    alarms = []
    for key in sorted(set(left) | set(right)):
        b = left.get(key, {})
        a = right.get(key, {})
        bv, av = b.get("r_selected"), a.get("r_selected")
        if bv is None or av is None:
            continue
        delta = float(av) - float(bv)
        if abs(delta) < ALARM_PP:
            continue
        sample = a or b
        alarms.append({
            "region": _region(sample),
            "asset_type": sample.get("asset_type") or "",
            "window_years": sample.get("window_years"),
            "before": float(bv),
            "after": float(av),
            "delta_pp": round(delta, 4),
        })
    return alarms


def _gate_state(value) -> str:
    if value is None:
        return "null"
    return "true" if bool(value) else "false"


def availability_changes(before: list[dict], after: list[dict]) -> list[dict]:
    """한쪽에만 있는 지역, r_selected 의 NULL 변화, gate_passed 의 null/참/거짓 변화."""
    left = {_key(r): r for r in before}
    right = {_key(r): r for r in after}
    changes = []
    for key in sorted(set(left) | set(right), key=lambda item: tuple(str(part) for part in item)):
        b = left.get(key)
        a = right.get(key)
        reasons = []
        if b is None or a is None:
            reasons.append("한쪽")
        else:
            if (b.get("r_selected") is None) != (a.get("r_selected") is None):
                reasons.append("r_selected")
            if _gate_state(b.get("gate_passed")) != _gate_state(a.get("gate_passed")):
                reasons.append("gate_passed")
        if not reasons:
            continue
        sample = a or b
        changes.append({
            "region": _region(sample),
            "asset_type": sample.get("asset_type") or "",
            "window_years": sample.get("window_years"),
            "before": _availability(b),
            "after": _availability(a),
            "reason": ",".join(reasons),
        })
    return changes


def _availability(row: dict | None) -> dict | None:
    if row is None:
        return None
    value = row.get("r_selected")
    return {
        "r_selected": None if value is None else float(value),
        "gate_passed": _gate_state(row.get("gate_passed")),
    }


def gate_flips(before: list[dict], after: list[dict]) -> list[dict]:
    left = {_key(r): bool(r.get("gate_passed")) for r in before}
    right = {_key(r): bool(r.get("gate_passed")) for r in after}
    flips = []
    for key in sorted(set(left) | set(right)):
        b = left.get(key, False)
        a = right.get(key, False)
        if b == a:
            continue
        sample = next(r for r in list(after) + list(before) if _key(r) == key)
        flips.append({
            "region": _region(sample),
            "asset_type": sample.get("asset_type") or "",
            "window_years": sample.get("window_years"),
            "before": b,
            "after": a,
        })
    return flips


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _engine(base_url: str, dbname: str):
    if dbname != "rent_stats_rc2r":
        raise SystemExit("영향표는 rent_stats_rc2r 만 읽는다")
    url = make_url(base_url).set(database=dbname)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    ops = str(Path(__file__).resolve().parents[2] / "scripts" / "ops" / "collective_p2_verify")
    if ops not in sys.path:
        sys.path.insert(0, ops)
    from ops_guards import assert_local_target

    assert_local_target(url)
    opts = "-c statement_timeout=0 -c default_transaction_read_only=on"
    return create_engine(url, pool_pre_ping=True, connect_args={"options": opts})


def snapshot(conn) -> dict:
    name = str(conn.execute(text("SELECT current_database()")).scalar() or "")
    if name != "rent_stats_rc2r":
        raise SystemExit("영향표는 rent_stats_rc2r 만 읽는다")
    as_of = conn.execute(text("SELECT max(as_of_month) FROM rent_conversion_rates")).scalar()
    rates = []
    if as_of is not None:
        rows = conn.execute(text(
            """
            SELECT window_years, addr1, addr2, addr3, asset_type,
                   r_selected, gate_passed, n_buildings, n_jeonse, n_mixed
            FROM rent_conversion_rates
            WHERE as_of_month = :as_of
            """
        ), {"as_of": as_of}).mappings().all()
        for row in rows:
            rates.append({
                "window_years": int(row["window_years"]),
                "addr1": row["addr1"] or "",
                "addr2": row["addr2"] or "",
                "addr3": row["addr3"] or "",
                "asset_type": row["asset_type"] or "",
                "r_selected": None if row["r_selected"] is None else float(row["r_selected"]),
                "gate_passed": None if row["gate_passed"] is None else bool(row["gate_passed"]),
                "n_buildings": int(row["n_buildings"] or 0),
                "n_jeonse": int(row["n_jeonse"] or 0),
                "n_mixed": int(row["n_mixed"] or 0),
            })
    buildings = conn.execute(text(
        """
        SELECT asset_type,
               count(*) FILTER (WHERE jeonse_n >= 15)::int AS basic_ok,
               count(*)::int AS buildings
        FROM rent_building_stats
        WHERE as_of_month = (SELECT max(as_of_month) FROM rent_building_stats)
        GROUP BY asset_type
        ORDER BY asset_type
        """
    )).mappings().all()
    conversion_ok = conn.execute(text(
        """
        SELECT asset_type, count(*)::int AS n
        FROM rent_conversion_rates
        WHERE as_of_month = (SELECT max(as_of_month) FROM rent_conversion_rates)
          AND gate_passed
        GROUP BY asset_type
        ORDER BY asset_type
        """
    )).mappings().all()
    links = {"exact": 0, "held_rent_only_groups": 0}
    if conn.execute(text("SELECT to_regclass('public.rent_sale_building_map')")).scalar():
        links["exact"] = int(conn.execute(text(
            "SELECT count(*) FROM rent_sale_building_map WHERE tier = 'exact'"
        )).scalar() or 0)
    if conn.execute(text("SELECT to_regclass('public.rent_building_key_c2_units')")).scalar():
        links["held_rent_only_groups"] = int(conn.execute(text(
            """
            SELECT count(DISTINCT base_key)
            FROM rent_building_key_c2_units
            WHERE decision = 'split' AND evidence = 'title_register' AND part = 0
            """
        )).scalar() or 0)
    pending = _pending_diff(conn)
    return {
        "as_of": None if as_of is None else str(as_of),
        "region_count": len(rates),
        "rates": rates,
        "basic_buildings": [dict(row) for row in buildings],
        "conversion_gate_passed": [dict(row) for row in conversion_ok],
        "links": links,
        "pending": pending,
    }


def _pending_diff(conn) -> dict:
    if not conn.execute(text("SELECT to_regclass('public.rent_building_key_c2_units')")).scalar():
        return {"buildings": 0, "included_tx": 0, "excluded_tx": 0, "included_deposit_mean": None, "excluded_deposit_mean": None}
    row = conn.execute(text(
        """
        WITH pending AS (
            SELECT DISTINCT base_key, asset_type, beopjungri_code, main_lot
            FROM rent_building_key_c2_units
            WHERE decision = 'pending'
        ),
        marked AS (
            SELECT t.deposit_manwon,
                   (p.base_key IS NOT NULL) AS is_pending
            FROM rent_transactions t
            JOIN (
                SELECT DISTINCT base_key FROM pending
            ) b ON rtrim(t.building_key) = b.base_key
            LEFT JOIN pending p
              ON rtrim(t.building_key) = p.base_key
             AND t.asset_type = p.asset_type
             AND left(t.beopjungri_code, 10) = left(p.beopjungri_code, 10)
             AND CASE WHEN split_part(btrim(t.lot_number), '-', 1) ~ '^[0-9]+$'
                      THEN coalesce(nullif(ltrim(split_part(btrim(t.lot_number), '-', 1), '0'), ''), '0')
                      ELSE btrim(split_part(btrim(t.lot_number), '-', 1)) END = p.main_lot
            WHERE t.is_valid
        )
        SELECT count(DISTINCT CASE WHEN is_pending THEN 1 END)::int AS dummy,
               count(*) FILTER (WHERE is_pending)::int AS included_tx,
               count(*) FILTER (WHERE NOT is_pending)::int AS other_tx,
               avg(deposit_manwon) FILTER (WHERE is_pending) AS included_mean,
               avg(deposit_manwon) FILTER (WHERE NOT is_pending) AS excluded_mean,
               (SELECT count(DISTINCT base_key)::int FROM pending) AS buildings
        FROM marked
        """
    )).mappings().one()
    def _num(value):
        return None if value is None else float(value)
    return {
        "buildings": int(row["buildings"] or 0),
        "included_tx": int(row["included_tx"] or 0),
        "excluded_tx": int(row["other_tx"] or 0),
        "included_deposit_mean": _num(row["included_mean"]),
        "excluded_deposit_mean": _num(row["excluded_mean"]),
    }


def compare(before: dict, after: dict) -> dict:
    alarms = rate_alarms(before.get("rates") or [], after.get("rates") or [])
    flips = gate_flips(before.get("rates") or [], after.get("rates") or [])
    return {
        "region_count_before": before.get("region_count"),
        "region_count_after": after.get("region_count"),
        "alarms": alarms,
        "gate_flips": flips,
        "availability_changes": availability_changes(before.get("rates") or [], after.get("rates") or []),
        "basic_buildings_before": before.get("basic_buildings"),
        "basic_buildings_after": after.get("basic_buildings"),
        "conversion_gate_passed_before": before.get("conversion_gate_passed"),
        "conversion_gate_passed_after": after.get("conversion_gate_passed"),
        "links_before": before.get("links"),
        "links_after": after.get("links"),
        "pending_before": before.get("pending"),
        "pending_after": after.get("pending"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="임대 C-2 영향표")
    parser.add_argument("--rent-db", default="rent_stats_rc2r")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--snapshot", type=Path, default=None)
    parser.add_argument("--before", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    from pipeline.collective.migrate_p2_keys import server_url_from_env

    engine = _engine(args.base_url or server_url_from_env(), args.rent_db)
    try:
        with engine.connect() as conn:
            current = snapshot(conn)
    finally:
        engine.dispose()
    if args.snapshot:
        write_report(args.snapshot, current)
    if args.before:
        before = json.loads(args.before.read_text(encoding="utf-8"))
        report = compare(before, current)
        write_report(args.out or Path("logs/rent_c2/rent_c2_impact.json"), report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
