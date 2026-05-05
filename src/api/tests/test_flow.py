"""End-to-end flow: enroll → approve → sync → config update → re-sync."""

DEVICE_ID = "router-test-01"
TOKEN = "secret-token-abc"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_enroll(client):
    r = client.post("/devices/enroll", json={"device_id": DEVICE_ID, "token": TOKEN})
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_status_before_approval(client):
    client.post("/devices/enroll", json={"device_id": DEVICE_ID, "token": TOKEN})
    r = client.get(f"/devices/{DEVICE_ID}/status", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["sync_status"] == "n/a"  # pending device has no sync state


def test_sync_rejected_before_approval(client):
    client.post("/devices/enroll", json={"device_id": DEVICE_ID, "token": TOKEN})
    r = client.post(f"/devices/{DEVICE_ID}/sync", json={"applied_version": 0}, headers=AUTH)
    assert r.status_code == 403


def test_wrong_token_rejected(client):
    client.post("/devices/enroll", json={"device_id": DEVICE_ID, "token": TOKEN})
    r = client.get(f"/devices/{DEVICE_ID}/status", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_approve_and_sync(client):
    client.post("/devices/enroll", json={"device_id": DEVICE_ID, "token": TOKEN})

    r = client.post(f"/admin/devices/{DEVICE_ID}/approve")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "approved"
    assert d["wg_peer_index"] == 2
    assert d["config_version"] == 1

    # First sync: applied_version=0, server has config_version=1 → returns config
    r = client.post(f"/devices/{DEVICE_ID}/sync", json={"applied_version": 0}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == 1
    assert body["config"] is not None  # TODO: will have real payload in step 3

    # Second sync: already up to date → no config returned
    r = client.post(f"/devices/{DEVICE_ID}/sync", json={"applied_version": 1}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["config"] is None


def test_local_config_bumps_version(client):
    client.post("/devices/enroll", json={"device_id": DEVICE_ID, "token": TOKEN})
    client.post(f"/admin/devices/{DEVICE_ID}/approve")

    r = client.put(
        f"/config/{DEVICE_ID}/local",
        json={"lan_network": "192.168.2.0/24", "lan_ip": "192.168.2.1"},
    )
    assert r.status_code == 200

    d = client.get(f"/admin/devices/{DEVICE_ID}").json()
    assert d["config_version"] == 2  # bumped from 1 to 2


def test_global_config_bumps_all_versions(client):
    # Two devices
    for i, dev in enumerate(["dev-a", "dev-b"]):
        client.post("/devices/enroll", json={"device_id": dev, "token": f"tok-{i}"})
        client.post(f"/admin/devices/{dev}/approve")

    client.put("/config/global", json={"pxe_tftp_server": "192.168.254.1"})

    for dev in ["dev-a", "dev-b"]:
        d = client.get(f"/admin/devices/{dev}").json()
        assert d["config_version"] == 2  # bumped from 1 to 2


def test_revoke(client):
    client.post("/devices/enroll", json={"device_id": DEVICE_ID, "token": TOKEN})
    client.post(f"/admin/devices/{DEVICE_ID}/approve")

    r = client.delete(f"/admin/devices/{DEVICE_ID}")
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"

    r = client.post(f"/devices/{DEVICE_ID}/sync", json={"applied_version": 1}, headers=AUTH)
    assert r.status_code == 403
