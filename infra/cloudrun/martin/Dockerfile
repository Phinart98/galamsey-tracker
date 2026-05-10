# Martin v0.13.x: function-source signature is (z, x, y, query_params json).
# If a newer Martin drops this convention the gfw_alerts_mvt SQL function
# in 0003_alerts_gfw.sql must be updated to match.
FROM ghcr.io/maplibre/martin:v0.13.0
COPY config.yaml /config.yaml
EXPOSE 3000
# --auto-bounds skip is mandatory against Supabase: without it, Martin's
# pg_class scan for geometry columns hangs past PgBouncer's transaction
# timeout. We declare bounds explicitly in config.yaml anyway.
CMD ["--config", "/config.yaml", "--auto-bounds", "skip"]
