"""표제부 「집합」 대전·충북 3스냅샷 → parcel_master.building / parcel.

  python -m parcel_master.load_title_pilot
  python -m parcel_master.load_title_pilot --refresh
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from sqlalchemy import text

from parcel_master.db_utils import get_parcel_engine
from parcel_master.paths import (
    ALL_SIDO,
    CACHE,
    EXPAND_SIDO,
    ISOLATED_SIDO,
    PILOT_SIDO,
    SNAPSHOTS,
    TITLE_COLS,
    land_ledger_csv,
    title_path,
)
from parcel_master.pnu import pnu_from_title_parts, split_pnu, structure_group

SCHEMA = Path(__file__).with_name("schema.sql")
NEED = max(TITLE_COLS.values())


def _num(v: str) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f > 0 else None


def _int(v: str) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _str(v: str, max_len: int) -> str | None:
    t = (v or "").strip()
    if not t:
        return None
    return t[:max_len]


def cache_path(sidos: tuple[str, ...], snapshot: str) -> Path:
    key = tuple(sidos)
    if key == PILOT_SIDO:
        name = f"title_집합_30_43_{snapshot}.csv"
    elif set(key) == set(ALL_SIDO):
        name = f"title_집합_national_{snapshot}.csv"
    elif set(key) == set(EXPAND_SIDO):
        name = f"title_집합_expand_{snapshot}.csv"
    else:
        name = f"title_집합_{'_'.join(key)}_{snapshot}.csv"
    return CACHE / name


def scan_snapshot(snapshot: str, sidos: tuple[str, ...], refresh: bool) -> Path:
    CACHE.mkdir(exist_ok=True)
    out = cache_path(sidos, snapshot)
    if out.exists() and not refresh:
        print(f"[표제부] 캐시 {out.name}", flush=True)
        return out
    src = title_path(snapshot)
    print(f"[표제부] 스캔 {snapshot} {src.name} ({src.stat().st_size / 2**30:.1f}GB)", flush=True)
    kept = total = short = skip_kind = isolated = 0
    want = set(sidos)
    with src.open(encoding="utf-8-sig", errors="replace") as f, out.open(
        "w", encoding="utf-8", newline=""
    ) as w:
        writer = csv.DictWriter(w, fieldnames=list(TITLE_COLS))
        writer.writeheader()
        for line in f:
            total += 1
            parts = line.rstrip("\n").split("|")
            if len(parts) <= NEED:
                short += 1
                continue
            sg = parts[TITLE_COLS["sigungu_code"]]
            prefix = sg[:2]
            if prefix not in want:
                continue
            if prefix in ISOLATED_SIDO:
                isolated += 1
                continue
            if parts[TITLE_COLS["ledger_kind"]] != "집합":
                skip_kind += 1
                continue
            writer.writerow({k: parts[i] for k, i in TITLE_COLS.items()})
            kept += 1
            if kept % 20_000 == 0:
                print(f"  kept {kept:,}", flush=True)
    print(
        f"[표제부] {snapshot} read={total:,} kept={kept:,} 일반건너뜀={skip_kind:,} "
        f"short={short:,} isolated={isolated:,}",
        flush=True,
    )
    return out


def _row_from_rec(rec: dict, snapshot: str) -> dict | None:
    pnu = pnu_from_title_parts(
        rec["sigungu_code"],
        rec["bjd_code"],
        rec["plat_gb"],
        rec["bun"],
        rec["ji"],
    )
    parts = split_pnu(pnu) if pnu else None
    if not parts:
        return None
    return {
        "mgmt_pk": rec["pk"].strip(),
        "snapshot": snapshot,
        "pnu": parts["pnu"],
        "beopjungri_code": parts["beopjungri_code"],
        "sido_code": parts["sido_code"],
        "ledger_kind": "집합",
        "building_name": _str(rec["building_name"], 200),
        "dong_name": _str(rec["dong_name"], 80),
        "structure_name": _str(rec["struct_name"], 60),
        "structure_group": structure_group(rec["struct_name"]),
        "main_purpose": _str(rec["main_purpose"], 80),
        "purpose_detail": _str(rec["purpose_detail"], 120),
        "households": _int(rec["households"]),
        "floors_above": _int(rec["floors_above"]),
        "floors_below": _int(rec["floors_below"]),
        "gross_area": _num(rec["gross_area"]),
        "arch_area": _num(rec["arch_area"]),
        "plat_area": _num(rec["plat_area"]),
        "title_land_area": _num(rec["title_land"]),
        "approve_date": _str(rec["approve_date"], 8),
    }


def iter_building_rows(path: Path, snapshot: str, batch_size: int = 20_000):
    batch: list[dict] = []
    bad_pnu = kept = 0
    with path.open(encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            row = _row_from_rec(rec, snapshot)
            if not row:
                bad_pnu += 1
                continue
            batch.append(row)
            kept += 1
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch
    print(f"[표제부] {path.name} rows={kept:,} bad_pnu={bad_pnu}", flush=True)


def apply_schema(engine) -> None:
    ddl = SCHEMA.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def replace_buildings(
    engine,
    rows: list[dict],
    sidos: tuple[str, ...],
    snapshot: str,
    *,
    clear: bool,
) -> None:
    from psycopg2.extras import execute_values

    in_sql = ",".join(f"'{s}'" for s in sidos)
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        if clear:
            cur.execute(
                f"DELETE FROM building WHERE snapshot = %s AND sido_code IN ({in_sql})",
                (snapshot,),
            )
        if rows:
            cols = list(rows[0])
            update_cols = [c for c in cols if c not in {"mgmt_pk", "snapshot"}]
            insert_sql = (
                f"INSERT INTO building ({', '.join(cols)}) VALUES %s "
                f"ON CONFLICT (mgmt_pk, snapshot) DO UPDATE SET "
                + ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)
            )
            tuples = [tuple(r[c] for c in cols) for r in rows]
            execute_values(cur, insert_sql, tuples, page_size=1000)
        raw.commit()
    finally:
        raw.close()


def rebuild_parcels(engine, sidos: tuple[str, ...]) -> None:
    in_sql = ",".join(f"'{s}'" for s in sidos)
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM parcel WHERE sido_code IN ({in_sql})"))
        conn.execute(
            text(
                f"""
                INSERT INTO parcel (
                    pnu, beopjungri_code, bun, ji, sido_code, sigungu_code,
                    land_area, land_area_source, first_seen, last_seen, n_buildings
                )
                SELECT
                    pnu,
                    MIN(beopjungri_code),
                    SUBSTRING(pnu FROM 12 FOR 4),
                    SUBSTRING(pnu FROM 16 FOR 4),
                    MIN(sido_code),
                    SUBSTRING(pnu FROM 1 FOR 5),
                    MAX(title_land_area),
                    CASE WHEN MAX(title_land_area) IS NOT NULL THEN 'title' END,
                    MIN(snapshot),
                    MAX(snapshot),
                    COUNT(DISTINCT mgmt_pk)
                FROM building
                WHERE sido_code IN ({in_sql})
                GROUP BY pnu
                """
            )
        )


def overlay_land_ledger(engine, sidos: tuple[str, ...]) -> dict:
    from parcel_master.pnu import make_pnu, parse_lot

    stats = {"files": 0, "updated": 0}
    with engine.connect() as conn:
        existing = {
            r[0]
            for r in conn.execute(
                text("SELECT pnu FROM parcel WHERE sido_code IN (" + ",".join(f"'{s}'" for s in sidos) + ")")
            )
        }
    updates: list[tuple[str | None, float | None, str]] = []
    for sido in sidos:
        src = land_ledger_csv(sido)
        if not src:
            print(f"[토지대장] {sido} 없음", flush=True)
            continue
        stats["files"] += 1
        print(f"[토지대장] {src.name}", flush=True)
        import pandas as pd

        for enc in ("cp949", "utf-8-sig", "euc-kr"):
            try:
                reader = pd.read_csv(
                    src,
                    usecols=["법정동코드", "지번", "지목코드", "면적"],
                    dtype=str,
                    chunksize=400_000,
                    encoding=enc,
                )
                for chunk in reader:
                    for bjd, lot, jimok, area in zip(
                        chunk["법정동코드"], chunk["지번"], chunk["지목코드"], chunk["면적"]
                    ):
                        parsed = parse_lot(str(lot))
                        if not parsed:
                            continue
                        bun, ji, gbn = parsed
                        pnu = make_pnu(str(bjd).zfill(10), gbn, bun, ji)
                        if not pnu or pnu not in existing:
                            continue
                        a = _num(str(area) if area is not None else "")
                        jk = str(jimok).strip().zfill(2)[-2:] if jimok and str(jimok).strip() else None
                        updates.append((jk, a, pnu))
                break
            except UnicodeDecodeError:
                continue
    if not updates:
        return stats
    by_pnu: dict[str, tuple[str | None, float | None]] = {}
    for jimok, area, pnu in updates:
        by_pnu[pnu] = (jimok, area)
    from psycopg2.extras import execute_values

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("BEGIN")
        cur.execute("CREATE TEMP TABLE _land_ov (jimok char(2), area numeric, pnu char(19))")
        execute_values(
            cur,
            "INSERT INTO _land_ov (jimok, area, pnu) VALUES %s",
            [(j, a, p) for p, (j, a) in by_pnu.items()],
            page_size=2000,
        )
        cur.execute(
            """
            UPDATE parcel p SET
                jimok_code = COALESCE(o.jimok, p.jimok_code),
                land_area = COALESCE(o.area, p.land_area),
                land_area_source = CASE
                    WHEN o.area IS NOT NULL THEN 'land_ledger'
                    ELSE p.land_area_source
                END
            FROM _land_ov o
            WHERE p.pnu = o.pnu
            """
        )
        stats["updated"] = cur.rowcount
        raw.commit()
    finally:
        raw.close()
    print(f"[토지대장] overlay updated={stats['updated']:,}", flush=True)
    return stats


def run(sidos: tuple[str, ...], refresh: bool, skip_ledger: bool) -> None:
    engine = get_parcel_engine()
    apply_schema(engine)
    for snap in SNAPSHOTS:
        cache = scan_snapshot(snap, sidos, refresh)
        cleared = False
        for batch in iter_building_rows(cache, snap):
            replace_buildings(engine, batch, sidos, snap, clear=not cleared)
            cleared = True
        if not cleared:
            print(f"[표제부] {snap} 0행 — 기존 building 유지", flush=True)
    rebuild_parcels(engine, sidos)
    if not skip_ledger:
        overlay_land_ledger(engine, sidos)
    with engine.connect() as conn:
        n_b = conn.execute(text("SELECT COUNT(*) FROM building")).scalar()
        n_p = conn.execute(text("SELECT COUNT(*) FROM parcel")).scalar()
    print(f"done building={n_b:,} parcel={n_p:,}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--sido", nargs="+", default=list(PILOT_SIDO))
    p.add_argument("--skip-ledger", action="store_true")
    args = p.parse_args()
    run(tuple(args.sido), args.refresh, args.skip_ledger)


if __name__ == "__main__":
    main()
