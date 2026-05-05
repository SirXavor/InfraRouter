import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db import crud
from ..db.models import DeviceStatus
from ..schemas import DeviceOut
from ..wg import generate_keypair
from .. import wg_hub

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(status: DeviceStatus | None = None, db: Session = Depends(get_db)):
    return crud.list_devices(db, status)


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return device


@router.post("/devices/{device_id}/approve", response_model=DeviceOut)
def approve_device(device_id: str, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    if device.status != DeviceStatus.pending:
        raise HTTPException(status_code=400, detail=f"device is {device.status.value}, expected pending")

    peer_index = crud.get_next_peer_index(db)
    private_key, public_key = generate_keypair()

    device = crud.approve_device(db, device_id, peer_index, private_key, public_key)
    try:
        wg_hub.add_peer(public_key, peer_index)
    except Exception as e:
        log.warning("wg: add_peer failed for %s: %s", device_id, e)
    return device


@router.post("/devices/{device_id}/reject", response_model=DeviceOut)
def reject_device(device_id: str, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    if device.status == DeviceStatus.approved:
        raise HTTPException(status_code=400, detail="use DELETE to revoke an approved device")
    return crud.set_device_status(db, device_id, DeviceStatus.rejected)


@router.delete("/devices/{device_id}", response_model=DeviceOut)
def revoke_device(device_id: str, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    if device.wg_public_key:
        try:
            wg_hub.remove_peer(device.wg_public_key)
        except Exception as e:
            log.warning("wg: remove_peer failed for %s: %s", device_id, e)
    return crud.set_device_status(db, device_id, DeviceStatus.revoked)
