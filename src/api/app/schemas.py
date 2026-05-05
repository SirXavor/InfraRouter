from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel, computed_field
from .db.models import DeviceStatus
from .settings import OFFLINE_THRESHOLD_SECONDS


class EnrollRequest(BaseModel):
    device_id: str
    token: str
    hostname: Optional[str] = None


class SyncRequest(BaseModel):
    applied_version: int
    status: str = "ok"


class SyncResponse(BaseModel):
    version: int
    config: Optional[dict] = None  # None = no change


class LocalConfigIn(BaseModel):
    lan_network: str  # e.g. 192.168.2.0/24
    lan_ip: str       # e.g. 192.168.2.1


class GlobalConfigIn(BaseModel):
    dns_servers: list[str] = []
    ntp_servers: list[str] = []
    pxe_tftp_server: Optional[str] = None
    pxe_boot_file_bios: str = "undionly.kpxe"
    pxe_boot_file_efi: str = "ipxe.efi"


class DeviceOut(BaseModel):
    device_id: str
    hostname: Optional[str]
    status: DeviceStatus
    token: str
    wg_peer_index: Optional[int]
    config_version: int
    applied_version: int
    last_seen: Optional[datetime]
    last_sync_status: Optional[str]

    @computed_field
    @property
    def sync_status(self) -> str:
        if self.status != DeviceStatus.approved:
            return "n/a"
        if self.last_seen is None:
            return "offline"
        threshold = timedelta(seconds=OFFLINE_THRESHOLD_SECONDS)
        if datetime.now(timezone.utc) - self.last_seen > threshold:
            return "offline"
        if self.applied_version < self.config_version:
            return "pending"
        return "synced"

    model_config = {"from_attributes": True}
