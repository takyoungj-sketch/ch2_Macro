"""AL_D155 → parcel_zone. 원본 48GB를 넣지 않고 parcel PNU만 남긴다.

  python -m parcel_master.load_zone
  python -m parcel_master.load_zone --sido 30 43
  python -m parcel_master.load_zone --refresh
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text

from parcel_master.db_utils import get_parcel_engine
from parcel_master.load_title_pilot import apply_schema
from parcel_master.paths import ALL_SIDO, CACHE, zone_csv, zone_snapshot
from parcel_master.pnu import make_pnu, parse_lot
from parcel_master.zone import ZONE_CODE_RE, ZONE_SOURCE, is_coarse_label, zone_family

COLS = ("법정동코드", "지번", "용도지역지구코드", "용도지역지구명")


def _keep_pnus(engine, sido: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT pnu FROM parcel WHERE sido_code = :s"),
            {"s": sido},
        )
        return {str(r[0]) for r in rows}


def _scan_file(src: Path, keep: set[str]) -> dict[tuple[str, str], dict]:
    found: dict[tuple[str, str], dict] = {}
    if not keep:
        return found
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            reader = pd.read_csv(
                src,
                usecols=lambda c: c in COLS,
                dtype=str,
                chunksize=300_000,
                encoding=enc,
            )
            n = 0
            for chunk in reader:
                n += 1
                code = chunk["용도지역지구코드"].astype(str)
                sub = chunk[code.str.match(ZONE_CODE_RE, na=False)]
                if sub.empty:
                    continue
                for bjd, lot, name in zip(
                    sub["법정동코드"], sub["지번"], sub["용도지역지구명"]
                ):
                    parsed = parse_lot(str(lot) if lot is not None else "")
                    if not parsed:
                        continue
                    bun, ji, gbn = parsed
                    pnu = make_pnu(str(bjd).zfill(10), gbn, bun, ji)
                    if not pnu or pnu not in keep:
                        continue
                    label = str(name).strip()
                    if not label:
                        continue
                    found[(pnu, label)] = {
                        "pnu": pnu,
                        "zone_label": label[:80],
                        "zone_family": zone_family(label),
                        "is_coarse": is_coarse_label(label),
                        "source": ZONE_SOURCE,
                    }
                if n % 20 == 0:
                    print(f"    chunk {n} hits={len(found):,}", flush=True)
            break
        except UnicodeDecodeError:
            continue
    return found


def load_sido(engine, sido: str, refresh: bool) -> dict:
    src = zone_csv(sido)
    snap = zone_snapshot(sido) or "unknown"
    marker = CACHE / f"parcel_zone_{sido}_{snap}.ok"
    CACHE.mkdir(exist_ok=True)
    if marker.exists() and not refresh:
        print(f"[AL_D155] {sido} 이미 적재 {marker.name} — 건너뜀", flush=True)
        return {"sido": sido, "skipped": True}

    if not src:
        print(f"[AL_D155] {sido} 파일 없음", flush=True)
        return {"sido": sido, "missing": True}

    keep = _keep_pnus(engine, sido)
    print(
        f"[AL_D155] {sido} {src.name} ({src.stat().st_size / 2**30:.1f}GB) "
        f"keep={len(keep):,}",
        flush=True,
    )
    found = _scan_file(src, keep) if keep else {}

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("DELETE FROM parcel_zone WHERE pnu LIKE %s", (sido + "%",))
        if found:
            rows = [
                (
                    rec["pnu"],
                    rec["zone_label"],
                    rec["zone_family"],
                    rec["is_coarse"],
                    rec["source"],
                    snap,
                )
                for rec in found.values()
            ]
            execute_values(
                cur,
                """
                INSERT INTO parcel_zone
                    (pnu, zone_label, zone_family, is_coarse, source, snapshot)
                VALUES %s
                ON CONFLICT (pnu, zone_label) DO UPDATE SET
                    zone_family = EXCLUDED.zone_family,
                    is_coarse = EXCLUDED.is_coarse,
                    source = EXCLUDED.source,
                    snapshot = EXCLUDED.snapshot
                """,
                rows,
                page_size=1000,
            )
        raw.commit()
    finally:
        raw.close()

    coarse = sum(1 for rec in found.values() if rec["is_coarse"])
    parcels = {p for p, _ in found}
    marker.write_text(
        f"parcels={len(parcels)} labels={len(found)} coarse={coarse} keep={len(keep)}\n",
        encoding="utf-8",
    )
    print(
        f"[AL_D155] {sido} parcels_with_zone={len(parcels):,} "
        f"labels={len(found):,} coarse={coarse:,} keep={len(keep):,}",
        flush=True,
    )
    return {
        "sido": sido,
        "keep": len(keep),
        "parcels": len(parcels),
        "labels": len(found),
        "coarse": coarse,
    }


def run(sidos: tuple[str, ...], refresh: bool) -> None:
    engine = get_parcel_engine()
    apply_schema(engine)
    for sido in sidos:
        load_sido(engine, sido, refresh)
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM parcel_zone")).scalar()
        fine = conn.execute(
            text("SELECT COUNT(*) FROM parcel_zone WHERE NOT is_coarse")
        ).scalar()
    print(f"done parcel_zone={n:,} fine={fine:,}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sido", nargs="+", default=list(ALL_SIDO))
    p.add_argument("--refresh", action="store_true")
    args = p.parse_args()
    run(tuple(args.sido), args.refresh)


if __name__ == "__main__":
    main()
