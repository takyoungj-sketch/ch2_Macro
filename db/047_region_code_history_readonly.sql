-- =============================================================================
-- 047: region_code_history — production read-only (D-028 ops)
-- =============================================================================
-- Purpose: prevent ad-hoc UPDATE/DELETE on mapping SSOT in production.
-- Changes to region_code_history MUST go through versioned migration SQL only.
--
-- Apply manually per DB after reviewing role names:
--   land_stats, built_stats, collective_stats
--
-- Example (adjust role names to match your deployment):
--   psql $DATABASE_URL -f db/047_region_code_history_readonly.sql
-- =============================================================================

-- Replace `ch2_app` with the application DB role that runs FastAPI/pipeline jobs.
-- Migration/admin role (e.g. ch2_admin) retains INSERT for controlled migrations.

REVOKE UPDATE, DELETE ON region_code_history FROM ch2_app;
GRANT SELECT ON region_code_history TO ch2_app;

-- Optional: revoke direct INSERT from app role (migrations use admin role)
-- REVOKE INSERT ON region_code_history FROM ch2_app;

COMMENT ON TABLE region_code_history IS
    'D-028 SSOT — production app role: SELECT only. Mutations via migration SQL + sync_region_code_history.py.';
