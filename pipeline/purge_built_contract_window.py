"""
계약연월 구간 built_transactions — 월간 12개월 재적재.

기본: 이번 CSV에 없는 해시만 DELETE (해시 유지). 창 전체 DELETE 금지.
보강 FK는 069에서 제거. 사라진 해시의 보강은 고아로 남긴다. CASCADE 없음.

  py purge_built_contract_window.py --cycle-id 202607 --keep-hashes-file logs/built_cycle_202607_hashes.txt
  py purge_built_contract_window.py --from-yyyymm 202507 --to-yyyymm 202606 --dry-run --keep-hashes-file hashes.txt
  py purge_built_contract_window.py --cycle-id 202607 --delete-all   # 창에 enrichment 있으면 거절
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

_SCRIPT_DIR = Path(__file__).resolve().parent
_MONTHLY = _SCRIPT_DIR.parent / "scripts" / "monthly"
if str(_MONTHLY) not in sys.path:
    sys.path.insert(0, str(_MONTHLY))

from cycle_utils import collection_yyyymm_range_from_cycle_id  # noqa: E402

sys.path.insert(0, str(_SCRIPT_DIR / "built"))
from db_utils import get_built_engine  # noqa: E402

DDL_069 = _SCRIPT_DIR.parent / "db" / "069_built_enrichment_orphan.sql"

def _window_pred(alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    return (
        f"{p}contract_year IS NOT NULL AND {p}contract_month IS NOT NULL "
        f"AND ({p}contract_year * 100 + {p}contract_month) BETWEEN :lo AND :hi"
    )


def _ym_bounds(from_yyyymm: str, to_yyyymm: str) -> tuple[int, int]:
    fy, fm = int(from_yyyymm[:4]), int(from_yyyymm[4:6])
    ty, tm = int(to_yyyymm[:4]), int(to_yyyymm[4:6])
    lo = fy * 100 + fm
    hi = ty * 100 + tm
    if lo > hi:
        raise ValueError(f"from-yyyymm({from_yyyymm}) > to-yyyymm({to_yyyymm})")
    return lo, hi


def validate_keep_hashes(hashes: set[str]) -> None:
    if not hashes:
        raise ValueError("keep-hashes empty — refusing window DELETE")


def read_keep_hashes(path: Path) -> set[str]:
    text_body = path.read_text(encoding="utf-8")
    hashes = {line.strip() for line in text_body.splitlines() if line.strip()}
    validate_keep_hashes(hashes)
    return hashes


def apply_orphan_ddl(engine: Engine) -> None:
    if not DDL_069.is_file():
        return
    with engine.begin() as conn:
        for stmt in DDL_069.read_text(encoding="utf-8").split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def _window_count(conn: Connection, lo: int, hi: int) -> int:
    return int(
        conn.execute(
            text(f"SELECT COUNT(*) FROM built_transactions WHERE {_window_pred()}"),
            {"lo": lo, "hi": hi},
        ).scalar()
        or 0
    )


def _enrichment_in_window(conn: Connection, lo: int, hi: int) -> int:
    return int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM built_transaction_enrichment e
                JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
                WHERE {_window_pred("t")}
                """
            ),
            {"lo": lo, "hi": hi},
        ).scalar()
        or 0
    )


def _orphan_enrichment(conn: Connection) -> int:
    return int(
        conn.execute(
            text(
                """
                SELECT COUNT(*) FROM built_transaction_enrichment e
                WHERE NOT EXISTS (
                    SELECT 1 FROM built_transactions t
                    WHERE t.transaction_hash = e.transaction_hash
                )
                """
            )
        ).scalar()
        or 0
    )


def _load_keep_temp(conn: Connection, hashes: set[str]) -> int:
    conn.execute(text("CREATE TEMP TABLE _keep_hashes (transaction_hash CHAR(64) PRIMARY KEY)"))
    rows = [{"h": h} for h in hashes]
    stmt = text("INSERT INTO _keep_hashes (transaction_hash) VALUES (:h) ON CONFLICT DO NOTHING")
    for i in range(0, len(rows), 5000):
        conn.execute(stmt, rows[i : i + 5000])
    return len(hashes)


