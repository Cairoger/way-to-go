import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app import auth
from app.core import COOKIE, digest, make_session
from app.main import app
from app.models import Invitation, LoginSession, utcnow


def test_guest_invite_lifecycle(owner, guest, client, trip, invitation):
    members = f"/api/v1/trips/{trip['id']}/members"
    assert len(owner.get(members).json()) == 2
    assert guest.post("/api/v1/trips", json={"title": "新旅程"}).status_code == 403
    assert client.get(members).status_code == 401
    assert (
        guest.post("/api/v1/invitations/accept", json={"code": invitation["code"]}).status_code
        == 200
    )
    assert len(owner.get(members).json()) == 2
    invite_url = f"/api/v1/trips/{trip['id']}/invitations"
    assert owner.delete(invite_url + "/" + invitation["id"]).status_code == 204
    body = {"code": invitation["code"], "nickname": "晚到"}
    assert client.post("/api/v1/auth/guest", json=body).status_code == 403
    replacement = owner.post(invite_url, json={}).json()
    with make_session() as db:
        db.get(Invitation, replacement["id"]).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post("/api/v1/auth/guest", json=body | {"code": replacement["code"]}).status_code
        == 403
    )
    assert guest.get(members).status_code == 200


def test_trip_versions_archives_and_idempotency(owner, guest, trip):
    endpoint = "/api/v1/trips"
    body = {"title": "週末旅程"}
    key = {"Idempotency-Key": "create-once"}
    created = owner.post(endpoint, json=body, headers=key)
    assert owner.post(endpoint, json=body, headers=key).json()["id"] == created.json()["id"]
    assert owner.post(endpoint, json={"title": "不同旅程"}, headers=key).status_code == 409
    path = endpoint + "/" + trip["id"]
    version = trip["version"]
    assert guest.patch(path, json={"version": version, "title": "擅自更名"}).status_code == 403
    updated = owner.patch(path, json={"version": version, "status": "completed"}).json()
    assert owner.patch(path, json={"version": version, "title": "過期修改"}).status_code == 409
    archived = owner.post(path + "/archive", json={"version": updated["version"]}).json()
    assert archived["status"] == "completed" and archived["archived"]
    removed = owner.delete(path, params={"version": archived["version"]}).json()
    assert guest.get(path).status_code == 404
    assert owner.post(path + "/restore", json={"version": removed["version"]}).status_code == 200
    assert guest.get(path).json()["status"] == "completed"


def test_member_removal_transfers_poll_control_and_transfer_owner(owner, guest, trip):
    path = "/api/v1/trips/" + trip["id"]
    first_id = owner.get("/api/v1/auth/me").json()["id"]
    second_id = guest.get("/api/v1/auth/me").json()["id"]
    poll = owner.post(
        path + "/polls",
        json={
            "title": "哪一天出發",
            "kind": "date",
            "mode": "single",
            "options": [{"text": "2027-02-12"}, {"text": "2027-02-13"}],
        },
    ).json()
    assert owner.delete(path + "/members/" + first_id).status_code == 409
    assert (
        guest.post(path + "/transfer", json={"user_id": first_id, "version": 1}).status_code == 403
    )
    assert (
        owner.post(
            path + "/transfer", json={"user_id": second_id, "version": trip["version"]}
        ).status_code
        == 200
    )
    assert guest.delete(path + "/members/" + first_id).status_code == 204
    assert owner.get(path).status_code == 403
    assert owner.get(path + "/polls").status_code == 403
    inherited = guest.get(path + "/polls").json()[0]
    assert inherited["id"] == poll["id"]
    assert inherited["created_by"] == first_id and inherited["editable_by"] == second_id
    assert (
        guest.post(
            "/api/v1/polls/" + poll["id"] + "/close", json={"version": inherited["version"]}
        ).status_code
        == 200
    )


def test_server_session_revocation_and_expiry(owner, guest, client, trip):
    raw = guest.cookies.get(COOKIE)
    assert guest.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me", headers={"Cookie": COOKIE + "=" + raw}).status_code == 401
    with make_session() as db:
        login = db.scalar(
            select(LoginSession).where(LoginSession.token_hash == digest(owner.cookies.get(COOKIE)))
        )
        login.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert owner.get("/api/v1/trips/" + trip["id"]).status_code == 401


