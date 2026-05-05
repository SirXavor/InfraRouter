from fastapi import APIRouter, HTTPException
from ..models import EnrollRequest, SyncRequest, SyncResponse

router = APIRouter()


@router.post("/enroll")
def enroll(req: EnrollRequest):
    """Device calls this on first boot with its ID and initial token."""
    # TODO: persist enrollment request, return ack
    return {"enrolled": True, "device_id": req.device_id}


@router.post("/{device_id}/sync")
def sync(device_id: str, req: SyncRequest) -> SyncResponse:
    """
    Single round-trip sync endpoint.
    Device reports its applied_version; server returns new config only if version changed.
    Also records heartbeat (last_seen, applied_version).
    """
    # TODO: load device config_version and config from DB
    # TODO: update device last_seen and applied_version
    config_version = 0
    if req.applied_version < config_version:
        # TODO: build and return full config
        return SyncResponse(version=config_version, config={})
    return SyncResponse(version=config_version, config=None)
