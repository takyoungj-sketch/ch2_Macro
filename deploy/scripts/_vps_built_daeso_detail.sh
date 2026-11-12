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
    for q, label in [
        ("SELECT COUNT(*) FROM built_transactions WHERE btrim(eupmyeondong_code::text)='43770340'", 'eup70340'),
        ("SELECT COUNT(*) FROM built_transactions WHERE btrim(eupmyeondong_code::text) LIKE '43770340%'", 'eup70340prefix'),
        ("SELECT COUNT(*) FROM built_transactions WHERE addr4 LIKE '%대소%'", 'addr4_daeso'),
        ("SELECT COUNT(*) FROM built_transactions WHERE addr2 LIKE '%음성%' AND addr4 LIKE '%대소%'", 'eumseong_daeso'),
        ("SELECT COUNT(*) FROM built_transactions WHERE asset_type='commercial' AND btrim(eupmyeondong_code::text) LIKE '43770340%'", 'comm70340'),
    ]:
        print(label, c.execute(text(q)).scalar())
PY