def test_google_oidc_cookie_rotation_and_state_binding(client, guest, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    previous = guest.cookies.get(COOKIE)
    guest_id = guest.get("/api/v1/auth/me").json()["id"]
    query = parse_qs(
        urlsplit(
            guest.post("/api/v1/auth/google", json={"return_to": "/?tab=trips"}).json()["url"]
        ).query
    )
    assert query["code_challenge_method"] == ["S256"]

    def fake_exchange(code, verifier, client_id, secret):
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert challenge == query["code_challenge"][0]
        assert (client_id, secret, code) == ("test-client", "test-secret", "mock-code")
        return {
            "sub": "mock-google-subject",
            "nonce": query["nonce"][0],
            "email_verified": True,
            "email": "traveler@example.test",
            "name": "Google 旅人",
        }

    monkeypatch.setattr(auth, "exchange_code", fake_exchange)
    args = {"state": query["state"][0], "code": "mock-code"}
    assert client.get(auth.OAUTH_PATH, params=args).status_code == 401
    success = guest.get(auth.OAUTH_PATH, params=args)
    assert (
        success.status_code == 303 and success.headers["location"] == "http://testserver/?tab=trips"
    )
    assert guest.cookies.get(COOKIE) != previous
    assert (
        client.get("/api/v1/auth/me", headers={"Cookie": COOKIE + "=" + previous}).status_code
        == 401
    )
    assert guest.get("/api/v1/auth/me").json()["id"] == guest_id
    assert guest.post("/api/v1/trips", json={"title": "升級後建立"}).status_code == 201
    assert guest.get(auth.OAUTH_PATH, params=args).status_code == 401
    query = parse_qs(urlsplit(client.post("/api/v1/auth/google", json={}).json()["url"]).query)
    monkeypatch.setattr(
        auth, "exchange_code", lambda *args: {"sub": "mock-google-subject", "nonce": "wrong"}
    )
    assert (
        client.get(
            auth.OAUTH_PATH, params={"code": "another-code", "state": query["state"][0]}
        ).status_code
        == 401
    )


def test_missing_oidc_settings_and_request_origin(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    response = client.post("/api/v1/auth/google")
    assert response.status_code == 503
    assert response.json()["code"] == "OIDC_NOT_CONFIGURED"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert (
        client.post("/api/v1/auth/logout", headers={"Origin": "https://other.example"}).status_code
        == 403
    )


def test_private_demo_membership_and_seeded_itinerary(client, owner):
    from seed_demo import seed_demo

    owner_id = owner.get("/api/v1/auth/me").json()["id"]
    seeded = seed_demo(owner_id, 2)
    code = parse_qs(urlsplit(seeded["url"]).query)["invite"][0]
    path = "/api/v1/trips/" + seeded["trip_id"]
    assert client.get(path).status_code == 401
    assert client.post("/api/v1/auth/guest", json={"code": code, "nickname": "看展旅伴"}).is_success
    assert [len(day["items"]) for day in client.get(path + "/days").json()] == [2, 2]
    assert len(client.get(path + "/places").json()) == 4
    assert client.get(path + "/polls").json()[0]["rounds"][0]["closed"] is False
    assert client.get(path + "/comments").json()[0]["content"]


def test_five_connected_clients_receive_committed_edits_and_revocation(
    owner, guest, trip, invitation
):
    path = "/api/v1/trips/" + trip["id"]
    ws = "/ws/trips/" + trip["id"]
    tokens = [owner.cookies.get(COOKIE), guest.cookies.get(COOKIE)]
    for i in range(3):
        with TestClient(app, headers={"Origin": "http://testserver"}) as browser:
            assert browser.post(
                "/api/v1/auth/guest", json={"code": invitation["code"], "nickname": f"旅伴 {i}"}
            ).is_success
            tokens.append(browser.cookies.get(COOKIE))
    headers = [{"cookie": COOKIE + "=" + raw, "origin": "http://testserver"} for raw in tokens]
    with ExitStack() as stack:
        sockets = [stack.enter_context(owner.websocket_connect(ws, headers=h)) for h in headers]
        for socket in sockets:
            presence = socket.receive_json()
            while presence["type"] == "presence" and len(presence["members"]) < 5:
                presence = socket.receive_json()
            assert presence["type"] == "presence" and len(presence["members"]) == 5
        with ThreadPoolExecutor(max_workers=5) as pool:
            submissions = list(
                pool.map(
                    lambda i: owner.post(
                        path + "/comments", headers=headers[i], json={"content": f"第 {i} 筆備忘"}
                    ),
                    range(5),
                )
            )
        assert all(r.status_code == 201 for r in submissions)
        committed = {r.json()["id"] for r in submissions}
        for socket in sockets:
            received = [socket.receive_json() for _ in range(5)]
            assert all(m["type"] == "comment.created" for m in received)
            assert {m["id"] for m in received} == committed
        assert {comment["id"] for comment in owner.get(path + "/comments").json()} == committed
        last_id = owner.get("/api/v1/auth/me", headers=headers[-1]).json()["id"]
        assert owner.delete(path + "/members/" + last_id).is_success
        with pytest.raises(WebSocketDisconnect) as disconnected:
            sockets[-1].receive_json()
        assert disconnected.value.code == 4403
        assert owner.get(path, headers=headers[-1]).status_code == 403
