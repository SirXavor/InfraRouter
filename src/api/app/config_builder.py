"""
Builds the JSON config payload delivered to the agent on each sync.

All addressing is derived deterministically from the peer index (X):
  WireGuard spoke IP : 192.168.254.X/32
  GRE hub end        : 10.0.X.1/30
  GRE spoke end      : 10.0.X.2/30
  GRE network        : 10.0.X.0/30
  OSPF router-id     : 192.168.254.X
"""
from . import settings
from .db.models import Device, DeviceLocalConfig, GlobalConfig


def build_config(
    device: Device,
    local: DeviceLocalConfig | None,
    global_cfg: GlobalConfig,
) -> dict:
    x = device.wg_peer_index

    wg = _wireguard(device, x)
    gre = _gre(x)
    ospf = _ospf(x, local)
    lan = _lan(local)
    pxe = _pxe(global_cfg)
    dns = global_cfg.dns_servers or []
    ntp = global_cfg.ntp_servers or []

    return {
        "wireguard": wg,
        "gre": gre,
        "ospf": ospf,
        "lan": lan,
        "pxe": pxe,
        "dns": dns,
        "ntp": ntp,
    }


# ── Section builders ──────────────────────────────────────────────────────────

def _wireguard(device: Device, x: int) -> dict:
    return {
        "private_key": device.wg_private_key,
        "address": f"192.168.254.{x}/32",
        "endpoint": settings.WG_ENDPOINT,
        "public_key": settings.WG_HUB_PUBLIC_KEY,
        "allowed_ips": [s.strip() for s in settings.WG_ALLOWED_IPS.split(",") if s.strip()],
    }


def _gre(x: int) -> dict:
    base = settings.GRE_BASE          # e.g. "10.0"
    return {
        "local_ip": f"{base}.{x}.2",  # spoke end
        "remote_ip": f"{base}.{x}.1", # hub end
        "network": f"{base}.{x}.0/30",
    }


def _ospf(x: int, local: DeviceLocalConfig | None) -> dict:
    networks = [f"{settings.GRE_BASE}.{x}.0/30"]
    if local:
        networks.append(local.lan_network)
    return {
        "router_id": f"192.168.254.{x}",
        "area": settings.OSPF_AREA,
        "networks": networks,
    }


def _lan(local: DeviceLocalConfig | None) -> dict | None:
    if not local:
        return None
    return {
        "network": local.lan_network,
        "ip": local.lan_ip,
    }


def _pxe(global_cfg: GlobalConfig) -> dict | None:
    if not global_cfg.pxe_tftp_server:
        return None
    return {
        "tftp_server": global_cfg.pxe_tftp_server,
        "file_bios": global_cfg.pxe_boot_file_bios,
        "file_efi": global_cfg.pxe_boot_file_efi,
    }
