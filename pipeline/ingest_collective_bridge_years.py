#!/usr/bin/env python3
"""
2019·2020 bridge ingest — long term CSV → 건별 원장 (7년 롤링·거래목록용).

원본: raw/raw long term/{유형}_2010_2020/*_{2019,2020}.csv
대상: collective_transactions (주거 4유형), collective_commercial_transactions (집합상가·공장)

2010~2018은 annual mart(장기 추세)만 — 여기서는 넣지 않음.
docs/ROLLING_WINDOW_7Y_PLAN.md §2.4·§13
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))
sys.path.insert(0, str(REPO / "pipeline" / "collective"))

from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_LONG = REPO / "raw" / "raw long term"
BRIDGE_YEARS_DEFAULT = (2019, 2020)

RESIDENTIAL: list[tuple[str, str, str]] = [
    ("apartment", "아파트_2010_2020", "_아파트_매매_"),
    ("rowhouse", "연립다세대_2010_2020", "_연립다세대_매매_"),
    ("officetel", "오피스텔_2010_2020", "_오피스텔_매매_"),
    ("presale", "분양입주권_2010_2020", "_분양입주권_매매_"),
]

COMMERCIAL: list[tuple[str, str, str]] = [
    ("shop", "상업업무_2010_2020", "_상업업무_"),
    ("factory", "공장창고_2010_2020", "_공장창고_"),
]

RESIDENTIAL_ASSETS = ("apartment", "rowhouse", "officetel", "presale")
COMMERCIAL_ASSETS = ("collective_shop", "collective_factory")


def _load_import_refined():
    spec = importlib.util.spec_from_file_location(
        "collective_import_refined", REPO / "pipeline" / "collective" / "import_refined.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("collective/import_refined.py not found")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_bridge_csvs(folder_name: str, name_token: str, years: tuple[int, ...]) -> list[Path]:
    root = RAW_LONG / folder_name
    if not root.is_dir():
        log.warning("missing folder %s", root)
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*.csv")):
        if name_token not in path.name:
            continue
        for y in years:
            if f"_{y}.csv" in path.name or path.name.endswith(f"{y}.csv"):
                out.append(path)
                break
    return sorted(set(out))


def purge_residential_bridge(engine, years: tuple[int, ...]) -> int:
    ys = list(years)
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                DELETE FROM collective_transactions
                WHERE asset_type = ANY(:assets)
                  AND contract_year = ANY(:years)
                """
            ),
            {"assets": list(RESIDENTIAL_ASSETS), "years": ys},
        )
        return int(r.rowcount or 0)


def purge_commercial_bridge(engine, years: tuple[int, ...]) -> int:
    ys = list(years)
    with engine.begin() as conn:
        r = conn.execute(
            text(
                """
                DELETE FROM collective_commercial_transactions
                WHERE asset_type = ANY(:assets)
                  AND contract_year = ANY(:years)
                """
            ),
            {"assets": list(COMMERCIAL_ASSETS), "years": ys},
        )
        return int(r.rowcount or 0)


def ingest_residential(
    engine,
    years: tuple[int, ...],
    *,
    refresh_region_codes: bool,
) -> int:
    imp = _load_import_refined()
    from clean import build_region_lookup

    imp.ensure_schema(engine)
    imp.sync_region_codes_from_land(
        engine, get_land_engine_for_region_copy(), force=refresh_region_codes
    )
    region_maps = build_region_lookup(engine)

    total = 0
    for asset_type, folder_name, token in RESIDENTIAL:
        paths = find_bridge_csvs(folder_name, token, years)
        if not paths:
            log.warning("no bridge CSV for %s under %s", asset_type, folder_name)
            continue
        log.info("[%s] %d files", asset_type, len(paths))
        n = imp.ingest_paths(
            paths,
            asset_type,
            engine,
            region_maps,
            truncate_type=False,
        )
        total += n
    return total


