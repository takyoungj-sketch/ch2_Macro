#!/usr/bin/env bash
# ch2_platform — 072 토스 빌링 DDL
set -euo pipefail
REPO_ROOT="/opt/ch2_Macro"
SQL="$REPO_ROOT/db/072_platform_toss_billing.sql"
DB="${CH2_PLATFORM_DB:-ch2_platform}"
if [[ ! -f "$SQL" ]]; then
  echo "ERROR: missing $SQL" >&2
  exit 1
fi
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DB" -f "$SQL"
echo "OK: applied 072_platform_toss_billing.sql to $DB"
