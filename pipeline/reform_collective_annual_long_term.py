"""행정개편 영향 시도 — 집합 장기추세(annual) mart purge·재빌드."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from collective.db_utils import get_collective_engine

ROOT = Path(__file__).resolve().parent
PY = sys.executable

AFFECTED_SIDO = ("12", "28", "29", "46")
REFORM_ADDR1 = ("인천광역시", "전남광주통합특별시")
LEGACY_ADDR1 = ("광주광역시", "전라남도")
ALL_ADDR1 = REFORM_ADDR1 + LEGACY_ADDR1


def purge_annual_marts() -> None:
    engine = get_collective_engine()
    with engine.begin() as conn:
        n_b = conn.execute(
            text(
                """
                DELETE FROM collective_building_annual_stats
                WHERE addr1 = ANY(:addr1)
                   OR btrim(beopjungri_code::text) LIKE ANY(:sido_pat)
                """
            ),
            {
                "addr1": list(ALL_ADDR1),
                "sido_pat": [f"{s}%" for s in AFFECTED_SIDO],
            },
        ).rowcount
        print(f"  collective_building_annual_stats deleted {n_b or 0}")

        n_m = conn.execute(
            text(
                """
                DELETE FROM market_annual_stats
                WHERE btrim(region_code::text) LIKE ANY(:sido_pat)
                """
            ),
            {"sido_pat": [f"{s}%" for s in AFFECTED_SIDO]},
        ).rowcount
        print(f"  market_annual_stats deleted {n_m or 0}")

        n_c = conn.execute(
            text(
                """
                DELETE FROM collective_commercial_cluster_annual_stats
                WHERE addr1 = ANY(:addr1)
                   OR EXISTS (
                       SELECT 1 FROM collective_commercial_transactions t
                       WHERE t.cluster_key = collective_commercial_cluster_annual_stats.cluster_key
                         AND btrim(t.sido_code::text) = ANY(:sido)
                   )
                """
            ),
            {"addr1": list(ALL_ADDR1), "sido": list(AFFECTED_SIDO)},
        ).rowcount
        print(f"  collective_commercial_cluster_annual_stats deleted {n_c or 0}")


def rebuild_annual_for_addr1(addr1: str) -> None:
    subprocess.run(
        [PY, str(ROOT / "build_collective_building_stats.py"), "--annual-only", "--addr1", addr1],
        check=True,
        cwd=str(ROOT),
    )
    subprocess.run(
        [PY, str(ROOT / "build_collective_market_stats.py"), "--annual-only", "--addr1", addr1],
        check=True,
        cwd=str(ROOT),
    )
    subprocess.run(
        [
            PY,
            str(ROOT / "build_collective_commercial_cluster_stats.py"),
            "--annual-only",
            "--addr1",
            addr1,
        ],
        check=True,
        cwd=str(ROOT),
    )


def verify_sample() -> None:
    engine = get_collective_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT MIN(contract_year) AS y_min, MAX(contract_year) AS y_max, COUNT(*) AS n
                FROM collective_building_annual_stats
                WHERE addr1 = '인천광역시' AND addr2 LIKE '%검단%'
                """
            )
        ).mappings().first()
        print("  geomdan annual years:", dict(row) if row else None)
        legacy = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM collective_building_annual_stats
                WHERE addr1 = ANY(:legacy)
                """
            ),
            {"legacy": list(LEGACY_ADDR1)},
        ).scalar()
        print("  legacy addr1 annual rows (expect 0):", legacy)


def main() -> None:
    parser = argparse.ArgumentParser(description="집합 장기추세 annual purge·재빌드 (12·28)")
    parser.add_argument("--purge-only", action="store_true")
    parser.add_argument("--skip-rebuild", action="store_true")
    args = parser.parse_args()

    print("=== purge collective annual marts (12,28,29,46) ===")
    purge_annual_marts()
    if args.purge_only:
        return

    if not args.skip_rebuild:
        print("=== rebuild annual (인천·전남광주) ===")
        for addr1 in REFORM_ADDR1:
            print(f"--- {addr1} ---")
            rebuild_annual_for_addr1(addr1)

    print("=== verify ===")
    verify_sample()


if __name__ == "__main__":
    main()
