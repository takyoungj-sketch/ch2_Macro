#!/bin/bash
set -e
sudo -u postgres psql -d land_stats <<'SQL'
GRANT SELECT, INSERT, UPDATE, DELETE ON land_annual_stats, land_annual_upper_stats TO ch2app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ch2app;
SQL
echo OK: grants applied
