# -*- coding: utf-8 -*-
"""P0 — partial Built/Collective market mart rebuild under D-028 canonical.

Prereq: sync_region_code_history.py (history on built_stats + collective_stats).

Steps:
  1) DELETE stale region_code grains (historical sigungu/eup prefixes from 1a pairs)
  2) Rebuild sido 41 (+ optional 43) via existing builders (region_canonical only)
  3) Verify: stale rows ↓, canonical eup/sig rows ↑; ledger hist counts unchanged

Does NOT touch cluster/building_key marts. Does NOT UPDATE ledgers.

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/rebuild_built_collective_market_canonical_p0.py
  .venv/Scripts/python.exe ../pipeline/rebuild_built_collective_market_canonical_p0.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

CSV_1A = ROOT / "docs" / "reports" / "REGION_CODE_PHASE1A_CLASSIFICATION.csv"
OUT_MD = ROOT / "docs" / "reports" / "REGION_CODE_BUILT_COLLECTIVE_P0_VERIFY.md"
DEFAULT_AS_OF = date(2026, 6, 1)


def load_pairs() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    with CSV_1A.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("change_type") != "code_reissue":
                continue
            a = (r.get("historical_code") or "").strip()
            b = (r.get("canonical_code") or "").strip()
            if len(a) == 10 and len(b) == 10:
                pairs.append((a, b))
    return pairs


def stale_prefixes(pairs: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    stale_sig = sorted({a[:5] for a, b in pairs if a[:5] != b[:5]})
    stale_eup = sorted({a[:8] for a, b in pairs if a[:8] != b[:8]})
    return stale_sig, stale_eup


def canon_prefixes(pairs: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    canon_sig = sorted({b[:5] for a, b in pairs if a[:5] != b[:5]})
    canon_eup = sorted({b[:8] for a, b in pairs if a[:8] != b[:8]})
    return canon_sig, canon_eup


def _run(cmd: list[str], *, dry_run: bool) -> int:
    print("+", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def _count_stale(conn, table: str, stale_sig: list[str], stale_eup: list[str]) -> int:
    return int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {table}
                WHERE (
                    length(btrim(region_code::text)) >= 5
                    AND left(btrim(region_code::text), 5) = ANY(:sig)
                ) OR (
                    length(btrim(region_code::text)) >= 8
                    AND left(btrim(region_code::text), 8) = ANY(:eup)
                )
                """
            ),
            {"sig": stale_sig or ["__none__"], "eup": stale_eup or ["__none__"]},
        ).scalar()
        or 0
    )


