import os

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./infrarouter.db")

# WireGuard hub
WG_HUB_IP = os.environ.get("WG_HUB_IP", "192.168.254.1")
WG_HUB_PUBLIC_KEY = os.environ.get("WG_HUB_PUBLIC_KEY", "")
WG_ENDPOINT = os.environ.get("WG_ENDPOINT", "")          # e.g. wg-hermes.manabo.org:443
WG_PEER_SUBNET = os.environ.get("WG_PEER_SUBNET", "192.168.254.0/24")
# Comma-separated list of CIDRs the spoke routes through the WireGuard tunnel
WG_ALLOWED_IPS = os.environ.get(
    "WG_ALLOWED_IPS", "192.168.0.0/16,10.0.0.0/8,10.42.0.0/16,10.43.0.0/16"
)

# GRE addressing derived from WireGuard peer index X:
#   Hub GRE end:   10.0.X.1  (point-to-point /30 → 10.0.X.0/30)
#   Spoke GRE end: 10.0.X.2
GRE_BASE = os.environ.get("GRE_BASE", "10.0")

# OSPF
OSPF_AREA = os.environ.get("OSPF_AREA", "0.0.0.0")

SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "60"))
OFFLINE_THRESHOLD_SECONDS = int(os.environ.get("OFFLINE_THRESHOLD_SECONDS", "300"))
