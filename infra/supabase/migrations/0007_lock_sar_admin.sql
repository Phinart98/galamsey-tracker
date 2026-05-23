-- 0007_lock_sar_admin.sql
-- Lock down sar_alerts_join_admin to service_role only.
--
-- Same rationale as 0005_lock_admin_functions.sql: Supabase's default-privileges
-- setup GRANTs EXECUTE on every public-schema function to anon and authenticated,
-- so REVOKE FROM PUBLIC alone is not sufficient -- the per-role grants must be
-- revoked explicitly.
--
-- With a guessable BIGINT run_id, anon could null out admin-column enrichment
-- for that run; locking down is non-optional.
REVOKE EXECUTE ON FUNCTION sar_alerts_join_admin(BIGINT) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION sar_alerts_join_admin(BIGINT) TO service_role;
