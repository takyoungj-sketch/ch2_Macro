#!/usr/bin/env bash
# Land 7y col_axis=group mart only (VPS gap fill vs local).
set -euo pipefail
REPO=/opt/ch2_Macro
ENV="$REPO/backend/.env"
PY="$REPO/backend/.venv/bin/python"
AS_OF="${AS_OF:-2026-07-01}"
WINDOWS="${WINDOWS:-7}"
LOG="/var/backups/ch2/promote_land_7y_group.log"

exec >>"$LOG" 2>&1
echo "==> land 7y group $(date -Is) AS_OF=$AS_OF WINDOWS=$WINDOWS"

unset STATS_V2_SIDO_CODE || true

set -a
# shellcheck disable=SC1090
source <(grep -E '^(DATABASE_URL|COLLECTIVE_DATABASE_URL|BUILT_DATABASE_URL)=' "$ENV" | tr -d '\r')
set +a

cd "$REPO/backend"
export PYTHONUNBUFFERED=1

echo "==> build_stats_v2 group $(date -Is)"
"$PY" ../pipeline/build_stats_v2.py --as-of "$AS_OF" --windows "$WINDOWS" --col-axis group

echo "==> build_upper_stats_v2 group $(date -Is)"
"$PY" ../pipeline/build_upper_stats_v2.py --as-of "$AS_OF" --windows "$WINDOWS" --col-axis group

echo "==> verify $(date -Is)"
sudo -u postgres psql -d land_stats -Atqc "
SELECT window_years, col_axis, count(*)
FROM land_basic_stats_v2
WHERE window_years=7
GROUP BY 1,2 ORDER BY 2;
"
sudo -u postgres psql -d land_stats -Atqc "
SELECT window_years, col_axis, count(*)
FROM land_upper_stats_v2
WHERE window_years=7
GROUP BY 1,2 ORDER BY 2;
"

sudo systemctl restart ch2-macro-backend
sleep 3
curl -sf http://127.0.0.1:8000/health | head -c 300
echo
echo "OK: land 7y group complete $(date -Is)"
