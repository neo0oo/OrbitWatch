import logging
import time

import uvicorn
from fastapi import FastAPI

from app.config import GIT_SHA, PORT
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("orbitwatch")

app = FastAPI(title="OrbitWatch propagation")


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code, ms)
    return response


@app.get("/health")
def health():
    return {"status": "ok", "version": GIT_SHA}


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
