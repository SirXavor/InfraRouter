from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from .models import Device, DeviceLocalConfig, GlobalConfig, DeviceStatus


# ── Devices ──────────────────────────────────────────────────────────────────

def get_device(db: Session, device_id: str) -> Device | None:
    return db.scalar(select(Device).where(Device.device_id == device_id))


def list_devices(db: Session, status: DeviceStatus | None = None) -> list[Device]:
    q = select(Device)
    if status:
        q = q.where(Device.status == status)
    return list(db.scalars(q).all())


def create_enrollment(db: Session, device_id: str, token: str, hostname: str | None) -> Device:
    existing = get_device(db, device_id)
    if existing:
        # Re-enrollment: update token and reset to pending
        existing.token = token
        existing.hostname = hostname
        existing.status = DeviceStatus.pending
        db.commit()
        db.refresh(existing)
        return existing
    device = Device(device_id=device_id, token=token, hostname=hostname)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def get_next_peer_index(db: Session) -> int:
    used = set(
        db.scalars(
            select(Device.wg_peer_index).where(Device.wg_peer_index.is_not(None))
        ).all()
    )
    # Start at 2 (1 is the hub), skip reserved (0, 1, 254, 255)
    for i in range(2, 254):
        if i not in used:
            return i
    raise RuntimeError("no peer indexes available")


def approve_device(
    db: Session,
    device_id: str,
    wg_peer_index: int,
    wg_private_key: str,
    wg_public_key: str,
) -> Device:
    device = get_device(db, device_id)
    if not device:
        raise ValueError(f"device {device_id} not found")
    device.status = DeviceStatus.approved
    device.wg_peer_index = wg_peer_index
    device.wg_private_key = wg_private_key
    device.wg_public_key = wg_public_key
    device.config_version = 1
    db.commit()
    db.refresh(device)
    return device


def set_device_status(db: Session, device_id: str, status: DeviceStatus) -> Device:
    device = get_device(db, device_id)
    if not device:
        raise ValueError(f"device {device_id} not found")
    device.status = status
    db.commit()
    db.refresh(device)
    return device


def bump_config_version(db: Session, device_id: str) -> Device:
    device = get_device(db, device_id)
    if not device:
        raise ValueError(f"device {device_id} not found")
    device.config_version += 1
    db.commit()
    db.refresh(device)
    return device


def bump_all_config_versions(db: Session) -> int:
    result = db.execute(
        update(Device)
        .where(Device.status == DeviceStatus.approved)
        .values(config_version=Device.config_version + 1)
    )
    db.commit()
    return result.rowcount


def record_heartbeat(db: Session, device_id: str, applied_version: int, status: str) -> Device:
    device = get_device(db, device_id)
    if not device:
        raise ValueError(f"device {device_id} not found")
    device.applied_version = applied_version
    device.last_seen = datetime.now(timezone.utc)
    device.last_sync_status = status
    db.commit()
    db.refresh(device)
    return device


# ── Local config ──────────────────────────────────────────────────────────────

def get_local_config(db: Session, device_id: str) -> DeviceLocalConfig | None:
    return db.scalar(
        select(DeviceLocalConfig).where(DeviceLocalConfig.device_id == device_id)
    )


def set_local_config(db: Session, device_id: str, lan_network: str, lan_ip: str) -> DeviceLocalConfig:
    cfg = get_local_config(db, device_id)
    if cfg:
        cfg.lan_network = lan_network
        cfg.lan_ip = lan_ip
    else:
        cfg = DeviceLocalConfig(device_id=device_id, lan_network=lan_network, lan_ip=lan_ip)
        db.add(cfg)
    db.commit()
    db.refresh(cfg)
    bump_config_version(db, device_id)
    return cfg


# ── Global config ─────────────────────────────────────────────────────────────

def get_global_config(db: Session) -> GlobalConfig:
    cfg = db.scalar(select(GlobalConfig).where(GlobalConfig.id == 1))
    if not cfg:
        cfg = GlobalConfig(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def set_global_config(db: Session, **kwargs) -> GlobalConfig:
    cfg = get_global_config(db)
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    cfg.version += 1
    db.commit()
    db.refresh(cfg)
    bump_all_config_versions(db)
    return cfg
