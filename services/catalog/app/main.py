import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import ALLOWED_ORIGINS, GIT_SHA, PORT
from app.database import check_db, run_migrations
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("orbitwatch")


@asynccontextmanager
async def lifespan(app):
    run_migrations()
    yield


app = FastAPI(title="OrbitWatch catalog", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code, ms)
    return response


@app.get("/health")
def health():
    ok = check_db()
    body = {"status": "ok" if ok else "unavailable", "db": "ok" if ok else "error", "version": GIT_SHA}
    return JSONResponse(body, status_code=200 if ok else 503)


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
