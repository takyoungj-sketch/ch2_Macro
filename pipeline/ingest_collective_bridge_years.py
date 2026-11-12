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

from admin_names import LEGACY_SIDO_TO_CURRENT, canonical_sido_name  # noqa: E402
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


def sido_addr1_names_from_paths(paths: list[Path]) -> list[str]:
    """적재할 원천 파일의 시도(파일명 첫 토큰) → 지울 addr1 이름들(개편 후 이름 + 같은 이름으로 모이는 옛 이름).

    2026-08 사고(D-084 C-02): 시도 조건 없이 연도만으로 지워, 개편 재적재로 넣은 새 이름 행을 옛 이름 파일로 덮었다.
    """
    cur = {canonical_sido_name(p.name.split("_", 1)[0]) for p in paths}
    names = set(cur)
    for old, new in LEGACY_SIDO_TO_CURRENT.items():
        if new in cur:
            names.add(old)
    return sorted(n for n in names if isinstance(n, str) and n)


def _purge(engine, table: str, assets: tuple[str, ...], years: tuple[int, ...], addr1_names: list[str], *, apply: bool) -> int:
    if not addr1_names:
        raise SystemExit(f"{table}: 시도 조건이 비어 purge 거부(원천 파일 없음?)")
    params = {"assets": list(assets), "years": list(years), "names": addr1_names}
    where = "asset_type = ANY(:assets) AND contract_year = ANY(:years) AND addr1 = ANY(:names)"
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT addr1, contract_year, asset_type, count(*) FROM {table} WHERE {where} "
                                 "GROUP BY 1,2,3 ORDER BY 1,2,3"), params).all()
    total = sum(int(r[3]) for r in rows)
    for r in rows:
        log.info("[purge %s] %s %s %s: %d", "실행" if apply else "드라이런", r[0], r[1], r[2], int(r[3]))
    log.info("[purge %s] %s 합계 %d행", "실행" if apply else "드라이런", table, total)
    if not apply:
        return total
    with engine.begin() as conn:
        r = conn.execute(text(f"DELETE FROM {table} WHERE {where}"), params)
        return int(r.rowcount or 0)


def purge_residential_bridge(engine, years: tuple[int, ...], addr1_names: list[str], *, apply: bool = False) -> int:
    return _purge(engine, "collective_transactions", RESIDENTIAL_ASSETS, years, addr1_names, apply=apply)


def purge_commercial_bridge(engine, years: tuple[int, ...], addr1_names: list[str], *, apply: bool = False) -> int:
    return _purge(engine, "collective_commercial_transactions", COMMERCIAL_ASSETS, years, addr1_names, apply=apply)


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
    p.add_argument("--dry-run", action="store_true", help="(기본 동작) 지울·넣을 건수만 출력")
    p.add_argument("--apply", action="store_true", help="실제 purge·적재. 없으면 드라이런")
    args = p.parse_args()

    years = tuple(sorted({int(x.strip()) for x in args.years.split(",") if x.strip()}))
    if not years:
        raise SystemExit("no years")

    do_res = not args.commercial_only
    do_comm = not args.residential_only

    log.info("bridge years=%s residential=%s commercial=%s", years, do_res, do_comm)

    res_paths = [p for _a, f, t in RESIDENTIAL for p in find_bridge_csvs(f, t, years)]
    com_paths = [p for _a, f, t in COMMERCIAL for p in find_bridge_csvs(f, t, years)]
    res_names = sido_addr1_names_from_paths(res_paths)
    com_names = sido_addr1_names_from_paths(com_paths)
    for asset_type, folder_name, token in RESIDENTIAL + COMMERCIAL:
        log.info("[plan] %s: %d files", asset_type, len(find_bridge_csvs(folder_name, token, years)))
    log.info("[plan] purge 시도(주거): %s", res_names)
    log.info("[plan] purge 시도(비주거): %s", com_names)
    engine = get_collective_engine()
    apply = bool(args.apply) and not args.dry_run
    if not apply:
        if not args.skip_purge:
            if do_res:
                purge_residential_bridge(engine, years, res_names, apply=False)
            if do_comm:
                purge_commercial_bridge(engine, years, com_names, apply=False)
        log.info("드라이런 — 쓰지 않았다. 확인 후 --apply 로 실행.")
        return

    batch_id = str(uuid.uuid4())
    log.info("batch_id=%s", batch_id)

    if not args.skip_purge:
        if do_res:
            n = purge_residential_bridge(engine, years, res_names, apply=True)
            log.info("purged residential bridge rows: %d", n)
        if do_comm:
            n = purge_commercial_bridge(engine, years, com_names, apply=True)
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
