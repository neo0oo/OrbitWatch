from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.config import PORT
from app.database import init_db
from app.routes import router


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="OrbitWatch catalog", lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
