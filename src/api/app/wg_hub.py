"""
Direct WireGuard peer management on the hub.

Requires the InfraRouter pod to have:
  - hostNetwork: true
  - NET_ADMIN capability
  - wireguard-tools installed in the image

If wg is unavailable (dev/test environment), operations are logged and skipped.
"""
import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .db.models import Device

log = logging.getLogger(__name__)

WG_IFACE = "wg0"


def add_peer(public_key: str, peer_index: int) -> None:
    """Add a spoke peer to the hub's wg0 interface."""
    allowed_ips = f"192.168.254.{peer_index}/32"
    _wg("set", WG_IFACE, "peer", public_key,
        "allowed-ips", allowed_ips,
        "persistent-keepalive", "25")
    log.info("wg: added peer index=%d pubkey=%.20s...", peer_index, public_key)


def remove_peer(public_key: str) -> None:
    """Remove a spoke peer from the hub's wg0 interface."""
    _wg("set", WG_IFACE, "peer", public_key, "remove")
    log.info("wg: removed peer pubkey=%.20s...", public_key)


def current_peers() -> set[str]:
    """Return the set of public keys currently registered on wg0."""
    result = subprocess.run(
        ["wg", "show", WG_IFACE, "peers"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def reconcile(devices: "list[Device]") -> None:
    """
    Ensure wg0 has a peer entry for every approved device.
    Only adds missing peers — never removes peers not managed by InfraRouter,
    so wg-easy's own peers are left untouched.
    """
    try:
        live = current_peers()
    except Exception as e:
        log.warning("wg: could not list peers: %s", e)
        return

    for device in devices:
        if not device.wg_public_key:
            continue
        if device.wg_public_key not in live:
            try:
                add_peer(device.wg_public_key, device.wg_peer_index)
            except Exception as e:
                log.warning("wg: reconcile failed for %s: %s", device.device_id, e)


# ── Internal ──────────────────────────────────────────────────────────────────

def _wg(*args: str) -> None:
    result = subprocess.run(["wg"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"wg {' '.join(args)}: {result.stderr.strip()}")
