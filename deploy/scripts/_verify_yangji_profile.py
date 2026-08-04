#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")
CANON = "41461262"

eng = create_engine(os.environ["COLLECTIVE_DATABASE_URL"])
with eng.connect() as c:
    apt = c.execute(
        text(
            """
            SELECT count FROM market_stats
            WHERE market_domain='apartment_market' AND region_level='eupmyeondong'
              AND region_code=:c ORDER BY as_of_month DESC LIMIT 1
            """
        ),
        {"c": CANON},
    ).scalar()
    comm = c.execute(
        text(
            """
            SELECT count FROM market_stats
            WHERE market_domain='commercial_market' AND region_level='eupmyeondong'
              AND region_code=:c ORDER BY as_of_month DESC LIMIT 1
            """
        ),
        {"c": CANON},
    ).scalar()
    row = c.execute(
        text(
            """
            SELECT features FROM regional_profile
            WHERE region_level='eupmyeondong' AND region_code=:c
              AND profile_version='v2.1-national'
            ORDER BY as_of_month DESC LIMIT 1
            """
        ),
        {"c": CANON},
    ).scalar()
    f = row if isinstance(row, dict) else json.loads(row)
    mp = f.get("market_presence") or {}
    ym = (f.get("yearly_mix") or {}).get("totals_by_type") or {}
    shop = ym.get("상가") or {}
    det = ym.get("단독다가구") or {}
    print("apartment_market", apt, "commercial_market", comm)
    print("profile apartment_count", f.get("apartment_count"), "commercial_count", f.get("commercial_count"))
    print("yearly_mix 상가", shop, "단독", det)
    print("market_presence", {k: mp.get(k) for k in ("아파트", "토지", "상가", "단독다가구")})
    ok = (
        apt
        and mp.get("아파트") == 1
        and comm
        and int(shop.get("count") or 0) > 0
        and int(det.get("count") or 0) > 0
        and mp.get("상가") == 1
        and mp.get("단독다가구") == 1
    )
    if not ok:
        sys.exit(1)
