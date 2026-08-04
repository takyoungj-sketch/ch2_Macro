#!/usr/bin/env bash
# Fix 양지읍 collective → profile (구·addr4 grain market_stats join)
set -euo pipefail
cd /opt/ch2_Macro/backend

echo "=== repair collective ledger codes (sido 41) — skip if already done ==="
.venv/bin/python ../pipeline/repair_collective_ledger_region_codes.py --sido-code 41 || true

echo "=== rebuild collective market_stats (경기도) ==="
.venv/bin/python ../pipeline/build_collective_market_stats.py --addr1 "경기도" --windows 3

echo "=== rebuild regional profile (sido 41) ==="
.venv/bin/python ../pipeline/build_regional_profile.py --sido-code 41 --window-years 3 --profile-version v2.1-national
.venv/bin/python ../pipeline/build_regional_profile.py --sido-code 41 --window-years 3 --profile-version v2.0-national

echo "=== verify 양지읍 41461262 ==="
.venv/bin/python ../deploy/scripts/_verify_yangji_profile.py
echo "=== done ==="
