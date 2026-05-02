from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Galamsey Tracker API",
    description="Open-source platform tracking illegal artisanal gold mining in Ghana.",
    version="0.1.0",
    license_info={"name": "AGPL-3.0", "url": "https://www.gnu.org/licenses/agpl-3.0.txt"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://galamseytracker.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
