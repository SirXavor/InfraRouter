from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db import crud
from ..db.models import DeviceStatus
from ..schemas import EnrollRequest, SyncRequest, SyncResponse

router = APIRouter()


@router.post("/enroll", status_code=200)
def enroll(req: EnrollRequest, db: Session = Depends(get_db)):
    device = crud.create_enrollment(db, req.device_id, req.token, req.hostname)
    return {"enrolled": True, "device_id": device.device_id, "status": device.status}


@router.post("/{device_id}/sync")
def sync(device_id: str, req: SyncRequest, db: Session = Depends(get_db)) -> SyncResponse:
    device = crud.get_device(db, device_id)
    if not device or device.status != DeviceStatus.approved:
        raise HTTPException(status_code=403, detail="device not approved")

    crud.record_heartbeat(db, device_id, req.applied_version, req.status)

    if req.applied_version >= device.config_version:
        return SyncResponse(version=device.config_version, config=None)

    # TODO: build full config payload (step 3)
    config_payload: dict = {}
    return SyncResponse(version=device.config_version, config=config_payload)