def purge_stale_in_window(
    from_yyyymm: str,
    to_yyyymm: str,
    keep_hashes: set[str],
    *,
    dry_run: bool = False,
    engine: Engine | None = None,
) -> dict[str, int]:
    validate_keep_hashes(keep_hashes)
    lo, hi = _ym_bounds(from_yyyymm, to_yyyymm)
    eng = engine or get_built_engine()
    apply_orphan_ddl(eng)
    with eng.connect() as conn:
        window = _window_count(conn, lo, hi)
        n_enr = _enrichment_in_window(conn, lo, hi)
    print(
        f"stale purge {from_yyyymm}~{to_yyyymm}: window={window:,} keep={len(keep_hashes):,} "
        f"enrichment_in_window={n_enr:,}"
    )
    if dry_run:
        with eng.begin() as conn:
            _load_keep_temp(conn, keep_hashes)
            stale = int(
                conn.execute(
                    text(
                        f"""
                        SELECT COUNT(*) FROM built_transactions t
                        WHERE {_window_pred("t")}
                          AND NOT EXISTS (
                              SELECT 1 FROM _keep_hashes k
                              WHERE k.transaction_hash = t.transaction_hash
                          )
                        """
                    ),
                    {"lo": lo, "hi": hi},
                ).scalar()
                or 0
            )
        print(f"dry-run stale would delete: {stale:,}")
        return {"window": window, "keep": len(keep_hashes), "stale": stale, "deleted": 0, "orphans": 0}

    with eng.begin() as conn:
        _load_keep_temp(conn, keep_hashes)
        res = conn.execute(
            text(
                f"""
                DELETE FROM built_transactions t
                WHERE {_window_pred("t")}
                  AND NOT EXISTS (
                      SELECT 1 FROM _keep_hashes k
                      WHERE k.transaction_hash = t.transaction_hash
                  )
                """
            ),
            {"lo": lo, "hi": hi},
        )
        deleted = int(res.rowcount or 0)
        orphans = _orphan_enrichment(conn)
    print(f"deleted stale: {deleted:,} orphan_enrichment={orphans:,}")
    return {
        "window": window,
        "keep": len(keep_hashes),
        "stale": deleted,
        "deleted": deleted,
        "orphans": orphans,
    }


def purge_built_contract_window(
    from_yyyymm: str,
    to_yyyymm: str,
    *,
    dry_run: bool = False,
    keep_hashes_file: Path | None = None,
    delete_all: bool = False,
) -> dict[str, int] | int:
    lo, hi = _ym_bounds(from_yyyymm, to_yyyymm)
    engine = get_built_engine()

    if keep_hashes_file is not None:
        hashes = read_keep_hashes(keep_hashes_file)
        return purge_stale_in_window(
            from_yyyymm, to_yyyymm, hashes, dry_run=dry_run, engine=engine
        )

    if not delete_all:
        raise SystemExit(
            "창 전체 DELETE는 기본 금지. --keep-hashes-file (ingest 후 stale) "
            "또는 enrichment 없는 창에만 --delete-all"
        )

    apply_orphan_ddl(engine)
    with engine.connect() as conn:
        n = _window_count(conn, lo, hi)
        n_enr = _enrichment_in_window(conn, lo, hi)
    print(f"purge target built contract {from_yyyymm}~{to_yyyymm}: {n} rows enrichment={n_enr}")
    if n_enr:
        raise SystemExit(
            f"window has {n_enr} enrichment rows — --delete-all 거절 (CASCADE 금지, 동결 유지)"
        )
    if dry_run:
        return n
    with engine.begin() as conn:
        res = conn.execute(
            text(f"DELETE FROM built_transactions WHERE {_window_pred()}"),
            {"lo": lo, "hi": hi},
        )
        deleted = int(res.rowcount or 0)
    print(f"deleted: {deleted}")
    return deleted


def main() -> None:
    p = argparse.ArgumentParser(description="built_transactions 계약연월 구간 purge (해시 유지)")
    p.add_argument("--cycle-id", help="YYYYMM (예: 202607)")
    p.add_argument("--from-yyyymm")
    p.add_argument("--to-yyyymm")
    p.add_argument("--keep-hashes-file", type=Path)
    p.add_argument(
        "--delete-all",
        action="store_true",
        help="창 전체 DELETE. enrichment가 있으면 거절",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.cycle_id:
        y_from, y_to = collection_yyyymm_range_from_cycle_id(args.cycle_id.strip())
    elif args.from_yyyymm and args.to_yyyymm:
        y_from, y_to = args.from_yyyymm, args.to_yyyymm
    else:
        raise SystemExit("--cycle-id 또는 --from-yyyymm/--to-yyyymm 필요")

    purge_built_contract_window(
        y_from,
        y_to,
        dry_run=args.dry_run,
        keep_hashes_file=args.keep_hashes_file,
        delete_all=args.delete_all,
    )


if __name__ == "__main__":
    main()
