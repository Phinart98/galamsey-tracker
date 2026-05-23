# TiTiler: dynamic raster tiles from Cloud Optimised GeoTIFFs.
#
# We use the developmentseed published image (FastAPI-based, GDAL pre-built),
# tuned for reading COGs over HTTP from Cloudflare R2. R2 is S3-compatible, so
# GDAL/VSI's /vsis3/ driver works with a custom endpoint and the AWS env vars
# below.
FROM ghcr.io/developmentseed/titiler:0.20.0

# GDAL VSI tuning for HTTP COG reads against R2:
#   - DISABLE_READDIR_ON_OPEN: GDAL otherwise lists the bucket on every open,
#     which fails on R2 unless explicit ListObjects perms exist; EMPTY_DIR
#     tells it to skip the listing and just open the file.
#   - VSI_CACHE + VSI_CACHE_SIZE: keep recently-read COG chunks hot so the
#     tile-fan-out doesn't refetch the same byte ranges.
#   - CPL_TMPDIR=/tmp: Cloud Run images are read-only outside /tmp.
#   - GDAL_HTTP_MULTIPLEX + GDAL_HTTP_VERSION: speeds up the parallel byte-
#     range fetches that COG tiling does.
#   - AWS_VIRTUAL_HOSTING=FALSE: R2 uses path-style addressing, not virtual-
#     hosted.
ENV GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR \
    VSI_CACHE=TRUE \
    VSI_CACHE_SIZE=536870912 \
    CPL_TMPDIR=/tmp \
    GDAL_HTTP_MULTIPLEX=YES \
    GDAL_HTTP_VERSION=2 \
    AWS_VIRTUAL_HOSTING=FALSE \
    AWS_S3_ENDPOINT="" \
    PORT=8080

EXPOSE 8080

# The published image's CMD already runs uvicorn with titiler.application.main:app.
# Keep it explicit so changes upstream don't silently shift the bind.
CMD ["uvicorn", "titiler.application.main:app", "--host", "0.0.0.0", "--port", "8080"]
