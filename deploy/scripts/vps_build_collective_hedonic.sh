#!/usr/bin/env bash
# VPS: 헤도닉 DDL 050·051 적용 + mart 빌드(품질지수·enrichment·특성회귀)
# Usage: bash deploy/scripts/vps_build_collective_hedonic.sh --as-of 2026-07-01
set -euo pipefail

REPO=/opt/ch2_Macro
PY="$REPO/backend/.venv/bin/python"
AS_OF="${AS_OF:-2026-07-01}"
WINDOWS="${WINDOWS:-5}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --as-of) AS_OF="${2:-}"; shift 2 ;;
    --windows) WINDOWS="${2:-}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

echo "==> DDL 050·051"
sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 -f "$REPO/db/050_collective_quality_index.sql"
sudo -u postgres psql -d collective_stats -v ON_ERROR_STOP=1 -f "$REPO/db/051_collective_attribute_effects.sql"

cd "$REPO/backend"
export PYTHONUNBUFFERED=1
"$PY" ../pipeline/build_collective_quality_index.py --as-of "$AS_OF" --windows "$WINDOWS" --replace
"$PY" ../pipeline/build_collective_hedonic_enrichment.py --as-of "$AS_OF" --windows "$WINDOWS" --replace
"$PY" ../pipeline/build_collective_attribute_effects.py --as-of "$AS_OF" --windows "$WINDOWS" --specs A,B,C,L --with-location --replace

echo "==> hedonic marts done"
