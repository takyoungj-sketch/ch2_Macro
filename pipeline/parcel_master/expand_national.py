"""표제부 「집합」 나머지 시도 + 용도지역 축약 적재.

대전·충북 building/parcel 은 지우지 않는다.
복합 「일반」 행·원본 48GB 적재·VPS 는 하지 않는다.

  cd pipeline
  python -m parcel_master.expand_national
  python -m parcel_master.expand_national --skip-zone
  python -m parcel_master.expand_national --skip-title --sido 30 43
"""

from __future__ import annotations

import argparse

from sqlalchemy import text

from parcel_master import apply_title_fill, load_title_pilot, load_zone, setup_db
from parcel_master.db_utils import get_parcel_engine
from parcel_master.paths import ALL_SIDO, EXPAND_SIDO


def _print_counts() -> None:
    engine = get_parcel_engine()
    with engine.connect() as conn:
        n_b = conn.execute(text("SELECT COUNT(*) FROM building")).scalar()
        n_p = conn.execute(text("SELECT COUNT(*) FROM parcel")).scalar()
        n_z = 0
        if _has_zone(conn):
            n_z = conn.execute(text("SELECT COUNT(*) FROM parcel_zone")).scalar()
        print(f"building={n_b:,} parcel={n_p:,} zone={n_z:,}", flush=True)
        rows = conn.execute(
            text(
                """
                SELECT sido_code, COUNT(*) AS n
                FROM parcel
                GROUP BY sido_code
                ORDER BY sido_code
                """
            )
        )
        for sido, n in rows:
            print(f"  parcel {sido} {n:,}", flush=True)


def _has_zone(conn) -> bool:
    n = conn.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'parcel_zone'")
    ).scalar()
    return bool(n)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--sido", nargs="+", default=list(EXPAND_SIDO))
    p.add_argument("--skip-title", action="store_true")
    p.add_argument("--skip-ledger", action="store_true")
    p.add_argument("--skip-zone", action="store_true")
    p.add_argument("--skip-fill", action="store_true")
    p.add_argument("--zone-sido", nargs="+", default=list(ALL_SIDO))
    args = p.parse_args()
    setup_db.main()
    sidos = tuple(args.sido)
    if not args.skip_title:
        print(f"title expand sidos={','.join(sidos)}", flush=True)
        load_title_pilot.run(sidos, args.refresh, skip_ledger=args.skip_ledger)
    if not args.skip_zone:
        print(f"zone sidos={','.join(args.zone_sido)}", flush=True)
        load_zone.run(tuple(args.zone_sido), args.refresh)
    if not args.skip_fill:
        apply_title_fill.run(dry_run=False)
    _print_counts()


if __name__ == "__main__":
    main()
