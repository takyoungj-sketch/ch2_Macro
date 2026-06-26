#!/usr/bin/env bash
set -euo pipefail
ENV=/opt/ch2_Macro/backend/.env
TOKEN=$(grep '^API_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r')
DB=$(grep '^COLLECTIVE_DATABASE_URL=' "$ENV" | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")

sudo -u postgres psql -d collective_stats -f /tmp/026_collective_tx_display_columns.sql
sudo systemctl restart ch2-macro-backend
sleep 4
systemctl is-active ch2-macro-backend

KEY=$(curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings?search=%EA%B4%91%EC%A7%84&asset_type=officetel&limit=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items') or []; print(next((x['building_key'] for x in items if '캠퍼스' in x.get('display_name','')), items[0]['building_key'] if items else ''))")
echo "building_key=$KEY"
if [[ -z "$KEY" ]]; then exit 0; fi

echo "==> rolling"
curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings/${KEY}/stats/rolling?window_years=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('points',len(d.get('points',[])),'source',d.get('data_source'))"

echo "==> tx"
curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings/${KEY}/transactions?page=1&page_size=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('total',d.get('total'),'items',len(d.get('items',[])))"

echo "==> yearly"
curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/collective/buildings/${KEY}/stats/by-year" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); pts=d.get('points',[]); ys=[p['year'] for p in pts]; print('years',min(ys) if ys else None,'-',max(ys) if ys else None,'n',len(ys),'source',d.get('data_source'))"
