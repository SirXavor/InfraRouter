import os

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./infrarouter.db")

WG_HUB_IP = os.environ.get("WG_HUB_IP", "192.168.254.1")
WG_PEER_SUBNET = os.environ.get("WG_PEER_SUBNET", "192.168.254.0/24")

# GRE addressing is derived from WireGuard peer index X:
# Hub GRE end:  10.0.X.1/30
# Spoke GRE end: 10.0.X.2/30
GRE_BASE = os.environ.get("GRE_BASE", "10.0")

SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "60"))
OFFLINE_THRESHOLD_SECONDS = int(os.environ.get("OFFLINE_THRESHOLD_SECONDS", "300"))
