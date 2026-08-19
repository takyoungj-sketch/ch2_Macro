#!/usr/bin/env bash
# VPS: K-apt 단지 속성(collective_building_attributes) 적재 + 사전 적용
# Usage:
#   bash deploy/scripts/vps_sync_collective_building_attributes.sh
#   bash deploy/scripts/vps_sync_collective_building_attributes.sh --kapt-file /path/to/kapt.xlsx
set -euo pipefail

REPO=/opt/ch2_Macro
ENV="$REPO/backend/.env"
PY="$REPO/backend/.venv/bin/python"
KAPT_FILE="${KAPT_FILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kapt-file) KAPT_FILE="${2:-}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -x "$PY" ]]; then
  echo "ERROR: missing $PY" >&2
  exit 1
fi

echo "==> DDL 049·052 (collective building attributes)"
sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 -f "$REPO/db/049_collective_building_attributes.sql"
sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 -f "$REPO/db/052_collective_attributes_dictionary_columns.sql"

if [[ -z "$KAPT_FILE" ]]; then
  KAPT_FILE="$(ls -1 "$REPO"/raw/**/apt_mst_info*.xlsx 2>/dev/null | head -1 || true)"
fi
if [[ -z "$KAPT_FILE" || ! -f "$KAPT_FILE" ]]; then
  echo "ERROR: K-apt xlsx not found — set KAPT_FILE or place apt_mst_info under raw/" >&2
  exit 1
fi

echo "==> build_collective_building_attributes ($KAPT_FILE)"
cd "$REPO/backend"
export PYTHONUNBUFFERED=1
"$PY" ../pipeline/build_collective_building_attributes.py --kapt-file "$KAPT_FILE" --replace --apply-ddl

SNAP="$("$PY" - <<'PY'
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv(".env")
url = os.environ.get("COLLECTIVE_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
if "collective_stats" not in url and os.environ.get("COLLECTIVE_DATABASE_URL") is None:
    url = url.rsplit("/", 1)[0] + "/collective_stats"
e = create_engine(url)
with e.connect() as c:
    print(c.execute(text("SELECT MAX(snapshot_ym) FROM collective_building_attributes")).scalar() or "")
PY
)"
if [[ -n "$SNAP" ]]; then
  echo "==> apply_danji_dictionary snapshot_ym=$SNAP"
  "$PY" ../pipeline/collective/apply_danji_dictionary.py --snapshot-ym "$SNAP"
fi

sudo -u postgres psql -d collective_stats -Atqc \
  "SELECT 'builder_master', count(*) FROM builder_master UNION ALL SELECT 'collective_building_attributes', count(*) FROM collective_building_attributes;"

echo "==> done"
