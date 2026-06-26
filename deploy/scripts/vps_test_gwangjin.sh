#!/usr/bin/env bash
set -euo pipefail
KEY="4aadb250e05177bf01c033fb4dc2469a4b88ed3800120400741416ef3a9b58f7"
TOKEN=$(grep '^API_TOKEN=' /opt/ch2_Macro/backend/.env | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")

echo "==> rolling"
curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings/${KEY}/stats/rolling?window_years=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('points',len(d.get('points',[])),'source',d.get('data_source'))"

echo "==> tx"
curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings/${KEY}/transactions?page=1&page_size=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('total',d.get('total'),'items',len(d.get('items',[])))"

echo "==> yearly"
curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings/${KEY}/stats/by-year" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); pts=d.get('points',[]); ys=[p['year'] for p in pts]; print('years',min(ys) if ys else None,'-',max(ys) if ys else None,'n',len(ys),'source',d.get('data_source'))"

sudo -u postgres psql -d collective_stats -Atc "SELECT MIN(contract_year), MAX(contract_year), COUNT(DISTINCT contract_year) FROM collective_building_annual_stats WHERE building_key='${KEY}'"
