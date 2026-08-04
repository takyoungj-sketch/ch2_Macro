#!/usr/bin/env bash
# Fix 대소읍 built 상가·공장 → profile (beop NULL · eup canonical grain)
set -euo pipefail
cd /opt/ch2_Macro/backend

echo "=== rebuild built market_stats (sido 43) ==="
.venv/bin/python ../pipeline/build_built_market_stats.py --sido-code 43 --windows 3

echo "=== rebuild collective_commercial market_stats (sido 43) ==="
.venv/bin/python ../pipeline/build_collective_commercial_market_stats.py --sido-code 43 --windows 3

echo "=== rebuild regional profile (sido 43) ==="
.venv/bin/python ../pipeline/build_regional_profile.py --sido-code 43 --window-years 3 --profile-version v2.1-national
.venv/bin/python ../pipeline/build_regional_profile.py --sido-code 43 --window-years 3 --profile-version v2.0-national

echo "=== verify 대소읍 43770256 ==="
.venv/bin/python ../deploy/scripts/_verify_daeso_profile.py
echo "=== done ==="
