"""Tests for config payload generation."""
import pytest
from unittest.mock import patch

from app.config_builder import build_config
from app.db.models import Device, DeviceLocalConfig, GlobalConfig, DeviceStatus


def _device(index: int, priv: str = "priv-key") -> Device:
    d = Device()
    d.device_id = f"dev-{index}"
    d.token = "tok"
    d.status = DeviceStatus.approved
    d.wg_peer_index = index
    d.wg_private_key = priv
    d.wg_public_key = "pub-key"
    d.config_version = 1
    d.applied_version = 0
    return d


def _local(device_id: str, net: str, ip: str) -> DeviceLocalConfig:
    lc = DeviceLocalConfig()
    lc.device_id = device_id
    lc.lan_network = net
    lc.lan_ip = ip
    return lc


def _global(**kwargs) -> GlobalConfig:
    g = GlobalConfig()
    g.dns_servers = kwargs.get("dns_servers", [])
    g.ntp_servers = kwargs.get("ntp_servers", [])
    g.pxe_tftp_server = kwargs.get("pxe_tftp_server")
    g.pxe_boot_file_bios = kwargs.get("pxe_boot_file_bios", "undionly.kpxe")
    g.pxe_boot_file_efi = kwargs.get("pxe_boot_file_efi", "ipxe.efi")
    return g


HUB_PUB = "hub-pub-key-base64=="
ENDPOINT = "wg.example.com:443"

PATCH_SETTINGS = patch.multiple(
    "app.config_builder.settings",
    WG_HUB_PUBLIC_KEY=HUB_PUB,
    WG_ENDPOINT=ENDPOINT,
    WG_ALLOWED_IPS="192.168.0.0/16,10.0.0.0/8",
    GRE_BASE="10.0",
    OSPF_AREA="0.0.0.0",
)


@PATCH_SETTINGS
def test_wireguard_section():
    cfg = build_config(_device(3), None, _global())
    wg = cfg["wireguard"]
    assert wg["address"] == "192.168.254.3/32"
    assert wg["private_key"] == "priv-key"
    assert wg["endpoint"] == ENDPOINT
    assert wg["public_key"] == HUB_PUB
    assert "192.168.0.0/16" in wg["allowed_ips"]
    assert "10.0.0.0/8" in wg["allowed_ips"]


@PATCH_SETTINGS
def test_gre_section_derived_from_index():
    cfg = build_config(_device(5), None, _global())
    gre = cfg["gre"]
    assert gre["local_ip"] == "10.0.5.2"   # spoke end
    assert gre["remote_ip"] == "10.0.5.1"  # hub end
    assert gre["network"] == "10.0.5.0/30"


@PATCH_SETTINGS
def test_ospf_without_local_config():
    cfg = build_config(_device(7), None, _global())
    ospf = cfg["ospf"]
    assert ospf["router_id"] == "192.168.254.7"
    assert ospf["area"] == "0.0.0.0"
    assert "10.0.7.0/30" in ospf["networks"]
    assert len(ospf["networks"]) == 1  # only GRE network, no LAN yet


@PATCH_SETTINGS
def test_ospf_with_local_config():
    local = _local("dev-2", "192.168.2.0/24", "192.168.2.1")
    cfg = build_config(_device(2), local, _global())
    ospf = cfg["ospf"]
    assert "10.0.2.0/30" in ospf["networks"]
    assert "192.168.2.0/24" in ospf["networks"]
    assert len(ospf["networks"]) == 2


@PATCH_SETTINGS
def test_lan_none_without_local_config():
    cfg = build_config(_device(2), None, _global())
    assert cfg["lan"] is None


@PATCH_SETTINGS
def test_lan_present_with_local_config():
    local = _local("dev-2", "192.168.2.0/24", "192.168.2.1")
    cfg = build_config(_device(2), local, _global())
    assert cfg["lan"]["network"] == "192.168.2.0/24"
    assert cfg["lan"]["ip"] == "192.168.2.1"


@PATCH_SETTINGS
def test_pxe_none_when_no_tftp():
    cfg = build_config(_device(2), None, _global())
    assert cfg["pxe"] is None


@PATCH_SETTINGS
def test_pxe_present_when_tftp_configured():
    gcfg = _global(pxe_tftp_server="192.168.254.1")
    cfg = build_config(_device(2), None, gcfg)
    pxe = cfg["pxe"]
    assert pxe["tftp_server"] == "192.168.254.1"
    assert pxe["file_bios"] == "undionly.kpxe"
    assert pxe["file_efi"] == "ipxe.efi"


@PATCH_SETTINGS
def test_dns_and_ntp_forwarded():
    gcfg = _global(dns_servers=["1.1.1.1", "8.8.8.8"], ntp_servers=["pool.ntp.org"])
    cfg = build_config(_device(2), None, gcfg)
    assert cfg["dns"] == ["1.1.1.1", "8.8.8.8"]
    assert cfg["ntp"] == ["pool.ntp.org"]


@PATCH_SETTINGS
def test_sync_endpoint_returns_full_payload(client):
    """Integration: sync endpoint returns the builder output when version differs."""
    client.post("/devices/enroll", json={"device_id": "dev-x", "token": "tok-x"})
    client.post("/admin/devices/dev-x/approve")
    client.put("/config/dev-x/local", json={"lan_network": "192.168.9.0/24", "lan_ip": "192.168.9.1"})
    client.put("/config/global", json={"pxe_tftp_server": "192.168.254.1"})

    r = client.post(
        "/devices/dev-x/sync",
        json={"applied_version": 0},
        headers={"Authorization": "Bearer tok-x"},
    )
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert cfg["wireguard"]["address"] == "192.168.254.2/32"
    assert cfg["gre"]["local_ip"] == "10.0.2.2"
    assert cfg["lan"]["ip"] == "192.168.9.1"
    assert cfg["pxe"]["tftp_server"] == "192.168.254.1"
    assert "192.168.9.0/24" in cfg["ospf"]["networks"]
