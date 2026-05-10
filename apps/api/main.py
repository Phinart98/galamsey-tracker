import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import get_pool
from routers import alerts as alerts_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Skip pool startup when no DB is configured (test runs, local /health probes).
    # Production deployments always set DATABASE_URL_POOLED via Cloud Run env.
    if "DATABASE_URL_POOLED" not in os.environ:
        yield
        return
    pool = get_pool()
    await pool.open()
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="Galamsey Tracker API",
    description="Open-source platform tracking illegal artisanal gold mining in Ghana.",
    version="0.1.0",
    license_info={"name": "AGPL-3.0", "url": "https://www.gnu.org/licenses/agpl-3.0.txt"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://galamseytracker.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts_router.router, prefix="/alerts", tags=["alerts"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
