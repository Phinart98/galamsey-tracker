-- 0005_lock_admin_functions.sql
-- Lock down maintenance functions to service_role only.
--
-- PostgreSQL grants EXECUTE to PUBLIC by default for new functions, and
-- Supabase additionally GRANTs EXECUTE on every public-schema function to
-- anon and authenticated via its default-privileges setup. So `REVOKE FROM
-- PUBLIC` alone is not sufficient -- the per-role grants must be revoked
-- explicitly. Verified via information_schema.routine_privileges.
--
-- alerts_gfw_join_admin is the concerning one: with a guessable BIGINT
-- run_id, anon could null out admin-column enrichment for that run.
-- ensure_alert_partitions is a no-op placeholder but still leaks internals.
REVOKE EXECUTE ON FUNCTION ensure_alert_partitions(INT)  FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION alerts_gfw_join_admin(BIGINT) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION ensure_alert_partitions(INT)  TO service_role;
GRANT  EXECUTE ON FUNCTION alerts_gfw_join_admin(BIGINT) TO service_role;
