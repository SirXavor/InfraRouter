from fastapi import FastAPI
from .routes import devices, config, admin

app = FastAPI(title="InfraRouter API")

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(config.router, prefix="/config", tags=["config"])


@app.get("/health")
def health():
    return {"status": "ok"}
