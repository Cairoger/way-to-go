import base64
import json
from time import time

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from app import notices


def test_push_device_cannot_reassign_another_active_account(owner, guest, monkeypatch):
    monkeypatch.setattr(notices, "vapid", lambda: (None, "public", "mailto:test@example.test"))
    url = "/api/v1/notifications/device"
    device = {"endpoint": "https://fcm.googleapis.com/fcm/send/unit-binding"}
    assert owner.put(url, json=device).status_code == 204
    assert guest.put(url, json=device).status_code == 409
    assert guest.delete(url).status_code == 204
    assert owner.get("/api/v1/notifications").json()["device_registered"]
    assert not guest.get("/api/v1/notifications").json()["device_registered"]
    assert owner.post("/api/v1/auth/logout").status_code == 204
    assert guest.put(url, json=device).status_code == 204


def test_preferences_read_and_membership(owner, guest, trip):
    base = "/api/v1/notifications"
    comments = f"/api/v1/trips/{trip['id']}/comments"
    recipient = guest.get("/api/v1/auth/me").json()
    first = owner.post(comments, json={"content": "@同行旅伴 討論集合時間"})
    assert first.is_success
    entry = guest.get(base).json()["items"][0]
    assert not entry["read"] and entry["trip_id"] == trip["id"]
    assert owner.post(base + "/" + entry["id"] + "/read").status_code == 404
    assert guest.post(base + "/" + entry["id"] + "/read").status_code == 204
    assert guest.get(base).json()["items"][0]["read"]
    pref = {"version": 0, "push": False, "mentions": False}
    assert guest.put(base + "/preferences", json=pref).json()["version"] == 1
    assert guest.put(base + "/preferences", json=pref).status_code == 409
    assert owner.post(comments, json={"content": "@同行旅伴 明天再討論"}).is_success
    assert len(guest.get(base).json()["items"]) == 1
    assert owner.delete(f"/api/v1/trips/{trip['id']}/members/{recipient['id']}").is_success
    assert guest.get(base).json()["items"] == []


def test_push_permission_delivery_and_gone(owner, guest, trip, monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setenv(
        "VAPID_PRIVATE_KEY", notices.b64(key.private_numbers().private_value.to_bytes(32, "big"))
    )
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:contact@example.org")
    device = "/api/v1/notifications/device"
    endpoint = "https://fcm.googleapis.com/fcm/send/test-token"
    assert guest.put(device, json={"endpoint": "http://localhost/other"}).status_code == 422
    assert guest.put(device, json={"endpoint": endpoint}).status_code == 204
    assert guest.put(
        "/api/v1/notifications/preferences", json={"version": 0, "push": True, "mentions": True}
    ).is_success
    requests = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, *, content, headers):
            requests.append((url, content, headers))
            return type("Response", (), {"status_code": 410})()

    monkeypatch.setattr(notices.httpx, "AsyncClient", Provider)
    for msg in ("第一天", "第二天"):
        assert owner.post(
            f"/api/v1/trips/{trip['id']}/comments", json={"content": "@同行旅伴 " + msg}
        ).is_success
    assert len(requests) == 1
    url, content, headers = requests[0]
    assert url == endpoint and content == b"" and headers["TTL"] == "300"
    token = headers["Authorization"].split("vapid t=")[1].split(", k=")[0]
    header, claims, sig = token.split(".")
    decoded = json.loads(base64.urlsafe_b64decode(claims + "==="))
    assert (
        decoded["aud"] == "https://fcm.googleapis.com" and time() < decoded["exp"] < time() + 86400
    )
    raw = base64.urlsafe_b64decode(sig + "===")
    signature = utils.encode_dss_signature(
        int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
    )
    key.public_key().verify(signature, (header + "." + claims).encode(), ec.ECDSA(hashes.SHA256()))
