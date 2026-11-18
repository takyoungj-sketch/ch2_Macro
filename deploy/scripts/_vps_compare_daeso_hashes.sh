#!/usr/bin/env bash
set -euo pipefail
cd /opt/ch2_Macro/backend
.venv/bin/python <<'PY'
import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os
load_dotenv('.env')
path = Path('../logs/built_slice_daeso.jsonl')
hashes = [json.loads(l)['transaction_hash'] for l in path.read_text().splitlines() if l.strip()]
eng = create_engine(os.environ['BUILT_DATABASE_URL'])
with eng.connect() as c:
    n = c.execute(text('SELECT COUNT(*) FROM built_transactions WHERE transaction_hash = ANY(:h)'), {'h': hashes}).scalar()
    wrong = c.execute(text("""
      SELECT COUNT(*) FROM built_transactions
      WHERE transaction_hash = ANY(:h)
        AND btrim(eupmyeondong_code::text) NOT LIKE '43770340%'
        AND btrim(eupmyeondong_code::text) NOT LIKE '43770256%'
    """), {'h': hashes}).scalar()
    sample = c.execute(text("""
      SELECT transaction_hash, eupmyeondong_code, addr4 FROM built_transactions
      WHERE transaction_hash = ANY(:h) LIMIT 5
    """), {'h': hashes[:20]}).fetchall()
print('hashes', len(hashes), 'found_on_vps', n, 'wrong_eup', wrong)
for s in sample: print(s)
PY
