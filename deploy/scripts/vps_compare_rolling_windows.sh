#!/usr/bin/env bash
set -euo pipefail
KEY="${1:-4aadb250e05177bf01c033fb4dc2469a4b88ed3800120400741416ef3a9b58f7}"
TOKEN=$(grep '^API_TOKEN=' /opt/ch2_Macro/backend/.env | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")

for W in 3 5; do
  echo "==> window_years=$W"
  curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings/${KEY}/stats/rolling?window_years=${W}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); pts=d.get('points',[]); print('n',len(pts),'source',d.get('data_source')); [print(p['bucket_index'],p.get('label'),p.get('count')) for p in pts]"
done
