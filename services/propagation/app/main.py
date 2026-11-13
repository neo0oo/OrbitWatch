import uvicorn
from fastapi import FastAPI

from app.config import PORT
from app.routes import router

app = FastAPI(title="OrbitWatch propagation")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
