"""AL_D151 → parcel_master.parcel_land_price. 수요 필지(parcel PNU)만.

광주·전남 폴더 29/46 의 PNU 앞 10자리는 region_codes 로 통합 12 에 맵핑한다.
연도 이력을 모두 보관한다. 제품 최신 1개 파생은 집합 마트 쪽(P3).

  cd pipeline
  python -m parcel_master.load_land_price
  python -m parcel_master.load_land_price --sido 43
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

from parcel_master.db_utils import get_collective_engine, get_parcel_engine
from parcel_master.load_title_pilot import apply_schema
from parcel_master.paths import land_price_csv, land_price_sidos, land_price_snapshot
from parcel_master.pnu import remap_pnu_old_sido
from parcel_master.snapshot import upsert_ledger_snapshot

COLS = ("고유번호", "기준연도", "공시지가", "공시일자")


def _old_to_current_bjd() -> dict[str, str]:
    engine = get_collective_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT old.beopjungri_code AS old_code,
                       current.beopjungri_code AS current_code
                FROM region_codes old
                JOIN region_codes current
                  ON current.sido_code = '12'
                 AND COALESCE(current.is_active, TRUE)
                 AND current.sigungu_name = old.sigungu_name
                 AND current.eupmyeondong_name = old.eupmyeondong_name
                 AND current.beopjungri_name = old.beopjungri_name
                WHERE LEFT(TRIM(old.beopjungri_code), 2) IN ('29', '46')
                """
            )
        ).all()
    mapping = {str(a).strip(): str(b).strip() for a, b in rows}
    print(f"[AL_D151] 구코드 맵핑 {len(mapping):,}건", flush=True)
    return mapping


def _keep_pnus(engine) -> set[str]:
    with engine.connect() as conn:
        return {str(r[0]) for r in conn.execute(text("SELECT pnu FROM parcel"))}


def _parse_date(raw: str | None) -> date | None:
    t = (raw or "").strip()[:10]
    if len(t) < 10:
        return None
    try:
        return datetime.strptime(t, "%Y-%m-%d").date()
    except ValueError:
        return None


def load_sido(
    engine,
    sido: str,
    keep: set[str],
    mapping: dict[str, str],
    *,
    refresh: bool,
) -> dict:
    src = land_price_csv(sido)
    snap = land_price_snapshot(sido) or "unknown"
    if not src:
        print(f"[AL_D151] {sido} 파일 없음", flush=True)
        return {"sido": sido, "missing": True}

    print(
        f"[AL_D151] {sido} {src.name} ({src.stat().st_size / 2**20:.0f}MB) keep={len(keep):,}",
        flush=True,
    )
    found: dict[tuple[str, int], tuple] = {}
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            reader = pd.read_csv(
                src,
                usecols=lambda c: c in COLS,
                dtype=str,
                chunksize=250_000,
                encoding=enc,
            )
            for chunk in reader:
                for pnu_raw, year_raw, price_raw, day_raw in zip(
                    chunk["고유번호"], chunk["기준연도"], chunk["공시지가"], chunk["공시일자"]
                ):
                    pnu = remap_pnu_old_sido(str(pnu_raw or "").strip(), mapping)
                    if not pnu or pnu not in keep:
                        continue
                    try:
                        year = int(float(str(year_raw)))
                    except (TypeError, ValueError):
                        continue
                    try:
                        price = float(str(price_raw).replace(",", ""))
                    except (TypeError, ValueError):
                        continue
                    if price <= 0 or year < 1900:
                        continue
                    found[(pnu, year)] = (
                        pnu,
                        year,
                        price,
                        _parse_date(str(day_raw) if day_raw is not None else None),
                        sido,
                        snap,
                    )
            break
        except UnicodeDecodeError:
            continue

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        if refresh:
            cur.execute(
                "DELETE FROM parcel_land_price WHERE source_sido = %s AND snapshot = %s",
                (sido, snap),
            )
        if found:
            execute_values(
                cur,
                """
                INSERT INTO parcel_land_price
                    (pnu, price_year, price_per_m2, base_date, source_sido, snapshot)
                VALUES %s
                ON CONFLICT (pnu, price_year) DO UPDATE SET
                    price_per_m2 = EXCLUDED.price_per_m2,
                    base_date = EXCLUDED.base_date,
                    source_sido = EXCLUDED.source_sido,
                    snapshot = EXCLUDED.snapshot
                """,
                list(found.values()),
                page_size=2000,
            )
        raw.commit()
    finally:
        raw.close()

    n = len(found)
    upsert_ledger_snapshot(
        engine,
        source="al_d151",
        snapshot=snap,
        sido_code=sido,
        row_count=n,
    )
    print(f"[AL_D151] {sido} upsert={n:,}", flush=True)
    return {"sido": sido, "n": n}


def smoke_overlap(parcel_engine) -> dict:
    coll = get_collective_engine()
    with coll.connect() as conn:
        mart = {
            str(r[0])
            for r in conn.execute(
                text("SELECT DISTINCT representative_pnu FROM collective_building_assessed_land_price")
            )
            if r[0]
        }
    if not mart:
        return {"mart": 0, "overlap": 0}
    with parcel_engine.connect() as conn:
        have = {
            str(r[0])
            for r in conn.execute(text("SELECT DISTINCT pnu FROM parcel_land_price"))
        }
    overlap = len(mart & have)
    print(
        f"[AL_D151] 집합마트 PNU {len(mart):,} · 축약 교집합 {overlap:,} ({100 * overlap / len(mart):.1f}%)",
        flush=True,
    )
    return {"mart": len(mart), "overlap": overlap}


def run(sidos: tuple[str, ...], *, refresh: bool) -> dict:
    engine = get_parcel_engine()
    apply_schema(engine)
    keep = _keep_pnus(engine)
    mapping = _old_to_current_bjd()
    stats = []
    for sido in sidos:
        stats.append(load_sido(engine, sido, keep, mapping, refresh=refresh))
    with engine.connect() as conn:
        total = int(conn.execute(text("SELECT COUNT(*) FROM parcel_land_price")).scalar() or 0)
        years = conn.execute(
            text("SELECT MIN(price_year), MAX(price_year) FROM parcel_land_price")
        ).one()
    overlap = smoke_overlap(engine)
    print(f"done parcel_land_price={total:,} years={years[0]}..{years[1]}", flush=True)
    return {"rows": total, "sidos": stats, "overlap": overlap}


def main() -> None:
    p = argparse.ArgumentParser(description="AL_D151 → parcel_land_price (수요 필지만)")
    p.add_argument("--sido", nargs="+", default=None)
    p.add_argument("--refresh", action="store_true")
    args = p.parse_args()
    sidos = tuple(args.sido) if args.sido else land_price_sidos()
    t0 = time.time()
    out = run(sidos, refresh=args.refresh)
    print(f"[P1.4] elapsed={time.time() - t0:.0f}s {out['rows']:,} rows overlap={out['overlap']}", flush=True)


if __name__ == "__main__":
    main()
