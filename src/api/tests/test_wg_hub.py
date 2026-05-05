"""Tests for wg_hub — all subprocess calls are mocked."""
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from app import wg_hub


def _make_result(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_add_peer_runs_correct_command():
    with patch("app.wg_hub.subprocess.run", return_value=_make_result()) as mock_run:
        wg_hub.add_peer("PUBKEY==", 5)
    cmd = mock_run.call_args[0][0]
    assert cmd == ["wg", "set", "wg0", "peer", "PUBKEY==",
                   "allowed-ips", "192.168.254.5/32",
                   "persistent-keepalive", "25"]


def test_remove_peer_runs_correct_command():
    with patch("app.wg_hub.subprocess.run", return_value=_make_result()) as mock_run:
        wg_hub.remove_peer("PUBKEY==")
    cmd = mock_run.call_args[0][0]
    assert cmd == ["wg", "set", "wg0", "peer", "PUBKEY==", "remove"]


def test_add_peer_raises_on_failure():
    with patch("app.wg_hub.subprocess.run", return_value=_make_result(returncode=1, stderr="Operation not permitted")):
        with pytest.raises(RuntimeError, match="Operation not permitted"):
            wg_hub.add_peer("PUBKEY==", 3)


def test_current_peers_returns_set():
    stdout = "KEY1==\nKEY2==\n"
    with patch("app.wg_hub.subprocess.run", return_value=_make_result(stdout=stdout)):
        peers = wg_hub.current_peers()
    assert peers == {"KEY1==", "KEY2=="}


def test_current_peers_returns_empty_on_failure():
    with patch("app.wg_hub.subprocess.run", return_value=_make_result(returncode=1)):
        peers = wg_hub.current_peers()
    assert peers == set()


def test_reconcile_adds_missing_peers():
    device = MagicMock()
    device.wg_public_key = "NEWKEY=="
    device.wg_peer_index = 4
    device.device_id = "router-01"

    with patch("app.wg_hub.current_peers", return_value=set()), \
         patch("app.wg_hub.add_peer") as mock_add:
        wg_hub.reconcile([device])

    mock_add.assert_called_once_with("NEWKEY==", 4)


def test_reconcile_skips_existing_peers():
    device = MagicMock()
    device.wg_public_key = "EXISTINGKEY=="
    device.wg_peer_index = 2

    with patch("app.wg_hub.current_peers", return_value={"EXISTINGKEY=="}), \
         patch("app.wg_hub.add_peer") as mock_add:
        wg_hub.reconcile([device])

    mock_add.assert_not_called()


def test_reconcile_skips_device_without_key():
    device = MagicMock()
    device.wg_public_key = None

    with patch("app.wg_hub.current_peers", return_value=set()), \
         patch("app.wg_hub.add_peer") as mock_add:
        wg_hub.reconcile([device])

    mock_add.assert_not_called()


def test_approve_calls_wg_add_peer(client):
    """Integration: approving a device triggers wg_hub.add_peer."""
    client.post("/devices/enroll", json={"device_id": "wg-test", "token": "tok"})
    with patch("app.wg_hub.add_peer") as mock_add:
        r = client.post("/admin/devices/wg-test/approve")
    assert r.status_code == 200
    assert mock_add.call_count == 1
    _, peer_index = mock_add.call_args[0]
    assert peer_index == 2


def test_revoke_calls_wg_remove_peer(client):
    """Integration: revoking a device triggers wg_hub.remove_peer."""
    client.post("/devices/enroll", json={"device_id": "wg-test", "token": "tok"})
    with patch("app.wg_hub.add_peer"):
        client.post("/admin/devices/wg-test/approve")

    with patch("app.wg_hub.remove_peer") as mock_remove:
        r = client.delete("/admin/devices/wg-test")
    assert r.status_code == 200
    assert mock_remove.call_count == 1
