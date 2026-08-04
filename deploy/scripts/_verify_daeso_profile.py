#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")
CANON = "43770256"

eng = create_engine(os.environ["COLLECTIVE_DATABASE_URL"])
with eng.connect() as c:
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
    fact = c.execute(
        text(
            """
            SELECT count FROM market_stats
            WHERE market_domain='factory_market' AND region_level='eupmyeondong'
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
    print("commercial_market", comm, "factory_market", fact)
    print("profile commercial_count", f.get("commercial_count"), "factory_count", f.get("factory_count"))
    print("yearly_mix 상가", ym.get("상가"), "공장", ym.get("공장"))
    print("market_presence 상가", mp.get("상가"), "공장", mp.get("공장"))
    if not comm or not fact or mp.get("상가") != 1 or mp.get("공장") != 1:
        sys.exit(1)
