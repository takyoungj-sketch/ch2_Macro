#!/usr/bin/env bash
set -euo pipefail
ENV=/opt/ch2_Macro/backend/.env
TOKEN=$(grep '^API_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r')
export PGPASSWORD=$(grep '^COLLECTIVE_DATABASE_URL=' "$ENV" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')

echo "==> beopjungri column?"
psql -h 127.0.0.1 -U ch2app -d collective_stats -Atc \
  "SELECT column_name FROM information_schema.columns WHERE table_name='collective_commercial_transactions' AND column_name='beopjungri_code';"

echo "==> gwangju namgu counts"
psql -h 127.0.0.1 -U ch2app -d collective_stats <<'SQL'
SELECT COUNT(*) AS total,
       COUNT(addr3) AS has_a3,
       COUNT(addr4) AS has_a4,
       COUNT(*) FILTER (WHERE addr3 LIKE '%구') AS gu_like
FROM collective_commercial_transactions
WHERE addr1='광주광역시' AND addr2='남구' AND asset_type='collective_shop' AND is_valid=true;

SELECT addr3, COUNT(*) FROM collective_commercial_transactions
WHERE addr1='광주광역시' AND addr2='남구' AND asset_type='collective_shop' AND is_valid=true
  AND addr3 IS NOT NULL
GROUP BY addr3 ORDER BY 2 DESC LIMIT 10;

SELECT addr4, COUNT(*) FROM collective_commercial_transactions
WHERE addr1='광주광역시' AND addr2='남구' AND asset_type='collective_shop' AND is_valid=true
  AND addr4 IS NOT NULL AND btrim(addr4::text) <> ''
GROUP BY addr4 ORDER BY 2 DESC LIMIT 5;
SQL

echo "==> api structure (python urlencode)"
python3 <<'PY'
import json, os, urllib.parse, urllib.request
token = open("/opt/ch2_Macro/backend/.env").read().split("API_TOKEN=")[1].split("\n")[0].strip()
q = urllib.parse.urlencode({"addr1": "광주광역시", "addr2": "남구", "asset_type": "collective_shop"})
url = f"http://127.0.0.1:8000/api/collective/commercial/regions/structure?{q}"
req = urllib.request.Request(url, headers={"X-Api-Token": token})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(r.status, r.read().decode()[:500])
except Exception as e:
    print("ERR", e)
    if hasattr(e, "read"):
        print(e.read().decode()[:800])
PY

echo "==> api addr3"
python3 <<'PY'
import json, os, urllib.parse, urllib.request
token = open("/opt/ch2_Macro/backend/.env").read().split("API_TOKEN=")[1].split("\n")[0].strip()
q = urllib.parse.urlencode({"addr1": "광주광역시", "addr2": "남구", "asset_type": "collective_shop"})
url = f"http://127.0.0.1:8000/api/collective/commercial/regions/addr3?{q}"
req = urllib.request.Request(url, headers={"X-Api-Token": token})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(r.status, r.read().decode()[:800])
except Exception as e:
    print("ERR", e)
    if hasattr(e, "read"):
        print(e.read().decode()[:800])
PY

echo "==> api clusters"
python3 <<'PY'
import urllib.parse, urllib.request
token = open("/opt/ch2_Macro/backend/.env").read().split("API_TOKEN=")[1].split("\n")[0].strip()
q = urllib.parse.urlencode({"addr1": "광주광역시", "addr2": "남구", "asset_type": "collective_shop", "page_size": "3"})
url = f"http://127.0.0.1:8000/api/collective/commercial/clusters?{q}"
req = urllib.request.Request(url, headers={"X-Api-Token": token})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(r.status, r.read().decode()[:500])
except Exception as e:
    print("ERR", e)
    if hasattr(e, "read"):
        print(e.read().decode()[:800])
PY
