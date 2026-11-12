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

from admin_names import LEGACY_SIDO_TO_CURRENT, canonical_sido_name  # noqa: E402
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


def sido_addr1_names_from_paths(paths: list[Path]) -> list[str]:
    """원천 파일 시도(파일명 첫 토큰) → 지울 addr1 이름(개편 후 + 옛 이름). D-084 C-02 재발 방지."""
    cur = {canonical_sido_name(p.name.split("_", 1)[0]) for p in paths}
    names = set(cur)
    for old, new in LEGACY_SIDO_TO_CURRENT.items():
        if new in cur:
            names.add(old)
    return sorted(n for n in names if isinstance(n, str) and n)


def purge_bridge(
    engine,
    years: tuple[int, ...],
    *,
    addr1_names: list[str],
    asset_types: tuple[str, ...] | None = None,
    apply: bool = False,
) -> int:
    """계약연도 + 시도(addr1) 조건 purge. apply=False 면 건수만 출력."""
    if not addr1_names:
        raise SystemExit("built purge: 시도 조건이 비어 거부(원천 파일 없음?)")
    where = "contract_year = ANY(:years) AND addr1 = ANY(:names)"
    params: dict = {"years": list(years), "names": addr1_names}
    if asset_types:
        where += " AND asset_type = ANY(:asset_types)"
        params["asset_types"] = list(asset_types)
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT addr1, contract_year, asset_type, count(*) FROM built_transactions "
                                 f"WHERE {where} GROUP BY 1,2,3 ORDER BY 1,2,3"), params).all()
    for r in rows:
        log.info("[purge %s] %s %s %s: %d", "실행" if apply else "드라이런", r[0], r[1], r[2], int(r[3]))
    total = sum(int(r[3]) for r in rows)
    log.info("[purge %s] built_transactions 합계 %d행", "실행" if apply else "드라이런", total)
    if not apply:
        return total
    with engine.begin() as conn:
        r = conn.execute(text(f"DELETE FROM built_transactions WHERE {where}"), params)
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
    p.add_argument("--dry-run", action="store_true", help="(기본 동작) 건수만 출력")
    p.add_argument("--apply", action="store_true", help="실제 purge·적재. 없으면 드라이런")
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

    all_paths = []
    for asset_type, folder_name, token in BUILT_ASSETS:
        if asset_filter is not None and asset_type not in asset_filter:
            continue
        paths = find_bridge_csvs(folder_name, token, years)
        all_paths += paths
        log.info("[plan] %s: %d files under %s", asset_type, len(paths), folder_name)
    names = sido_addr1_names_from_paths(all_paths)
    log.info("[plan] purge 시도: %s", names)
    engine = get_built_engine()
    apply = bool(args.apply) and not args.dry_run
    if not apply:
        if not args.skip_purge:
            purge_bridge(engine, years, addr1_names=names,
                         asset_types=tuple(asset_filter) if asset_filter else None, apply=False)
        log.info("드라이런 — 쓰지 않았다. 확인 후 --apply 로 실행.")
        return
    log.info("batch_id=%s years=%s", uuid.uuid4(), years)

    if not args.skip_purge:
        n = purge_bridge(engine, years, addr1_names=names,
                         asset_types=tuple(asset_filter) if asset_filter else None, apply=True)
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
