import logging
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, Form
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db import crud
from ..db.models import DeviceStatus
from ..schemas import DeviceOut
from ..wg import generate_keypair
from .. import wg_hub

log = logging.getLogger(__name__)

router = APIRouter(default_response_class=HTMLResponse)
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _redirect(url: str, msg: str = "") -> RedirectResponse:
    if msg:
        url += f"?msg={quote(msg)}"
    return RedirectResponse(url, status_code=303)


# ── Pages ─────────────────────────────────────────────────────────────────────

@router.get("/")
def devices_page(request: Request, msg: str = "", db: Session = Depends(get_db)):
    devices = [DeviceOut.model_validate(d) for d in crud.list_devices(db, DeviceStatus.approved)]
    pending_count = len(crud.list_devices(db, DeviceStatus.pending))
    return templates.TemplateResponse(request, "devices.html", {
        "devices": devices, "msg": msg, "active": "devices", "pending_count": pending_count,
    })


@router.get("/pending")
def pending_page(request: Request, msg: str = "", db: Session = Depends(get_db)):
    pending = crud.list_devices(db, DeviceStatus.pending)
    rejected = crud.list_devices(db, DeviceStatus.rejected)
    pending_count = len(pending)
    return templates.TemplateResponse(request, "pending.html", {
        "pending": pending, "rejected": rejected,
        "msg": msg, "active": "pending", "pending_count": pending_count,
    })


@router.get("/global")
def global_page(request: Request, msg: str = "", db: Session = Depends(get_db)):
    cfg = crud.get_global_config(db)
    pending_count = len(crud.list_devices(db, DeviceStatus.pending))
    return templates.TemplateResponse(request, "global.html", {
        "cfg": cfg,
        "dns": ", ".join(cfg.dns_servers or []),
        "ntp": ", ".join(cfg.ntp_servers or []),
        "msg": msg, "active": "global", "pending_count": pending_count,
    })


@router.get("/devices/{device_id}")
def device_page(device_id: str, request: Request, msg: str = "", db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if not device:
        return _redirect("/panel/")
    local = crud.get_local_config(db, device_id)
    pending_count = len(crud.list_devices(db, DeviceStatus.pending))
    return templates.TemplateResponse(request, "device.html", {
        "device": DeviceOut.model_validate(device),
        "local": local,
        "msg": msg, "active": "devices", "pending_count": pending_count,
    })


# ── Actions ───────────────────────────────────────────────────────────────────

@router.post("/devices/{device_id}/approve")
def approve(device_id: str, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if device and device.status == DeviceStatus.pending:
        peer_index = crud.get_next_peer_index(db)
        private_key, public_key = generate_keypair()
        crud.approve_device(db, device_id, peer_index, private_key, public_key)
        try:
            wg_hub.add_peer(public_key, peer_index)
        except Exception as e:
            log.warning("wg: add_peer failed for %s: %s", device_id, e)
    return _redirect("/panel/pending", f"Device {device_id} approved")


@router.post("/devices/{device_id}/reject")
def reject(device_id: str, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if device and device.status == DeviceStatus.pending:
        crud.set_device_status(db, device_id, DeviceStatus.rejected)
    return _redirect("/panel/pending", f"Device {device_id} rejected")


@router.post("/devices/{device_id}/revoke")
def revoke(device_id: str, db: Session = Depends(get_db)):
    device = crud.get_device(db, device_id)
    if device:
        if device.wg_public_key:
            try:
                wg_hub.remove_peer(device.wg_public_key)
            except Exception as e:
                log.warning("wg: remove_peer failed for %s: %s", device_id, e)
        crud.set_device_status(db, device_id, DeviceStatus.revoked)
    return _redirect("/panel/", f"Device {device_id} revoked")


@router.post("/devices/{device_id}/local")
def set_local(
    device_id: str,
    lan_network: str = Form(...),
    lan_ip: str = Form(...),
    db: Session = Depends(get_db),
):
    crud.set_local_config(db, device_id, lan_network, lan_ip)
    return _redirect(f"/panel/devices/{device_id}", "Local config saved. Config version bumped.")


@router.post("/global")
def set_global(
    dns: str = Form(""),
    ntp: str = Form(""),
    pxe_tftp_server: str = Form(""),
    pxe_boot_file_bios: str = Form("undionly.kpxe"),
    pxe_boot_file_efi: str = Form("ipxe.efi"),
    db: Session = Depends(get_db),
):
    dns_list = [s.strip() for s in dns.split(",") if s.strip()]
    ntp_list = [s.strip() for s in ntp.split(",") if s.strip()]
    crud.set_global_config(
        db,
        dns_servers=dns_list,
        ntp_servers=ntp_list,
        pxe_tftp_server=pxe_tftp_server or None,
        pxe_boot_file_bios=pxe_boot_file_bios,
        pxe_boot_file_efi=pxe_boot_file_efi,
    )
    return _redirect("/panel/global", "Global config saved. All device versions bumped.")