def _count_canon(conn, table: str, canon_sig: list[str], canon_eup: list[str]) -> int:
    return int(
        conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {table}
                WHERE (
                    length(btrim(region_code::text)) >= 5
                    AND left(btrim(region_code::text), 5) = ANY(:sig)
                ) OR (
                    length(btrim(region_code::text)) >= 8
                    AND left(btrim(region_code::text), 8) = ANY(:eup)
                )
                """
            ),
            {"sig": canon_sig or ["__none__"], "eup": canon_eup or ["__none__"]},
        ).scalar()
        or 0
    )


def delete_stale(conn, table: str, stale_sig: list[str], stale_eup: list[str]) -> int:
    n = 0
    if stale_sig:
        n += int(
            conn.execute(
                text(
                    f"""
                    DELETE FROM {table}
                    WHERE length(btrim(region_code::text)) >= 5
                      AND left(btrim(region_code::text), 5) = ANY(:p)
                    """
                ),
                {"p": stale_sig},
            ).rowcount
            or 0
        )
    if stale_eup:
        n += int(
            conn.execute(
                text(
                    f"""
                    DELETE FROM {table}
                    WHERE length(btrim(region_code::text)) >= 8
                      AND left(btrim(region_code::text), 8) = ANY(:p)
                    """
                ),
                {"p": stale_eup},
            ).rowcount
            or 0
        )
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--as-of", default=DEFAULT_AS_OF.isoformat())
    ap.add_argument("--windows", default="3,5")
    ap.add_argument("--skip-delete", action="store_true")
    ap.add_argument("--skip-rebuild", action="store_true")
    ap.add_argument("--sidos", default="41,43", help="sido codes for built/commercial")
    args = ap.parse_args()

    pairs = load_pairs()
    stale_sig, stale_eup = stale_prefixes(pairs)
    canon_sig, canon_eup = canon_prefixes(pairs)
    print(
        f"pairs={len(pairs)} stale_sig={stale_sig} stale_eup_n={len(stale_eup)} "
        f"canon_sig={canon_sig}"
    )

    from built.db_utils import get_built_engine
    from collective.db_utils import get_collective_engine

    built = get_built_engine()
    coll = get_collective_engine()

    # before metrics
    before: dict = {}
    with built.connect() as conn:
        before["built_tx_hist"] = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM built_transactions
                    WHERE beopjungri_code = ANY(:c)
                    """
                ),
                {"c": [a for a, _ in pairs]},
            ).scalar()
            or 0
        )
        before["built_annual_stale"] = _count_stale(conn, "built_annual_stats", stale_sig, stale_eup)
        before["built_annual_canon"] = _count_canon(conn, "built_annual_stats", canon_sig, canon_eup)
    with coll.connect() as conn:
        before["coll_tx_hist"] = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM collective_transactions
                    WHERE beopjungri_code = ANY(:c)
                    """
                ),
                {"c": [a for a, _ in pairs]},
            ).scalar()
            or 0
        )
        before["market_stale"] = _count_stale(conn, "market_stats", stale_sig, stale_eup)
        before["market_canon"] = _count_canon(conn, "market_stats", canon_sig, canon_eup)
        before["market_annual_stale"] = _count_stale(
            conn, "market_annual_stats", stale_sig, stale_eup
        )
        before["cc_annual_stale"] = _count_stale(
            conn, "collective_commercial_region_annual_stats", stale_sig, stale_eup
        )

    deleted: dict = {}
    if not args.skip_delete and not args.dry_run:
        with coll.begin() as conn:
            deleted["market_stats"] = delete_stale(conn, "market_stats", stale_sig, stale_eup)
            deleted["market_annual_stats"] = delete_stale(
                conn, "market_annual_stats", stale_sig, stale_eup
            )
            deleted["collective_commercial_region_annual_stats"] = delete_stale(
                conn,
                "collective_commercial_region_annual_stats",
                stale_sig,
                stale_eup,
            )
        with built.begin() as conn:
            deleted["built_annual_stats"] = delete_stale(
                conn, "built_annual_stats", stale_sig, stale_eup
            )
        print("deleted", deleted)
    else:
        print("skip delete / dry-run")

    py = sys.executable
    pipe = ROOT / "pipeline"
    rc = 0
    if not args.skip_rebuild:
        sidos = [s.strip() for s in args.sidos.split(",") if s.strip()]
        # collective residential/office etc. — addr1 for 경기/충북
        addr_map = {"41": "경기도", "43": "충청북도"}
        for sc in sidos:
            addr1 = addr_map.get(sc)
            if addr1:
                rc = _run(
                    [
                        py,
                        str(pipe / "build_collective_market_stats.py"),
                        "--as-of",
                        args.as_of,
                        "--windows",
                        args.windows,
                        "--addr1",
                        addr1,
                    ],
                    dry_run=args.dry_run,
                ) or rc
            rc = _run(
                [
                    py,
                    str(pipe / "build_built_market_stats.py"),
                    "--as-of",
                    args.as_of,
                    "--windows",
                    args.windows,
                    "--sido-code",
                    sc,
                ],
                dry_run=args.dry_run,
            ) or rc
            rc = _run(
                [
                    py,
                    str(pipe / "build_collective_commercial_market_stats.py"),
                    "--as-of",
                    args.as_of,
                    "--windows",
                    args.windows,
                    "--sido-code",
                    sc,
                ],
                dry_run=args.dry_run,
            ) or rc

    if args.dry_run:
        return 0

    after: dict = {}
    with built.connect() as conn:
        after["built_tx_hist"] = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM built_transactions WHERE beopjungri_code = ANY(:c)"
                ),
                {"c": [a for a, _ in pairs]},
            ).scalar()
            or 0
        )
        after["built_annual_stale"] = _count_stale(conn, "built_annual_stats", stale_sig, stale_eup)
        after["built_annual_canon"] = _count_canon(conn, "built_annual_stats", canon_sig, canon_eup)
        after["history_n"] = int(
            conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0
        )
    with coll.connect() as conn:
        after["coll_tx_hist"] = int(
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM collective_transactions WHERE beopjungri_code = ANY(:c)"
                ),
                {"c": [a for a, _ in pairs]},
            ).scalar()
            or 0
        )
        after["market_stale"] = _count_stale(conn, "market_stats", stale_sig, stale_eup)
        after["market_canon"] = _count_canon(conn, "market_stats", canon_sig, canon_eup)
        after["market_annual_stale"] = _count_stale(
            conn, "market_annual_stats", stale_sig, stale_eup
        )
        after["market_annual_canon"] = _count_canon(
            conn, "market_annual_stats", canon_sig, canon_eup
        )
        after["cc_annual_stale"] = _count_stale(
            conn, "collective_commercial_region_annual_stats", stale_sig, stale_eup
        )
        after["cc_annual_canon"] = _count_canon(
            conn, "collective_commercial_region_annual_stats", canon_sig, canon_eup
        )
        after["history_n"] = int(
            conn.execute(text("SELECT COUNT(*) FROM region_code_history")).scalar() or 0
        )

    ok_ledger = (
        after["built_tx_hist"] == before["built_tx_hist"]
        and after["coll_tx_hist"] == before["coll_tx_hist"]
    )
    ok_grain = after["market_stale"] == 0 and after["built_annual_stale"] == 0
    lines = [
        "# Built·Collective P0 market canonical rebuild verify",
        "",
        f"- as_of={args.as_of} windows={args.windows} sidos={args.sidos}",
        f"- deleted: `{deleted}`",
        "",
        "## Before → After",
        "",
        f"- built_tx hist (immutable): {before['built_tx_hist']} → **{after['built_tx_hist']}**",
        f"- coll_tx hist (immutable): {before['coll_tx_hist']} → **{after['coll_tx_hist']}**",
        f"- market_stats stale→canon: {before['market_stale']}→**{after['market_stale']}** / "
        f"{before['market_canon']}→**{after['market_canon']}**",
        f"- market_annual stale: {before['market_annual_stale']}→**{after['market_annual_stale']}** "
        f"(canon {after.get('market_annual_canon')})",
        f"- built_annual stale→canon: {before['built_annual_stale']}→**{after['built_annual_stale']}** / "
        f"{before['built_annual_canon']}→**{after['built_annual_canon']}**",
        f"- commercial region annual stale→canon: {before['cc_annual_stale']}→**{after['cc_annual_stale']}** / "
        f"**{after.get('cc_annual_canon')}**",
        f"- history_n built/coll: {after.get('history_n')}",
        "",
        f"- ledger_immutable_ok: **{ok_ledger}**",
        f"- stale_grain_cleared_ok: **{ok_grain}**",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {OUT_MD}")
    return 0 if ok_ledger and (after["market_canon"] > 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
