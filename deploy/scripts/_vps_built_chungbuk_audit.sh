#!/usr/bin/env bash
set -euo pipefail
cd /opt/ch2_Macro/backend
.venv/bin/python <<'PY'
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path('.env'))
import os
from sqlalchemy import create_engine, text
eng = create_engine(os.environ['BUILT_DATABASE_URL'])
with eng.connect() as c:
    total = c.execute(text('SELECT COUNT(*) FROM built_transactions')).scalar()
    print('total', total)
    rows = c.execute(text("""
      SELECT btrim(eupmyeondong_code::text) AS eup, COUNT(*) n
      FROM built_transactions
      WHERE btrim(eupmyeondong_code::text) LIKE '43770%'
         OR btrim(eupmyeondong_code::text) LIKE '43770340%'
         OR btrim(eupmyeondong_code::text) LIKE '43770256%'
      GROUP BY 1 ORDER BY n DESC LIMIT 20
    """)).fetchall()
    print('eup43770*', rows)
    rows2 = c.execute(text("""
      SELECT addr1, addr2, addr4, COUNT(*) n
      FROM built_transactions
      WHERE addr2 LIKE '%음성%' OR addr4 LIKE '%대소%'
      GROUP BY 1,2,4 ORDER BY n DESC LIMIT 15
    """)).fetchall()
    print('addr_daeso', rows2)
PY
