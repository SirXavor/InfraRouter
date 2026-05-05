from fastapi import APIRouter
from ..models import DeviceInfo, DeviceStatus

router = APIRouter()


@router.get("/devices")
def list_devices(status: DeviceStatus = None) -> list[DeviceInfo]:
    # TODO: load from DB, filter by status
    return []


@router.post("/devices/{device_id}/approve")
def approve_device(device_id: str):
    """
    Approve a pending enrollment.
    Triggers: WireGuard peer creation, GRE address assignment, initial config generation.
    """
    # TODO: assign wg_peer_index, generate WireGuard keypair, build initial config
    return {"approved": True, "device_id": device_id}


@router.post("/devices/{device_id}/reject")
def reject_device(device_id: str):
    return {"rejected": True, "device_id": device_id}


@router.delete("/devices/{device_id}")
def revoke_device(device_id: str):
    """Remove device from the system and revoke its WireGuard peer."""
    # TODO: remove WireGuard peer, mark device revoked
    return {"revoked": True, "device_id": device_id}
