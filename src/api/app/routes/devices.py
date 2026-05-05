from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db import crud
from ..db.models import Device
from ..auth import get_device, get_approved_device
from ..schemas import EnrollRequest, SyncRequest, SyncResponse, DeviceOut

router = APIRouter()


@router.post("/enroll", status_code=200)
def enroll(req: EnrollRequest, db: Session = Depends(get_db)):
    device = crud.create_enrollment(db, req.device_id, req.token, req.hostname)
    return {"enrolled": True, "device_id": device.device_id, "status": device.status}


@router.get("/{device_id}/status", response_model=DeviceOut)
def device_status(device: Device = Depends(get_device)):
    """Agent polls this to know if it has been approved yet."""
    return device


@router.post("/{device_id}/sync")
def sync(
    req: SyncRequest,
    device: Device = Depends(get_approved_device),
    db: Session = Depends(get_db),
) -> SyncResponse:
    crud.record_heartbeat(db, device.device_id, req.applied_version, req.status)
    db.refresh(device)

    if req.applied_version >= device.config_version:
        return SyncResponse(version=device.config_version, config=None)

    # TODO step 3: build full config payload
    config_payload: dict = {}
    return SyncResponse(version=device.config_version, config=config_payload)
