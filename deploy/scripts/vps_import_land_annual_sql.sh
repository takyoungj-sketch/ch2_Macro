#!/bin/bash
set -euo pipefail
LOG=/tmp/land_annual_import.log
: > "$LOG"
echo "start $(date -Is)" >> "$LOG"
grep -v -E 'transaction_timeout|^\\restrict' /tmp/land_annual.sql \
  | sudo -u postgres psql -d land_stats -v ON_ERROR_STOP=1 -f - >> "$LOG" 2>&1
echo "done $(date -Is)" >> "$LOG"
sudo -u postgres psql -d land_stats -t -c "SELECT COUNT(*) FROM land_annual_stats;" >> "$LOG"
sudo -u postgres psql -d land_stats -t -c "SELECT COUNT(*) FROM land_annual_upper_stats;" >> "$LOG"
rm -f /tmp/land_annual.sql
