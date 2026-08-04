#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")
from sqlalchemy import create_engine, text

eng = create_engine(os.environ["COLLECTIVE_DATABASE_URL"])
with eng.connect() as c:
    apt = c.execute(
        text(
            """
            SELECT count FROM market_stats
            WHERE market_domain='apartment_market' AND region_level='eupmyeondong'
              AND region_code='41461262' ORDER BY as_of_month DESC LIMIT 1
            """
        )
    ).scalar()
    row = c.execute(
        text(
            """
            SELECT features FROM regional_profile
            WHERE region_level='eupmyeondong' AND region_code='41461262'
              AND profile_version='v2.1-national'
            ORDER BY as_of_month DESC LIMIT 1
            """
        )
    ).scalar()
    f = row if isinstance(row, dict) else json.loads(row)
    mp = f.get("market_presence") or {}
    print("apartment_market count", apt)
    print("profile apartment_count", f.get("apartment_count"))
    print("market_presence 아파트", mp.get("아파트"))
    print("market_presence 토지", mp.get("토지"))
    if not apt or mp.get("아파트") != 1:
        sys.exit(1)
