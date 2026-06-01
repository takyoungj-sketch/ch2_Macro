#!/usr/bin/env bash
set -euo pipefail
sudo -u postgres psql -d land_stats -v ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;
SQL
sudo systemctl restart ch2-macro-backend
sleep 3
curl -sf http://127.0.0.1:8000/health
echo
