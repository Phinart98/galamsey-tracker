# TiTiler raster tile server

Serves XYZ raster tiles from Cloud Optimised GeoTIFFs stored on Cloudflare R2.
Used by the Sentinel-1 SAR methodology page to render the +1.65 dB delta dB
heatmap from `r2://galamsey-static/cog/sentinel1/{YYYY-MM}.tif`.

## Endpoint shape

```
GET /cog/info?url=<cog-url>
GET /cog/tilejson.json?url=<cog-url>&rescale=-3,3&colormap_name=rdbu_r
GET /cog/tiles/{z}/{x}/{y}@2x.png?url=<cog-url>&rescale=-3,3&colormap_name=rdbu_r
GET /cog/preview.png?url=<cog-url>&rescale=-3,3&colormap_name=rdbu_r
```

`url` can be either a fully public HTTPS URL to the COG (preferred -- one
extra step on a Cloudflare custom domain or `.r2.dev`) or an `s3://bucket/key`
URI when the service has R2 credentials set.

## Local development

```bash
cd infra/cloudrun/titiler
docker build -t titiler:phase3 .

# IMPORTANT: COG URLs we feed it should already be publicly resolvable
# (catalog.json publishes the public URL). If they're not, set the env vars
# below so GDAL can hit R2 via /vsis3/ with credentials.

docker run --rm -p 8080:8080 \
  -e AWS_S3_ENDPOINT=<account-id>.r2.cloudflarestorage.com \
  -e AWS_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY \
  -e AWS_REGION=auto \
  titiler:phase3
```

Smoke test:

```bash
COG_URL=https://galamsey-static.<account-id>.r2.dev/cog/sentinel1/2026-04.tif
curl "http://localhost:8080/cog/info?url=${COG_URL}" | jq .
# expect: 3 bands, dtype float32, bounds within Ghana

curl -o /tmp/preview.png \
  "http://localhost:8080/cog/preview.png?url=${COG_URL}&rescale=-3,3&colormap_name=rdbu_r"
# expect: PNG showing red blotches over SW mining corridors
```

## Cloud Run deploy

```bash
gcloud run deploy titiler \
  --source infra/cloudrun/titiler \
  --region $GCP_REGION \
  --allow-unauthenticated \
  --memory 1Gi \
  --concurrency 80 \
  --max-instances 5
```

If the COGs in R2 are kept private, also pass:

```bash
  --set-env-vars "AWS_S3_ENDPOINT=<account-id>.r2.cloudflarestorage.com,AWS_REGION=auto" \
  --set-secrets "AWS_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest,AWS_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest"
```

(The simpler default of public-by-default R2 URLs avoids the secret indirection
entirely; only switch if you want to enforce signed access from the methodology
page.)

## Security note

This is a public read endpoint. Anyone who knows the COG URL can request
tiles. The catalog.json on R2 is the only place URLs are published, and
catalog publication is gated by the pipeline (no manual upload step). If you
later need access control, wrap with Cloudflare Access at the load balancer
rather than baking auth into TiTiler itself -- the upstream image has no
out-of-the-box auth and forking it is not worth the surface.
