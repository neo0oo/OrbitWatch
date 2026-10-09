from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.catalog.routes import router as catalog_router
from app.config import PORT
from app.database import init_db
from app.propagation.routes import router as propagation_router

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="OrbitWatch", lifespan=lifespan)
app.include_router(catalog_router)
app.include_router(propagation_router)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)