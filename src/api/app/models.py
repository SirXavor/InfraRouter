from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class DeviceStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class SyncStatus(str, Enum):
    synced = "synced"
    pending = "pending"
    offline = "offline"
    error = "error"


class EnrollRequest(BaseModel):
    device_id: str
    token: str
    hostname: Optional[str] = None


class SyncRequest(BaseModel):
    applied_version: int
    status: Optional[str] = "ok"


class SyncResponse(BaseModel):
    version: int
    config: Optional[dict] = None  # None means no change


class LocalConfig(BaseModel):
    lan_network: str  # e.g. "192.168.2.0/24"
    lan_ip: str       # e.g. "192.168.2.1"


class GlobalConfig(BaseModel):
    dns_servers: list[str] = []
    ntp_servers: list[str] = []
    pxe_tftp_server: Optional[str] = None
    pxe_boot_file_bios: Optional[str] = "undionly.kpxe"
    pxe_boot_file_efi: Optional[str] = "ipxe.efi"


class DeviceInfo(BaseModel):
    device_id: str
    token: str
    hostname: Optional[str] = None
    status: DeviceStatus = DeviceStatus.pending
    wg_peer_index: Optional[int] = None   # X in 192.168.254.X
    config_version: int = 0
    applied_version: int = 0
    last_seen: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.offline
