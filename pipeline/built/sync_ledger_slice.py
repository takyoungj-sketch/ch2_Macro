# -*- coding: utf-8 -*-
"""Export/import built_transactions slice by eup prefix (ledger gap fix).

Usage (export local):
  cd backend
  .venv/Scripts/python.exe ../pipeline/built/sync_ledger_slice.py export \\
    --prefixes 43770340,43770256 --out ../logs/built_slice_daeso.jsonl

Usage (import on VPS):
  cd backend
  python3 ../pipeline/built/sync_ledger_slice.py import --in ../logs/built_slice_daeso.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=True)
load_dotenv(ROOT / "pipeline" / ".env.built")
load_dotenv()

from sqlalchemy import text

from built.db_utils import get_built_engine

INSERT_SQL = text(
    """
    INSERT INTO built_transactions (
        transaction_hash, asset_type, deal_form,
        addr1, addr2, addr3, addr4, addr5, lot_number,
        road_name, display_address,
        beopjungri_code, sido_code, sigungu_code, eupmyeondong_code,
        trade_year_label, contract_year, contract_month, contract_date,
        zone_type, building_use, building_scale, land_scale, age_bucket,
        price, gross_area, land_area, building_age,
        road_code, road_width_label, floor, deal_type,
        is_valid, needs_review, mapping_notes
    ) VALUES (
        :transaction_hash, :asset_type, :deal_form,
        :addr1, :addr2, :addr3, :addr4, :addr5, :lot_number,
        :road_name, :display_address,
        :beopjungri_code, :sido_code, :sigungu_code, :eupmyeondong_code,
        :trade_year_label, :contract_year, :contract_month, :contract_date,
        :zone_type, :building_use, :building_scale, :land_scale, :age_bucket,
        :price, :gross_area, :land_area, :building_age,
        :road_code, :road_width_label, :floor, :deal_type,
        :is_valid, :needs_review, :mapping_notes
    )
    ON CONFLICT (transaction_hash) DO NOTHING
    """
)

UPDATE_CODES_SQL = text(
    """
    UPDATE built_transactions SET
        addr1 = COALESCE(:addr1, addr1),
        addr2 = COALESCE(:addr2, addr2),
        addr3 = COALESCE(:addr3, addr3),
        addr4 = COALESCE(:addr4, addr4),
        addr5 = COALESCE(:addr5, addr5),
        beopjungri_code = COALESCE(:beopjungri_code, beopjungri_code),
        sido_code = COALESCE(:sido_code, sido_code),
        sigungu_code = COALESCE(:sigungu_code, sigungu_code),
        eupmyeondong_code = COALESCE(:eupmyeondong_code, eupmyeondong_code),
        display_address = COALESCE(:display_address, display_address),
        needs_review = COALESCE(:needs_review, needs_review),
        mapping_notes = COALESCE(:mapping_notes, mapping_notes)
    WHERE transaction_hash = :transaction_hash
    """
)


def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def _row_to_dict(row) -> dict:
    d = dict(row._mapping)
    for k, v in list(d.items()):
        if v is None:
            continue
        if isinstance(v, Decimal):
            d[k] = float(v)
        elif isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
    return d


def cmd_export(prefixes: list[str], out: Path) -> None:
    eng = get_built_engine()
    clauses = " OR ".join(
        f"btrim(eupmyeondong_code::text) LIKE :p{i}" for i in range(len(prefixes))
    )
    params = {f"p{i}": f"{p}%" for i, p in enumerate(prefixes)}
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT * FROM built_transactions
                WHERE {clauses}
                ORDER BY id
                """
            ),
            params,
        ).fetchall()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(_row_to_dict(row), ensure_ascii=False, default=_json_default))
            f.write("\n")
    print(f"exported {len(rows)} rows -> {out}")


def cmd_import(path: Path, *, mode: str = "insert") -> None:
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    eng = get_built_engine()
    inserted = 0
    skipped = 0
    updated = 0
    with eng.begin() as conn:
        before = int(conn.execute(text("SELECT COUNT(*) FROM built_transactions")).scalar() or 0)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            rec.pop("id", None)
            rec.pop("created_at", None)
            if mode == "update-codes":
                result = conn.execute(UPDATE_CODES_SQL, rec)
                if result.rowcount:
                    updated += 1
                else:
                    skipped += 1
            else:
                result = conn.execute(INSERT_SQL, rec)
                if result.rowcount:
                    inserted += 1
                else:
                    skipped += 1
        after = int(conn.execute(text("SELECT COUNT(*) FROM built_transactions")).scalar() or 0)
    if mode == "update-codes":
        print(f"updated={updated} skipped={skipped} total {before} -> {after}")
    else:
        print(f"inserted={inserted} skipped={skipped} total {before} -> {after}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--prefixes", required=True, help="comma eup prefixes e.g. 43770340,43770256")
    ex.add_argument("--out", type=Path, required=True)
    im = sub.add_parser("import")
    im.add_argument("--in", dest="in_path", type=Path, required=True)
    im.add_argument(
        "--mode",
        choices=("insert", "update-codes"),
        default="insert",
        help="insert=ON CONFLICT skip; update-codes=patch admin codes on existing hash",
    )
    args = ap.parse_args()
    if args.cmd == "export":
        prefixes = [p.strip() for p in args.prefixes.split(",") if p.strip()]
        cmd_export(prefixes, args.out)
    else:
        cmd_import(args.in_path, mode=args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
