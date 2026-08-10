#!/usr/bin/env python3
"""
2019·2020 bridge ingest — long term MOLIT CSV → built_transactions.

원본: raw/raw long term/{상업업무|공장창고|단독다가구}_2010_2020/*_{2019,2020}.csv
docs/ROLLING_WINDOW_7Y_PLAN.md §2.4 (복합)
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

from built.db_utils import get_built_engine, get_land_engine_for_region_copy  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RAW_LONG = REPO / "raw" / "raw long term"
BRIDGE_YEARS_DEFAULT = (2019, 2020)

BUILT_ASSETS: list[tuple[str, str, str]] = [
    ("commercial", "상업업무_2010_2020", "_상업업무_"),
    ("factory", "공장창고_2010_2020", "_공장창고_"),
    ("detached", "단독다가구_2010_2020", "_단독다가구_"),
]


def _load_import_molit():
    spec = importlib.util.spec_from_file_location(
        "built_import_molit", REPO / "pipeline" / "built" / "import_molit.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("built/import_molit.py not found")
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


def purge_bridge(
    engine, years: tuple[int, ...], *, asset_types: tuple[str, ...] | None = None
) -> int:
    if asset_types:
        sql = """
            DELETE FROM built_transactions
            WHERE contract_year = ANY(:years)
              AND asset_type = ANY(:asset_types)
        """
        params: dict = {"years": list(years), "asset_types": list(asset_types)}
    else:
        sql = """
            DELETE FROM built_transactions
            WHERE contract_year = ANY(:years)
        """
        params = {"years": list(years)}
    with engine.begin() as conn:
        r = conn.execute(text(sql), params)
        return int(r.rowcount or 0)


def ingest_built(
    engine,
    years: tuple[int, ...],
    *,
    refresh_region_codes: bool,
    asset_filter: set[str] | None = None,
) -> dict[str, int]:
    imp = _load_import_molit()
    from clean import build_region_lookup
    from region_mapping import log_mapping_coverage

    imp.ensure_schema(engine)
    land = get_land_engine_for_region_copy()
    if refresh_region_codes:
        imp.sync_region_codes_from_land(engine, land, force=True)
    else:
        imp.copy_region_codes_if_empty(engine, land)
    region_maps = build_region_lookup(engine)

    totals: dict[str, int] = {}
    for asset_type, folder_name, token in BUILT_ASSETS:
        if asset_filter is not None and asset_type not in asset_filter:
            continue
        paths = find_bridge_csvs(folder_name, token, years)
        if not paths:
            log.warning("no bridge CSV for %s (%s)", asset_type, folder_name)
            totals[asset_type] = 0
            continue
        log.info("[%s] %d files", asset_type, len(paths))
        stats = imp.ingest_paths(paths, asset_type, engine, region_maps)  # type: ignore[arg-type]
        attempted = int(stats.get("insert_attempted") or 0)
        totals[asset_type] = attempted
        log_mapping_coverage(engine, "built_transactions", asset_type=asset_type)
        log.info("%s bridge: %s", asset_type, stats)
    return totals


def rebuild_scope_stats(as_of: str, windows: str) -> None:
    cmd = [
        sys.executable,
        str(REPO / "pipeline" / "built" / "build_scope_stats.py"),
        "--as-of",
        as_of,
        "--windows",
        windows,
    ]
    log.info("scope stats rebuild: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(REPO / "pipeline"))


def main() -> None:
    p = argparse.ArgumentParser(description="2019·2020 bridge → built_transactions")
    p.add_argument("--years", default="2019,2020")
    p.add_argument("--skip-purge", action="store_true")
    p.add_argument("--skip-scope-stats", action="store_true")
    p.add_argument("--as-of", default="2026-07-01")
    p.add_argument("--windows", default="3,5,7")
    p.add_argument("--refresh-region-codes", action="store_true")
    p.add_argument("--commercial-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    p.add_argument("--detached-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    only_flags = sum([args.commercial_only, args.factory_only, args.detached_only])
    if only_flags > 1:
        raise SystemExit("use at most one of --commercial-only / --factory-only / --detached-only")
    asset_filter: set[str] | None = None
    if args.commercial_only:
        asset_filter = {"commercial"}
    elif args.factory_only:
        asset_filter = {"factory"}
    elif args.detached_only:
        asset_filter = {"detached"}

    years = tuple(sorted({int(x.strip()) for x in args.years.split(",") if x.strip()}))
    if not years:
        raise SystemExit("no years")

    if args.dry_run:
        for asset_type, folder_name, token in BUILT_ASSETS:
            if asset_filter is not None and asset_type not in asset_filter:
                continue
            paths = find_bridge_csvs(folder_name, token, years)
            log.info("[dry-run] %s: %d files under %s", asset_type, len(paths), folder_name)
        return

    engine = get_built_engine()
    log.info("batch_id=%s years=%s", uuid.uuid4(), years)

    if not args.skip_purge:
        n = purge_bridge(engine, years, asset_types=tuple(asset_filter) if asset_filter else None)
        log.info("purged built bridge rows: %d", n)

    totals = ingest_built(
        engine,
        years,
        refresh_region_codes=args.refresh_region_codes,
        asset_filter=asset_filter,
    )
    log.info("built bridge inserted (attempted): %s", totals)

    if not args.skip_scope_stats:
        rebuild_scope_stats(args.as_of, args.windows)

    log.info("built bridge ingest complete")


if __name__ == "__main__":
    main()
