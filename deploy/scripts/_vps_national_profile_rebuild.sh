#!/usr/bin/env bash
# 전국 market_stats + regional_profile 재빌드 (구·addr4 grain · eup canonical fix)
set -euo pipefail
cd /opt/ch2_Macro/backend

LOG=/tmp/national_profile_rebuild.log
exec > >(tee -a "$LOG") 2>&1
echo "=== $(date -Is) START pid=$$ ==="

echo "=== $(date -Is) collective ledger region code backfill (전국) ==="
.venv/bin/python ../pipeline/repair_collective_ledger_region_codes.py

echo "=== $(date -Is) national market_stats + profile v2.1 ==="
.venv/bin/python ../pipeline/rebuild_regional_profile_national.py \
  --skip-land --skip-twin --profile-version v2.1-national

echo "=== $(date -Is) profile v2.0 (mart skip) ==="
.venv/bin/python ../pipeline/rebuild_regional_profile_national.py \
  --skip-land --skip-twin --skip-built --skip-collective --skip-collective-commercial \
  --profile-version v2.0-national

echo "=== $(date -Is) smoke: 양지읍 · 대소읍 ==="
.venv/bin/python ../deploy/scripts/_verify_yangji_profile.py
.venv/bin/python ../deploy/scripts/_verify_daeso_profile.py

echo "=== $(date -Is) national rebuild DONE ==="
