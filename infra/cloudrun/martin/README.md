# Martin tile server

Serves dynamic vector tiles for the GFW alerts layer (and future dynamic
layers: SAR alerts, citizen reports). Static layers like boundaries and
concessions stay on PMTiles.

## Endpoint

```
GET /gfw_alerts_mvt/{z}/{x}/{y}?from=YYYY-MM-DD&to=YYYY-MM-DD&min_confidence=low|high|highest
```

Tile body is a Mapbox Vector Tile (`Content-Type: application/x-protobuf`)
with one layer named `gfw_alerts`.

## Local development

```bash
cd infra/cloudrun/martin
docker build -t martin:phase2 .

# IMPORTANT: --auto-bounds skip is required against Supabase. Without it
# Martin scans pg_class for geometry columns at startup and PgBouncer's
# transaction-mode timeout (~5 min) kills the query. Skipping is safe
# because we declare bounds explicitly in config.yaml.
#
# IMPORTANT: connect via pooler-port-5432 (session mode), NOT 6543. The
# 6543 transaction mode times out Martin's keep-alive; the direct host
# (db.<ref>.supabase.co) is no longer exposed for new Supabase projects.
#
# On Windows + Git Bash, prefix with MSYS_NO_PATHCONV=1 so /config.yaml
# isn't mangled into a Windows path before reaching the container.

docker run --rm -p 3001:3000 \
  -e DATABASE_URL_POOLED='postgresql://martin_reader.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
  martin:phase2 --config /config.yaml --auto-bounds skip
```

Smoke test:

```bash
curl -I 'http://localhost:3001/gfw_alerts_mvt/4/7/7?from=2025-01-01&to=2025-12-31'
# expect: Content-Type: application/x-protobuf, non-empty Content-Length
```

## Cloud Run deploy

Manual for Phase 2 (no automation required for sign-off):

```bash
gcloud run deploy martin \
  --source infra/cloudrun/martin \
  --region $GCP_REGION \
  --set-env-vars DATABASE_URL_POOLED='postgresql://martin_reader.<ref>:<pw>@<region>.pooler.supabase.com:5432/postgres' \
  --command=martin --args='--config,/config.yaml,--auto-bounds,skip' \
  --allow-unauthenticated
```

Then point the Nuxt app at the Cloud Run URL via the
`NUXT_PUBLIC_MARTIN_BASE_URL` env var on Vercel.

## Connection-role security

The public Martin URL exposes whatever the connecting Postgres role can
SELECT. The gfw_alerts_mvt SQL function is `GRANTed EXECUTE TO anon`, so:

- **Use** the `anon` role from your Supabase pooler URL, or
- **Create** a dedicated `martin_reader` role with `EXECUTE` on
  `gfw_alerts_mvt` and `SELECT` on `alerts_gfw`, nothing else.
- **Never** use `service_role` -- the entire database becomes drainable
  through the open MVT endpoint.

If you need to verify which role a deployed Martin instance is using:

```bash
psql $DATABASE_URL -c "SELECT usename FROM pg_stat_activity WHERE application_name LIKE '%martin%'"
```