def ingest_commercial(years: tuple[int, ...], *, refresh_region_codes: bool) -> int:
    shop_paths = find_bridge_csvs("상업업무_2010_2020", "_상업업무_", years)
    factory_paths = find_bridge_csvs("공장창고_2010_2020", "_공장창고_", years)
    if not shop_paths and not factory_paths:
        log.warning("no commercial bridge CSV found")
        return 0

    paths_file = REPO / "pipeline" / ".bridge_commercial_paths.tmp"
    lines = [str(p) for p in shop_paths + factory_paths]
    paths_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    cmd = [
        sys.executable,
        str(REPO / "pipeline" / "collective_commercial" / "import_refined.py"),
        "--paths-file",
        str(paths_file),
        "--skip-ddl",
    ]
    if refresh_region_codes:
        cmd.append("--refresh-region-codes")
    if shop_paths and not factory_paths:
        cmd.append("--shop-only")
    elif factory_paths and not shop_paths:
        cmd.append("--factory-only")

    log.info("commercial ingest: %d shop + %d factory files", len(shop_paths), len(factory_paths))
    subprocess.run(cmd, check=True, cwd=str(REPO / "pipeline"))

    try:
        paths_file.unlink(missing_ok=True)
    except OSError:
        pass
    return len(lines)


def rebuild_rolling(as_of: str, windows: str) -> None:
    for script in (
        "build_collective_building_rolling_stats.py",
        "build_collective_commercial_cluster_rolling_stats.py",
    ):
        cmd = [
            sys.executable,
            str(REPO / "pipeline" / script),
            "--as-of",
            as_of,
            "--windows",
            windows,
        ]
        log.info("rolling rebuild: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, cwd=str(REPO / "pipeline"))


def main() -> None:
    p = argparse.ArgumentParser(description="2019·2020 bridge → collective transactions")
    p.add_argument("--years", default="2019,2020", help="쉼표 구분 연도 (기본 2019,2020)")
    p.add_argument("--residential-only", action="store_true")
    p.add_argument("--commercial-only", action="store_true")
    p.add_argument("--skip-purge", action="store_true", help="기존 동일 연도 원장 삭제 생략")
    p.add_argument("--skip-rolling", action="store_true")
    p.add_argument("--as-of", default="2026-07-01", help="rolling mart as_of_month")
    p.add_argument("--windows", default="3,5,7")
    p.add_argument("--refresh-region-codes", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    years = tuple(sorted({int(x.strip()) for x in args.years.split(",") if x.strip()}))
    if not years:
        raise SystemExit("no years")

    do_res = not args.commercial_only
    do_comm = not args.residential_only

    log.info("bridge years=%s residential=%s commercial=%s", years, do_res, do_comm)

    if args.dry_run:
        for asset_type, folder_name, token in RESIDENTIAL:
            paths = find_bridge_csvs(folder_name, token, years)
            log.info("[dry-run] %s: %d files", asset_type, len(paths))
        for label, folder_name, token in [
            ("shop", "상업업무_2010_2020", "_상업업무_"),
            ("factory", "공장창고_2010_2020", "_공장창고_"),
        ]:
            paths = find_bridge_csvs(folder_name, token, years)
            log.info("[dry-run] %s: %d files", label, len(paths))
        return

    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())
    log.info("batch_id=%s", batch_id)

    if not args.skip_purge:
        if do_res:
            n = purge_residential_bridge(engine, years)
            log.info("purged residential bridge rows: %d", n)
        if do_comm:
            n = purge_commercial_bridge(engine, years)
            log.info("purged commercial bridge rows: %d", n)

    if do_res:
        n = ingest_residential(engine, years, refresh_region_codes=args.refresh_region_codes)
        log.info("residential bridge inserted: %d", n)

    if do_comm:
        n = ingest_commercial(years, refresh_region_codes=args.refresh_region_codes)
        log.info("commercial bridge files processed: %d", n)

    if not args.skip_rolling:
        rebuild_rolling(args.as_of, args.windows)

    log.info("bridge ingest complete")


if __name__ == "__main__":
    main()
