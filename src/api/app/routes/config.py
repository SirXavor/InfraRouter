from fastapi import APIRouter
from ..models import GlobalConfig, LocalConfig

router = APIRouter()


@router.get("/global")
def get_global_config() -> GlobalConfig:
    # TODO: load from DB
    return GlobalConfig()


@router.put("/global")
def set_global_config(cfg: GlobalConfig):
    # TODO: persist, bump config_version on all approved devices
    return {"updated": True}


@router.get("/{device_id}/local")
def get_local_config(device_id: str) -> LocalConfig:
    # TODO: load from DB
    raise NotImplementedError


@router.put("/{device_id}/local")
def set_local_config(device_id: str, cfg: LocalConfig):
    # TODO: persist, bump device config_version
    return {"updated": True}
