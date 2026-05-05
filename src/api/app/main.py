from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db.database import init_db
from .routes import devices, config, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="InfraRouter API", lifespan=lifespan)

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(config.router, prefix="/config", tags=["config"])


@app.get("/health")
def health():
    return {"status": "ok"}
