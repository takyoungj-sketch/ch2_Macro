#!/usr/bin/env bash
set -euo pipefail
TOKEN=$(grep '^API_TOKEN=' /opt/ch2_Macro/backend/.env | cut -d= -f2- | tr -d '\r')
echo "=== API meta/filters (no client token — nginx injects) ==="
curl -sk https://macro.ch2data.com/api/built/meta/filters \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('count', len(d.get('addr1_list',[]))); print('sample', d.get('addr1_list',[])[:5])"

echo "=== API addr2 for Seoul ==="
curl -sk "https://macro.ch2data.com/api/built/regions/addr2?addr1=%EC%84%9C%EC%9A%B8%ED%8A%B9%EB%B3%84%EC%8B%9C" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('count', len(d)); print('sample', d[:5])"

