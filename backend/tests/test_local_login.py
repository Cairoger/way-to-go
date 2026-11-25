import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import COOKIE, make_session, public_origin
from app.main import app
from app.models import AuthIdentity, User

PATH = "/api/v1/auth/local-test"
ORIGIN = "http://localhost:3000"


@pytest.fixture
def local_config(monkeypatch, database):
    username, password, salt = (
        secrets.token_hex(8),
        secrets.token_urlsafe(24),
        secrets.token_bytes(16),
    )
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
    monkeypatch.setenv("PUBLIC_ORIGIN", ORIGIN)
    monkeypatch.setenv("LOCAL_TEST_USERNAME", username)
    monkeypatch.setenv(
        "LOCAL_TEST_PASSWORD_HASH", f"pbkdf2_sha256$600000${salt.hex()}${hashed.hex()}"
    )
    public_origin.cache_clear()
    return {"username": username, "password": password}


def browser():
    return TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN})


def test_local_auth_is_private_stable_and_can_own_trips(local_config, monkeypatch):
    # A matching nickname on a Google user cannot be used to claim their account.
    with make_session() as db:
        other = User(account_type="google", nickname=local_config["username"])
        db.add(other)
        db.flush()
        db.add(
            AuthIdentity(
                user_id=other.id, provider="google", provider_subject=local_config["username"]
            )
        )
        db.commit()
    with browser() as client:
        assert client.get(PATH).json() == {"enabled": True}
        assert (
            client.post(PATH, json={**local_config, "password": secrets.token_hex()}).status_code
            == 401
        )
        assert client.post(PATH, json={**local_config, "username": "different"}).status_code == 401
        assert not client.cookies.get(COOKIE)
        response = client.post(PATH, json=local_config)
        assert response.status_code == 200, response.text
        user = response.json()
        assert user == {
            "id": user["id"],
            "nickname": local_config["username"],
            "version": 1,
            "account_type": "local_test",
            "email": None,
        }
        assert user["id"] != other.id
        assert "HttpOnly" in response.headers["set-cookie"]
        assert client.get("/api/v1/auth/me").json() == user
        raw = client.cookies.get(COOKIE)
        assert client.post(PATH, json=local_config).json() == user
        assert client.cookies.get(COOKIE) != raw
        with browser() as old:
            old.cookies.set(COOKIE, raw)
            assert old.get("/api/v1/auth/me").status_code == 401
        trip = client.post("/api/v1/trips", json={"title": "本機行程"})
        assert trip.status_code == 201, trip.text
        assert trip.json()["owner_id"] == user["id"]
        assert (
            client.patch(
                "/api/v1/trips/" + trip.json()["id"], json={"title": "更新", "version": 1}
            ).status_code
            == 200
        )
        monkeypatch.delenv("LOCAL_TEST_PASSWORD_HASH")
        assert client.get(PATH).json() == {"enabled": False}
        assert client.get("/api/v1/auth/me").status_code == 401
        assert client.post(PATH, json=local_config).status_code == 404


def test_simultaneous_first_signins_share_one_subject(local_config):
    def login(_):
        with browser() as client:
            response = client.post(PATH, json=local_config)
            assert response.status_code == 200, response.text
            return response.json()["id"]

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert len(set(pool.map(login, range(3)))) == 1
    with make_session() as db:
        assert db.scalar(select(func.count(User.id)).where(User.account_type == "local_test")) == 1


@pytest.mark.parametrize(
    "origin", ["https://localhost", "https://travel.example", "http://testserver"]
)
def test_local_login_disabled_outside_http_loopback(local_config, monkeypatch, origin):
    monkeypatch.setenv("PUBLIC_ORIGIN", origin)
    public_origin.cache_clear()
    with TestClient(app, base_url=origin, headers={"Origin": origin}) as client:
        assert client.get(PATH).json() == {"enabled": False}
        assert client.post(PATH, json=local_config).status_code == 404


def test_incomplete_local_configuration_fails_closed(local_config, monkeypatch):
    monkeypatch.setenv("LOCAL_TEST_PASSWORD_HASH", "invalid")
    with browser() as client:
        assert client.get(PATH).json() == {"enabled": False}
        assert client.post(PATH, json=local_config).status_code == 404
