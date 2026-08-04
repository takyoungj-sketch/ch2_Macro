#!/usr/bin/env bash
set -euo pipefail
cd /opt/ch2_Macro/backend
TOKEN=$(grep '^API_TOKEN=' .env | cut -d= -f2- | tr -d '\r')
export API_TOKEN="$TOKEN"
python3 ../pipeline/smoke_region_code_deploy.py --base-url http://127.0.0.1:8000
