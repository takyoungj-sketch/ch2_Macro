#!/usr/bin/env bash
# Resume land 7y mart only (after collective/commercial done).
set -euo pipefail
REPO=/opt/ch2_Macro
ENV="$REPO/backend/.env"
PY="$REPO/backend/.venv/bin/python"
AS_OF="${AS_OF:-2026-07-01}"
WINDOWS="${WINDOWS:-3,5,7}"
LOG="/var/backups/ch2/promote_land_resume.log"

exec >>"$LOG" 2>&1
echo "==> land resume $(date -Is) AS_OF=$AS_OF WINDOWS=$WINDOWS"

set -a
# shellcheck disable=SC1090
source <(grep -E '^(DATABASE_URL|COLLECTIVE_DATABASE_URL|BUILT_DATABASE_URL)=' "$ENV" | tr -d '\r')
set +a

cd "$REPO/backend"
export PYTHONUNBUFFERED=1
"$PY" ../pipeline/build_stats_v2.py --as-of "$AS_OF" --windows "$WINDOWS"
echo "==> upper stats $(date -Is)"
"$PY" ../pipeline/build_upper_stats_v2.py --as-of "$AS_OF" --windows "$WINDOWS"
echo "==> verify $(date -Is)"
sudo -u postgres psql -d land_stats -Atqc "SELECT window_years, count(*) FROM land_basic_stats_v2 GROUP BY 1 ORDER BY 1;"
sudo systemctl restart ch2-macro-backend
sleep 3
curl -sf http://127.0.0.1:8000/health | head -c 300
echo
echo "OK: land resume complete $(date -Is)"
