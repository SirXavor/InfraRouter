from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .db.database import get_db
from .db import crud
from .db.models import Device, DeviceStatus

_bearer = HTTPBearer()


def get_device(
    device_id: str,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    db: Session = Depends(get_db),
) -> Device:
    device = crud.get_device(db, device_id)
    if not device or device.token != credentials.credentials:
        raise HTTPException(status_code=401, detail="invalid credentials")
    return device


def get_approved_device(device: Device = Depends(get_device)) -> Device:
    if device.status != DeviceStatus.approved:
        raise HTTPException(status_code=403, detail=f"device is {device.status.value}")
    return device
