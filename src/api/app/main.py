import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db.database import init_db, SessionLocal
from .db import crud
from .db.models import DeviceStatus
from . import wg_hub
from .routes import devices, config, admin, panel

log = logging.getLogger(__name__)

RECONCILE_INTERVAL = 30  # seconds


async def _reconcile_loop():
    while True:
        await asyncio.sleep(RECONCILE_INTERVAL)
        try:
            db = SessionLocal()
            approved = crud.list_devices(db, DeviceStatus.approved)
            wg_hub.reconcile(approved)
        except Exception as e:
            log.warning("reconcile error: %s", e)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(_reconcile_loop())
    yield


app = FastAPI(title="InfraRouter API", lifespan=lifespan)

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(config.router, prefix="/config", tags=["config"])
app.include_router(panel.router, prefix="/panel", tags=["panel"])


@app.get("/health")
def health():
    return {"status": "ok"}
