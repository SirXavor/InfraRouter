from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
import enum


class DeviceStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    revoked = "revoked"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String)
    status: Mapped[DeviceStatus] = mapped_column(
        SAEnum(DeviceStatus), default=DeviceStatus.pending, nullable=False
    )

    # Assigned on approval
    wg_peer_index: Mapped[int | None] = mapped_column(Integer, unique=True)
    wg_private_key: Mapped[str | None] = mapped_column(String)
    wg_public_key: Mapped[str | None] = mapped_column(String)

    # Config versioning
    config_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applied_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    last_sync_status: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    local_config: Mapped["DeviceLocalConfig | None"] = relationship(
        back_populates="device", uselist=False, cascade="all, delete-orphan"
    )


class DeviceLocalConfig(Base):
    __tablename__ = "device_local_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(
        String, ForeignKey("devices.device_id", ondelete="CASCADE"), unique=True
    )
    lan_network: Mapped[str] = mapped_column(String, nullable=False)  # e.g. 192.168.2.0/24
    lan_ip: Mapped[str] = mapped_column(String, nullable=False)        # e.g. 192.168.2.1

    device: Mapped["Device"] = relationship(back_populates="local_config")


class GlobalConfig(Base):
    __tablename__ = "global_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    dns_servers: Mapped[list] = mapped_column(JSON, default=list)
    ntp_servers: Mapped[list] = mapped_column(JSON, default=list)
    pxe_tftp_server: Mapped[str | None] = mapped_column(String)
    pxe_boot_file_bios: Mapped[str] = mapped_column(String, default="undionly.kpxe")
    pxe_boot_file_efi: Mapped[str] = mapped_column(String, default="ipxe.efi")
    # Incremented when global config changes; triggers config_version bump on all devices
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
