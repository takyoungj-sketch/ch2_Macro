#!/bin/bash
# VPS: land_annual_stats / land_annual_upper_stats DDL 적용
set -euo pipefail
REPO=/opt/ch2_Macro
for f in 014_land_annual_stats.sql 021_land_annual_upper_stats.sql; do
  echo "==> apply db/$f"
  sudo -u postgres psql -d land_stats -v ON_ERROR_STOP=1 -f "$REPO/db/$f"
done
sudo -u postgres psql -d land_stats -t -c "SELECT to_regclass('land_annual_stats'), to_regclass('land_annual_upper_stats');"
echo OK: annual tables created
