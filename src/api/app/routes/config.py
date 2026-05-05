from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db import crud
from ..schemas import GlobalConfigIn, LocalConfigIn

router = APIRouter()


@router.get("/global")
def get_global_config(db: Session = Depends(get_db)):
    return crud.get_global_config(db)


@router.put("/global")
def set_global_config(cfg: GlobalConfigIn, db: Session = Depends(get_db)):
    return crud.set_global_config(db, **cfg.model_dump())


@router.get("/{device_id}/local")
def get_local_config(device_id: str, db: Session = Depends(get_db)):
    cfg = crud.get_local_config(db, device_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="no local config for device")
    return cfg


@router.put("/{device_id}/local")
def set_local_config(device_id: str, cfg: LocalConfigIn, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="device not found")
    return crud.set_local_config(db, device_id, cfg.lan_network, cfg.lan_ip)
