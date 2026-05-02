# Migrations — conventions

Schema changes live here as numbered SQL files applied via Supabase CLI
(`supabase db push`). The full database design rationale is in the plan
at section 3a.

---

## File naming

```
NNNN_short_description.sql
```

`NNNN` is a zero-padded four-digit integer, incremented by one per migration.
Every migration is paired with a pgTAP test at
`infra/supabase/tests/NNNN_short_description_test.sql`.

**Never edit a shipped migration.** Create a new one instead.

---

## Geometry conventions

- All geometries stored in **EPSG:4326** (WGS84) throughout the schema.
- Use **`GEOGRAPHY`** for distance computations (great-circle, accurate at
  Ghana scale — ~800 km north-south).
- Use **`GEOMETRY`** for clipping, tile generation, and spatial joins
  (planar, faster, accurate enough at the Ghana bounding box).
- Every `geom` column gets a **`GIST` index** immediately after column
  creation:
  ```sql
  CREATE INDEX ON table_name USING GIST (geom);
  ```
- After any large bulk load, run `CLUSTER` on the GIST index once to
  physically reorder rows for spatial locality.

---

## Index conventions

- Spatial: `GIST` on every `geom` column. Always.
- Time-series tables: composite `B-tree` on `(date DESC, confidence DESC)`.
- Moderator-path tables: **partial** indexes on hot query predicates
  (e.g. `WHERE status = 'pending'`) — smaller and faster than full indexes.
- Full-text: `GIN` on stored `tsvector` generated columns.
- Don't over-index. Drop any index with zero scans after 30 days
  (`pg_stat_user_indexes.idx_scan`).

---

## Partitioning conventions

`alerts_gfw` and `alerts_sar` use **declarative range partitioning by
month** from migration 0003 onwards. `pg_partman` is NOT available on
Supabase Cloud (verified 2025-05). Use the custom
`ensure_alert_partitions()` pg_cron function defined in 0003 to create
monthly child tables.

Detach partitions older than 5 years and archive to Cloudflare R2 as
Parquet (queryable via DuckDB). Run as a yearly pg_cron job.

---

## Row-Level Security (RLS) conventions

RLS is enabled on every table from migration 0001. The default is
**DENY ALL**. Policies are always defined in the same migration as the
table, not added later.

Standard policy matrix:

| Table type | anon SELECT | authenticated SELECT | INSERT | UPDATE/DELETE |
|---|---|---|---|---|
| Public data (`alerts_*`, `boundaries`, `incidents`) | All rows | All rows | service_role only | service_role only |
| `reports` | `WHERE status = 'approved'` | own rows + approved | anon (rate-limited at API) | moderator role |
| `profiles` | none | own row | own row | own row |

Test every RLS policy in the paired pgTAP test using
`SET LOCAL ROLE anon` / `SET LOCAL ROLE authenticated`.

---

## Bulk ingestion pattern

Pipelines load 1K–50K rows per run. Pattern:

1. `UNLOGGED` staging table (no WAL, no indexes).
2. `COPY FROM STDIN` into staging.
3. Validation pass in SQL against staging.
4. Single transaction: `INSERT ... ON CONFLICT (alert_uid) DO NOTHING`.
5. `TRUNCATE` staging.

`alert_uid` = `encode(digest(source || alert_date::text || lat || lon, 'md5'), 'hex')` — unique per source/date/location, makes re-runs idempotent.

---

## Connection pooling

| Port | Mode | Used by |
|---|---|---|
| 5432 (direct) | Session | Migrations, pipelines, `LISTEN`/`NOTIFY` |
| 6543 (PgBouncer) | Transaction | FastAPI request handlers |

FastAPI uses psycopg3 with `NullPool` on port 6543. psycopg3 does not
auto-prepare statements, avoiding the asyncpg + PgBouncer crash
(Supabase issue #39227).

---

## pgTAP test conventions

Each migration's paired test:

1. Wraps all assertions in `BEGIN` / `ROLLBACK` so the test database is
   never modified.
2. Asserts column existence, NOT NULL constraints, CHECK constraints, and
   FK references using pgTAP `has_column`, `col_not_null`, etc.
3. Tests RLS: `SET LOCAL ROLE anon; SELECT is(count(*), ...)`.
4. Tests index presence using `has_index`.
5. Tests the canonical query for that table uses the expected index by
   parsing `EXPLAIN (FORMAT JSON, ANALYZE FALSE)` output.

Run tests locally: `pg_prove -d galamsey_test infra/supabase/tests/`.
Run in CI: see `.github/workflows/ci.yml` `test-migrations` job.
