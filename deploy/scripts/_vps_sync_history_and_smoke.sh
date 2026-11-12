#!/usr/bin/env bash
set -euo pipefail
cd /opt/ch2_Macro/backend
PY=/opt/ch2_Macro/backend/.venv/bin/python
if [[ ! -x "$PY" ]]; then PY=python3; fi

echo "==> sync region_code_history land -> built/collective"
$PY ../pipeline/sync_region_code_history.py --targets built,collective

echo "==> re-smoke built daeso"
export API_TOKEN=$(grep '^API_TOKEN=' .env | cut -d= -f2- | tr -d '\r')
$PY ../pipeline/smoke_region_code_deploy.py --base-url http://127.0.0.1:8000 2>&1 | grep -E 'built\.|scope|lookup|PASS|FAIL'
